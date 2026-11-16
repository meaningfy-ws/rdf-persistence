"""The pending mark every recorded commit writes with its activity (aggregate-events 1.2; PD-1, PD-2, PD-14).

The mark is ``<activity> rp:pendingSince ?now``, written in the activity's own ``INSERT`` with the store's
``NOW()``. It is store plumbing: no read of an activity returns it.
"""

import io
from datetime import UTC, datetime

import pytest
from rdflib import RDF, Literal, URIRef

from rdf_persistence.domain.exceptions import Conflict, DatabaseGone, InvalidIri, KeyConflict
from rdf_persistence.domain.generated.rp_provenance import Add
from rdf_persistence.domain.iris import Iris, application_database_name
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.tenant_dump import dump, restore
from rdf_persistence.testkit import FakeStore
from rdf_persistence.testkit.fakes import FAKE_DATABASE
from tests.toy import SETTINGS, template, toy_mapper
from tests.unit.services.test_session_activity import (
    B1,
    B2,
    PROVENANCE,
    RESTORER,
    VIEW,
    Hook,
    activities,
    book,
    opened,
    stored_graph,
)
from tests.unit.services.test_session_activity_adversarial import KEYS, X, overtaken_commit
from tests.unit.services.test_session_unique_keys import book as isbn_book
from tests.unit.services.test_tenant_dump import BASE_STAMPS, TOY_CHAINS
from tests.unit.services.test_tenant_sweep import CREATOR, make_world

PLUMBING = (v.PENDING_SINCE, v.RELAYED_AT, v.PUBLICATION_FAILED)


@pytest.fixture
async def store() -> FakeStore:
    fake = FakeStore()
    await fake.create_dataset(FAKE_DATABASE)
    return fake


async def marks(store: FakeStore, graph: URIRef = PROVENANCE, database: str = FAKE_DATABASE):
    """The ``pendingSince`` values of a provenance graph, by activity."""
    found = await stored_graph(store, graph, database)
    return {str(s): o for s, o in found.subject_objects(v.PENDING_SINCE)}


async def activity_ids(store: FakeStore) -> set[str]:
    return {a.id for a in await activities(store)}


def test_the_plumbing_predicates_are_the_toolkit_namespace_ones():
    prefix = str(v.STARTED_AT).removesuffix("startedAt")
    assert [str(p) for p in PLUMBING] == [
        f"{prefix}pendingSince",
        f"{prefix}relayedAt",
        f"{prefix}publicationFailed",
    ], "the plumbing predicates are the toolkit ones"


async def test_tc01_each_commit_is_pending_once_in_commit_order(store):
    async with opened(store) as session:
        version = await session.add_graph(B1, book(B1))
        version = await session.replace_graph(B1, book(B1), version)
        await session.remove(B1, version)
    found = await activities(store)
    pending = await marks(store)
    assert len(found) == 3, "add, replace, remove"
    assert set(pending) == {a.id for a in found}, "each activity has a mark, no other subject does"
    in_order = [Literal(pending[a.id]).toPython() for a in found]
    assert in_order == sorted(in_order), "pendingSince does not decrease in commit order"
    stored = await stored_graph(store, PROVENANCE)
    assert all(len(list(stored.objects(URIRef(i), v.PENDING_SINCE))) == 1 for i in pending), (
        "one mark each"
    )


async def test_tc02_a_session_that_does_not_record_marks_nothing_and_still_hands_the_activity(
    store,
):
    hook = Hook()
    async with opened(store, record_activities=False, on_commit=hook) as session:
        await session.add_graph(B1, book(B1))
    assert len(await stored_graph(store, PROVENANCE)) == 0, "no activity, no mark"
    assert [type(a) for a, _ in hook.calls] == [Add], "the hook got the activity"


async def test_tc03_a_refused_commit_leaves_no_activity_and_no_mark(store):
    async with opened(store, keys=KEYS) as session:
        v1 = await session.add_graph(B1, isbn_book(B1, "1"))
        await session.replace_graph(B1, isbn_book(B1, "1"), v1)
        before = await stored_graph(store, PROVENANCE)
        with pytest.raises(Conflict):
            await session.replace_graph(B1, isbn_book(B1, "1"), v1)  # stale
        with pytest.raises(InvalidIri):
            await session.add_graph(str(PROVENANCE), [(PROVENANCE, RDF.type, v.ACTIVITY)])
        with pytest.raises(KeyConflict):
            await session.add_graph(B2, isbn_book(B2, "1"))
        after = await stored_graph(store, PROVENANCE)
    assert set(after) == set(before), "no new triple, so no new activity and no new mark"
    assert len(await marks(store)) == 2, "the two commits that applied"


async def test_tc03a_an_overtaken_commit_stores_its_activity_and_its_mark(store):
    await overtaken_commit(store)
    pending = await marks(store)
    assert pending.keys() == await activity_ids(store), "every stored activity is pending"
    ours = [a for a in await activities(store) if len(a.generations or []) == 2]
    assert [a.id in pending for a in ours] == [True], "the two-root commit's mark is stored"


async def test_a_read_of_activities_does_not_return_the_plumbing(store):
    async with opened(store) as session:
        await session.add_graph(B1, book(B1))
        found = await session.activities(v.ADD, RDF.type, v.ADD)
    assert len(found) == 1, "the add is read"
    (graph,) = found.values()
    assert [t for p in PLUMBING for t in graph.triples((None, p, None))] == [], "without its marks"
    assert (None, RDF.type, v.ADD) in graph, "and with the rest"


async def test_a_served_activity_is_pending_like_any_other(store):
    served = toy_mapper().served(Add(id=X))
    async with opened(store) as session:
        await session.add_graph(B1, book(B1), served=served)
    assert set(await marks(store)) == {X}, "the client-chosen id is marked"


async def test_the_mark_is_written_by_the_stores_clock_not_the_sessions(store):
    async with opened(store, clock=lambda: datetime(2001, 1, 1, tzinfo=UTC)) as session:
        await session.add_graph(B1, book(B1))
    (stamped,) = (await marks(store)).values()
    assert Literal(stamped).toPython().year >= 2026, "NOW() of the store, not the session clock"


async def test_tc04_an_application_commit_is_pending_in_the_application_provenance_graph():
    world = await make_world(Iris(SETTINGS), SETTINGS)
    await world.tenancy.ensure_application_database()
    iri = str(world.iris.mint_aggregate(str(world.iris.application), "Template", "templates"))
    async with world.tenancy.application_session(CREATOR) as session:
        await session.add_graph(iri, list(toy_mapper().to_triples(template(iri))))
    graph = world.iris.provenance(str(world.iris.application))
    found = await marks(world.store, graph, application_database_name(SETTINGS.prefix))
    assert len(found) == 1, "the template's activity is pending in the application graph"


async def test_the_system_database_records_nothing_so_marks_nothing():
    world = await make_world(Iris(SETTINGS), SETTINGS)
    asked = await world.store.query(
        world.tenancy.system_database, f"ASK {{ GRAPH ?g {{ ?s <{v.PENDING_SINCE}> ?o }} }}"
    )
    assert not asked.askAnswer, "no mark in the system database"


async def test_tc05_a_restore_drops_every_mark_and_keeps_the_activities():
    world = await make_world(Iris(SETTINGS), SETTINGS, BASE_STAMPS)
    iri = str(world.iris.mint_aggregate(world.tenant, "Book", "books"))
    async with world.session() as session:
        await session.add_graph(iri, book(iri))
    provenance = world.iris.provenance(world.tenant)
    original = await activities(world.store, provenance, world.database)
    relayed, pending = original[0], original[-1]
    assert relayed.id != pending.id, "one to relay, one left pending"
    await world.store.update(
        world.database,
        f"INSERT DATA {{ GRAPH <{provenance}> {{ <{relayed.id}> <{v.RELAYED_AT}> "
        f'"2026-11-15T10:00:00Z" . <{pending.id}> <{v.PUBLICATION_FAILED}> "x" }} }}',
    )
    out = io.BytesIO()
    await dump(world.tenancy, world.store, world.files, world.iris, VIEW, world.tenant, out)
    summary = await restore(
        world.tenancy,
        world.iris,
        VIEW,
        io.BytesIO(out.getvalue()),
        RESTORER,
        max_bytes=1 << 30,
        chains=TOY_CHAINS,
    )
    record, _ = await world.tenancy.get(summary.id)
    restored = world.iris.provenance(summary.id)
    found = await activities(world.store, restored, record.database_name)
    assert [a.id for a in found] == [a.id for a in original], "both activities are restored"
    stored = await stored_graph(world.store, restored, record.database_name)
    assert [t for p in PLUMBING for t in stored.triples((None, p, None))] == [], "no plumbing"


async def three_commits(session) -> None:
    version = await session.add_graph(B1, book(B1))
    version = await session.replace_graph(B1, book(B1), version)
    await session.remove(B1, version)


async def test_tc43_pending_activities_are_the_unrelayed_ones_in_pending_since_order(store):
    async with opened(store) as session:
        await three_commits(session)
        first, middle, last = (a.id for a in await activities(store))
        await session.mark_relayed(middle)
        pending = await session.pending_activities()
    assert [iri for iri, _ in pending] == [first, last], "two, the relayed one gone"
    assert [t for _, g in pending for p in PLUMBING for t in g.triples((None, p, None))] == [], (
        "without the plumbing predicates"
    )
    assert all((URIRef(i), RDF.type, v.ACTIVITY) in g for i, g in pending), "with the activity"


async def test_pending_activities_are_ordered_by_the_mark_then_by_iri(store):
    async with opened(store) as session:
        await three_commits(session)
        a, b, c = sorted(a.id for a in await activities(store))
        marks_by_hand = {
            c: "2026-01-01T00:00:00Z",
            b: "2026-01-02T00:00:00Z",
            a: "2026-01-02T00:00:00Z",
        }
        for iri, when in marks_by_hand.items():
            await store.update(
                FAKE_DATABASE,
                f"DELETE WHERE {{ GRAPH <{PROVENANCE}> {{ <{iri}> <{v.PENDING_SINCE}> ?o }} }};"
                f'INSERT DATA {{ GRAPH <{PROVENANCE}> {{ <{iri}> <{v.PENDING_SINCE}> "{when}"^^<http://www.w3.org/2001/XMLSchema#dateTime> }} }}',
            )
        assert [i for i, _ in await session.pending_activities()] == [c, a, b], "mark, then IRI"


async def test_a_mark_that_is_not_a_zoned_time_is_ordered_after_every_valid_one(store):
    async with opened(store) as session:
        await three_commits(session)
        a, b, c = sorted(a.id for a in await activities(store))
        marks_by_hand = {  # a is the bad one and has the smallest IRI
            a: '"yesterday"',
            b: '"2026-01-02T00:00:00Z"^^<http://www.w3.org/2001/XMLSchema#dateTime>',
            c: '"2026-01-01T00:00:00"^^<http://www.w3.org/2001/XMLSchema#dateTime>',
        }
        for iri, mark in marks_by_hand.items():
            await store.update(
                FAKE_DATABASE,
                f"DELETE WHERE {{ GRAPH <{PROVENANCE}> {{ <{iri}> <{v.PENDING_SINCE}> ?o }} }};"
                f"INSERT DATA {{ GRAPH <{PROVENANCE}> {{ <{iri}> <{v.PENDING_SINCE}> {mark} }} }}",
            )
        assert [i for i, _ in await session.pending_activities()] == [b, a, c], "valid, then bad"


async def test_pending_activities_of_a_database_that_is_gone_raise_database_gone(store):
    async with opened(store) as session:
        await store.drop_dataset(FAKE_DATABASE)
        with pytest.raises(DatabaseGone):
            await session.pending_activities()
        with pytest.raises(DatabaseGone):
            await session.mark_relayed(X)


async def test_tc44_marking_relayed_twice_relays_once_and_marking_failed_is_the_same(store):
    async with opened(store) as session:
        await three_commits(session)
        a, b, _ = (a.id for a in await activities(store))
        await session.mark_relayed(a)
        await session.mark_relayed(a)
        await session.mark_failed(b)
        left = {i for i, _ in await session.pending_activities()}
    stored = await stored_graph(store, PROVENANCE)
    assert len(list(stored.objects(URIRef(a), v.RELAYED_AT))) == 1, "a is relayed once"
    assert (URIRef(a), v.PENDING_SINCE, None) not in stored, "and not pending"
    assert len(list(stored.objects(URIRef(b), v.PUBLICATION_FAILED))) == 1, "b is failed"
    assert (URIRef(b), v.RELAYED_AT, None) not in stored, "not relayed"
    assert {a, b}.isdisjoint(left), "neither is pending"


async def test_a_mark_of_an_activity_that_is_not_pending_adds_nothing(store):
    async with opened(store) as session:
        await session.add_graph(B1, book(B1))
        await session.mark_failed(X)  # unknown
        (only,) = (a.id for a in await activities(store))
        await session.mark_failed(only)
        await session.mark_relayed(only)  # failed already: no longer pending
    stored = await stored_graph(store, PROVENANCE)
    assert (None, v.RELAYED_AT, None) not in stored, "a failed activity is not relayed after"
    assert (None, v.PENDING_SINCE, None) not in stored, "the unmarked activity adds no pending mark"
