"""Adversarial tests of the message bus (message-bus PD-8, PD-10, PD-13 to PD-17, Error matrix, D-5, D-6, D-9).

Each test names the design.md item it holds the code to. ``B1`` to ``B3`` are books of the toy tenant.
A test marked ``xfail`` is a finding: the code does not do what the design says (or what it must).
"""

import asyncio
import contextlib
import functools
import logging
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from rdflib import RDF, URIRef

from rdf_persistence import bootstrap
from rdf_persistence.core.domain.exceptions import (
    Conflict,
    InvalidBody,
    MessageLimitExceeded,
    PersistenceError,
)
from rdf_persistence.core.domain.generated.rp_core import Principal
from rdf_persistence.core.domain.generated.rp_provenance import Activity, Add, Remove, Replace
from rdf_persistence.core.domain.generated.rp_workflow import Transition
from rdf_persistence.iris.services.iris import Iris
from rdf_persistence.services.generated.settings.rp_settings import LimitSettings
from rdf_persistence.services.mapper import UnitOfWork
from rdf_persistence.services.messagebus import MessageBus, Work, command
from rdf_persistence.services.tenancy import Tenancy
from rdf_persistence.testkit import FakeStore, RecordingObserver
from rdf_persistence.testkit.fakes import FAKE_DATABASE
from tests.fixtures.library.generated.books import Book
from tests.fixtures.library.generated.library import Library
from tests.fixtures.library.generated.library_access import LibraryAccess
from tests.fixtures.library.generated.templates import Template
from tests.logs import records_of
from tests.toy import (
    ADA,
    BOB,
    SETTINGS,
    ApproveBook,
    ShelveBooks,
    book_iri,
    dune,
    library_slots,
    template,
    toy_mapper,
)
from tests.unit.services.test_messagebus import Recorder, ShelvedReplace, fakes
from tests.unit.services.test_messagebus_wiring import (
    B1,
    B2,
    B3,
    DRAFT,
    IN_REVIEW,
    PROVENANCE,
    World,
    provenance,
    shelving,
    types_of,
    version_of,
    world,
)
from tests.unit.services.test_session_activity import activities
from tests.unit.services.test_tenant_sweep import CREATOR, EventFiles, Events

NOW = datetime(2026, 11, 14, 10, 0, tzinfo=UTC)
ALL_QUADS = "SELECT ?g ?s ?p ?o WHERE { GRAPH ?g { ?s ?p ?o } }"
RUNAWAY = 40  # an observer that must be stopped by the bus stops itself here, to end the test


class Both(Replace, Add):
    """A command class under two command classes (diamond)."""


async def quads(store: FakeStore) -> frozenset[tuple[str, ...]]:
    rows = await store.query(FAKE_DATABASE, ALL_QUADS)
    return frozenset(tuple(map(str, row)) for row in rows)  # type: ignore[union-attr]


SHELVE_BOOKS = URIRef("https://example.org/ns/library#ShelveBooks")


async def shelvings(w: World) -> int:
    """How many ShelveBooks activities the provenance graph holds."""
    return len(set((await provenance(w)).subjects(RDF.type, SHELVE_BOOKS)))


async def stored_ids(w: World) -> list[str]:
    return [a.id for a in await activities(w.store, PROVENANCE)]


def move(w_version: str, **slots) -> ApproveBook:
    return command(
        ApproveBook, used_resource=B1, to_state="in_review", expected_version=w_version, **slots
    )


# -- dispatch ------------------------------------------------------------------------------------


async def test_a_command_under_two_command_classes_goes_to_the_first_in_its_mro():  # PD-13
    rec, (_, collaboration) = Recorder(), fakes()
    bus = MessageBus({Add: rec.handler("add"), Replace: rec.handler("replace")}, {})

    await bus.handle(command(Both), collaboration)

    assert rec.names() == ["replace"], "Both(Replace, Add) goes to the handler of Replace, once"


async def test_a_diamond_activity_reaches_each_observer_class_once_nearest_first():  # PD-13
    rec, (session, _) = Recorder(), fakes()
    bus = MessageBus(
        {},
        {
            Activity: [rec.observer("activity")],
            Add: [rec.observer("add")],
            Replace: [rec.observer("replace")],
        },
    )

    await bus.publish(command(Both), session)

    assert rec.names() == ["replace", "add", "activity"], "each class once, in mro order"


async def test_a_catch_all_handler_takes_only_what_no_nearer_class_handles():  # PD-13
    rec, (_, collaboration) = Recorder(), fakes()
    bus = MessageBus({Activity: rec.handler("all"), Replace: rec.handler("replace")}, {})

    for cls in (Replace, ShelvedReplace, Add, ShelveBooks):
        await bus.handle(command(cls), collaboration)

    assert rec.names() == ["replace", "replace", "all", "all"], "the nearest class wins"


async def test_a_subclass_and_its_parent_both_observe_once_each_nearest_first():  # PD-13
    rec, (session, _) = Recorder(), fakes()
    bus = MessageBus(
        {}, {Replace: [rec.observer("parent")], ShelvedReplace: [rec.observer("child")]}
    )

    await bus.publish(command(ShelvedReplace), session)
    await bus.publish(command(Replace), session)

    assert rec.names() == ["child", "parent", "parent"], "the parent is not called twice"


async def test_a_consumer_handler_of_transition_also_takes_an_extension_of_it():  # PD-14, PD-15
    async def mine(cmd: Activity, work: Work) -> str:
        return "mine"

    async with world(commands={Transition: mine}) as w:
        before = await quads(w.store)

        result = await w.bus.handle(move(await version_of(w)), w.collaboration)

        assert result == "mine", "the consumer's handler took the ApproveBook"
        assert await quads(w.store) == before, "the toolkit's handler did not run: nothing stored"


class Dependencies:
    """Callables whose parameters, after the first two, name a dependency."""

    def __init__(self, seen: list) -> None:
        self.seen = seen

    async def method(self, cmd: Activity, work: Work, notifier: object) -> None:
        self.seen.append(notifier)

    async def __call__(self, cmd: Activity, work: Work, notifier: object) -> None:
        self.seen.append(notifier)


def callables(seen: list):
    async def keyword_only(cmd: Activity, work: Work, *, notifier: object) -> None:
        seen.append(notifier)

    async def with_default(cmd: Activity, work: Work, notifier: object = None) -> None:
        seen.append(notifier)

    async def prefixed(prefix: str, cmd: Activity, work: Work, notifier: object) -> None:
        seen.append(notifier)

    async def plain(cmd: Activity, work: Work, notifier: object) -> None:
        seen.append(notifier)

    return {
        "keyword only": keyword_only,
        "default": with_default,
        "partial": functools.partial(prefixed, "x"),
        "lambda": lambda cmd, work, notifier: plain(cmd, work, notifier),
        "bound method": Dependencies(seen).method,
        "callable object": Dependencies(seen),
    }


@pytest.mark.parametrize("kind", list(callables([])))
async def test_every_kind_of_callable_gets_its_dependency_as_handler_and_observer(kind):  # PD-14
    fake, seen = object(), []
    each = callables(seen)[kind]
    bus = bootstrap(commands={ShelveBooks: each}, observers={Activity: [each]}, notifier=fake)

    await bus.handle(command(ShelveBooks), SimpleNamespace(session=object()))  # type: ignore[arg-type]
    await bus.publish(command(ShelveBooks), object())  # type: ignore[arg-type]

    assert seen == [fake, fake], f"{kind}: the handler and the observer both got the dependency"


async def test_a_dependency_bound_to_a_var_positional_parameter_fails_at_bootstrap_or_works():
    async def handler(cmd: Activity, work: Work, *notifier: object) -> str:
        return "done"

    try:
        bus = bootstrap(commands={ShelveBooks: handler}, notifier=object())
    except ValueError:
        return

    result = await bus.handle(command(ShelveBooks), SimpleNamespace(session=object()))  # type: ignore[arg-type]
    assert result == "done", "the handler ran"


# -- the refusal of toolkit-filled slots ------------------------------------------------------------


@pytest.mark.parametrize("slot", ["from_state_iri", "to_state_iri", "transition_comment"])
async def test_an_empty_string_in_a_toolkit_filled_slot_is_a_set_slot(slot):  # PD-13, D-5
    rec, (_, collaboration) = Recorder(), fakes()
    bus = MessageBus({Transition: rec.handler("h")}, {})

    with pytest.raises(InvalidBody, match=slot):
        await bus.handle(command(ApproveBook, used_resource=B1, **{slot: ""}), collaboration)

    assert rec.calls == [], "the handler did not run"


async def test_a_forged_principal_is_refused_and_nothing_is_stored_or_published():  # D-5, PD-13
    seen = RecordingObserver()
    async with world(observers={Activity: [seen]}) as w:
        before, published = await quads(w.store), len(seen.activities)

        with pytest.raises(InvalidBody, match="was_associated_with"):
            await w.bus.handle(
                move(await version_of(w), was_associated_with=[BOB]), w.collaboration
            )

        assert await quads(w.store) == before, "nothing is stored"
        assert len(seen.activities) == published, "nothing is published"


@pytest.mark.parametrize("id_", [B1, "https://example.org/not-a-uuid", "urn:uuid:not-a-uuid"])
async def test_a_command_whose_id_is_not_a_urn_uuid_is_refused_and_the_book_stays_a_book(id_):
    # PD-8 and the Error matrix: a Served whose id is not a urn:uuid: is a ValueError
    seen = RecordingObserver()
    async with world(commands={ShelveBooks: shelving()}, observers={Activity: [seen]}) as w:
        before, published = await quads(w.store), len(seen.activities)

        with pytest.raises(ValueError):
            await w.bus.handle(ShelveBooks(id=id_), w.collaboration)

        assert await quads(w.store) == before, "nothing is stored"
        assert len(seen.activities) == published, "nothing is published"
        assert types_of(await provenance(w), B1) == set(), "an aggregate is never an activity"


async def test_a_transition_command_with_an_aggregate_iri_as_its_id_is_refused():  # PD-8
    async with world() as w:
        before = await quads(w.store)
        forged = ApproveBook(
            id=B2, used_resource=B1, to_state="in_review", expected_version=await version_of(w)
        )

        with pytest.raises(ValueError):
            await w.bus.handle(forged, w.collaboration)

        assert await quads(w.store) == before, "the book did not move and nothing was recorded"


async def test_a_command_instance_handled_twice_records_once_and_the_second_fails():  # PD-8
    async with world(commands={ShelveBooks: shelving()}) as w:
        shelve = command(ShelveBooks)
        await w.bus.handle(shelve, w.collaboration)
        before = await quads(w.store)

        with pytest.raises(PersistenceError):
            await w.bus.handle(shelve, w.collaboration)

        assert await quads(w.store) == before, "the second handle wrote nothing"
        assert (await stored_ids(w)).count(shelve.id) == 1, "one record of the command"


async def test_a_command_naming_an_aggregate_of_another_tenant_records_and_publishes_nothing():
    # D-5: the command is carried out by the caller's collaboration, whose tenant is the session's
    seen = RecordingObserver()
    async with world(observers={Activity: [seen]}) as w:
        before, published = await quads(w.store), len(seen.activities)
        elsewhere = book_iri(9).replace("6f1c0c1e", "0a0a0a0a")
        assert elsewhere != book_iri(9), "the IRI is of another tenant"

        with pytest.raises(PersistenceError):
            await w.bus.handle(
                command(
                    ApproveBook,
                    used_resource=elsewhere,
                    to_state="in_review",
                    expected_version="v",
                ),
                w.collaboration,
            )

        assert await quads(w.store) == before, "nothing is stored"
        assert len(seen.activities) == published, "nothing is published"


# -- one command, one commit -------------------------------------------------------------------------


async def test_a_handler_that_commits_nothing_records_and_publishes_nothing():  # PD-8, D-5
    seen = RecordingObserver()

    async def idle(cmd: Activity, work: Work) -> str:
        return "idle"

    async with world(commands={ShelveBooks: idle}, observers={Activity: [seen]}) as w:
        before, published = await quads(w.store), len(seen.activities)

        result = await w.bus.handle(command(ShelveBooks), w.collaboration)

        assert result == "idle", "handle returns the result"
        assert await quads(w.store) == before, "nothing is recorded"
        assert len(seen.activities) == published, "nothing is published"


async def test_an_empty_commit_of_a_unit_of_work_records_and_publishes_nothing():  # D-5
    seen = RecordingObserver()

    async def empty(cmd: Activity, work: Work) -> None:
        await work.unit_of_work().commit()

    async with world(commands={ShelveBooks: empty}, observers={Activity: [seen]}) as w:
        before, published = await quads(w.store), len(seen.activities)

        await w.bus.handle(command(ShelveBooks), w.collaboration)

        assert await quads(w.store) == before, "no activity of an empty commit"
        assert len(seen.activities) == published, "nothing is published"


async def test_an_empty_commit_does_not_spend_the_command_for_the_real_one_after_it():
    async def shelve(cmd: Activity, work: Work) -> None:
        unit = work.unit_of_work()
        await unit.commit()  # nothing to write yet: a helper that always commits
        book = await unit.get(Book, B1)
        unit.add(book.model_copy(update={"label": "Shelved"}))
        await unit.commit()

    async with world(commands={ShelveBooks: shelve}) as w:
        shelved = command(ShelveBooks)

        await w.bus.handle(shelved, w.collaboration)

        assert (await stored_ids(w)).count(shelved.id) == 1, (
            "the real commit is recorded as the command"  # the world's seeds are stored too
        )


async def test_a_handler_that_commits_twice_unserved_makes_two_standard_activities():  # PD-8
    seen = RecordingObserver()

    async def two(cmd: Activity, work: Work) -> None:
        await work.session.add_graph(B3, toy_mapper().to_triples(dune(B3, chapters=1)))
        book = await UnitOfWork(work.session, toy_mapper()).get(Book, B1)
        unit = UnitOfWork(work.session, toy_mapper())
        unit.add(await unit.get(Book, B1))
        assert book.id == B1, "the read worked"
        async with work.session.transaction() as transaction:
            await transaction.add_graph(
                book_iri(4), toy_mapper().to_triples(dune(book_iri(4), chapters=1))
            )

    async with world(commands={ShelveBooks: two}, observers={Activity: [seen]}) as w:
        await w.bus.handle(command(ShelveBooks), w.collaboration)

        assert [type(a) for a in seen.activities].count(Add) == 4, "two seeds and two adds"
        assert not seen.of(ShelveBooks), "no activity of the command: it committed nothing served"


async def test_a_served_transaction_opened_directly_twice_is_refused_the_second_time():  # PD-8
    seen = RecordingObserver()

    async def twice(cmd: Activity, work: Work) -> None:
        for iri in (B3, book_iri(4)):
            async with work.session.transaction(served=work.served) as transaction:
                await transaction.add_graph(iri, toy_mapper().to_triples(dune(iri, chapters=1)))

    async with world(commands={ShelveBooks: twice}, observers={ShelveBooks: [seen]}) as w:
        shelved = command(ShelveBooks)

        with pytest.raises(RuntimeError, match=shelved.id):
            await w.bus.handle(shelved, w.collaboration)

        assert [g.entity for a in seen.of(ShelveBooks) for g in a.generations or []] == [B3], (
            "the first commit stands and was published, the second wrote nothing"
        )


async def test_a_handler_that_raises_after_committing_keeps_and_publishes_the_commit():
    # Error matrix: the handler raises: commits it already made stand and were published
    seen = RecordingObserver()

    async def commit_then_fail(cmd: Activity, work: Work) -> None:
        await shelving()(cmd, work)
        raise ZeroDivisionError

    async with world(
        commands={ShelveBooks: commit_then_fail}, observers={ShelveBooks: [seen]}
    ) as w:
        shelved = command(ShelveBooks)

        with pytest.raises(ZeroDivisionError):
            await w.bus.handle(shelved, w.collaboration)

        assert shelved.id in await stored_ids(w), "the commit stands"
        assert [a.id for a in seen.of(ShelveBooks)] == [shelved.id], "and was published"


async def test_a_failed_served_commit_publishes_nothing_and_leaves_the_store_as_it_was():  # PD-8
    seen = RecordingObserver()
    async with world(commands={ShelveBooks: shelving()}, observers={Activity: [seen]}) as w:
        before, published = await quads(w.store), len(seen.activities)
        w.store.on("update", PersistenceError("the store is down"))

        with pytest.raises(PersistenceError, match="down"):
            await w.bus.handle(command(ShelveBooks), w.collaboration)

        assert await quads(w.store) == before, "the store holds what it held"
        assert len(seen.activities) == published, "nothing is published"


async def test_what_a_handler_raised_leaves_no_state_in_the_next_commit_outside_handle():
    # PD-13: the running call is in a ContextVar; a failed handle resets it
    seen: list[Work] = []

    async def watch(activity: Activity, work: Work) -> None:
        seen.append(work)

    async def boom(cmd: Activity, work: Work) -> None:
        raise ZeroDivisionError

    async with world(commands={ShelveBooks: boom}, observers={Activity: [watch]}) as w:
        with pytest.raises(ZeroDivisionError):
            await w.bus.handle(command(ShelveBooks), w.collaboration)

        await w.session.add_graph(B3, toy_mapper().to_triples(dune(B3, chapters=1)))

        assert seen[-1].collaboration is None, "a generic commit has no collaboration"
        with pytest.raises(RuntimeError):
            await seen[-1].send(command(ShelveBooks))


# -- the queue and the limit ---------------------------------------------------------------------------


async def test_many_queued_commands_run_up_to_the_limit_then_the_rest_is_dropped():  # PD-13
    rec, (_, collaboration) = Recorder(), fakes()
    bus: MessageBus

    async def first(cmd: Activity, work: Work) -> None:
        for _ in range(10):
            await work.send(command(Remove))

    bus = MessageBus(
        {Replace: first, Remove: rec.handler("remove")},
        {},
        limits=LimitSettings(max_messages=4),
    )

    with pytest.raises(MessageLimitExceeded, match="message limit 4 reached"):
        await bus.handle(command(Replace), collaboration)

    assert rec.names() == ["remove"] * 3, "the first command and three queued ones were started"


async def test_a_limit_of_one_lets_a_command_that_sends_nothing_through_and_refuses_a_send():
    rec, (_, collaboration) = Recorder(), fakes()

    async def sends(cmd: Activity, work: Work) -> str:
        await work.send(command(Remove))
        return "result"

    bus = MessageBus(
        {Replace: rec.handler("replace", "ok"), Add: sends, Remove: rec.handler("r")},
        {},
        limits=LimitSettings(max_messages=1),
    )

    assert await bus.handle(command(Replace), collaboration) == "ok", "one command fits"
    with pytest.raises(MessageLimitExceeded):
        await bus.handle(command(Add), collaboration)
    assert rec.names() == ["replace"], "the queued command was refused, not run"


async def test_a_command_sent_by_a_handler_runs_after_it_and_after_its_observers():  # PD-13
    rec, (_, collaboration) = Recorder(), fakes()
    bus: MessageBus

    async def first(cmd: Activity, work: Work) -> str:
        await work.send(command(Remove))
        await bus.publish(cmd, work.session)
        rec.calls.append(("first-end", cmd, work))
        return "first"

    bus = MessageBus(
        {Replace: first, Remove: rec.handler("remove")}, {Replace: [rec.observer("observer")]}
    )

    assert await bus.handle(command(Replace), collaboration) == "first", "the first result"
    assert rec.names() == ["observer", "first-end", "remove"], "FIFO after the handler returned"


async def test_commands_an_observer_queued_are_dropped_when_the_handler_then_raises():
    # PD-13/Error matrix: "a handler's error reaches the caller"; the queue it had grown is not run.
    # Pinned as built: the commit stands and was published, and what its observers asked is lost.
    rec, (_, collaboration) = Recorder(), fakes()
    bus: MessageBus

    async def first(cmd: Activity, work: Work) -> None:
        await bus.publish(cmd, work.session)
        raise ZeroDivisionError

    async def asks(activity: Activity, work: Work) -> None:
        await work.send(command(Remove))

    bus = MessageBus({Replace: first, Remove: rec.handler("remove")}, {Replace: [asks]})

    with pytest.raises(ZeroDivisionError):
        await bus.handle(command(Replace), collaboration)

    assert rec.names() == [], "the queued command never ran"


async def test_a_nested_handle_from_a_handler_returns_its_result_and_its_queue_runs_last():
    rec, (_, collaboration) = Recorder(), fakes()
    bus: MessageBus

    async def outer(cmd: Activity, work: Work) -> object:
        inner = await bus.handle(command(Add), collaboration)
        rec.calls.append(("outer-end", cmd, work))
        return inner

    async def inner(cmd: Activity, work: Work) -> str:
        await work.send(command(Remove))
        return "inner"

    bus = MessageBus({Replace: outer, Add: inner, Remove: rec.handler("remove")}, {})

    assert await bus.handle(command(Replace), collaboration) == "inner", "the nested result"
    assert rec.names() == ["outer-end", "remove"], "the nested call's send waits for the outer"


async def test_a_nested_handle_that_fails_raises_into_its_caller_not_into_the_log(caplog):
    _, collaboration = fakes()
    bus: MessageBus

    async def outer(cmd: Activity, work: Work) -> str:
        try:
            await bus.handle(command(Add), collaboration)
        except KeyError:
            return "caught"
        return "not raised"

    async def boom(cmd: Activity, work: Work) -> None:
        raise KeyError("boom")

    bus = MessageBus({Replace: outer, Add: boom}, {})

    with caplog.at_level(logging.ERROR):
        assert await bus.handle(command(Replace), collaboration) == "caught", "raised to the caller"
    assert not records_of(caplog, "bus-queued-failed"), "a nested call is not a queued one"


async def test_a_queued_command_that_fails_does_not_lose_the_one_behind_it_nor_the_result(caplog):
    rec, (_, collaboration) = Recorder(), fakes()

    async def bad(cmd: Activity, work: Work) -> None:
        raise KeyError("bad")

    async def first(cmd: Activity, work: Work) -> str:
        await work.send(command(Add))
        await work.send(command(Remove))
        return "first"

    bus = MessageBus({Replace: first, Add: bad, Remove: rec.handler("remove")}, {})

    with caplog.at_level(logging.ERROR):
        assert await bus.handle(command(Replace), collaboration) == "first", "the first result"
    assert rec.names() == ["remove"], "the command after the failed one still ran"
    assert len(records_of(caplog, "bus-queued-failed")) == 1, "the failure is logged once"


async def test_an_observer_that_sends_a_command_each_time_stops_at_the_limit_with_a_real_session():
    # Error matrix: an observer sends the command it observes: MessageLimitExceeded from handle,
    # earlier commits stand
    async def again(activity: Activity, work: Work) -> None:
        await work.send(command(ShelveBooks))

    async with world(
        commands={ShelveBooks: shelving()},
        observers={ShelveBooks: [again]},
        limits=LimitSettings(max_messages=3),
    ) as w:
        # the toy handler commits the same labels again: each run changes nothing but the version
        with pytest.raises(MessageLimitExceeded):
            await w.bus.handle(command(ShelveBooks), w.collaboration)

        assert await shelvings(w) == 3, "three commands committed, the fourth was refused"


async def test_an_observer_that_commits_in_a_loop_outside_handle_stops_with_a_real_session(caplog):
    # Error matrix: an observer commits on its session outside handle, in a loop: logged, loop ends
    count = 0

    async def breed(activity: Activity, work: Work) -> None:
        nonlocal count
        count += 1
        if count >= RUNAWAY:
            return
        iri = book_iri(100 + count)
        await work.session.add_graph(iri, toy_mapper().to_triples(dune(iri, chapters=1)))

    async with world(observers={Add: [breed]}, limits=LimitSettings(max_messages=5)) as w:
        with caplog.at_level(logging.ERROR):
            await w.session.add_graph(B3, toy_mapper().to_triples(dune(B3, chapters=1)))

        assert count < RUNAWAY, "the bus stopped the loop"
        assert "message limit 5 reached" in caplog.text, "logged as the observer's error"


async def test_an_observer_that_commits_in_a_loop_inside_handle_is_stopped_by_the_limit():
    count = 0

    async def breed(activity: Activity, work: Work) -> None:
        nonlocal count
        count += 1
        if count >= RUNAWAY:
            return
        iri = book_iri(100 + count)
        await work.session.add_graph(iri, toy_mapper().to_triples(dune(iri, chapters=1)))

    async with world(
        commands={ShelveBooks: shelving()},
        observers={Activity: [breed]},
        limits=LimitSettings(max_messages=5),
    ) as w:
        with contextlib.suppress(MessageLimitExceeded):
            await w.bus.handle(command(ShelveBooks), w.collaboration)

        assert count < RUNAWAY, "the observer was stopped before it ran away"


async def test_a_nested_handle_loop_in_an_observer_is_bounded_with_a_real_session(caplog):  # TC-72a
    count = 0

    async def nested(activity: Activity, work: Work) -> None:
        nonlocal count
        count += 1
        if count < RUNAWAY and work.collaboration is not None:
            await w.bus.handle(command(ShelveBooks), work.collaboration)

    async with world(
        commands={ShelveBooks: shelving()},
        observers={ShelveBooks: [nested]},
        limits=LimitSettings(max_messages=4),
    ) as w:
        with caplog.at_level(logging.ERROR):
            await w.bus.handle(command(ShelveBooks), w.collaboration)  # D-10: not raised to us

        assert await shelvings(w) == 4, "exactly the limit's commands committed"
        assert count == 4, "the observer ran once for each"
        assert "message limit 4 reached" in caplog.text, "the commit's hook logged the limit error"


# -- the hook --------------------------------------------------------------------------------------------


async def test_an_observer_that_raises_cancelled_error_leaves_the_commit_in_place():  # PD-10
    async def cancelled(activity: Activity, work: Work) -> None:
        if [g.entity for g in activity.generations or []] == [B3]:
            raise asyncio.CancelledError

    async with world(observers={Add: [cancelled]}) as w:
        with pytest.raises(asyncio.CancelledError):
            await w.session.add_graph(B3, toy_mapper().to_triples(dune(B3, chapters=1)))

        assert (await w.session.get_graph(B3))[0], "the commit stands"


async def test_a_cancelled_observer_leaves_no_nesting_count_behind():  # PD-13
    state = {"cancel": False}

    async def sometimes(activity: Activity, work: Work) -> None:
        if state["cancel"]:
            raise asyncio.CancelledError

    async with world(observers={Add: [sometimes]}, limits=LimitSettings(max_messages=2)) as w:
        for n in range(5):
            state["cancel"] = n % 2 == 0
            iri = book_iri(50 + n)
            with contextlib.suppress(asyncio.CancelledError):
                await w.session.add_graph(iri, toy_mapper().to_triples(dune(iri, chapters=1)))

        assert (await w.session.get_graph(book_iri(54)))[0], (
            "five commits went through a limit of two"
        )


async def test_a_slow_observer_does_not_hold_up_the_commit_of_another_session():  # PD-10, D-9
    entered, release = asyncio.Event(), asyncio.Event()
    published: list[tuple[str, object]] = []

    async def slow(activity: Activity, work: Work) -> None:
        [entity] = [g.entity for g in activity.generations or []]
        published.append((entity, work.session))
        if entity == B3:
            entered.set()
            await release.wait()

    async with world(observers={Add: [slow]}) as w:
        published.clear()
        first = asyncio.create_task(
            w.session.add_graph(B3, toy_mapper().to_triples(dune(B3, chapters=1)))
        )
        await entered.wait()

        await asyncio.wait_for(
            w.session.add_graph(
                book_iri(4), toy_mapper().to_triples(dune(book_iri(4), chapters=1))
            ),
            timeout=5,
        )
        release.set()
        await first

        assert [entity for entity, _ in published] == [B3, book_iri(4)], (
            "the other commit was published while the first observer was still waiting"
        )


async def test_an_observer_that_mutates_its_activity_does_not_change_what_the_next_one_gets():
    # PD-13: each exception is logged and the rest still run: observers are independent
    async def vandal(activity: Activity, work: Work) -> None:
        activity.generations = None
        activity.was_associated_with = ["urn:x:nobody"]

    seen = RecordingObserver()
    async with world(observers={Add: [vandal, seen]}) as w:
        await w.session.add_graph(B3, toy_mapper().to_triples(dune(B3, chapters=1)))

        [last] = seen.activities[-1:]
        assert [g.entity for g in last.generations or []] == [B3], "the second observer's record"
        assert last.was_associated_with == [ADA], "its principal"


async def test_the_work_of_an_observer_is_that_of_the_session_that_committed():  # PD-13, D-9
    seen: list[Work] = []

    async def watch(activity: Activity, work: Work) -> None:
        seen.append(work)

    async with world(observers={Add: [watch]}) as w:
        await w.session.add_graph(B3, toy_mapper().to_triples(dune(B3, chapters=1)))

        assert seen[-1].session is w.session, "the session that committed"
        assert seen[-1].served is None, "an observer serves no command"
        assert seen[-1].collaboration is None, "outside handle there is no collaboration"


async def test_a_bus_without_a_mapper_gives_an_observer_no_unit_of_work_but_runs_the_rest(caplog):
    async def uses_unit(activity: Activity, work: Work) -> None:
        work.unit_of_work()

    seen = RecordingObserver()
    async with world(observers={Add: [uses_unit, seen]}, mapper=False) as w:
        with caplog.at_level(logging.ERROR):
            await w.session.add_graph(B3, toy_mapper().to_triples(dune(B3, chapters=1)))

        assert "no mapper" in caplog.text, "the RuntimeError is logged as the observer's"
        assert seen.of(Add), "the next observer ran"


# -- types and records ---------------------------------------------------------------------------------------


async def test_the_observer_of_an_extension_gets_it_whole_and_the_transition_observer_too():
    # PD-11, PD-15, TC-75
    seen = RecordingObserver()
    async with world(observers={Transition: [seen]}) as w:
        await w.bus.handle(move(await version_of(w)), w.collaboration)

        [got] = seen.of(ApproveBook)
        assert type(got) is ApproveBook, "an ApproveBook, not a Transition"
        assert got.id.startswith("urn:uuid:"), "the command's id"
        assert (got.from_state_iri, got.to_state_iri) == (DRAFT, IN_REVIEW), "the states"
        assert got.used_resource == B1, "the resource"
        assert got.started_at_time, "the times"
        assert got.ended_at_time, "the times"
        assert got.was_associated_with == [ADA], "the principal"
        assert (got.to_state, got.expected_version, got.body_value) == (None, None, None), (
            "no payload"
        )


async def test_a_transition_with_a_comment_publishes_the_record_naming_the_comment():  # PD-15
    seen = RecordingObserver()
    async with world(observers={Transition: [seen]}) as w:
        await w.bus.handle(move(await version_of(w), body_value="ready"), w.collaboration)

        [got] = seen.of(ApproveBook)
        assert got.transition_comment, "the record names the comment of the thread"
        assert got.body_value is None, "the text is payload: it is not stored on the record"


async def test_a_mixed_commit_in_a_handler_is_one_activity_of_the_command_class():  # PD-8, TC-106
    on_command, on_add, on_replace, on_remove = (RecordingObserver() for _ in range(4))

    async def mixed(cmd: Activity, work: Work) -> None:
        unit = work.unit_of_work()
        one, two = await unit.get(Book, B1), await unit.get(Book, B2)
        unit.add(one.model_copy(update={"label": "Changed"}))
        unit.remove(two)
        unit.add(dune(B3, chapters=1))
        await unit.commit()

    async with world(
        commands={ShelveBooks: mixed},
        observers={
            ShelveBooks: [on_command],
            Add: [on_add],
            Replace: [on_replace],
            Remove: [on_remove],
        },
    ) as w:
        await w.bus.handle(command(ShelveBooks), w.collaboration)

        [got] = on_command.of(ShelveBooks)
        assert sorted(g.entity for g in got.generations or []) == [B1, B3], "new and changed"
        assert sorted(i.entity for i in got.invalidations or []) == [B1, B2], "changed and removed"
        assert got.was_associated_with == [ADA], "the principal"
        assert [a for a in on_add.activities if isinstance(a, ShelveBooks)] == [], "not an Add"
        assert [a for a in on_replace.activities if isinstance(a, ShelveBooks)] == [], (
            "not a Replace"
        )
        assert [a for a in on_remove.activities if isinstance(a, ShelveBooks)] == [], "not a Remove"


async def test_the_recording_observer_sees_extensions_of_a_class_it_is_asked_for():  # PD-22
    seen = RecordingObserver()
    async with world(observers={Activity: [seen]}) as w:
        await w.bus.handle(move(await version_of(w)), w.collaboration)

        assert [type(a) for a in seen.of(Transition)] == [ApproveBook], "of(Transition) sees it"
        assert seen.of(Add) == seen.of(Add), "the base class filter is stable"
        assert all(isinstance(a, Add) for a in seen.of(Add)), "of(Add) holds Adds only"


async def test_a_refused_command_leaves_no_record_of_any_kind():  # spec: a refused commit records nothing
    seen = RecordingObserver()
    async with world(observers={Activity: [seen]}) as w:
        before, published = await quads(w.store), len(seen.activities)

        with pytest.raises(Conflict):
            await w.bus.handle(move("not-the-version"), w.collaboration)

        assert await quads(w.store) == before, "the store is as it was"
        assert len(seen.activities) == published, "nothing is published"
        assert URIRef(B1) not in set(
            (await provenance(w)).subjects(RDF.type, URIRef("http://www.w3.org/ns/prov#Activity"))
        ), "the book is no activity"


# -- the tenancy and the databases (PD-9, PD-17) -------------------------------------------------------------


async def tenancy_publishing(published: list[Activity]) -> tuple[Tenancy, FakeStore, str]:
    store = Events([])

    async def hook(activity: Activity, session: object) -> None:
        published.append(activity)

    tenancy = Tenancy(
        store,
        EventFiles([], lambda: NOW),
        SETTINGS,
        mapper=toy_mapper(),
        root_class=Library,
        access_class=LibraryAccess,
        iris=Iris(SETTINGS),
        on_commit=hook,
    )
    await tenancy.ensure_system_database()
    tenant = (await tenancy.create("Ghent", library_slots(), CREATOR)).id
    return tenancy, store, tenant


async def test_the_system_database_records_and_publishes_nothing_the_tenant_database_does():
    # PD-9, PD-17
    published: list[Activity] = []

    tenancy, store, _ = await tenancy_publishing(published)

    ask = "ASK { GRAPH ?g { ?s a <http://www.w3.org/ns/prov#Activity> } }"
    assert not (await store.query(tenancy.system_database, ask)).askAnswer, "no tenancy activities"
    assert published, "the tenant root's commit was published"
    assert all([g.entity for g in a.generations or []] and Add is type(a) for a in published), (
        "each is an Add of a tenant-database root"
    )


async def test_an_application_session_publishes_its_commit_with_the_application_iri():  # PD-9
    published: list[Activity] = []
    tenancy, _, _ = await tenancy_publishing(published)
    await tenancy.ensure_application_database()
    published.clear()

    async with tenancy.application_session(Principal(id=ADA)) as session:
        iri = tenancy.application_iri(Template)
        unit = UnitOfWork(session, toy_mapper())
        unit.add(template(iri))
        await unit.commit()

    assert [type(a) for a in published] == [Add], "one Add published"
    assert [g.entity for g in published[0].generations or []] == [iri], "of the template"
