"""The documents of the generic API: bodies in, the shapes, representations out (PD-14, PD-12).

A body is JSON, which the generated context turns into RDF, or JSON-LD, which is used as it comes.
Either way the router gets the triples of one node rooted at the IRI of the path, validated against
the generated shapes. No generated class is used here (D-2): the schema, the context, the frames and
the shapes, read from the folder the generator wrote them to, say everything.

A representation is built from the stored graph: JSON and JSON-LD by framing it with the type's
frame, Turtle by serialising it. The statements the session makes about a graph (its version and
tracking) are bookkeeping, not content, and are left out.
"""

import json
from collections.abc import Iterable, Iterator
from functools import cached_property
from pathlib import Path
from typing import Any, cast

import anyio.to_thread
from linkml_runtime.linkml_model.meta import ClassDefinition, SlotDefinition
from linkml_runtime.utils.formatutils import camelcase
from linkml_runtime.utils.schemaview import SchemaView
from pyld import jsonld
from pyshacl import validate
from rdflib import RDF, SH, XSD, BNode, Graph, Literal, URIRef
from rdflib.term import Node

from rdf_persistence.domain.exceptions import InvalidBody, PayloadTooLarge
from rdf_persistence.domain.generated.rp_core import RpAnnotation
from rdf_persistence.domain.iris import DEFAULT_IRIS, Iris, graph_iri
from rdf_persistence.domain.media import JSON, JSON_LD, TURTLE
from rdf_persistence.domain.sparql import FORBIDDEN_IRI_CHARS, Triple
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.artifacts import (
    CONTEXT_FILE,
    CONTEXT_KEY,
    FRAME_SUFFIX,
    ID_KEY,
    SHAPES_FILE,
    TYPE_KEY,
)
from rdf_persistence.services.schema_structure import (
    annotation_text,
    holds_owned_part,
    internal_predicates,
    iri_type_of,
    is_internal,
    json_name,
    refuse_internal,
    served_roots,
    tenant_root_class,
)

NQUADS = {"format": "application/n-quads"}
NATIVE = {"useNativeTypes": True}
NOT_INLINE = "a JSON-LD context must be inline: remote contexts are not followed"
MAX_MESSAGES = 5
# Objects in a body; with the byte bound, it keeps one request from costing a minute.
MAX_NODES = 10_000
TYPE_KEYS = ("type", TYPE_KEY)


def _refuse_remote(url: str, _options: Any) -> Any:
    raise InvalidBody(NOT_INLINE)


# pyld fetches nothing: every context it needs is in the document or the frame.
LOADER = {"documentLoader": _refuse_remote}


def dataset_of(graph: Graph) -> dict:
    """The triples of ``graph`` as the dataset ``jsonld.from_rdf`` takes.

    pyld 3.3.0 reads backslash sequences in N-Quads text wrongly (a literal of a backslash and `r`
    comes back as a backslash and a carriage return), so the text goes through rdflib instead.
    """

    def term(node: Node) -> dict:
        if isinstance(node, URIRef):
            return {"type": "IRI", "value": str(node)}
        if isinstance(node, BNode):
            return {"type": "blank node", "value": f"_:{node}"}
        assert isinstance(node, Literal)
        return {"type": "literal", "value": str(node), "datatype": str(node.datatype or XSD.string)}

    triples = [{"subject": term(s), "predicate": term(p), "object": term(o)} for s, p, o in graph]
    return {"@default": triples}


class Documents:
    """The schema's context, frames and shapes, and what turns a body into triples and triples into a body."""

    def __init__(self, view: SchemaView, folder: Path, iris: Iris = DEFAULT_IRIS) -> None:
        """Read the artefacts the generator wrote to ``folder`` for the schema ``view``; new parts get
        their IRIs from ``iris`` (default: the default policy)."""
        self._iris = iris
        self._view = view
        self._folder = folder
        self._frames: dict[str, dict] = {}
        self.context: dict = json.loads((folder / CONTEXT_FILE).read_text(encoding="utf-8"))[
            CONTEXT_KEY
        ]
        self.shapes = Graph().parse(folder / SHAPES_FILE)
        self._class_of = {self._iri_of(c): c for c in view.all_classes().values()}
        self._slots = {
            name: {json_name(slot): slot for slot in view.class_induced_slots(name)}
            for name in view.all_classes()
        }
        self._family = {
            name: {self._iri_of(view.get_class(c)) for c in view.class_descendants(name)}
            for name in view.all_classes()
        }
        self._internal = internal_predicates(view)
        self._parts = self._part_predicates()

    @cached_property
    def tenant_root(self) -> ClassDefinition:
        """The class of the tenant's root object.

        Raises:
            LookupError: The schema has none or several.
        """
        return tenant_root_class(self._view)

    def family(self, cls: ClassDefinition) -> set[URIRef]:
        """The IRIs of ``cls`` and of the classes derived from it."""
        return self._family[cls.name]

    @cached_property
    def aggregates(self) -> dict[str, ClassDefinition]:
        """The aggregate types the generic router serves, by the path they are served at."""
        return {
            str(annotation_text(cls, RpAnnotation.RP_PATH)): cls for cls in served_roots(self._view)
        }

    def _frame_of(self, class_name: str) -> dict:
        if class_name not in self._frames:
            text = (self._folder / f"{class_name}{FRAME_SUFFIX}").read_text(encoding="utf-8")
            self._frames[class_name] = json.loads(text)
        return self._frames[class_name]

    def require_frames(self) -> None:
        """Read the frame of every type the service serves, so a folder without one stops start-up.

        Raises:
            OSError: A frame is missing.
            LookupError: The schema has no tenant root class.
        """
        for cls in (*self.aggregates.values(), self.tenant_root):
            self._frame_of(cls.name)

    def _part_predicates(self) -> dict[Node, set[URIRef]]:
        """The predicates of the owned-part slots, by the classes they take."""
        parts: dict[
            Node, set[URIRef]
        ] = {}  # keyed by Node: rdflib types the predicates of a graph so
        for slots in self._slots.values():
            for slot in slots.values():
                if not is_internal(slot) and holds_owned_part(self._view, slot):
                    predicate = URIRef(self._view.get_uri(slot, expand=True))
                    parts.setdefault(predicate, set()).update(self._family[str(slot.range)])
        return parts

    def _iri_of(self, cls: ClassDefinition) -> URIRef:
        return URIRef(self._view.get_uri(cls, expand=True))

    # -- reading a body ------------------------------------------------------------------------

    async def parse(
        self,
        data: bytes,
        media_type: str,
        cls: ClassDefinition,
        iri: str,
        *,
        creating: bool,
        tenant: str,
    ) -> tuple[Graph, set[URIRef]]:
        """The triples of the body ``data`` and the subjects it names: one node of class ``cls`` rooted
        at ``iri``, with its parts.

        A JSON body is expanded with the generated context, its nodes typed by the schema; a JSON-LD
        body is used as it is. The root has the IRI of the path; on a create that IRI is minted, so a
        body naming one is refused, and on a replace a body naming another is refused. A part without
        an IRI gets one from the IRI policy, by its class (PD-7a); ``tenant`` is the tenant of ``iri``.

        Parts are nested under the root when the policy's part template says so, and a subject outside
        the root is refused. Otherwise (PD-7) only the root and the parts minted now are accepted
        here, and every other subject IRI of the body is returned as ``named``, for the caller to
        check against what the aggregate stores; ``named`` is empty for nested parts.

        Raises:
            InvalidBody: The body is not a JSON object, is not valid JSON-LD, uses a remote context, or
                describes anything but the one node and its parts; or a part needs a ``{type}`` in
                its IRI and has no ``rdf:type`` that is an owned class of the schema.
        """
        document = self._document(data, media_type, cls)
        graph = await anyio.to_thread.run_sync(self._triples, document)
        refuse_internal(graph, self._internal)
        return self._settled(graph, cls, URIRef(iri), creating, tenant)

    def _document(self, data: bytes, media_type: str, cls: ClassDefinition) -> dict:
        try:
            body = json.loads(data)
        except (ValueError, RecursionError) as error:  # the second: brackets nested past the parser
            raise InvalidBody(f"the body is not valid JSON: {str(error)[:200]}") from error
        if not isinstance(body, dict):
            raise InvalidBody("the body must be a JSON object")
        _bound(body)
        return body if media_type == JSON_LD else self._plain_document(body, cls)

    def _plain_document(self, body: dict, cls: ClassDefinition) -> dict:
        """A plain JSON ``body`` as a JSON-LD document: typed by the schema, read with the generated context."""
        body = {
            key: value for key, value in body.items() if key != CONTEXT_KEY
        }  # ours is the only one
        try:
            return {**self._typed(body, cls.name), CONTEXT_KEY: self.context}
        except RecursionError as error:
            raise InvalidBody("the body is nested too deeply") from error

    def expand(self, body: dict, cls: ClassDefinition) -> Graph:
        """The triples of a plain JSON ``body`` of class ``cls``, as the router reads a JSON request.

        The keys are the JSON names of the class's slots; the types of the body and its owned parts
        come from the schema, and the generated context alone decides how the values read.

        Raises:
            InvalidBody: A key is no slot of the class, or names an ``internal`` one, or the body is
                not valid JSON-LD once typed.
        """
        return self._triples(self._plain_document(body, cls))

    def _typed(self, node: dict, class_name: str) -> dict:
        """``node`` with an ``@type`` on it and on every owned part below, as the schema says.

        A key is a slot of the class (by its JSON name), ``@id`` or the type; anything else, a compact
        or full IRI included, is refused.
        """
        slots = self._slots[class_name]
        typed: dict = {TYPE_KEY: str(self._iri_of(self._view.get_class(class_name)))}
        for key, value in node.items():
            if key in TYPE_KEYS:
                typed[TYPE_KEY] = self._type_of(value, class_name)
            elif key == ID_KEY:
                typed[key] = value
            elif key in slots and is_internal(slots[key]):
                raise InvalidBody(f"{key} is set by the service")
            elif key in slots:
                typed[key] = self._valued(slots[key], value)
            else:
                raise self._unknown(key, class_name)
        return typed

    def _type_of(self, value: Any, class_name: str) -> str:
        """The IRI of the class a body names for a node: the class itself or one of its subclasses."""
        family = {
            camelcase(c): str(self._iri_of(self._view.get_class(c)))
            for c in self._view.class_descendants(class_name)
        }
        named = family.get(value) if isinstance(value, str) else None
        if named is None and value in family.values():
            named = value
        if named is None:
            raise InvalidBody(f"a {class_name} cannot be typed {value!r}")
        return named

    def _valued(self, slot: SlotDefinition, value: Any) -> Any:
        if holds_owned_part(self._view, slot):
            return self._typed_parts(value, str(slot.range))
        return self._plain(value)

    def _typed_parts(self, value: Any, class_name: str) -> Any:
        if isinstance(value, list):
            return [self._typed_parts(item, class_name) for item in value]
        return self._typed(value, class_name) if isinstance(value, dict) else value

    def _plain(self, value: Any) -> Any:
        """A value that is no part: a literal, or a reference, an IRI string or an object holding only its ``@id``."""
        if isinstance(value, list):
            return [self._plain(item) for item in value]
        if isinstance(value, dict) and set(value) != {ID_KEY}:
            raise InvalidBody("a reference is an IRI, or an object with only an @id")
        return value

    def _unknown(self, key: str, class_name: str) -> InvalidBody:
        """The refusal of a key the class has no slot for; it names the internal slot the key stands for."""
        try:
            expanded = jsonld.expand({CONTEXT_KEY: self.context, key: 0}, LOADER)
            predicates = {URIRef(p) for node in expanded for p in node}
        except Exception:
            predicates = set()
        for predicate in predicates:
            if predicate in self._internal:
                return InvalidBody(f"{self._internal[predicate]} is set by the service")
        return InvalidBody(f"a {class_name} has no field {key!r}")

    @staticmethod
    def _triples(document: dict) -> Graph:
        try:
            nquads = jsonld.to_rdf(document, {**NQUADS, **LOADER})
            return Graph().parse(data=nquads, format="nt")
        except Exception as error:  # pyld and the N-Quads parser raise their own types
            refusal = _refusal_in(error)  # pyld wraps what the loader raised
            if refusal is not None:
                raise refusal from error
            raise InvalidBody(f"the body is not valid JSON-LD: {str(error)[:200]}") from error

    def _part_iri(self, graph: Graph, node: Node, root: URIRef, tenant: str) -> URIRef:
        """A fresh IRI for the part ``node`` of ``root``, by the class its ``rdf:type`` names (PD-7a)."""
        types = list(graph.objects(node, RDF.type))
        owned = self._class_of.get(types[0]) if len(types) == 1 else None  # type: ignore[call-overload]
        cls_type = iri_type_of(owned) if owned is not None else ""
        if self._iris.part_needs_type() and cls_type not in self._iris.owned_types:
            raise InvalidBody(
                f"a part of {root} needs a type that is an owned class: {types or 'none given'}"
            )
        return self._iris.mint_part(tenant, str(root), cls_type)

    def _settled(
        self, graph: Graph, cls: ClassDefinition, iri: URIRef, creating: bool, tenant: str
    ) -> tuple[Graph, set[URIRef]]:
        """``graph`` rooted at ``iri``, its parts named, without the bookkeeping, and the subjects the
        body named itself (flat parts only), or the refusal."""
        root = self._root(graph, iri, creating)
        if (root, RDF.type, self._iri_of(cls)) not in graph:
            raise InvalidBody(f"the body must be a {cls.name}")
        names: dict[Node, URIRef] = {}

        def named(node: Node) -> Node:
            if node == root:
                return iri
            if isinstance(node, BNode) and self._has_identifier(graph, node):
                if node not in names:
                    names[node] = self._part_iri(graph, node, iri, tenant)
                return names[node]
            return node

        settled = Graph()
        for s, p, o in graph:
            if p in v.BOOKKEEPING_PREDICATES:
                continue
            settled.add((named(s), p, named(o)))
        _refuse_bad_iris(settled)
        claimed = self._named_subjects(settled, iri, set(names.values()))
        self._refuse_strays(settled, iri, cls)
        return settled, claimed

    def _named_subjects(self, graph: Graph, iri: URIRef, minted: set[URIRef]) -> set[URIRef]:
        """The subjects the body named itself when parts sit beside their root (none when nested); the
        root's graph IRI is never a part, and a nested part must be inside the root (PD-7, PD-12d)."""
        subjects = {s for s in graph.subjects() if isinstance(s, URIRef)}
        if graph_iri(iri) in subjects:
            raise InvalidBody(f"{graph_iri(iri)} is the aggregate's graph and cannot be a part")
        if not self._iris.nested_parts:
            return subjects - {iri, *minted}
        outside = [s for s in subjects if not _inside(iri, s)]
        if outside:
            raise InvalidBody(f"{outside[0]} is not inside the aggregate {iri}")
        return set()

    def _refuse_strays(self, graph: Graph, root: URIRef, cls: ClassDefinition) -> None:
        """Only the root and the parts reached from it through owned-part slots, each of the slot's class, may be described."""
        reached = self._reached(graph, root, cls)
        stray = next((s for s in graph.subjects() if s not in reached), None)
        if stray is not None:
            raise InvalidBody(f"{stray} is not part of the aggregate {root}")

    def _reached(self, graph: Graph, root: URIRef, cls: ClassDefinition) -> set[Node]:
        reached: set[Node] = {root}
        pending: list[tuple[Node, set[URIRef]]] = [(root, self._family[cls.name])]
        while pending:
            node, classes = pending.pop()
            types = set(graph.objects(node, RDF.type))
            if not types or not types <= classes:
                raise InvalidBody(
                    f"{node} is not part of the aggregate {root}: it has the wrong type"
                )
            for part, part_classes in self._owned_parts(graph, node):
                if part not in reached:
                    reached.add(part)
                    pending.append((part, part_classes))
        return reached

    def _owned_parts(self, graph: Graph, node: Node) -> Iterator[tuple[Node, set[URIRef]]]:
        """The nodes ``node`` holds through owned-part slots, with the classes each slot takes."""
        for predicate, part in graph.predicate_objects(node):
            if predicate in self._parts and not isinstance(part, Literal):
                yield part, self._parts[predicate]

    def internal_values(self, stored: Graph, replacement: Iterable[Triple]) -> list[Triple]:
        """The statements of ``stored`` that give an ``internal`` slot a value, of the nodes ``replacement`` still describes.

        No body can set an internal slot, so a replacement is made without them; adding these keeps
        what the service stored for the root and the parts that persist, which a replace must not erase.
        """
        nodes = {subject for subject, _, _ in replacement}
        kept = [(s, p, o) for s, p, o in stored if p in self._internal and s in nodes]
        # a stored graph holds only URIs, literals and blank nodes; rdflib types its terms as Node
        return cast(list[Triple], kept)

    @staticmethod
    def _root(graph: Graph, iri: URIRef, creating: bool) -> Node:
        contained = set(graph.objects())
        roots = [s for s in set(graph.subjects()) if s not in contained]
        if len(roots) != 1:
            raise InvalidBody(
                f"the body must describe one node that holds the others, found {len(roots)}"
            )
        root = roots[0]
        if isinstance(root, BNode):
            return root
        if creating:
            raise InvalidBody(f"the service assigns the IRI of a new object; the body names {root}")
        if root != iri:
            raise InvalidBody(f"the id {root} differs from the path {iri}")
        return root

    def _has_identifier(self, graph: Graph, node: Node) -> bool:
        """True when a typed blank node is an instance of a class with an identifier slot."""
        return any(
            (cls := self._class_of.get(t)) is not None
            and self._view.get_identifier_slot(cls.name) is not None
            for t in graph.objects(node, RDF.type)
            if isinstance(t, URIRef)
        )

    # -- the shapes ----------------------------------------------------------------------------

    async def validate(self, graph: Graph) -> None:
        """Check ``graph`` against the generated shapes.

        Raises:
            InvalidBody: A shape is violated; the message names the slots.
        """
        conforms, report, _ = await anyio.to_thread.run_sync(self._check, graph)
        if not conforms:
            raise InvalidBody(_messages(report))

    def _check(self, graph: Graph) -> tuple[bool, Graph, str]:
        shapes = Graph()
        shapes += self.shapes  # pyshacl adds to the graph it is given, and requests share this one
        conforms, report, text = validate(graph, shacl_graph=shapes, inference="none")
        assert isinstance(report, Graph)
        return bool(conforms), report, str(text)

    # -- the representations -------------------------------------------------------------------

    async def render(
        self, stored: Graph, graph_iri: URIRef, cls: ClassDefinition, media_type: str
    ) -> str:
        """``stored``, the graph read for an aggregate of class ``cls``, as ``media_type`` text.

        ``graph_iri`` is the graph the session read it from: the statements about it are left out, and
        so are the values of the ``internal`` slots, which no representation shows.
        """
        shown = Graph()
        for s, p, o in stored:
            if s != graph_iri and p not in self._internal:
                shown.add((s, p, o))
        if media_type == TURTLE:
            return str(shown.serialize(format="turtle"))
        framed = await anyio.to_thread.run_sync(self.frame, shown, cls)
        if media_type == JSON:
            framed.pop(CONTEXT_KEY, None)
        return json.dumps(framed, ensure_ascii=False)

    def frame(self, graph: Graph, cls: ClassDefinition) -> dict:
        """The aggregate of class ``cls`` in ``graph``, framed with the generated frame and compacted with the generated context."""
        frame = {**self._frame_of(cls.name), CONTEXT_KEY: self.context}
        expanded = jsonld.from_rdf(dataset_of(graph), NATIVE)
        framed: dict = jsonld.frame(expanded, frame, LOADER)
        return framed


def _bound(body: dict) -> None:
    """Raise unless the body holds at most ``MAX_NODES`` objects and list values; counted without recursion."""
    pending: list[Any] = [body]
    count = 0
    while pending:
        value = pending.pop()
        if isinstance(value, dict):
            count += 1
            if count > MAX_NODES:
                raise PayloadTooLarge(f"a body holds at most {MAX_NODES} objects")
            pending.extend(value.values())
        elif isinstance(value, list):
            count += sum(
                not isinstance(item, dict | list) for item in value
            )  # a list of strings costs as much as one of objects
            if count > MAX_NODES:
                raise PayloadTooLarge(
                    f"a body holds at most {MAX_NODES} objects and values in lists"
                )
            pending.extend(value)


def _refuse_bad_iris(graph: Graph) -> None:
    """Raise unless every IRI of ``graph`` is one SPARQL can carry: the store would refuse it later."""
    for term in {t for triple in graph for t in triple if isinstance(t, URIRef)}:
        if FORBIDDEN_IRI_CHARS.search(term):
            raise InvalidBody(f"{str(term)[:100]!r} is not a valid IRI")


def _refusal_in(error: BaseException) -> InvalidBody | None:
    """The ``InvalidBody`` somewhere in the chain of causes of ``error``, if one is."""
    seen: set[int] = set()
    link: BaseException | None = error
    while link is not None and id(link) not in seen:
        if isinstance(link, InvalidBody):
            return link
        seen.add(id(link))
        link = link.__cause__ or link.__context__
    return None


def _inside(root: URIRef, iri: URIRef) -> bool:
    return iri == root or str(iri).startswith(f"{root}/")


def _local(name: Node | None) -> str:
    return str(name).rsplit("#", 1)[-1].rsplit("/", 1)[-1] if name is not None else "the body"


def _messages(report: Graph) -> str:
    """The distinct ``slot: message`` lines of a validation report, the first few."""
    lines = dict.fromkeys(
        f"{_local(report.value(r, SH.resultPath))}: {report.value(r, SH.resultMessage)}"
        for r in report.subjects(SH.resultMessage, None)
    )
    return "; ".join(list(lines)[:MAX_MESSAGES])
