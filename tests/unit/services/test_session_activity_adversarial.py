"""Adversarial tests of the activity every commit records (message-bus PD-6 to PD-10, Error matrix).

Each test names the design.md item it holds the code to. ``B1`` to ``B3`` are books of the toy tenant,
``X`` and ``Y`` activity IRIs, "other" a second session on the same fake store. A test marked
``xfail`` is a finding: the code does not do what the design says.
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from rdflib import RDF, BNode, Literal, URIRef

from rdf_persistence.domain.exceptions import (
    CommitTooLarge,
    Conflict,
    InvalidIri,
    KeyConflict,
    NotFound,
    PersistenceError,
)
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.generated.rp_files import RdfFormat
from rdf_persistence.domain.generated.rp_provenance import (
    Activity,
    Add,
    Generation,
    Remove,
    Replace,
)
from rdf_persistence.domain.sparql import SparqlError
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.iris import DEFAULT_IRIS, Iris
from rdf_persistence.services.listing import Listings
from rdf_persistence.services.mapper import UnitOfWork
from rdf_persistence.services.provenance import Served
from rdf_persistence.services.schema import load_schema
from rdf_persistence.services.schema_structure import aggregate_keys
from rdf_persistence.services.session import Session
from rdf_persistence.testkit import FakeStore, fake_session
from rdf_persistence.testkit.fakes import FAKE_DATABASE
from tests.logs import attributes
from tests.toy import ADA, BOB, SETTINGS, TENANT, TOY_SCHEMA, Book, dune, toy_mapper
from tests.unit.services.test_session_activity import (
    B1,
    B2,
    B3,
    BOOK_CLASS,
    PROVENANCE,
    SHELF_CLASS,
    Hook,
    X,
    activities,
    book,
    events,
    only_activity,
    opened,
    stored_graph,
    ticking,
)
from tests.unit.services.test_session_unique_keys import ISBN
from tests.unit.services.test_session_unique_keys import book as isbn_book
from tests.unit.services.test_tenant_sweep import make_world

Y = "urn:uuid:5c0f5f4a-8d0a-4c1e-9d55-0e5bb1b6c002"
EVE = "https://example.org/people/eve"
KEYS = aggregate_keys(load_schema(TOY_SCHEMA))
ALL_QUADS = "SELECT ?g ?s ?p ?o WHERE { GRAPH ?g { ?s ?p ?o } }"
PROV = "http://www.w3.org/ns/prov#"


def served(command: Activity | None = None) -> Served:
    return toy_mapper().served(command or Replace(id=X))


async def quads(store: FakeStore) -> frozenset[tuple[str, ...]]:
    """Every statement of the dataset, graph first; the whole state, to compare before and after."""
    rows = await store.query(FAKE_DATABASE, ALL_QUADS)
    return frozenset(tuple(map(str, row)) for row in rows)  # type: ignore[union-attr]


@pytest.fixture
async def store() -> FakeStore:
    fake = FakeStore()
    await fake.create_dataset(FAKE_DATABASE)
    return fake


@pytest.fixture
async def session(store) -> AsyncIterator[Session]:
    async with opened(store) as s:
        yield s


@pytest.fixture
async def other(store) -> AsyncIterator[Session]:
    async with opened(store) as s:
        yield s


# -- atomicity: an activity never without its commit, a commit never without its activity ----------


async def test_a_store_error_mid_request_records_nothing_and_the_command_is_spent(store):
    # Error matrix: a guard fails / the request fails: no activity, no publish.
    hook = Hook()
    async with opened(store, on_commit=hook) as session:
        v1 = await session.add_graph(B1, book(B1))
        before = await quads(store)
        store.on("update", PersistenceError("the store is down"))
        command = served()
        with pytest.raises(PersistenceError):
            async with session.transaction(served=command) as transaction:
                await transaction.replace_graph(B1, book(B1), v1)
        assert await quads(store) == before, "the store holds exactly what it held"
        assert len(hook.calls) == 1, "the hook ran for the add only"
        with pytest.raises(RuntimeError, match=X):  # it reached the store, so it is spent (D-10 b)
            async with session.transaction(served=command) as transaction:
                await transaction.replace_graph(B1, book(B1), v1)
        async with session.transaction(served=served()) as transaction:
            await transaction.replace_graph(B1, book(B1), v1)
        assert [a.id for a in await activities(store)].count(X) == 1, "a new command records once"


async def test_an_exception_in_the_block_records_nothing_and_leaves_the_command_unspent(
    store, session
):
    # D-10 b: a served command is claimed when its transaction sends its request; none was sent.
    command = served()
    with pytest.raises(ZeroDivisionError):
        async with session.transaction(served=command) as transaction:
            await transaction.add_graph(B1, book(B1))
            1 / 0  # noqa: B018
    assert store.sent("update") == [], "nothing was sent"
    assert await activities(store) == [], "nothing was recorded"
    async with session.transaction(served=command) as transaction:
        await transaction.add_graph(B1, book(B1))
    assert [a.id for a in await activities(store)] == [X], "the command still serves one commit"


async def test_a_failed_guard_beside_a_real_change_records_no_activity(store, session):
    # PD-6: the insert matches only while the commit marker is there.
    before = await quads(store)
    with pytest.raises(Conflict):
        async with session.transaction(served=served(Add(id=X))) as transaction:
            await transaction.add_graph(B2, book(B2))
            transaction._require_present(B1)  # B1 was never stored
    assert await quads(store) == before, "no aggregate, no activity"


async def test_a_key_conflict_of_a_served_commit_names_the_key_and_records_nothing(store):
    async with opened(store, keys=KEYS) as session:
        await session.add_graph(B1, isbn_book(B1, "1"))
        before = await quads(store)
        with pytest.raises(KeyConflict) as refused:
            async with session.transaction(served=served(Add(id=X))) as transaction:
                await transaction.add_graph(B2, isbn_book(B2, "1"))
        assert X not in str(refused.value), "the activity is not blamed"
        assert await quads(store) == before, "nothing changed, nothing recorded"
        assert str(ISBN) not in {t[1] for t in await quads(store) if t[0] == str(B2)}, "no B2"


async def test_commit_too_large_sends_nothing_and_records_nothing(store, session):
    unit = UnitOfWork(session, toy_mapper(), max_roots=2)
    for iri in (B1, B2, B3):
        unit.add(dune(iri))
    with pytest.raises(CommitTooLarge):
        await unit.commit()
    assert store.sent("update") == [], "no request"
    assert await activities(store) == [], "no activity"


async def test_batches_record_one_activity_per_batch_and_a_failed_batch_none(store, session):
    # PD-8: a batch is its own transaction. After a failure, the stored roots and the records agree.
    unit = UnitOfWork(session, toy_mapper(), max_roots=2)
    for iri in (B1, B2, B3):
        unit.add(dune(iri))
    store.on("update", PersistenceError("second batch fails"), after=1)
    with pytest.raises(PersistenceError):
        await unit.commit(batches=True)
    found = await activities(store)
    assert [type(a) for a in found] == [Add], "the first batch only"
    assert sorted(g.entity for g in found[0].generations) == [B1, B2], "its two roots"
    with pytest.raises(NotFound):
        await session.get_graph(B3)


async def test_a_served_command_with_no_change_sends_nothing_and_records_nothing(store, session):
    hook = Hook()
    async with opened(store, on_commit=hook) as hooked, hooked.transaction(served=served()):
        pass
    assert store.sent("update") == [], "no request, no hook call"
    assert not hook.calls, "no request, no hook call"
    assert await activities(store) == [], "no record of a command that changed nothing"


# -- concurrency -------------------------------------------------------------------------------


async def test_a_remove_of_a_root_another_writer_removed_records_and_publishes_nothing(store):
    # Error matrix, "removes-only success path": the guard fails, so nothing is written; the
    # confirming ASK (the graph is absent) cannot tell, so the hook must not hear of a Remove
    # that is not in the provenance graph.
    hook = Hook()
    async with opened(store, on_commit=hook) as session, opened(store) as other:
        v1 = await session.add_graph(B1, book(B1))
        hook.calls.clear()
        async with session.transaction() as transaction:
            await transaction.remove(B1, v1)
            await other.remove(B1, v1)  # lands before the commit's request
        recorded = [a.id for a in await activities(store) if type(a) is Remove]
        assert len(recorded) == 1, "one Remove is stored: the other writer's"
        assert [a.id for a, _ in hook.calls if type(a) is Remove] == [], (
            "the hook is not given a Remove that was not stored"
        )


async def test_an_overwritten_commit_is_recorded_not_published_and_conflicts(store):
    # Error matrix: applied, but the confirming ASK is false -> recorded and not published.
    hook = Hook()
    async with opened(store, on_commit=hook) as session, opened(store) as other:
        v1 = await session.add_graph(B1, book(B1))
        hook.calls.clear()

        async def overwrite() -> None:
            store.after_update = None
            _, _, current = await other.get_graph(B1)
            await other.replace_graph(B1, book(B1), current)

        store.after_update = overwrite
        with pytest.raises(Conflict):
            await session.replace_graph(B1, book(B1), v1)
        replaces = [a for a in await activities(store) if type(a) is Replace]
        assert len(replaces) == 2, "the false conflict's replace and the other writer's"
        assert hook.calls == [], "nothing was published"


async def overtaken_commit(store, **options):
    """A commit of two replaces; another writer changes one of the two graphs before the ASK, so the
    commit applied and the call returns (PD-4)."""
    async with opened(store, **options) as session, opened(store) as other:
        v1 = await session.add_graph(B1, book(B1))
        v2 = await session.add_graph(B2, book(B2))

        async def overtake() -> None:
            store.after_update = None
            _, _, current = await other.get_graph(B1)
            await other.replace_graph(B1, book(B1), current)

        store.after_update = overtake
        async with session.transaction() as transaction:
            await transaction.replace_graph(B1, book(B1), v1)
            await transaction.replace_graph(B2, book(B2), v2)


async def test_an_overtaken_commit_that_applied_is_published_with_the_activity_it_recorded(store):
    # D-6 a: publish exactly what is recorded.
    hook = Hook()
    await overtaken_commit(store, on_commit=hook)
    ours = [a for a, _ in hook.calls if type(a) is Replace and len(a.generations) == 2]
    assert len(ours) == 1, "the two-root commit was published once"
    assert ours[0].id in [a.id for a in await activities(store)], "and it is stored"


async def test_an_overtaken_commit_of_a_session_that_does_not_record_is_not_published(
    store, caplog
):
    # D-6 a: nothing is stored to publish, so the hook is not called and the warning names why.
    hook = Hook()
    await overtaken_commit(store, record_activities=False, on_commit=hook)
    assert [a for a, _ in hook.calls if a.generations and len(a.generations) == 2] == [], (
        "not handed to the hook"
    )
    [record] = caplog.records  # TC-13b
    assert record.levelno == logging.WARNING, "and the log says so, as a warning"
    assert record.getMessage() == "an activity was applied but overtaken; not handed to on_commit"
    assert attributes(record)["rp.step"] == "commit-overtaken", "at which step"
    assert attributes(record)["rp.activity.id"], "naming the activity"


async def test_a_served_commit_overwritten_before_the_ask_still_names_its_graph_or_activity(store):
    # PD-8: the false conflict of a served commit names a reason that is true.
    async with opened(store) as session, opened(store) as other:
        v1 = await session.add_graph(B1, book(B1))

        async def overwrite() -> None:
            store.after_update = None
            _, _, current = await other.get_graph(B1)
            await other.replace_graph(B1, book(B1), current)

        store.after_update = overwrite
        with pytest.raises(Conflict) as refused:
            await session.replace_graph(B1, book(B1), v1, served=served())
        assert B1 in str(refused.value) or X in str(refused.value), "names the book or the activity"
        assert X in [a.id for a in await activities(store)], "and the record exists"


async def test_a_commit_serving_an_id_taken_while_the_first_request_ran_writes_nothing(store):
    # PD-8, race: between the first commit's update and its ASK, a second commit serves the same id.
    async with opened(store) as session, opened(store) as other:
        v1 = await session.add_graph(B1, book(B1))
        raced: list[Exception] = []

        async def second() -> None:
            store.after_update = None
            try:
                await other.add_graph(B2, book(B2), served=served(Add(id=X)))
            except Exception as error:  # noqa: BLE001 -- the race outcome is whichever error comes back
                raced.append(error)

        store.after_update = second
        await session.replace_graph(B1, book(B1), v1, served=served())
        assert len(raced) == 1, "the second is refused"
        assert isinstance(raced[0], Conflict), "the second is refused"
        assert X in str(raced[0]), "naming the activity"
        with pytest.raises(NotFound):
            await other.get_graph(B2)
        assert [a.id for a in await activities(store)].count(X) == 1, "one record of X"


async def test_two_served_commits_with_one_id_at_once_let_exactly_one_win(store):
    async with opened(store) as one, opened(store) as two:
        results = await asyncio.gather(
            one.add_graph(B1, book(B1), served=served(Add(id=X))),
            two.add_graph(B2, book(B2), served=served(Add(id=X))),
            return_exceptions=True,
        )
        assert sum(isinstance(r, Conflict) for r in results) == 1, "one conflict"
        assert sum(isinstance(r, str) for r in results) == 1, "one commit"
        winners = {g.entity for a in await activities(store) for g in a.generations or []}
        assert len(winners) == 1, "one book recorded, and only one stored"
        stored = [iri for iri in (B1, B2) if iri in winners]
        assert len(stored) == 1, "the stored book is the recorded one"


# -- the id guard and its diagnosis ----------------------------------------------------------


async def test_a_served_commit_of_a_taken_id_leaves_the_whole_dataset_as_it_was(store, session):
    # PD-8: nothing at all (no aggregate graph, no registry entry, no key).
    async with opened(store, keys=KEYS) as keyed:
        await keyed.add_graph(B1, isbn_book(B1, "1"), served=served(Add(id=X)))
        before = await quads(store)
        with pytest.raises(Conflict, match=X):
            await keyed.add_graph(B2, isbn_book(B2, "2"), served=served(Add(id=X)))
        assert await quads(store) == before, "not a statement more or less"


async def test_a_taken_id_and_a_stale_version_report_the_stale_version(store, session):
    v1 = await session.add_graph(B1, book(B1))
    await session.replace_graph(B1, book(B1), v1, served=served())
    with pytest.raises(Conflict) as refused:
        await session.replace_graph(B1, book(B1), v1, served=served())
    assert B1 in str(refused.value), "the existing reason first (TC-40c)"
    assert X not in str(refused.value), "the id, which is also taken, is not blamed"


async def test_the_id_guard_does_not_mix_with_the_guards_of_many_changes_and_keys(store):
    async with opened(store, keys=KEYS) as session:
        async with session.transaction(served=served(Add(id=X))) as transaction:
            for n, iri in enumerate((B1, B2, B3), 1):
                await transaction.add_graph(iri, isbn_book(iri, str(n)))
        found = await only_activity(store)
        assert found.id == X, "the command's IRI"
        assert sorted(g.entity for g in found.generations) == [B1, B2, B3], "three generations"


@pytest.mark.parametrize(
    "hostile",
    [
        "urn:uuid:a> } ; DROP ALL ; <b",
        "urn:uuid:a b",
        "urn:uuid:a\n> ; DROP ALL ; <b",
        "urn:uuid:<x>",
    ],
)
async def test_an_id_with_text_that_could_change_the_request_sends_nothing(store, session, hostile):
    # PD-8 / D-3: no unchecked text reaches an IRI.
    before = await quads(store)
    sent = len(store.sent("update"))
    with pytest.raises((ValueError, SparqlError)):
        command = Served(Add(id=hostile), [], [v.ADD, v.ACTIVITY])
        await session.add_graph(B1, book(B1), served=command)
    assert len(store.sent("update")) == sent, "no request left the session"
    assert await quads(store) == before, "nothing stored"


async def test_ids_that_are_not_a_urn_uuid_are_refused_before_a_transaction_opens(store, session):
    for bad in (B1, TENANT, str(PROVENANCE), "URN:UUID:" + X[9:], "", "urn:uuid"):
        with pytest.raises(ValueError, match="urn:uuid"):
            Served(Add(id=bad), [], [v.ADD])


# -- content ----------------------------------------------------------------------------------


async def test_a_transaction_of_many_roots_records_each_generation_at_its_stored_version(
    store, session
):
    async with session.transaction() as transaction:
        versions = {iri: await transaction.add_graph(iri, book(iri)) for iri in (B1, B2, B3)}
    found = await only_activity(store)
    assert type(found) is Add, "all adds"
    assert {e[0]: e[2] for e in events(found.generations)} == versions, "each at its version"
    for iri, version in versions.items():
        assert (await session.get_graph(iri))[2] == version, f"{iri} stored at that version"


async def test_every_part_is_stamped_with_the_end_of_the_activity(store, session):
    v1 = await session.add_graph(B1, book(B1))
    await session.replace_graph(B1, book(B1), v1)
    for found in await activities(store):
        parts = [*(found.generations or []), *(found.invalidations or [])]
        assert {p.at_time for p in parts} == {found.ended_at_time}, "prov:atTime is the end"
        assert {p.activity for p in parts} == {found.id}, "and each names its activity"


async def test_the_parts_of_two_commits_never_share_an_iri_even_from_one_blank_label(
    store, session
):
    # PD-3: parts are skolemised under the provenance graph, fresh at every commit.
    same = BNode("same")
    forged = (URIRef(X), URIRef("https://example.org/x/note"), same)
    note = (same, URIRef("https://example.org/x/text"), Literal("t"))
    await session.add_graph(B1, book(B1), served=Served(Add(id=X), [forged, note], [v.ADD]))
    await session.add_graph(
        B2,
        book(B2),
        served=Served(Add(id=Y), [(URIRef(Y), *forged[1:]), (same, *note[1:])], [v.ADD]),
    )
    stored = await stored_graph(store, PROVENANCE)
    first = {*stored.objects(URIRef(X), forged[1])}
    second = {*stored.objects(URIRef(Y), forged[1])}
    assert len(first) == 1, "two different parts"
    assert len(second) == 1, "two different parts"
    assert first != second, "two different parts"
    assert all(str(n).startswith(f"{PROVENANCE}/") for n in first | second), "under the graph"


async def test_a_loaded_graph_is_not_an_entity_of_the_commit_that_registers_it(store, session):
    loaded = await session.load_graph(
        B1,
        b'<https://example.org/b> <http://purl.org/dc/terms/title> "x" .',
        rdf_format=RdfFormat.TURTLE,
    )
    await session.add_graph(B1, book(B1), loaded_graphs=[loaded])
    found = await only_activity(store)
    assert [g.entity for g in found.generations] == [B1], "the root only, not its loaded graph"


async def test_the_start_of_an_activity_is_not_after_its_end_when_the_clock_goes_back(store):
    # PD-7: start is the marker time, end the clock at commit; a clock that goes back inverts them.
    times = iter(
        [datetime(2026, 11, 14, 12, 0, tzinfo=UTC) - timedelta(minutes=n) for n in range(50)]
    )
    async with opened(store, clock=lambda: next(times)) as session:
        await session.add_graph(B1, book(B1))
    found = await only_activity(store)
    assert found.started_at_time <= found.ended_at_time, "start <= end"


async def test_a_replace_of_a_root_with_several_types_invalidates_the_first_sorted(store, session):
    triples = [(URIRef(B1), RDF.type, URIRef(c)) for c in (SHELF_CLASS, BOOK_CLASS)]
    v1 = await session.add_graph(B1, triples)
    await session.replace_graph(B1, [(URIRef(B1), RDF.type, URIRef(SHELF_CLASS))], v1)
    replace = (await activities(store))[-1]
    assert events(replace.invalidations) == [(B1, BOOK_CLASS, v1)], "the old first type"
    assert [e[1] for e in events(replace.generations)] == [SHELF_CLASS], "the new type"


# -- forgery and unchecked input ----------------------------------------------------------------


async def test_the_session_overwrites_the_slots_it_fills_on_a_command_that_carries_them(
    store, session
):
    forged = Generation(
        activity=X,
        at_time=datetime(2000, 1, 1, tzinfo=UTC),
        entity=B3,
        entity_version="forged",
    )
    command = Add(
        id=X,
        started_at_time=datetime(2000, 1, 1, tzinfo=UTC),
        ended_at_time=datetime(2000, 1, 2, tzinfo=UTC),
        was_associated_with=[EVE],
        generations=[forged],
    )
    await session.add_graph(B1, book(B1), served=toy_mapper().served(command))
    found = await only_activity(store)
    assert found.was_associated_with == [ADA], "the session's principal, not EVE"
    assert [g.entity for g in found.generations] == [B1], "the session's parts, not the forged one"
    assert found.started_at_time.year == 2026, "its times"
    assert found.ended_at_time.year == 2026, "its times"


async def test_a_served_with_statements_about_another_subject_writes_none_of_them(store, session):
    # PD-3 / PD-8: a Served is the command's own statements; the activity and its parts are the
    # only subjects of the provenance graph.
    await session.add_graph(B1, book(B1))
    old = (await only_activity(store)).id
    forged = [
        (URIRef(old), v.ASSOCIATED_WITH, URIRef(EVE)),
        (URIRef(B1), URIRef("http://purl.org/dc/terms/title"), Literal("hijacked")),
        (PROVENANCE, URIRef("https://example.org/x/says"), Literal("hijacked")),
    ]
    with pytest.raises(ValueError, match="subject"):  # D-5 b: refused where it is built
        await session.add_graph(B2, book(B2), served=Served(Add(id=X), forged, [v.ADD, v.ACTIVITY]))
    stored = await stored_graph(store, PROVENANCE)
    assert (URIRef(old), v.ASSOCIATED_WITH, URIRef(EVE)) not in stored, (
        "the old record is as it was"
    )
    subjects = {s for s in stored.subjects() if not str(s).startswith(f"{PROVENANCE}/")}
    assert subjects == {URIRef(old)}, (
        "the commit is refused: no new subject, the old one is as it was"
    )


async def test_a_served_with_a_session_filled_statement_cannot_add_a_second_principal(
    store, session
):
    # PD-8: the session fills the principal, the times and the parts; only Mapper.served strips them.
    forged = [(URIRef(X), v.ASSOCIATED_WITH, URIRef(EVE))]
    with pytest.raises(ValueError, match="not its own"):  # D-5 b: refused where it is built
        await session.add_graph(B1, book(B1), served=Served(Add(id=X), forged, [v.ADD, v.ACTIVITY]))
    await session.add_graph(B1, book(B1), served=Served(Add(id=X), [], [v.ADD, v.ACTIVITY]))
    stored = await stored_graph(store, PROVENANCE)
    assert {*stored.objects(URIRef(X), v.ASSOCIATED_WITH)} == {URIRef(ADA)}, "ADA only"


async def test_a_served_with_odd_types_still_records_the_standard_class_it_names(store, session):
    # Served.types is unchecked text the caller names; pin what lands, so a change is seen.
    types = [URIRef("https://example.org/x/Odd"), v.ACTIVITY]
    await session.add_graph(B1, book(B1), served=Served(Add(id=X), [], types))
    stored = await stored_graph(store, PROVENANCE)
    assert {*stored.objects(URIRef(X), RDF.type)} == set(types), "exactly the types named"


@pytest.mark.slow
async def test_a_huge_served_triple_list_commits_whole_or_not_at_all(store, session):
    triples = [(URIRef(X), URIRef("https://example.org/x/n"), Literal(n)) for n in range(1500)]
    await session.add_graph(B1, book(B1), served=Served(Add(id=X), triples, [v.ADD, v.ACTIVITY]))
    stored = await stored_graph(store, PROVENANCE)
    assert len([*stored.objects(URIRef(X), URIRef("https://example.org/x/n"))]) == 1500, "all kept"


async def test_a_command_class_the_schema_does_not_know_is_refused_as_not_an_activity():
    # Mapper.served: "Raises ValueError: command is no activity".
    class Stranger(Activity):
        pass

    with pytest.raises(ValueError):
        toy_mapper().served(Stranger(id=X))


async def test_a_command_whose_id_is_an_aggregate_iri_is_refused_by_the_mapper():
    with pytest.raises(ValueError, match="urn:uuid"):
        toy_mapper().served(Add(id=B1))


async def test_a_served_whose_id_is_urn_uuid_but_no_uuid_is_refused():
    with pytest.raises(ValueError, match="uuid"):
        Served(Add(id="urn:uuid:not-a-uuid"), [], [v.ADD, v.ACTIVITY])


async def test_a_served_given_to_a_session_that_neither_records_nor_has_a_hook_is_refused(store):
    async with opened(store, record_activities=False) as session:
        with pytest.raises(ValueError, match="records activities"):
            async with session.transaction(served=served()):
                pass
    assert store.sent("update") == [], "nothing was sent"


def test_the_types_of_an_activity_class_come_from_the_metamodel():
    assert v.activity_types("Add") == [v.ADD, v.ACTIVITY], "own class first, then the ancestor"
    assert v.activity_types("Activity") == [v.ACTIVITY], "the plain one has itself only"
    with pytest.raises(ValueError, match="Principal"):
        v.activity_types("Principal")


async def test_a_served_is_spent_by_a_refused_commit_and_a_retry_needs_a_new_one(store, session):
    v1 = await session.add_graph(B1, book(B1))
    await session.replace_graph(B1, book(B1), v1)
    command = served()
    with pytest.raises(Conflict):
        await session.replace_graph(B1, book(B1), v1, served=command)
    with pytest.raises(RuntimeError, match=X):
        await session.replace_graph(B1, book(B1), (await session.get_graph(B1))[2], served=command)
    await session.replace_graph(B1, book(B1), (await session.get_graph(B1))[2], served=served())
    assert [a.id for a in await activities(store)].count(X) == 1, "the retry with a new one stands"


# -- the hook -----------------------------------------------------------------------------------


async def test_a_hook_that_is_cancelled_lets_the_cancellation_through_and_the_commit_stands(store):
    async def cancelled(activity, session) -> None:
        raise asyncio.CancelledError

    async with opened(store, on_commit=cancelled) as session:
        with pytest.raises(asyncio.CancelledError):
            await session.add_graph(B1, book(B1))
        assert len(await activities(store)) == 1, "the activity was stored"
        assert (await session.get_graph(B1))[2], "and so was the book"


async def test_a_hook_that_commits_on_its_own_session_is_recorded_and_published_once_each(store):
    calls: list[str] = []

    async def hook(activity: Activity, session: Session) -> None:
        calls.append(activity.generations[0].entity)
        if len(calls) == 1:
            await session.add_graph(B2, book(B2))

    async with opened(store, on_commit=hook) as session:
        await session.add_graph(B1, book(B1))
    assert calls == [B2, B1] or calls == [B1, B2], "both commits were published"
    assert sorted(g.entity for a in await activities(store) for g in a.generations) == [B1, B2], (
        "and both were recorded"
    )


async def test_a_hook_that_changes_its_activity_changes_neither_the_record_nor_the_command(store):
    seen: list[Activity] = []

    async def meddling(activity: Activity, session: Session) -> None:
        seen.append(activity)
        activity.generations.clear()
        activity.was_associated_with.append(EVE)

    command = served(Add(id=X))
    async with opened(store, on_commit=meddling) as session:
        await session.add_graph(B1, book(B1), served=command)
    found = await only_activity(store)
    assert [g.entity for g in found.generations] == [B1], "the stored generations are whole"
    assert found.was_associated_with == [ADA], "and the stored principal is ADA only"
    assert command.activity.generations is None, "the command's own model has none"
    assert command.activity.was_associated_with is None, "and no principal"


async def test_a_slow_hook_holds_up_its_own_commit_and_no_other_writer(store):
    entered, release = asyncio.Event(), asyncio.Event()

    async def slow(activity: Activity, session: Session) -> None:
        entered.set()
        await release.wait()

    async with opened(store, on_commit=slow) as slowed, opened(store) as other:
        first = asyncio.create_task(slowed.add_graph(B1, book(B1)))
        await entered.wait()
        await other.add_graph(B2, book(B2))
        assert not first.done(), "the commit waits for its hook"
        release.set()
        await first
    assert len(await activities(store)) == 2, "both commits recorded"


async def test_a_hook_failure_is_logged_with_the_activity_iri_and_the_next_commit_is_published(
    store, caplog
):
    calls: list[str] = []

    async def flaky(activity: Activity, session: Session) -> None:
        calls.append(activity.id)
        if len(calls) == 1:
            raise RuntimeError("observer broke")

    async with opened(store, on_commit=flaky) as session:
        with caplog.at_level(logging.ERROR):
            await session.add_graph(B1, book(B1), served=served(Add(id=X)))
        await session.add_graph(B2, book(B2))
    [record] = caplog.records
    assert attributes(record)["rp.activity.id"] == X, "the log names the activity"
    assert len(calls) == 2, "the second commit still reached the hook"


# -- isolation ----------------------------------------------------------------------------------


async def test_the_provenance_graph_is_in_no_listing_no_referrer_no_head_no_key_scan(store):
    async with opened(store, listings=Listings(load_schema(TOY_SCHEMA))) as session:
        await _isolation(store, session)


async def _isolation(store: FakeStore, session: Session) -> None:
    v1 = await session.add_graph(B1, book(B1))
    await session.replace_graph(B1, book(B1), v1)
    await session.remove(B1, (await session.get_graph(B1))[2])
    await session.add_graph(B2, book(B2))
    prov = str(PROVENANCE)
    assert await session.heads([prov]) == [], "not a head"
    assert await session.referrer_rows(B1) == [], "the activities naming B1 are not referrers"
    assert prov not in await session.graphs_with(RDF.type), "not among graphs with a type"
    assert await session.graphs_with(RDF.type, v.ACTIVITY) == {}, "no aggregate is an activity"
    assert await session.named_file_keys(["a", "b"]) == set(), "no file key"
    assert await session.key_duplicates() == [], "no key duplicates"
    assert B1 not in await session.find(Book), "the removed book is not found"


@pytest.mark.parametrize("graph", [str(PROVENANCE), f"{PROVENANCE}/.well-known/genid/1"])
async def test_the_provenance_graph_cannot_be_written_as_an_aggregate(store, session, graph):
    await session.add_graph(B1, book(B1))
    before = await quads(store)
    with pytest.raises(InvalidIri):
        await session.add_graph(graph, [(URIRef(graph), RDF.type, v.ACTIVITY)])
    assert await quads(store) == before, "nothing changed"


async def test_a_sweep_that_removes_everything_old_keeps_the_provenance_graph():
    world = await make_world(Iris(SETTINGS), SETTINGS)
    provenance = world.iris.provenance(world.tenant)
    await world.commit(f"{world.tenant}/books/00000000-0000-0000-0000-000000000009")
    before = await activities(world.store, provenance, world.database)
    await world.sweep(remove=True, remove_blobs=True, older_than=timedelta(0))
    assert await activities(world.store, provenance, world.database) == before, "all kept"
    assert len(before) >= 2, "there was something to keep"


async def test_a_session_that_does_not_record_still_hands_its_hook_the_activity(store):
    # PD-9 / PD-10: the hook is independent of the record.
    hook = Hook()
    async with opened(store, record_activities=False, on_commit=hook) as session:
        await session.add_graph(B1, book(B1), served=served(Add(id=X)))
    assert len(await stored_graph(store, PROVENANCE)) == 0, "nothing stored"
    assert [a.id for a, _ in hook.calls] == [X], "the hook was given the activity"


async def test_a_session_that_does_not_record_does_not_guard_the_id(store):
    # D-6 h: a served command needs a hook when the session records nothing
    async with opened(store, record_activities=False, on_commit=Hook()) as session:
        await session.add_graph(B1, book(B1), served=served(Add(id=X)))
        await session.add_graph(B2, book(B2), served=served(Add(id=X)))
    assert len(await stored_graph(store, PROVENANCE)) == 0, "no guard, no record"


async def test_the_provenance_graph_of_one_tenant_never_receives_another_tenants_activity(store):
    other_tenant = "https://example.org/libraries/other"
    b = f"{other_tenant}/books/00000000-0000-0000-0000-000000000001"
    async with fake_session(
        store, tenant_iri=other_tenant, principal=Principal(id=BOB), clock=ticking()
    ) as elsewhere:
        await elsewhere.add_graph(b, book(b))
    assert await activities(store) == [], "TENANT's provenance graph is empty"
    found = await activities(store, DEFAULT_IRIS.provenance(other_tenant))
    assert [g.entity for g in found[0].generations] == [b], "recorded under its own tenant"
