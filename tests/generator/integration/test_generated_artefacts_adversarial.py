"""Attacks on what the fresh artefacts claim, beyond the conformance cases (PD-12, adversarial).

The conformance cases never carry the predicates the session writes about a graph; a fresh shape that
refused them would refuse every stored aggregate, yet the cases would still pass.
"""

from pathlib import Path

import yaml
from linkml_runtime.linkml_model.meta import SlotDefinition
from linkml_runtime.utils.schemaview import SchemaView
from rdflib import XSD, Graph, Literal, URIRef

from rdf_persistence.api.services.documents import Documents
from rdf_persistence.api.services.shacl import validate_locked
from rdf_persistence.schema.services.schema_structure import generation_view, is_bookkeeping
from rdf_persistence_generation.config import TOOLKIT_ROOTS

BOOK = Path(__file__).parents[2] / "fixtures" / "conformance" / "instances" / "book-minimal.yaml"


def _value(view: SchemaView, slot: SlotDefinition) -> Literal | URIRef:
    """A well-typed value for the slot: the session writes typed values, and a shape may check the type."""
    if slot.range in view.all_classes():
        return URIRef("https://example.org/library/principal-1")
    if slot.range == "datetime":
        return Literal("2026-01-01T00:00:00Z", datatype=XSD.dateTime)
    return Literal("written by the session")


def _book_graph(view: SchemaView, documents: Documents) -> tuple[Graph, URIRef]:
    body = yaml.safe_load(BOOK.read_text(encoding="utf-8"))
    graph = documents.expand(body, view.get_class("Book"))
    return graph, URIRef(body["id"])


def test_the_fresh_shapes_accept_the_predicates_the_session_writes(fresh_toy: Path) -> None:
    view = generation_view(fresh_toy / "library.yaml", roots=TOOLKIT_ROOTS)
    documents = Documents(view, fresh_toy / "generated")
    bookkeeping = [
        (URIRef(str(view.get_uri(slot, expand=True))), _value(view, slot))
        for slot in view.all_slots().values()
        if is_bookkeeping(slot)
    ]
    assert bookkeeping, (
        "the toolkit's schema declares no bookkeeping slot: the test attacks nothing"
    )
    refused = []
    for predicate, value in bookkeeping:
        graph, subject = _book_graph(view, documents)
        graph.add((subject, predicate, value))
        conforms, _, _ = validate_locked(graph, documents.shapes)
        if not conforms:
            refused.append(str(predicate))
    assert not refused, f"the closed Book shape refuses the session's predicates {refused}"
