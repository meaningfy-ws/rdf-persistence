"""The store the toolkit's own SPARQL goes through: a refusal of the text is the service's fault."""

import pytest
from opentelemetry.trace import SpanKind
from rdflib import Dataset, Graph, URIRef

from rdf_persistence.adapters.fuseki import FusekiStore
from rdf_persistence.domain.exceptions import BadQuery, DatabaseGone, SparqlError
from rdf_persistence.services.store import ToolkitStore, TracedStore, system_name_of
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


SECRET = "secret-tenant-text"


async def _call(store, method: str) -> None:
    """Call ``method`` of the port once, with arguments that succeed on a ``FakeStore``."""
    graph = Graph().parse(data="<urn:x> <urn:y> <urn:z> .", format="nt")
    calls = {
        "query": lambda: store.query(DATASET, "ASK { ?s ?p ?o }"),
        "update": lambda: store.update(
            DATASET, "INSERT DATA { GRAPH <urn:g> { <urn:a> <urn:b> <urn:c> } }"
        ),
        "put_graph": lambda: store.put_graph(DATASET, GRAPH, graph),
        "export_quads": lambda: store.export_quads(DATASET),
        "import_quads": lambda: store.import_quads(DATASET, b""),
        "create_dataset": lambda: store.create_dataset("extra"),
        "drop_dataset": lambda: store.drop_dataset("extra"),
        "list_datasets": lambda: store.list_datasets(),
    }
    if method == "drop_dataset":
        await store.create_dataset("extra")
    await calls[method]()


@pytest.mark.parametrize("method", sorted(FakeStore.OPERATIONS))
async def test_tc25_each_port_method_is_one_client_span_named_after_it(spans, method):
    fake = FakeStore()
    await fake.create_dataset(DATASET)
    traced_store = TracedStore(fake, "rdflib")
    await _call(traced_store, method)
    (span,) = [s for s in spans() if s.name == method]
    assert span.kind is SpanKind.CLIENT, "a client span"
    expected = {
        "db.system.name": "rdflib",
        "db.operation.name": method,
        "rp.step": method,
    }
    if method == "list_datasets":
        assert "db.namespace" not in span.attributes, "a listing has no dataset"
    elif method in ("create_dataset", "drop_dataset"):
        expected["db.namespace"] = "extra"
    else:
        expected["db.namespace"] = DATASET
    assert dict(span.attributes) == expected


def test_tc26_system_name_of_reads_the_attribute_and_falls_back_to_sparql():
    fuseki = FusekiStore("http://fuseki.test:3030", "u", "p")
    assert system_name_of(fuseki) == "fuseki"
    assert system_name_of(FakeStore()) == "rdflib"
    assert system_name_of(object()) == "sparql", "no attribute: the generic name"


async def test_tc18_no_span_holds_the_text_of_an_update(spans):
    fake = FakeStore()
    await fake.create_dataset(DATASET)
    traced_store = TracedStore(fake, "rdflib")
    await traced_store.update(
        DATASET, f'INSERT DATA {{ GRAPH <urn:g> {{ <urn:a> <urn:b> "{SECRET}" }} }}'
    )
    await traced_store.query(DATASET, f'ASK {{ ?s ?p "{SECRET}" }}')
    finished = spans()
    assert finished, "the calls were traced"
    for span in finished:
        assert "db.query.text" not in span.attributes, "no query text attribute"
        assert not any(SECRET in str(value) for value in span.attributes.values()), (
            "no attribute holds the text"
        )


async def test_a_failure_of_the_store_passes_through_and_marks_the_span(spans):
    traced_store = TracedStore(FakeStore(), "rdflib")
    with pytest.raises(DatabaseGone):
        await traced_store.query("missing", "ASK { ?s ?p ?o }")
    (span,) = spans()
    assert span.attributes["error.type"].endswith("DatabaseGone")
