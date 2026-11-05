"""The session's commit with loaded graphs and blank nodes, over the in-memory FakeStore."""

from datetime import UTC, datetime

import pytest
from rdflib import BNode, Graph, Literal, URIRef

from rdf_persistence.domain import vocabulary as v
from rdf_persistence.domain.errors import Conflict
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.iris import registry_graph_iri
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


async def test_replace_without_loaded_graphs_unregisters_them(session, store):
    version = await session.add_graph(ROOT, [], loaded_graphs=LOADED)
    await session.replace_graph(ROOT, [], version)
    assert await registered_loaded(store) == set(), "the default is no loaded graphs"


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


async def test_replace_with_no_loaded_graphs_empties_all_of_them(session, store):
    for graph in LOADED:
        await store.put_graph("db", graph, Graph().parse(data=LOADED_TTL, format="turtle"))
    version = await session.add_graph(ROOT, [], loaded_graphs=LOADED)
    await session.replace_graph(ROOT, [], version)
    assert [g for g in LOADED if await has_triples(store, g)] == [], "none is left"


async def test_a_stale_replace_leaves_the_loaded_graphs_alone(session, store):
    await store.put_graph("db", LOADED[0], Graph().parse(data=LOADED_TTL, format="turtle"))
    await session.add_graph(ROOT, [], loaded_graphs=LOADED[:1])
    with pytest.raises(Conflict):
        await session.replace_graph(ROOT, [], "stale")
    assert await has_triples(store, LOADED[0]), "the guard protects the loaded graph too"
