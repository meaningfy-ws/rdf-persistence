"""The store the toolkit's own SPARQL goes through: a refusal of the text is the service's fault."""

import pytest
from rdflib import Dataset, Graph, URIRef

from rdf_persistence.domain.exceptions import BadQuery, DatabaseGone, SparqlError
from rdf_persistence.services.store import ToolkitStore
from rdf_persistence.testkit import FakeStore, assert_isomorphic

DATASET = "d"
GRAPH = URIRef("https://example.org/g")


@pytest.fixture
async def store() -> ToolkitStore:
    fake = FakeStore()
    await fake.create_dataset(DATASET)
    return ToolkitStore(fake)


async def test_a_query_the_store_finds_malformed_is_a_sparql_error_that_hides_the_text(store):
    with pytest.raises(SparqlError) as raised:
        await store.query(DATASET, "SELEKT secret")
    assert "secret" not in str(raised.value), "the text stays out of the message"
    assert isinstance(raised.value.__cause__, BadQuery), "and the store's refusal is the cause"


async def test_an_update_the_store_finds_malformed_is_a_sparql_error(store):
    with pytest.raises(SparqlError):
        await store.update(DATASET, "INSERT nothing")


async def test_the_dataset_level_export_and_import_pass_through_unchanged(store):
    put = Graph().parse(data="<urn:x> <urn:y> <urn:z> .", format="nt")
    await store.put_graph(DATASET, GRAPH, put)
    exported = await store.export_quads(DATASET)
    exported_dataset = Dataset().parse(data=exported, format="nquads")
    assert {graph.identifier for graph in exported_dataset.graphs() if len(graph)} == {GRAPH}, (
        "the quads of the one named graph"
    )
    assert_isomorphic(exported_dataset.graph(GRAPH), put)
    await store.create_dataset("copy")
    await store.import_quads("copy", exported)
    imported = Dataset().parse(data=await store.export_quads("copy"), format="nquads")
    assert {graph.identifier for graph in imported.graphs() if len(graph)} == {GRAPH}, (
        "the import added no graph beyond the one named graph"
    )
    assert_isomorphic(imported.graph(GRAPH), put)
    with pytest.raises(DatabaseGone):
        await store.export_quads("missing")
    with pytest.raises(DatabaseGone):
        await store.import_quads("missing", exported)


async def test_everything_else_passes_through_unchanged(store):
    await store.put_graph(
        DATASET, GRAPH, Graph().parse(data="<urn:x> <urn:y> <urn:z> .", format="nt")
    )
    await store.update(DATASET, "INSERT DATA { GRAPH <urn:g> { <urn:a> <urn:b> <urn:c> } }")
    assert (
        await store.query(DATASET, "ASK { GRAPH <urn:g> { <urn:a> <urn:b> <urn:c> } }")
    ).askAnswer, "the query passes through unchanged"
    assert DATASET in await store.list_datasets(), "the dataset listing passes through unchanged"
    with pytest.raises(DatabaseGone):
        await store.query("missing", "ASK { ?s ?p ?o }")
    await store.drop_dataset(DATASET)
    await store.create_dataset(DATASET)
