"""The session against a real Fuseki: scenarios 'graph name', 'two editors', 'a commit records who and when'."""

import asyncio
import time
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from rdflib import Graph, Literal, URIRef
from rdflib.compare import graph_diff, isomorphic

from rdf_persistence.adapters.fuseki import FusekiStore
from rdf_persistence.domain.exceptions import Conflict, DatabaseGone, InvalidIri, NotFound
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.iris import (
    graph_iri,
    loaded_graph_iri,
    meta_graph_iri,
    registry_graph_iri,
)
from rdf_persistence.domain.sparql import fill, term
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.session import Session, open_session

TENANT = "https://example.org/libraries/6f1c0c1e"
TITLE = URIRef("http://purl.org/dc/terms/title")
START = datetime(2026, 11, 5, 9, 0, tzinfo=UTC)
ADA, BEN, CY = (Principal(id=f"https://example.org/people/{n}") for n in ("ada", "ben", "cy"))
SELECT_GRAPHS = "SELECT DISTINCT ?g WHERE { GRAPH ?g { ?s ?p ?o } }"


class Ticker:
    """A clock that moves one minute on each reading."""

    def __init__(self) -> None:
        self.now = START

    def __call__(self) -> datetime:
        self.now += timedelta(minutes=1)
        return self.now


class RendezvousStore(FusekiStore):
    """Holds each update until ``parties`` have reached it, so two commits are in flight together."""

    barrier: asyncio.Barrier | None = None

    async def update(self, dataset: str, sparql: str) -> None:
        if self.barrier is not None:
            await self.barrier.wait()
        await super().update(dataset, sparql)


def book(n: int) -> str:
    return f"{TENANT}/books/{UUID(int=n)}"


def title(root: str, text: str) -> list:
    return [(URIRef(root), TITLE, Literal(text))]


def without_bookkeeping(graph: Graph) -> Graph:
    plain = Graph()
    for s, p, o in graph:
        if p not in v.BOOKKEEPING_PREDICATES:
            plain.add((s, p, o))
    return plain


def graph_of(triples: list) -> Graph:
    graph = Graph()
    for triple in triples:
        graph.add(triple)
    return graph


@pytest.fixture
async def store(fuseki) -> AsyncIterator[RendezvousStore]:
    async with RendezvousStore(fuseki.url, fuseki.user, fuseki.password) as client:
        yield client


@pytest.fixture
async def database(store: RendezvousStore) -> AsyncIterator[str]:
    name = f"t-{uuid.uuid4().hex}"
    await store.create_dataset(name)
    yield name
    await store.drop_dataset(name)


def session_for(store, database, principal=ADA, clock=None) -> Session:
    return Session(
        store, database=database, tenant_iri=TENANT, principal=principal, clock=clock or Ticker()
    )


async def graphs_in(store, database) -> set[str]:
    return {str(row.g) for row in await store.query(database, SELECT_GRAPHS)}


async def about_graph(store, database, graph: URIRef) -> Graph:
    """Every statement whose subject is the graph IRI, in that graph."""
    query = fill("CONSTRUCT { $g ?p ?o } WHERE { GRAPH $g { $g ?p ?o } }", g=term(graph))
    return (await store.query(database, query)).graph


async def registry(store, database) -> Graph:
    query = fill(
        "CONSTRUCT { ?s ?p ?o } WHERE { GRAPH $r { ?s ?p ?o } }", r=term(registry_graph_iri(TENANT))
    )
    return (await store.query(database, query)).graph


async def test_an_aggregate_is_stored_in_its_derived_graph_and_never_in_a_graph_named_after_the_root(
    store, database
):
    session = session_for(store, database)
    await session.add_graph(book(1), title(book(1), "Dune"))
    names = await graphs_in(store, database)
    assert str(graph_iri(book(1))) in names, "the derived graph holds the triples"
    assert book(1) not in names, "no graph is named after the root"


async def test_get_graph_returns_what_was_added_and_its_version(store, database):
    session = session_for(store, database)
    version = await session.add_graph(book(1), title(book(1), "Dune"))
    graph, _, read = await session.get_graph(book(1))
    assert read == version, "the version read is the one returned by the commit"
    expected = graph_of(title(book(1), "Dune"))
    assert isomorphic(without_bookkeeping(graph), expected), graph_diff(
        without_bookkeeping(graph), expected
    )


async def test_a_graph_read_can_be_written_back_as_it_is(store, database):
    session = session_for(store, database)
    version = await session.add_graph(book(1), title(book(1), "Dune"))
    graph, _, _ = await session.get_graph(book(1))
    new_version = await session.replace_graph(book(1), graph, version)
    assert new_version != version, "a write-back is a new version"
    stored = await about_graph(store, database, graph_iri(book(1)))
    assert len(list(stored.objects(graph_iri(book(1)), v.CREATOR))) == 1, (
        "no duplicated bookkeeping"
    )


async def test_hostile_literals_are_stored_and_read_back_unchanged(store, database):
    session = session_for(store, database)
    hostile = '"} ; DROP ALL ; #\n\\'
    await session.add_graph(book(1), title(book(1), hostile))
    graph, _, _ = await session.get_graph(book(1))
    assert (URIRef(book(1)), TITLE, Literal(hostile)) in graph, "stored as a plain value"
    assert str(graph_iri(book(1))) in await graphs_in(store, database), "nothing was dropped"


async def test_getting_a_missing_graph_is_not_found(store, database):
    with pytest.raises(NotFound):
        await session_for(store, database).get_graph(book(1))


async def test_adding_an_existing_aggregate_is_a_conflict_and_keeps_the_first(store, database):
    session = session_for(store, database)
    await session.add_graph(book(1), title(book(1), "first"))
    with pytest.raises(Conflict):
        await session.add_graph(book(1), title(book(1), "second"))
    graph, _, _ = await session.get_graph(book(1))
    assert (URIRef(book(1)), TITLE, Literal("first")) in graph, "the first stays"
    assert (URIRef(book(1)), TITLE, Literal("second")) not in graph, "the second is not stored"


async def test_replacing_with_the_current_version_stores_the_new_triples_under_a_new_version(
    store, database
):
    session = session_for(store, database)
    first = await session.add_graph(book(1), title(book(1), "old"))
    second = await session.replace_graph(book(1), title(book(1), "new"), first)
    graph, _, read = await session.get_graph(book(1))
    expected = graph_of(title(book(1), "new"))
    assert read == second != first, "a fresh token, never the old one"
    assert isomorphic(without_bookkeeping(graph), expected), graph_diff(
        without_bookkeeping(graph), expected
    )


async def test_replacing_with_a_stale_version_is_a_conflict_and_changes_nothing(store, database):
    session = session_for(store, database)
    first = await session.add_graph(book(1), title(book(1), "old"))
    await session.replace_graph(book(1), title(book(1), "winner"), first)
    before, _, version = await session.get_graph(book(1))
    with pytest.raises(Conflict):
        await session.replace_graph(book(1), title(book(1), "loser"), first)
    after, _, version_after = await session.get_graph(book(1))
    assert version_after == version, "the version did not move"
    assert isomorphic(after, before), graph_diff(after, before)


async def test_replacing_a_missing_graph_is_not_found(store, database):
    with pytest.raises(NotFound):
        await session_for(store, database).replace_graph(book(1), title(book(1), "x"), "v")


async def test_two_editors_who_read_the_same_version_get_one_commit_and_one_conflict(
    store, database
):
    await session_for(store, database).add_graph(book(1), title(book(1), "v0"))
    _, _, seen = await session_for(store, database).get_graph(book(1))
    store.barrier = asyncio.Barrier(2)
    ada, ben = session_for(store, database, ADA), session_for(store, database, BEN)
    outcomes = await asyncio.gather(
        ada.replace_graph(book(1), title(book(1), "by ada"), seen),
        ben.replace_graph(book(1), title(book(1), "by ben"), seen),
        return_exceptions=True,
    )
    store.barrier = None
    winners = [o for o in outcomes if isinstance(o, str)]
    losers = [o for o in outcomes if isinstance(o, Conflict)]
    assert (len(winners), len(losers)) == (1, 1), f"one wins, one conflicts: {outcomes}"
    graph, _, stored = await session_for(store, database).get_graph(book(1))
    winning_title = "by ada" if isinstance(outcomes[0], str) else "by ben"
    expected = graph_of(title(book(1), winning_title))
    assert stored == winners[0], "the stored token is the winner's"
    assert isomorphic(without_bookkeeping(graph), expected), (
        "the stored book is the winner's, whole"
    )
    assert len(await registry(store, database)) == 3, "one registry entry, nothing half-written"


async def test_two_adds_of_one_iri_give_one_success_and_one_conflict(store, database):
    store.barrier = asyncio.Barrier(2)
    ada, ben = session_for(store, database, ADA), session_for(store, database, BEN)
    outcomes = await asyncio.gather(
        ada.add_graph(book(1), title(book(1), "by ada")),
        ben.add_graph(book(1), title(book(1), "by ben")),
        return_exceptions=True,
    )
    store.barrier = None
    winners = [o for o in outcomes if isinstance(o, str)]
    assert (len(winners), sum(isinstance(o, Conflict) for o in outcomes)) == (1, 1), outcomes
    graph, _, stored = await session_for(store, database).get_graph(book(1))
    assert stored == winners[0], "the stored token is the winner's"
    assert len(list(graph.objects(None, v.VERSION))) == 1, "one version token, nothing doubled"
    assert len(list(graph.objects(URIRef(book(1)), TITLE))) == 1, "one title, the winner's"
    assert len(await registry(store, database)) == 3, "one registry entry"


@pytest.mark.parametrize(
    "bad", [graph_iri(book(2)), registry_graph_iri(TENANT)], ids=["aggregate", "registry"]
)
async def test_a_loaded_graph_outside_the_aggregate_is_refused_and_nothing_changes(
    store, database, bad
):
    session = session_for(store, database)
    await session.add_graph(book(2), title(book(2), "victim"))
    before = await graphs_in(store, database)
    with pytest.raises(InvalidIri, match="not loaded graphs"):
        await session.add_graph(book(1), [], [bad])
    assert await graphs_in(store, database) == before, "no graph was touched"
    graph, _, _ = await session.get_graph(book(2))
    assert (URIRef(book(2)), TITLE, Literal("victim")) in graph, "the other aggregate is intact"


async def test_a_commit_records_who_and_when_about_the_graph_iri_and_not_the_root(store, database):
    clock = Ticker()
    graph = graph_iri(book(1))
    ada = session_for(store, database, ADA, clock)
    first = await ada.add_graph(book(1), title(book(1), "v1"))
    created = clock.now
    stored = await about_graph(store, database, graph)
    assert (graph, v.CREATED, Literal(created)) in stored, "created is the first commit's time"
    assert (graph, v.CREATOR, URIRef(ADA.id)) in stored, "creator is the first committer"
    assert (graph, v.MODIFIED, None) not in stored, "nothing modified yet"
    graph_read, _, _ = await ada.get_graph(book(1))
    on_root = [p for p in graph_read.predicates(URIRef(book(1))) if p in v.BOOKKEEPING_PREDICATES]
    assert on_root == [], "the root entity carries no tracking"
    await session_for(store, database, BEN, clock).replace_graph(
        book(1), title(book(1), "v2"), first
    )
    stored = await about_graph(store, database, graph)
    assert (graph, v.CREATED, Literal(created)) in stored, "created is kept"
    assert (graph, v.CREATOR, URIRef(ADA.id)) in stored, "creator is kept"
    assert (graph, v.MODIFIED, Literal(clock.now)) in stored, "modified is the second commit's time"
    assert set(stored.objects(graph, v.CONTRIBUTOR)) == {URIRef(BEN.id)}, "the committer is added"


async def test_contributors_accumulate_and_modified_is_replaced(store, database):
    clock = Ticker()
    graph = graph_iri(book(1))
    version = await session_for(store, database, ADA, clock).add_graph(book(1), title(book(1), "1"))
    for principal in (BEN, CY, BEN):
        version = await session_for(store, database, principal, clock).replace_graph(
            book(1), title(book(1), "n"), version
        )
    stored = await about_graph(store, database, graph)
    assert set(stored.objects(graph, v.CONTRIBUTOR)) == {URIRef(BEN.id), URIRef(CY.id)}, "each once"
    assert list(stored.objects(graph, v.MODIFIED)) == [Literal(clock.now)], "one modified, the last"
    assert list(stored.objects(graph, v.CREATOR)) == [URIRef(ADA.id)], "one creator"


async def test_the_registry_entry_is_written_replaced_and_removed_with_the_aggregate(
    store, database
):
    session = session_for(store, database)
    entry = graph_iri(book(1))
    version = await session.add_graph(book(1), title(book(1), "a"))
    after_add = await registry(store, database)
    assert (entry, v.REGISTRY_OWNED_BY, URIRef(book(1))) in after_add, "owner recorded"
    assert (entry, v.REGISTRY_KIND, v.REGISTRY_KIND_IRIS["aggregate"]) in after_add, "kind recorded"
    version = await session.replace_graph(book(1), title(book(1), "b"), version)
    after_replace = await registry(store, database)
    assert isomorphic(after_replace, after_add), "replaced entry equals the first, not duplicated"
    await session.remove(book(1), version)
    assert len(await registry(store, database)) == 0, "the entry goes with the aggregate"


async def test_removing_with_a_stale_version_is_a_conflict_and_keeps_everything(store, database):
    session = session_for(store, database)
    first = await session.add_graph(book(1), title(book(1), "a"))
    await session.replace_graph(book(1), title(book(1), "b"), first)
    with pytest.raises(Conflict):
        await session.remove(book(1), first)
    graph, _, _ = await session.get_graph(book(1))
    assert (URIRef(book(1)), TITLE, Literal("b")) in graph, "the aggregate is still there"
    assert len(await registry(store, database)) == 3, "and so is its entry"


async def test_removing_with_the_current_version_deletes_the_graph_and_removing_a_missing_one_is_not_found(
    store, database
):
    session = session_for(store, database)
    version = await session.add_graph(book(1), title(book(1), "a"))
    await session.remove(book(1), version)
    assert str(graph_iri(book(1))) not in await graphs_in(store, database), "graph gone"
    with pytest.raises(NotFound):
        await session.remove(book(1), version)


async def test_other_aggregates_are_not_touched_by_a_commit(store, database):
    session = session_for(store, database)
    await session.add_graph(book(2), title(book(2), "neighbour"))
    neighbour, _, _ = await session.get_graph(book(2))
    version = await session.add_graph(book(1), title(book(1), "a"))
    await session.replace_graph(book(1), title(book(1), "b"), version)
    await session.remove(book(1), (await session.get_graph(book(1)))[2])
    after, _, _ = await session.get_graph(book(2))
    assert isomorphic(after, neighbour), graph_diff(after, neighbour)
    assert len(await registry(store, database)) == 3, "the neighbour keeps its entry"


async def test_the_tenant_root_lives_in_the_meta_graph_versioned_and_tracked_without_a_registry_entry(
    store, database
):
    session = session_for(store, database)
    meta = meta_graph_iri(TENANT)
    first = await session.add_graph(TENANT, title(TENANT, "Central"))
    names = await graphs_in(store, database)
    assert str(meta) in names, "the root is in the meta graph"
    assert str(graph_iri(TENANT)) not in names, "not in a graph of its own"
    second = await session.replace_graph(TENANT, title(TENANT, "Renamed"), first)
    with pytest.raises(Conflict):
        await session.replace_graph(TENANT, title(TENANT, "Stale"), first)
    stored = await about_graph(store, database, meta)
    assert (meta, v.VERSION, Literal(second)) in stored, "versioned about the meta graph"
    assert (meta, v.CREATOR, URIRef(ADA.id)) in stored, "tracked about the meta graph"
    assert len(await registry(store, database)) == 0, "no registry entry"


async def test_client_sent_bookkeeping_is_not_stored(store, database):
    session = session_for(store, database)
    graph = graph_iri(book(1))
    forged = [
        (graph, v.CREATOR, URIRef("https://example.org/people/mallory")),
        *title(book(1), "a"),
    ]
    await session.add_graph(book(1), forged)
    stored = await about_graph(store, database, graph)
    assert list(stored.objects(graph, v.CREATOR)) == [URIRef(ADA.id)], "the session's creator only"


@pytest.mark.parametrize(
    "call",
    [
        lambda s: s.get_graph(book(1)),
        lambda s: s.add_graph(book(1), title(book(1), "x")),
        lambda s: s.replace_graph(book(1), title(book(1), "x"), "v"),
        lambda s: s.remove(book(1), "v"),
    ],
    ids=["get", "add", "replace", "remove"],
)
async def test_a_dropped_database_is_database_gone(store, call):
    name = f"t-{uuid.uuid4().hex}"
    await store.create_dataset(name)
    session = session_for(store, name)
    await store.drop_dataset(name)
    with pytest.raises(DatabaseGone):
        await call(session)


async def test_open_session_yields_a_working_session(store, database):
    async with open_session(store, database=database, tenant_iri=TENANT, principal=ADA) as session:
        await session.add_graph(book(1), title(book(1), "via the context manager"))
        graph, _, _ = await session.get_graph(book(1))
    assert (URIRef(book(1)), TITLE, Literal("via the context manager")) in graph, "stored"


@pytest.mark.parametrize("call", ["replace", "remove"])
async def test_replace_and_remove_cost_the_size_of_the_graphs_not_their_product(
    store, database, call
):
    """50 aggregate triples and a loaded graph of 2000: the cartesian form took tens of seconds."""
    session = session_for(store, database)
    loaded = loaded_graph_iri(book(1))
    root = URIRef(book(1))
    await store.put_graph(
        database, loaded, graph_of([(root, TITLE, Literal(i)) for i in range(2000)])
    )
    triples = [(root, TITLE, Literal(f"title {i}")) for i in range(50)]
    version = await session.add_graph(book(1), triples, [loaded])
    started = time.perf_counter()
    if call == "replace":
        await session.replace_graph(book(1), triples, version)
    else:
        await session.remove(book(1), version)
    assert time.perf_counter() - started < 2.0
