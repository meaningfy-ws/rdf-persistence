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
import re
from collections.abc import Iterable, Iterator
from functools import cached_property
from pathlib import Path
from typing import Any, cast

import anyio.to_thread
from linkml_runtime.linkml_model.meta import ClassDefinition, SlotDefinition
from linkml_runtime.utils.formatutils import camelcase
from linkml_runtime.utils.schemaview import SchemaView
from pyld import jsonld
from rdflib import RDF, SH, XSD, BNode, Dataset, Graph, Literal, URIRef
from rdflib.term import Node

from rdf_persistence.api.services.shacl import load_warm_shapes, validate_warm
from rdf_persistence.core.domain.exceptions import InvalidBody, NotAcceptable, PayloadTooLarge
from rdf_persistence.core.domain.generated.rp_core import RpAnnotation
from rdf_persistence.core.domain.media import (
    DATASET_REPRESENTATIONS,
    JSON,
    JSON_LD,
    RDF_XML,
)
from rdf_persistence.core.domain.sparql import FORBIDDEN_IRI_CHARS, Triple
from rdf_persistence.core.services.artifacts import (
    CONTEXT_FILE,
    CONTEXT_KEY,
    FRAME_SUFFIX,
    ID_KEY,
    SHAPES_FILE,
    TYPE_KEY,
)
from rdf_persistence.iris.domain.layout import graph_iri
from rdf_persistence.iris.services.iris import DEFAULT_IRIS, Iris
from rdf_persistence.persistence.services.generated.settings.rp_persistence_settings import (
    LimitSettings,
)
from rdf_persistence.persistence.services.jsonld import (
    ABSOLUTE_IRIS,
    INVALID_IRI,
    LOADER,
    OBJECT_OR_ARRAY,
    InvalidIriRefused,
    NamedGraphRefused,
    NotADocumentRefused,
    RelativeIriRefused,
    RemoteContextRefused,
    dataset_of,
    triples_of,
)
from rdf_persistence.schema.services import vocabulary as v
from rdf_persistence.schema.services.schema_structure import (
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

NATIVE = {"useNativeTypes": True}
NOT_INLINE = "a JSON-LD context must be inline: remote contexts are not followed"
ONE_GRAPH = "a body describes one graph"
MAX_MESSAGES = 5
TYPE_KEYS = ("type", TYPE_KEY)
VALUE_KEY = "@value"
GRAPH_KEY = "@graph"
LANGUAGE_KEY = "@language"
# What XML 1.0 forbids in text: rdflib's RDF/XML writer passes it through, and no XML parser reads it.
XML_FORBIDDEN = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f]")


class Documents:
    """The schema's context, frames and shapes, and what turns a body into triples and triples into a body."""

    def __init__(
        self,
        view: SchemaView,
        folder: Path,
        iris: Iris = DEFAULT_IRIS,
        *,
        limits: LimitSettings | None = None,
    ) -> None:
        """Read the artefacts the generator wrote to ``folder`` for the schema ``view``; new parts get
        their IRIs from ``iris`` (default: the default policy). A body holds at most
        ``limits.max_document_nodes`` objects and list values (a fresh ``LimitSettings`` unless
        given); with the byte bound, that keeps one request from costing a minute."""
        self._iris = iris
        self._max_nodes = (limits or LimitSettings()).max_document_nodes
        self._view = view
        self._folder = folder
        self._frames: dict[str, dict] = {}
        self.context: dict = json.loads((folder / CONTEXT_FILE).read_text(encoding="utf-8"))[
            CONTEXT_KEY
        ]
        # warmed, so that validation in worker threads needs no parser lock
        self.shapes = load_warm_shapes(folder / SHAPES_FILE)
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
        _bound(body, self._max_nodes)
        if media_type == JSON_LD:
            return dict(self._double_values(body, cls.name))
        return self._plain_document(body, cls)

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
        if self._is_double(slot):
            return _typed_doubles(self._plain(value), json_name(slot))
        return self._plain(value)

    def _is_double(self, slot: SlotDefinition) -> bool:
        """Whether ``slot`` takes ``xsd:double``: the context leaves it untagged, so a write is typed here (PD-9).

        The range is a type whose nearest URI, up its ancestors, is ``xsd:double``: a type derived
        from double is one too.
        """
        range_name = str(slot.range) if slot.range else None
        if range_name is None or range_name not in self._view.all_types():
            return False
        for ancestor in self._view.type_ancestors(range_name):
            curie = self._view.get_type(ancestor).uri
            if curie:
                return URIRef(self._view.expand_curie(str(curie))) == XSD.double
        return False

    def _double_values(self, node: Any, class_name: str) -> Any:
        """``node``, a JSON-LD body of class ``class_name``, with the values of its double slots typed (PD-9).

        Per class, as a plain JSON body is: a key is looked up in the slots of the node's class, and an
        owned part is walked as its own class. ``@context`` and any key that is no slot stay as written.
        """
        if isinstance(node, list):
            return [self._double_values(item, class_name) for item in node]
        if not isinstance(node, dict):
            return node
        class_name = self._named_class(node, class_name)
        slots = self._slots[class_name]
        return {
            key: self._double_value(slots.get(key), key, value, class_name)
            for key, value in node.items()
        }

    def _double_value(
        self, slot: SlotDefinition | None, key: str, value: Any, class_name: str
    ) -> Any:
        """One entry of a JSON-LD node: typed if ``slot`` is a double, walked if it holds a part or is ``@graph``."""
        if key == GRAPH_KEY and isinstance(value, list):  # each node of the graph is its own class
            return [
                self._double_values(item, self._named_class(item, class_name, everywhere=True))
                if isinstance(item, dict)
                else item
                for item in value
            ]
        if slot is None:
            return value
        if holds_owned_part(self._view, slot):
            return self._double_values(value, str(slot.range))
        return _typed_doubles(value, key) if self._is_double(slot) else value

    def _named_class(self, node: dict, class_name: str, everywhere: bool = False) -> str:
        """The class a node says it is, when it names ``class_name`` or a subclass of it (any class, if ``everywhere``); else ``class_name``."""
        named = next((node[key] for key in TYPE_KEYS if key in node), None)
        if isinstance(named, str):
            candidates = (
                self._view.all_classes() if everywhere else self._view.class_descendants(class_name)
            )
            for name in candidates:
                if named in (camelcase(name), str(self._iri_of(self._view.get_class(name)))):
                    return str(name)
        return class_name

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
        except Exception:  # noqa: BLE001 -- the key is already refused: any expansion failure only loses the hint
            predicates = set()
        for predicate in predicates:
            if predicate in self._internal:
                return InvalidBody(f"{self._internal[predicate]} is set by the service")
        return InvalidBody(f"a {class_name} has no field {key!r}")

    @staticmethod
    def _triples(document: dict) -> Graph:
        try:
            return triples_of(document)
        except RemoteContextRefused as error:
            raise InvalidBody(NOT_INLINE) from error
        except NamedGraphRefused as error:
            raise InvalidBody(ONE_GRAPH) from error
        except RelativeIriRefused as error:
            raise InvalidBody(ABSOLUTE_IRIS) from error
        except InvalidIriRefused as error:
            raise InvalidBody(INVALID_IRI) from error
        except NotADocumentRefused as error:
            raise InvalidBody(OBJECT_OR_ARRAY) from error
        except Exception as error:  # pyld and the N-Quads parser raise their own types
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
        return validate_warm(graph, shapes)  # the shapes were warmed up when this was built

    # -- the representations -------------------------------------------------------------------

    async def render(
        self, stored: Graph, graph_iri: URIRef, cls: ClassDefinition, media_type: str
    ) -> str:
        """``stored``, the graph read for an aggregate of class ``cls``, as ``media_type`` text.

        ``graph_iri`` is the graph the session read it from: the statements about it are left out, and
        so are the values of the ``internal`` slots, which no representation shows. JSON and JSON-LD
        come from framing; JSON loses the language tag of a value (it keeps the published ``string``
        schema), JSON-LD and the RDF serialisations keep it. N-Quads and TriG hold the aggregate in the
        graph ``graph_iri``; the other RDF serialisations hold its triples.

        Raises:
            NotAcceptable: The aggregate has no form in ``media_type``; RDF/XML cannot write a
                predicate that ends where no XML name can start.
        """
        whole = Dataset() if media_type in DATASET_REPRESENTATIONS else Graph()
        shown = whole.graph(graph_iri) if isinstance(whole, Dataset) else whole
        for s, p, o in stored:
            if s != graph_iri and p not in self._internal:
                shown.add((s, p, o))
        if media_type not in (JSON, JSON_LD):
            return await anyio.to_thread.run_sync(_serialised, whole, media_type)
        framed = await anyio.to_thread.run_sync(self.frame, shown, cls)
        if media_type == JSON:
            framed.pop(CONTEXT_KEY, None)
            return json.dumps(_without_languages(framed), ensure_ascii=False)
        return json.dumps(framed, ensure_ascii=False)

    @staticmethod
    def require_form(triples: Iterable[Triple], media_type: str) -> None:
        """Raise unless the aggregate ``triples`` can be served as ``media_type``; a write calls it before it stores.

        Only RDF/XML can fail (see ``render``): the others write any graph, so the check costs a
        serialisation for RDF/XML alone.

        Raises:
            NotAcceptable: ``triples`` have no form in ``media_type``.
        """
        if media_type == RDF_XML:
            graph = Graph()
            for triple in triples:
                graph.add(triple)
            _serialised(graph, media_type)

    def frame(self, graph: Graph, cls: ClassDefinition) -> dict:
        """The aggregate of class ``cls`` in ``graph``, framed with the generated frame and compacted with the generated context."""
        frame = {**self._frame_of(cls.name), CONTEXT_KEY: self.context}
        expanded = jsonld.from_rdf(dataset_of(graph), NATIVE)
        framed: dict = jsonld.frame(expanded, frame, LOADER)
        return framed


def _serialised(rdf: Graph, media_type: str) -> str:
    """``rdf`` as the RDF serialisation ``media_type``; a dataset type takes a ``Dataset`` holding the named graph."""
    if media_type != RDF_XML:
        return str(rdf.serialize(format=media_type))
    if any(isinstance(o, Literal) and XML_FORBIDDEN.search(str(o)) for o in rdf.objects()):
        raise NotAcceptable(f"this aggregate has no {media_type} form: a value XML cannot hold")
    try:
        return str(rdf.serialize(format=media_type))
    except ValueError as refusal:  # rdflib's RDF/XML writer: "Can't split <predicate>"
        raise NotAcceptable(f"this aggregate has no {media_type} form") from refusal


def _typed_doubles(value: Any, term: str) -> Any:
    """What a body wrote on the double term ``term``, as typed value objects (PD-9).

    The context leaves a double untagged, so JSON-LD would read ``3`` as an integer and ``"3"`` as a
    string. A number or a string becomes ``{"@value": v, "@type": xsd:double}``; a list is typed item
    by item; anything else (a value object, say) is left to JSON-LD.

    Raises:
        InvalidBody: A boolean, which JSON-LD would read as ``xsd:boolean``.
    """
    if isinstance(value, list):
        return [_typed_doubles(item, term) for item in value]
    if isinstance(value, bool):
        raise InvalidBody(f"{term} must be a number, not a boolean")
    if isinstance(value, int | float | str):
        return {VALUE_KEY: value, TYPE_KEY: str(XSD.double)}
    return value


def _without_languages(value: Any) -> Any:
    """``value`` with each value object ``{"@value": v, "@language": l}`` replaced by ``v``, at any depth."""
    if isinstance(value, list):
        return [_without_languages(item) for item in value]
    if isinstance(value, dict):
        if value.keys() == {VALUE_KEY, LANGUAGE_KEY}:
            return value[VALUE_KEY]
        return {key: _without_languages(item) for key, item in value.items()}
    return value


def _bound(body: dict, limit: int) -> None:
    """Raise unless the body holds at most ``limit`` objects and list values; counted without recursion."""
    pending: list[Any] = [body]
    count = 0
    while pending:
        value = pending.pop()
        if isinstance(value, dict):
            count += 1
            if count > limit:
                raise PayloadTooLarge(f"a body holds at most {limit} objects")
            pending.extend(value.values())
        elif isinstance(value, list):
            count += sum(
                not isinstance(item, dict | list) for item in value
            )  # a list of strings costs as much as one of objects
            if count > limit:
                raise PayloadTooLarge(f"a body holds at most {limit} objects and values in lists")
            pending.extend(value)


def _refuse_bad_iris(graph: Graph) -> None:
    """Raise unless every IRI of ``graph`` is one SPARQL can carry: the store would refuse it later."""
    for term in {t for triple in graph for t in triple if isinstance(t, URIRef)}:
        if FORBIDDEN_IRI_CHARS.search(term):
            raise InvalidBody(f"{str(term)[:100]!r} is not a valid IRI")


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
