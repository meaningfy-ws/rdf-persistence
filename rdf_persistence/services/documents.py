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
from pathlib import Path
from typing import Any

import anyio.to_thread
from linkml_runtime.linkml_model.meta import ClassDefinition
from linkml_runtime.utils.formatutils import underscore
from linkml_runtime.utils.schemaview import SchemaView
from pyld import jsonld
from pyshacl import validate
from rdflib import RDF, SH, XSD, BNode, Graph, Literal, URIRef
from rdflib.term import Node

from rdf_persistence.domain.exceptions import InvalidBody
from rdf_persistence.domain.generated.rp_core import RpAnnotation
from rdf_persistence.domain.iris import mint_part_iri
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.artifacts import CONTEXT_FILE, FRAME_SUFFIX, SHAPES_FILE
from rdf_persistence.services.schema_structure import (
    annotation_text,
    holds_owned_part,
    served_roots,
    tenant_root_class,
)

JSON = "application/json"
JSON_LD = "application/ld+json"
TURTLE = "text/turtle"
REPRESENTATIONS = (JSON, JSON_LD, TURTLE)
NQUADS = {"format": "application/n-quads"}
NATIVE = {"useNativeTypes": True}
NOT_INLINE = "a JSON-LD context must be inline: remote contexts are not followed"
MAX_MESSAGES = 5


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

    def __init__(self, view: SchemaView, folder: Path) -> None:
        """Read the artefacts the generator wrote to ``folder`` for the schema ``view``."""
        self._view = view
        self.context: dict = json.loads((folder / CONTEXT_FILE).read_text(encoding="utf-8"))[
            "@context"
        ]
        self.shapes = Graph().parse(folder / SHAPES_FILE)
        self.tenant_root = tenant_root_class(view)
        self.aggregates = {
            str(annotation_text(cls, RpAnnotation.RP_PATH)): cls for cls in served_roots(view)
        }
        types = [*self.aggregates.values(), self.tenant_root]
        self._frames = {
            cls.name: json.loads((folder / f"{cls.name}{FRAME_SUFFIX}").read_text(encoding="utf-8"))
            for cls in types
        }
        self._class_of = {self._iri_of(c): c for c in view.all_classes().values()}

    def _iri_of(self, cls: ClassDefinition) -> URIRef:
        return URIRef(self._view.get_uri(cls, expand=True))

    # -- reading a body ------------------------------------------------------------------------

    async def parse(
        self, data: bytes, media_type: str, cls: ClassDefinition, iri: str, *, creating: bool
    ) -> Graph:
        """The triples of the body ``data``: one node of class ``cls`` rooted at ``iri``, with its parts.

        A JSON body is expanded with the generated context, its nodes typed by the schema; a JSON-LD
        body is used as it is. The root has the IRI of the path; on a create that IRI is minted, so a
        body naming one is refused, and on a replace a body naming another is refused. A part without
        an IRI gets one under the root.

        Raises:
            InvalidBody: The body is not a JSON object, is not valid JSON-LD, uses a remote context, or
                describes anything but the one node and its parts.
        """
        document = self._document(data, media_type, cls)
        graph = await anyio.to_thread.run_sync(self._triples, document)
        return self._settled(graph, cls, URIRef(iri), creating)

    def _document(self, data: bytes, media_type: str, cls: ClassDefinition) -> dict:
        try:
            body = json.loads(data)
        except ValueError as error:
            raise InvalidBody(f"the body is not valid JSON: {error}") from error
        if not isinstance(body, dict):
            raise InvalidBody("the body must be a JSON object")
        if media_type == JSON_LD:
            return body
        return {**self._typed(body, cls.name), "@context": self.context}

    def _typed(self, node: dict, class_name: str) -> dict:
        """``node`` with an ``@type`` on it and on every owned part below, as the schema says."""
        slots = {underscore(s.name): s for s in self._view.class_induced_slots(class_name)}
        typed = {"@type": str(self._iri_of(self._view.get_class(class_name)))}
        for key, value in node.items():
            slot = slots.get(key)
            if slot is not None and holds_owned_part(self._view, slot):
                typed[key] = self._typed_parts(value, str(slot.range))
            elif key != "@context":
                typed[key] = value
        return typed

    def _typed_parts(self, value: Any, class_name: str) -> Any:
        if isinstance(value, list):
            return [self._typed_parts(item, class_name) for item in value]
        return self._typed(value, class_name) if isinstance(value, dict) else value

    @staticmethod
    def _triples(document: dict) -> Graph:
        try:
            nquads = jsonld.to_rdf(document, {**NQUADS, **LOADER})
            return Graph().parse(data=nquads, format="nt")
        except InvalidBody:
            raise
        except Exception as error:  # pyld and the N-Quads parser raise their own types
            raise InvalidBody(f"the body is not valid JSON-LD: {str(error)[:200]}") from error

    def _settled(self, graph: Graph, cls: ClassDefinition, iri: URIRef, creating: bool) -> Graph:
        """``graph`` rooted at ``iri``, its parts named, without the bookkeeping, or the refusal."""
        root = self._root(graph, iri, creating)
        if (root, RDF.type, self._iri_of(cls)) not in graph:
            raise InvalidBody(f"the body must be a {cls.name}")
        names: dict[Node, URIRef] = {}

        def named(node: Node) -> Node:
            if node == root:
                return iri
            if isinstance(node, BNode) and self._has_identifier(graph, node):
                names.setdefault(node, mint_part_iri(str(iri)))
                return names[node]
            return node

        settled = Graph()
        for s, p, o in graph:
            if p in v.BOOKKEEPING_PREDICATES:
                continue
            settled.add((named(s), p, named(o)))
        outside = [s for s in settled.subjects() if isinstance(s, URIRef) and not _inside(iri, s)]
        if outside:
            raise InvalidBody(f"{outside[0]} is not inside the aggregate {iri}")
        return settled

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

        ``graph_iri`` is the graph the session read it from: the statements about it are left out.
        """
        shown = Graph()
        for s, p, o in stored:
            if s != graph_iri:
                shown.add((s, p, o))
        if media_type == TURTLE:
            return str(shown.serialize(format="turtle"))
        framed = await anyio.to_thread.run_sync(self._frame, shown, cls.name)
        if media_type == JSON:
            framed.pop("@context", None)
        return json.dumps(framed, ensure_ascii=False)

    def _frame(self, graph: Graph, class_name: str) -> dict:
        frame = {**self._frames[class_name], "@context": self.context}
        expanded = jsonld.from_rdf(dataset_of(graph), NATIVE)
        framed: dict = jsonld.frame(expanded, frame, LOADER)
        return framed


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
