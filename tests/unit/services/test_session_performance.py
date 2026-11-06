"""REPLACE and REMOVE cost the size of the graphs they touch, not the product of them (fixer C)."""

import time

import pytest
from rdflib import Graph, Literal, URIRef

from rdf_persistence.domain.iris import loaded_graph_iri, mint_aggregate_iri
from rdf_persistence.testkit import FakeStore, fake_session
from rdf_persistence.testkit.fakes import FAKE_DATABASE
from tests.toy import TENANT

TITLE = URIRef("http://purl.org/dc/terms/title")
BUDGET_SECONDS = 2.0  # the cartesian form took 51 s for the first case
SIZES = [pytest.param(50, 2000, id="50 aggregate, 2000 loaded")]


def titles(subject: URIRef, n: int) -> list:
    return [(subject, TITLE, Literal(f"title {i}")) for i in range(n)]


async def committed(session, store, aggregate_size: int, loaded_size: int):
    iri = str(mint_aggregate_iri(TENANT, "books"))
    loaded = loaded_graph_iri(iri)
    await store.put_graph(FAKE_DATABASE, loaded, _graph(titles(URIRef(iri), loaded_size)))
    version = await session.add_graph(iri, titles(URIRef(iri), aggregate_size), [loaded])
    return iri, loaded, version


def _graph(triples: list) -> Graph:
    graph = Graph()
    for triple in triples:
        graph.add(triple)
    return graph


# The aggregate stays small: rdflib parses an update text of 2000 triples in seconds, as it does an
# INSERT DATA of that size; that is the fake's parser, not the shape of the update.
@pytest.mark.parametrize(("aggregate_size", "loaded_size"), SIZES)
@pytest.mark.parametrize("keep_loaded", [True, False], ids=["keeps the loaded graph", "drops it"])
async def test_replace_stays_within_the_budget(aggregate_size, loaded_size, keep_loaded):
    store = FakeStore()
    async with fake_session(store, tenant_iri=TENANT) as session:
        iri, loaded, version = await committed(session, store, aggregate_size, loaded_size)
        started = time.perf_counter()
        await session.replace_graph(
            iri, titles(URIRef(iri), aggregate_size), version, [loaded] if keep_loaded else []
        )
        assert time.perf_counter() - started < BUDGET_SECONDS


@pytest.mark.parametrize(("aggregate_size", "loaded_size"), SIZES)
async def test_remove_stays_within_the_budget(aggregate_size, loaded_size):
    store = FakeStore()
    async with fake_session(store, tenant_iri=TENANT) as session:
        iri, _, version = await committed(session, store, aggregate_size, loaded_size)
        started = time.perf_counter()
        await session.remove(iri, version)
        assert time.perf_counter() - started < BUDGET_SECONDS
