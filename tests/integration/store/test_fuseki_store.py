"""FusekiStore against a real Fuseki; each test works in a dataset of its own."""

import uuid
from collections.abc import AsyncIterator

import pytest
from rdflib import Graph, Literal, URIRef
from rdflib.compare import graph_diff, isomorphic

from rdf_persistence.adapters.fuseki import FusekiStore
from rdf_persistence.domain.errors import (
    BadQuery,
    Conflict,
    DatabaseGone,
    NotFound,
    StoreUnavailable,
)
from rdf_persistence.domain.sparql import fill, term

EX = "http://example.org/"
A, B, P, G = (URIRef(f"{EX}{n}") for n in "abpg")
ASK_TRIPLE = "ASK { GRAPH $graph { $s $p $o } }"
INSERT = "INSERT DATA { GRAPH $graph { $s $p $o } }"


def triple_text(template: str, obj: Literal | URIRef, graph: URIRef = G) -> str:
    return fill(template, graph=term(graph), s=term(A), p=term(P), o=term(obj))


@pytest.fixture
async def store(fuseki) -> AsyncIterator[FusekiStore]:
    async with FusekiStore(fuseki.url, fuseki.user, fuseki.password) as client:
        yield client


@pytest.fixture
async def dataset(store: FusekiStore) -> AsyncIterator[str]:
    name = f"t-{uuid.uuid4().hex}"
    await store.create_dataset(name)
    yield name
    await store.drop_dataset(name)


async def test_create_list_and_drop_a_dataset(store):
    name = f"t-{uuid.uuid4().hex}"
    await store.create_dataset(name)
    assert name in await store.list_datasets(), "created"
    await store.drop_dataset(name)
    assert name not in await store.list_datasets(), "dropped"


async def test_creating_an_existing_dataset_is_a_conflict(store, dataset):
    with pytest.raises(Conflict):
        await store.create_dataset(dataset)


async def test_dropping_a_missing_dataset_is_not_found(store):
    with pytest.raises(NotFound):
        await store.drop_dataset(f"t-{uuid.uuid4().hex}")


async def test_update_then_ask(store, dataset):
    obj = Literal('a "quoted"\nvalue\\')
    assert (await store.query(dataset, triple_text(ASK_TRIPLE, obj))).askAnswer is False
    await store.update(dataset, triple_text(INSERT, obj))
    assert (await store.query(dataset, triple_text(ASK_TRIPLE, obj))).askAnswer is True


async def test_select_returns_rdflib_terms(store, dataset):
    await store.update(dataset, triple_text(INSERT, Literal(7)))
    result = await store.query(dataset, "SELECT ?s ?o WHERE { GRAPH ?g { ?s ?p ?o } }")
    assert [(row.s, row.o) for row in result] == [(A, Literal(7))]


async def test_construct_returns_a_graph(store, dataset):
    await store.update(dataset, triple_text(INSERT, B))
    result = await store.query(dataset, "CONSTRUCT { ?s ?p ?o } WHERE { GRAPH ?g { ?s ?p ?o } }")
    expected = Graph()
    expected.add((A, P, B))
    assert isomorphic(result.graph, expected), graph_diff(result.graph, expected)


async def test_put_graph_replaces_the_named_graph_and_only_it(store, dataset):
    other = URIRef(f"{EX}other")
    await store.update(dataset, triple_text(INSERT, Literal("old")))
    await store.update(dataset, triple_text(INSERT, Literal("elsewhere"), graph=other))
    replacement = Graph()
    replacement.add((A, P, Literal("new")))
    await store.put_graph(dataset, G, replacement)
    assert (await store.query(dataset, triple_text(ASK_TRIPLE, Literal("new")))).askAnswer
    assert not (await store.query(dataset, triple_text(ASK_TRIPLE, Literal("old")))).askAnswer
    assert (
        await store.query(dataset, triple_text(ASK_TRIPLE, Literal("elsewhere"), graph=other))
    ).askAnswer


async def test_a_graph_iri_with_reserved_characters_is_one_graph(store, dataset):
    graph_iri = URIRef(f"{EX}g?x=1&y=2#z")
    replacement = Graph()
    replacement.add((A, P, Literal("v")))
    await store.put_graph(dataset, graph_iri, replacement)
    assert (
        await store.query(dataset, triple_text(ASK_TRIPLE, Literal("v"), graph=graph_iri))
    ).askAnswer


async def test_a_malformed_query_is_bad_query(store, dataset):
    with pytest.raises(BadQuery):
        await store.query(dataset, "SELEKT nothing")


@pytest.mark.parametrize("operation", ["query", "update", "put_graph"])
async def test_a_dropped_dataset_is_gone(store, operation):
    name = f"t-{uuid.uuid4().hex}"
    await store.create_dataset(name)
    await store.drop_dataset(name)
    calls = {
        "query": lambda: store.query(name, "ASK {}"),
        "update": lambda: store.update(name, "CLEAR ALL"),
        "put_graph": lambda: store.put_graph(name, G, Graph()),
    }
    with pytest.raises(DatabaseGone):
        await calls[operation]()


async def test_an_unreachable_store_is_unavailable(fuseki):
    async with FusekiStore("http://127.0.0.1:9", fuseki.user, fuseki.password) as unreachable:
        with pytest.raises(StoreUnavailable):
            await unreachable.list_datasets()
