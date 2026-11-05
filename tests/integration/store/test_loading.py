"""Graph loading against a real Fuseki: scenario 'a broken file', and the commit that registers a load."""

import uuid
from collections.abc import AsyncIterator

import pytest
from rdflib import BNode, Graph, Literal, URIRef
from rdflib.compare import graph_diff, isomorphic

from rdf_persistence import InvalidGraph, load_graph
from rdf_persistence.adapters.fuseki import FusekiStore
from rdf_persistence.domain import vocabulary as v
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.generated.rp_files import RdfFormat
from rdf_persistence.domain.iris import graph_iri, registry_graph_iri
from rdf_persistence.domain.sparql import fill, term
from rdf_persistence.services.session import Session

TENANT = "https://example.org/libraries/6f1c0c1e"
BOOK = f"{TENANT}/books/1"
TITLE = URIRef("http://purl.org/dc/terms/title")
ADA = Principal(id="https://example.org/people/ada")
SELECT_GRAPHS = "SELECT DISTINCT ?g WHERE { GRAPH ?g { ?s ?p ?o } }"
CONSTRUCT = "CONSTRUCT { ?s ?p ?o } WHERE { GRAPH $g { ?s ?p ?o } }"
TURTLE = b'<https://example.org/b> <http://purl.org/dc/terms/title> "Dune", "Arrakis" .\n'
BROKEN_TURTLE = b"<https://example.org/b> <http://purl.org/dc/terms/title> ??? ."


@pytest.fixture
async def store(fuseki) -> AsyncIterator[FusekiStore]:
    async with FusekiStore(fuseki.url, fuseki.user, fuseki.password) as client:
        yield client


@pytest.fixture
async def database(store: FusekiStore) -> AsyncIterator[str]:
    name = f"t-{uuid.uuid4().hex}"
    await store.create_dataset(name)
    yield name
    await store.drop_dataset(name)


@pytest.fixture
def session(store, database) -> Session:
    return Session(store, database=database, tenant_iri=TENANT, principal=ADA, clock=lambda: None)


async def graphs_in(store, database) -> set[str]:
    return {str(row.g) for row in await store.query(database, SELECT_GRAPHS)}


async def contents(store, database, graph: URIRef) -> Graph:
    return (await store.query(database, fill(CONSTRUCT, g=term(graph)))).graph


async def registered(store, database) -> Graph:
    return await contents(store, database, registry_graph_iri(TENANT))


async def test_a_broken_file_fails_with_the_parsers_message_and_creates_no_graph(store, database):
    with pytest.raises(InvalidGraph) as raised:
        await load_graph(store, database, BOOK, BROKEN_TURTLE, format=RdfFormat.TURTLE)
    assert str(raised.value), "the parser's message"
    assert await graphs_in(store, database) == set(), "no graph was created"


async def test_a_good_file_lands_in_its_own_graph_under_the_aggregate(store, database):
    loaded = await load_graph(store, database, BOOK, TURTLE, format=RdfFormat.TURTLE)
    expected = Graph().parse(data=TURTLE, format="turtle")
    held = await contents(store, database, loaded)
    assert str(loaded).startswith(f"{BOOK}/content/"), "named under the aggregate"
    assert isomorphic(held, expected), graph_diff(held, expected)
    assert await graphs_in(store, database) == {str(loaded)}, "only the loaded graph exists"


async def test_the_callers_commit_registers_the_loaded_graph_and_removing_the_aggregate_unregisters_it(
    store, database, session
):
    loaded = await load_graph(store, database, BOOK, TURTLE, format=RdfFormat.TURTLE)
    version = await session.add_graph(BOOK, [(URIRef(BOOK), TITLE, Literal("x"))], [loaded])
    entries = await registered(store, database)
    assert (loaded, v.REGISTRY_OWNED_BY, URIRef(BOOK)) in entries, "owned by the aggregate"
    kind = v.REGISTRY_KIND_IRIS["loaded_graph"]
    assert (loaded, v.REGISTRY_KIND, kind) in entries, "registered as a loaded graph"
    await session.remove(BOOK, version)
    assert len(await registered(store, database)) == 0, "no entry survives the aggregate"


async def test_a_replace_that_drops_a_loaded_graph_unregisters_it(store, database, session):
    first = await load_graph(store, database, BOOK, TURTLE, format=RdfFormat.TURTLE)
    second = await load_graph(store, database, BOOK, TURTLE, format=RdfFormat.TURTLE)
    version = await session.add_graph(BOOK, [], [first, second])
    await session.replace_graph(BOOK, [], version, [second])
    entries = await registered(store, database)
    assert (first, v.REGISTRY_OWNED_BY, URIRef(BOOK)) not in entries, "dropped graph unregistered"
    assert (second, v.REGISTRY_OWNED_BY, URIRef(BOOK)) in entries, "kept graph still registered"
    assert (graph_iri(BOOK), v.REGISTRY_OWNED_BY, URIRef(BOOK)) in entries, "own entry kept"


async def test_blank_nodes_are_stored_once_as_skolem_iris_under_the_graph_iri(
    store, database, session
):
    part = BNode("part")
    triples = [(URIRef(BOOK), TITLE, part), (part, TITLE, Literal("part"))]
    version = await session.add_graph(BOOK, triples)
    await session.replace_graph(BOOK, triples, version)
    stored = await contents(store, database, graph_iri(BOOK))
    plain = [t for t in stored if t[1] not in v.BOOKKEEPING_PREDICATES]
    assert len(plain) == 2, "two statements, none copied by the guarded update's many rows"
    assert not any(isinstance(n, BNode) for t in stored for n in t), "no blank node stored"
    skolem = next(o for s, _, o in plain if s == URIRef(BOOK))
    assert str(skolem).startswith(f"{graph_iri(BOOK)}/.well-known/genid/"), "skolem under the graph"
