"""An application slot that shares an IRI or a name with a toolkit slot keeps its value (#277).

The toy's ``Template`` has a business ``identifier`` on ``dcterms:identifier``, the property of the
toolkit's ``id``.
"""

import json

import pytest
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS

from rdf_persistence.api.services.documents import Documents
from rdf_persistence.collaboration.services.referrer_naming import slot_name
from rdf_persistence.core.domain.media import JSON
from rdf_persistence.iris.domain.layout import graph_iri
from rdf_persistence.schema.services.schema import load_schema
from tests.fixtures.library.domain.generated.templates import Template
from tests.toy import GENERATED, TENANT, TOY_SCHEMA, encoded, template, toy_mapper

TEMPLATE = "https://example.org/templates/t1"
CODE = "tpl-1"
VALUES = {"identifier": CODE}
BODY = {"label": "Quarterly report", **VALUES}


@pytest.fixture(scope="module")
def documents() -> Documents:
    return Documents(load_schema(TOY_SCHEMA), GENERATED)


@pytest.fixture(scope="module")
def stored() -> Graph:
    return toy_mapper().to_graph(template(TEMPLATE).model_copy(update=VALUES))


async def test_a_body_with_the_values_becomes_their_triples_and_passes_the_shapes(
    documents: Documents,
) -> None:
    cls = load_schema(TOY_SCHEMA).get_class("Template")
    graph, _ = await documents.parse(
        encoded(BODY), JSON, cls, TEMPLATE, creating=True, tenant=TENANT
    )
    node = URIRef(TEMPLATE)
    assert (node, DCTERMS.identifier, Literal(CODE)) in graph, "the business identifier, a literal"
    await documents.validate(graph)  # #277: no shape asks dcterms:identifier to be an IRI


def test_the_mapper_writes_and_reads_the_values(stored: Graph) -> None:
    node = URIRef(TEMPLATE)
    assert (node, DCTERMS.identifier, Literal(CODE)) in stored, "the identifier is written"
    read = toy_mapper().from_graph(Template, TEMPLATE, stored, None)
    assert (read.id, read.identifier) == (TEMPLATE, CODE), "read back"


def test_the_identifier_slot_never_names_a_predicate() -> None:
    """#277: a dcterms:identifier statement is the business identifier, not the IRI."""
    view = load_schema(TOY_SCHEMA)
    assert slot_name(view, "Template", str(DCTERMS.identifier)) == "identifier", "not id"


async def test_the_json_representation_shows_the_values(
    documents: Documents, stored: Graph
) -> None:
    cls = load_schema(TOY_SCHEMA).get_class("Template")
    shown = json.loads(await documents.render(stored, graph_iri(TEMPLATE), cls, JSON))
    assert shown["id"] == TEMPLATE, shown
    assert {k: shown.get(k) for k in VALUES} == VALUES, shown
