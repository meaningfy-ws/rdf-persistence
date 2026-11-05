"""The session's commit with loaded graphs and blank nodes, over the in-memory FakeStore."""

import asyncio
from datetime import UTC, datetime

import pytest
from rdflib import BNode, Graph, Literal, URIRef

from rdf_persistence.domain import vocabulary as v
from rdf_persistence.domain.errors import Conflict
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.iris import graph_iri, registry_graph_iri
from rdf_persistence.domain.sparql import fill, term
from rdf_persistence.services.session import Session
from rdf_persistence.testkit import FakeStore

TENANT = "https://example.org/libraries/6f1c0c1e"
ROOT = f"{TENANT}/books/1"
TITLE = URIRef("http://purl.org/dc/terms/title")
LOADED = [URIRef(f"{ROOT}/content/a"), URIRef(f"{ROOT}/content/b")]
LOADED_TTL = '<https://example.org/b> <http://purl.org/dc/terms/title> "Dune" .'
ENTRIES = "SELECT ?g WHERE { GRAPH $r { ?g $kind $loaded } }"


@pytest.fixture
async def store():
    fake = FakeStore()
    await fake.create_dataset("db")
    return fake


@pytest.fixture
def session(store) -> Session:
    return Session(
        store,
        database="db",
        tenant_iri=TENANT,
        principal=Principal(id="https://example.org/people/ada"),
        clock=lambda: datetime(2026, 11, 5, tzinfo=UTC),
    )


async def has_triples(store, graph: URIRef) -> bool:
    result = await store.query("db", fill("ASK { GRAPH $g { ?s ?p ?o } }", g=term(graph)))
    return bool(result.askAnswer)


async def registered_loaded(store) -> set[URIRef]:
    text = fill(
        ENTRIES,
        r=term(registry_graph_iri(TENANT)),
        kind=term(v.REGISTRY_KIND),
        loaded=term(v.REGISTRY_KIND_IRIS["loaded_graph"]),
    )
    return {row.g for row in await store.query("db", text)}


async def test_add_registers_every_loaded_graph_in_the_same_update(session, store):
    await session.add_graph(ROOT, [], loaded_graphs=LOADED)
    assert await registered_loaded(store) == set(LOADED), "one entry per loaded graph"
    assert len(store.sent("update")) == 1, "graph and entries are one update"


async def test_replace_rewrites_the_loaded_graph_entries_to_the_given_ones(session, store):
    version = await session.add_graph(ROOT, [], loaded_graphs=LOADED)
    await session.replace_graph(ROOT, [], version, loaded_graphs=LOADED[:1])
    assert await registered_loaded(store) == set(LOADED[:1]), "the dropped graph is unregistered"


async def test_replace_with_an_empty_list_unregisters_them(session, store):
    version = await session.add_graph(ROOT, [], loaded_graphs=LOADED)
    await session.replace_graph(ROOT, [], version, loaded_graphs=[])
    assert await registered_loaded(store) == set(), "an explicit empty list drops them all"


async def test_replace_without_a_list_keeps_the_registered_loaded_graphs(session, store):
    for graph in LOADED:
        await store.put_graph("db", graph, Graph().parse(data=LOADED_TTL, format="turtle"))
    version = await session.add_graph(ROOT, [], loaded_graphs=LOADED)
    await session.replace_graph(ROOT, [(URIRef(ROOT), TITLE, Literal("edited"))], version)
    assert await registered_loaded(store) == set(LOADED), "their entries stay"
    assert [g for g in LOADED if await has_triples(store, g)] == LOADED, "their triples stay"


async def test_replace_without_a_list_leaves_the_loaded_graphs_of_another_aggregate_alone(
    session, store
):
    other = f"{TENANT}/books/2"
    other_loaded = URIRef(f"{other}/content/z")
    await session.add_graph(other, [], loaded_graphs=[other_loaded])
    version = await session.add_graph(ROOT, [], loaded_graphs=LOADED)
    await session.replace_graph(ROOT, [], version)
    assert await registered_loaded(store) == {*LOADED, other_loaded}


OUTSIDE_THE_CONTENT = [
    pytest.param(URIRef(f"{TENANT}/books/2/graph"), id="another aggregate's graph"),
    pytest.param(registry_graph_iri(TENANT), id="the registry graph"),
    pytest.param(URIRef(f"{TENANT}/books/2/content/z"), id="another aggregate's loaded graph"),
    pytest.param(URIRef(f"{ROOT}/content"), id="the content segment without a graph"),
    pytest.param(URIRef(f"{ROOT}0/content/a"), id="a sibling that shares the prefix text"),
]


@pytest.mark.parametrize("bad", OUTSIDE_THE_CONTENT)
async def test_add_refuses_a_loaded_graph_outside_the_aggregate_before_any_request(
    session, store, bad
):
    with pytest.raises(ValueError, match="content"):
        await session.add_graph(ROOT, [], loaded_graphs=[LOADED[0], bad])
    assert (store.sent("query"), store.sent("update")) == ([], []), "the store was not touched"


@pytest.mark.parametrize("bad", OUTSIDE_THE_CONTENT)
async def test_replace_refuses_a_loaded_graph_outside_the_aggregate_before_any_request(
    session, store, bad
):
    version = await session.add_graph(ROOT, [], loaded_graphs=LOADED)
    requests = (len(store.sent("query")), len(store.sent("update")))
    with pytest.raises(ValueError, match="content"):
        await session.replace_graph(ROOT, [], version, loaded_graphs=[bad])
    assert (len(store.sent("query")), len(store.sent("update"))) == requests, "nothing was sent"
    assert await registered_loaded(store) == set(LOADED), "and nothing changed"


async def test_removing_an_aggregate_cannot_empty_the_graph_of_another(session, store):
    victim = f"{TENANT}/books/2"
    await session.add_graph(victim, [(URIRef(victim), TITLE, Literal("victim"))])
    with pytest.raises(ValueError, match="content"):
        await session.add_graph(ROOT, [], loaded_graphs=[graph_iri(victim)])
    stored, _ = await session.get_graph(victim)
    assert (URIRef(victim), TITLE, Literal("victim")) in stored, "the victim is intact"


async def test_remove_unregisters_the_loaded_graphs_with_the_aggregate(session, store):
    version = await session.add_graph(ROOT, [], loaded_graphs=LOADED)
    await session.remove(ROOT, version)
    assert await registered_loaded(store) == set(), "no entry survives the aggregate"


async def test_a_graph_with_blank_nodes_is_stored_once_with_skolem_iris(session):
    part = BNode("part")
    triples = [(URIRef(ROOT), TITLE, part), (part, TITLE, Literal("x"))]
    version = await session.add_graph(ROOT, triples)
    await session.replace_graph(ROOT, triples, version)  # the guard matches many rows here
    stored, _ = await session.get_graph(ROOT)
    plain = [t for t in stored if t[1] not in v.BOOKKEEPING_PREDICATES]
    assert len(plain) == 2, "two statements, none copied per matched row"
    assert not any(isinstance(n, BNode) for t in stored for n in t), "no blank node stored"
    skolem = next(o for s, _, o in plain if s == URIRef(ROOT))
    assert str(skolem).startswith(f"{ROOT}/graph/.well-known/genid/"), (
        "a skolem IRI under the graph"
    )


async def test_remove_drops_the_triples_of_the_loaded_graphs_it_owned(session, store):
    for graph in LOADED:
        await store.put_graph("db", graph, Graph().parse(data=LOADED_TTL, format="turtle"))
    other = URIRef(f"{TENANT}/books/2/content/z")
    await store.put_graph("db", other, Graph().parse(data=LOADED_TTL, format="turtle"))
    version = await session.add_graph(ROOT, [], loaded_graphs=LOADED)
    await session.remove(ROOT, version)
    assert [g for g in (*LOADED, other) if await has_triples(store, g)] == [other], (
        "only the removed aggregate's loaded graphs are gone"
    )


async def test_replace_drops_the_triples_of_unlisted_loaded_graphs_and_keeps_listed_ones(
    session, store
):
    for graph in LOADED:
        await store.put_graph("db", graph, Graph().parse(data=LOADED_TTL, format="turtle"))
    version = await session.add_graph(ROOT, [], loaded_graphs=LOADED)
    await session.replace_graph(ROOT, [], version, loaded_graphs=LOADED[:1])
    assert await has_triples(store, LOADED[0]), "the listed graph keeps its triples"
    assert not await has_triples(store, LOADED[1]), "the unlisted graph is emptied"


async def test_replace_with_an_empty_list_empties_all_of_them(session, store):
    for graph in LOADED:
        await store.put_graph("db", graph, Graph().parse(data=LOADED_TTL, format="turtle"))
    version = await session.add_graph(ROOT, [], loaded_graphs=LOADED)
    await session.replace_graph(ROOT, [], version, loaded_graphs=[])
    assert [g for g in LOADED if await has_triples(store, g)] == [], "none is left"


async def test_a_stale_replace_leaves_the_loaded_graphs_alone(session, store):
    await store.put_graph("db", LOADED[0], Graph().parse(data=LOADED_TTL, format="turtle"))
    await session.add_graph(ROOT, [], loaded_graphs=LOADED[:1])
    with pytest.raises(Conflict):
        await session.replace_graph(ROOT, [], "stale")
    assert await has_triples(store, LOADED[0]), "the guard protects the loaded graph too"


async def test_two_concurrent_adds_of_one_iri_give_one_success_and_one_conflict(store):
    gate = asyncio.Barrier(2)
    original = store.update

    async def held(dataset: str, sparql: str) -> None:
        await gate.wait()  # both have passed any pre-check by now
        await original(dataset, sparql)

    store.update = held
    first, second = (
        Session(
            store, database="db", tenant_iri=TENANT, principal=Principal(id=who), clock=lambda: None
        )
        for who in ("https://example.org/people/ada", "https://example.org/people/ben")
    )
    outcomes = await asyncio.gather(
        first.add_graph(ROOT, []), second.add_graph(ROOT, []), return_exceptions=True
    )
    stored, _ = await first.get_graph(ROOT)
    assert sorted(type(o).__name__ for o in outcomes) == ["Conflict", "str"], "one wins"
    assert len(list(stored.objects(None, v.VERSION))) == 1, "one version token was written"
