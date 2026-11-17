"""The message bus dispatches commands to handlers and completed activities to observers (message-bus PD-13).

Dispatch only: nothing is stored. The handlers and observers are async functions that record their
calls, and the session and the collaboration are small fakes.
"""

import asyncio
import logging
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from opentelemetry.trace import StatusCode
from pydantic import BaseModel, ValidationError

from rdf_persistence.domain.exceptions import Conflict, InvalidBody, MessageLimitExceeded
from rdf_persistence.domain.generated.rp_provenance import (
    Activity,
    Add,
    Generation,
    Invalidation,
    Remove,
    Replace,
)
from rdf_persistence.domain.generated.rp_workflow import Transition
from rdf_persistence.services.generated.settings.rp_settings import LimitSettings
from rdf_persistence.services.mapper import UnitOfWork
from rdf_persistence.services.messagebus import MessageBus, Work, command
from tests.logs import attributes
from tests.spans import assert_no_text_in_spans
from tests.toy import toy_mapper

NOW = datetime(2026, 11, 14, 10, 0, tzinfo=UTC)
BOOK = "https://example.org/book/1"


class ShelvedReplace(Replace):
    """A consumer's subclass of a standard activity."""


def fakes() -> tuple[SimpleNamespace, SimpleNamespace]:
    """A session and a collaboration that holds it."""
    session = SimpleNamespace(name="session")
    return session, SimpleNamespace(name="collaboration", session=session)


class Recorder:
    """Records what the handlers and observers were called with, in order."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Activity, Work]] = []

    def names(self) -> list[str]:
        return [name for name, _, _ in self.calls]

    def handler(self, name: str, result: object = None):
        async def handle(cmd: Activity, work: Work) -> object:
            self.calls.append((name, cmd, work))
            return result

        handle.__qualname__ = name
        return handle

    def observer(self, name: str):
        async def observe(activity: Activity, work: Work) -> None:
            self.calls.append((name, activity, work))

        observe.__qualname__ = name
        return observe


async def test_a_handler_gets_the_command_and_a_work_of_the_collaboration():  # TC-60
    rec, (session, collaboration) = Recorder(), fakes()
    bus = MessageBus({Replace: rec.handler("h", result="done")}, {})
    cmd = command(Replace)

    result = await bus.handle(cmd, collaboration)

    assert result == "done", "handle returns the handler's result"
    assert rec.names() == ["h"], "the handler is called once"
    _, got, work = rec.calls[0]
    assert got is cmd, "the handler gets the command"
    assert work.collaboration is collaboration, "the work holds the caller's collaboration"
    assert work.session is session, "the work's session is the collaboration's"


async def test_the_nearest_class_has_the_handler():  # TC-61
    rec, (_, collaboration) = Recorder(), fakes()
    bus = MessageBus({Activity: rec.handler("activity"), Replace: rec.handler("replace")}, {})

    await bus.handle(command(ShelvedReplace), collaboration)

    assert rec.names() == ["replace"], "the handler of Replace, not of Activity, ran"


async def test_a_command_with_no_handler_along_its_hierarchy_is_a_lookup_error():  # TC-62
    _, collaboration = fakes()
    bus = MessageBus({Remove: Recorder().handler("h")}, {})

    with pytest.raises(LookupError, match="no handler for Replace"):
        await bus.handle(command(Replace), collaboration)


SESSION_SLOTS = [
    ("started_at_time", NOW),
    ("ended_at_time", NOW),
    ("was_associated_with", ["https://example.org/ada"]),
    (
        "generations",
        [Generation(activity="urn:x", at_time=NOW, entity=BOOK, entity_version="v1")],
    ),
    (
        "invalidations",
        [Invalidation(activity="urn:x", at_time=NOW, entity=BOOK, entity_version="v1")],
    ),
]
TRANSITION_SLOTS = [
    ("from_state_iri", "https://example.org/state/a"),
    ("to_state_iri", "https://example.org/state/b"),
    ("transition_comment", "https://example.org/comment/1"),
]


@pytest.mark.parametrize(
    ("cls", "slot", "value"),
    [(Replace, *pair) for pair in SESSION_SLOTS]
    + [(Transition, *pair) for pair in TRANSITION_SLOTS],
)
async def test_a_command_with_a_toolkit_filled_slot_is_refused(cls, slot, value):  # TC-63
    rec, (_, collaboration) = Recorder(), fakes()
    bus = MessageBus({cls: rec.handler("h")}, {})
    extra = {"used_resource": BOOK} if cls is Transition else {}

    with pytest.raises(InvalidBody, match=slot):
        await bus.handle(command(cls, **{slot: value}, **extra), collaboration)

    assert rec.calls == [], "the handler is not called"


async def test_an_empty_list_is_not_a_set_slot():  # TC-63a
    rec, (_, collaboration) = Recorder(), fakes()
    bus = MessageBus({Replace: rec.handler("h", result="ok")}, {})

    result = await bus.handle(command(Replace, generations=[]), collaboration)

    assert result == "ok", "a command with generations=[] is handled"


async def test_a_handlers_error_reaches_the_caller():  # TC-64
    _, collaboration = fakes()

    async def failing(cmd: Activity, work: Work) -> None:
        raise Conflict("lost the race")

    with pytest.raises(Conflict, match="lost the race"):
        await MessageBus({Replace: failing}, {}).handle(command(Replace), collaboration)


async def test_observers_run_nearest_class_first_in_registration_order():  # TC-65
    rec, (session, _) = Recorder(), fakes()
    bus = MessageBus(
        {},
        {
            Activity: [rec.observer("o1")],
            Replace: [rec.observer("o2"), rec.observer("o3")],
        },
    )

    await bus.publish(command(Replace), session)

    assert rec.names() == ["o2", "o3", "o1"], "nearest class first, registration order, once each"


async def test_a_failing_observer_is_logged_and_the_others_run(caplog):  # TC-66
    rec, (session, _) = Recorder(), fakes()

    async def o2(activity: Activity, work: Work) -> None:
        raise ValueError("boom")

    bus = MessageBus({}, {Replace: [o2, rec.observer("o3")], Activity: [rec.observer("o1")]})
    activity = command(Replace)

    with caplog.at_level(logging.ERROR):
        await bus.publish(activity, session)

    assert rec.names() == ["o3", "o1"], "the observers after the failing one still run"
    [record] = [r for r in caplog.records if r.exc_info]  # TC-12
    assert record.getMessage() == "an observer failed", "one error is logged, with its traceback"
    assert attributes(record) == {
        "rp.step": "bus-observer-failed",
        "rp.observer.name": o2.__qualname__,
        "rp.activity.class": "Replace",
        "rp.activity.id": activity.id,
    }, "it names the observer and the activity"


def sender(rec: Recorder, name: str, *commands: Activity):
    async def observe(activity: Activity, work: Work) -> None:
        rec.calls.append((name, activity, work))
        for each in commands:
            await work.send(each)

    return observe


async def test_a_command_an_observer_sends_runs_after_the_handler_returned():  # TC-67
    rec, (_, collaboration) = Recorder(), fakes()
    bus: MessageBus

    async def replace(cmd: Activity, work: Work) -> str:
        rec.calls.append(("replace-start", cmd, work))
        await bus.publish(cmd, work.session)  # what the session's hook does after a commit
        rec.calls.append(("replace-end", cmd, work))
        return "first"

    bus = MessageBus(
        {Replace: replace, Remove: rec.handler("remove")},
        {Replace: [sender(rec, "observer", command(Remove))]},
    )

    result = await bus.handle(command(Replace), collaboration)

    assert rec.names() == ["replace-start", "observer", "replace-end", "remove"], (
        "the queue runs last"
    )
    assert result == "first", "handle returns the first command's result"


async def test_a_command_that_sends_itself_again_stops_at_the_limit():  # TC-68
    rec, (_, collaboration) = Recorder(), fakes()
    bus: MessageBus

    async def replace(cmd: Activity, work: Work) -> None:
        rec.calls.append(("replace", cmd, work))
        await bus.publish(cmd, work.session)

    async def again(activity: Activity, work: Work) -> None:
        await work.send(activity)

    bus = MessageBus({Replace: replace}, {Replace: [again]}, limits=LimitSettings(max_messages=5))

    with pytest.raises(MessageLimitExceeded, match="message limit 5 reached") as caught:
        await bus.handle(command(Replace), collaboration)

    assert caught.value.limit == 5, "the error names the limit"
    assert rec.names() == ["replace"] * 5, "the handler ran five times"


async def test_send_outside_handle_is_a_runtime_error_logged_as_the_observers(caplog):  # TC-69
    rec, (session, _) = Recorder(), fakes()
    bus = MessageBus(
        {Remove: rec.handler("remove")}, {Replace: [sender(rec, "o", command(Remove))]}
    )

    with caplog.at_level(logging.ERROR):
        await bus.publish(command(Replace), session)

    assert rec.names() == ["o"], "nothing was handled"
    errors = [r.exc_info[1] for r in caplog.records if r.exc_info]
    assert [type(e) for e in errors] == [RuntimeError], "the observer's RuntimeError is logged"


async def test_a_failing_queued_command_is_logged_and_the_queue_goes_on(caplog):  # TC-70
    rec, (_, collaboration) = Recorder(), fakes()
    bus: MessageBus
    bad = command(Remove)

    async def replace(cmd: Activity, work: Work) -> str:
        await bus.publish(cmd, work.session)
        return "first"

    async def failing(cmd: Activity, work: Work) -> None:
        raise ValueError("queued boom")

    bus = MessageBus(
        {Replace: replace, Remove: failing, Add: rec.handler("add")},
        {Replace: [sender(rec, "o", bad, command(Add))]},
    )

    with caplog.at_level(logging.ERROR):
        result = await bus.handle(command(Replace), collaboration)

    assert result == "first", "handle returns the first result"
    assert rec.names() == ["o", "add"], "the command after the failing one ran"
    [record] = [r for r in caplog.records if r.exc_info]
    assert record.getMessage() == "a queued command failed", "the failure is logged"
    assert attributes(record) == {
        "rp.step": "bus-queued-failed",
        "rp.activity.class": "Remove",
        "rp.activity.id": bad.id,
    }, "naming the command"


def test_a_key_that_is_no_activity_or_the_old_limit_keyword_is_refused():  # TC-71, DEC-5
    handler = Recorder().handler("h")
    with pytest.raises(ValueError, match="Activity"):
        MessageBus({Conflict: handler}, {})  # type: ignore[dict-item]
    with pytest.raises(ValueError, match="Activity"):
        MessageBus({}, {str: [handler]})  # type: ignore[dict-item]
    with pytest.raises(TypeError, match="limit"):
        MessageBus({}, {}, limit=5)  # type: ignore[call-arg]


async def test_an_observer_that_publishes_again_stops_at_the_limit_outside_handle():  # TC-72
    (session, _), runs = fakes(), []
    bus: MessageBus

    async def again(activity: Activity, work: Work) -> None:
        runs.append(activity)
        await bus.publish(activity, work.session)

    bus = MessageBus({}, {Replace: [again]}, limits=LimitSettings(max_messages=5))

    with pytest.raises(MessageLimitExceeded, match="message limit 5 reached"):
        await bus.publish(command(Replace), session)

    assert len(runs) == 5, "the observer ran five times; the sixth publish was refused"


async def test_a_nested_handle_joins_the_running_count():  # TC-72a
    rec, (_, collaboration) = Recorder(), fakes()
    bus: MessageBus

    async def replace(cmd: Activity, work: Work) -> None:
        rec.calls.append(("replace", cmd, work))
        await bus.publish(cmd, work.session)

    async def nested(activity: Activity, work: Work) -> None:
        await bus.handle(activity, collaboration)

    bus = MessageBus({Replace: replace}, {Replace: [nested]}, limits=LimitSettings(max_messages=5))

    with pytest.raises(MessageLimitExceeded, match="message limit 5 reached"):
        await bus.handle(command(Replace), collaboration)

    assert rec.names() == ["replace"] * 5, "the nested calls count with the outer one"


async def test_two_handles_in_two_tasks_each_have_their_own_count_and_work():  # TC-72b
    seen: list[Work] = []

    async def replace(cmd: Activity, work: Work) -> None:
        seen.append(work)
        await asyncio.sleep(0)  # let the other task run
        assert work is not None, "the handler got a unit of work"

    bus = MessageBus({Replace: replace}, {}, limits=LimitSettings(max_messages=1))
    (_, one), (_, other) = fakes(), fakes()

    await asyncio.gather(bus.handle(command(Replace), one), bus.handle(command(Replace), other))

    assert len(seen) == 2, "neither call went over a limit of one: the counts are not shared"
    assert seen[0] is not seen[1], "each call has its own work"
    assert {id(w.collaboration) for w in seen} == {id(one), id(other)}, (
        "each holds its own collaboration"
    )


def test_a_command_gets_a_fresh_urn_uuid_id():  # TC-72c
    one, other = command(Replace), command(Replace)

    assert one.id.startswith("urn:uuid:"), "ids are urn:uuid:"
    assert other.id.startswith("urn:uuid:"), "ids are urn:uuid:"
    assert one.id != other.id, "ids are fresh"


async def test_an_observer_of_another_sessions_commit_gets_no_collaboration(caplog):  # D-11 a
    rec, (_, collaboration) = Recorder(), fakes()
    other, _ = fakes()
    bus: MessageBus

    async def replace(cmd: Activity, work: Work) -> None:
        await bus.publish(cmd, other)  # a commit of a session this collaboration does not hold

    bus = MessageBus(
        {Replace: replace, Remove: rec.handler("remove")},
        {Replace: [sender(rec, "o", command(Remove))]},
    )

    with caplog.at_level(logging.ERROR):
        await bus.handle(command(Replace), collaboration)

    assert rec.names() == ["o"], "the queued command did not run"
    assert rec.calls[0][2].collaboration is None, "the observer has no collaboration"
    errors = [r.exc_info[1] for r in caplog.records if r.exc_info]
    assert [type(e) for e in errors] == [RuntimeError], "its send is the observer's logged error"


async def test_a_queued_command_runs_with_the_collaboration_it_was_sent_under():  # D-11 a
    rec, (_, first), (_, second) = Recorder(), fakes(), fakes()
    bus: MessageBus

    async def publishing(cmd: Activity, work: Work) -> None:
        await bus.publish(cmd, work.session)

    async def nested(activity: Activity, work: Work) -> None:
        await bus.handle(command(Add), second)  # another collaboration, in the same run

    bus = MessageBus(
        {Replace: publishing, Add: publishing, Remove: rec.handler("remove")},
        {Replace: [nested], Add: [sender(rec, "o", command(Remove))]},
    )

    await bus.handle(command(Replace), first)

    assert rec.names() == ["o", "remove"], "the nested commit's observer queued a command"
    (_, _, observed), (_, _, removed) = rec.calls
    assert observed.collaboration is second, "the observer has the collaboration of its commit"
    assert removed.collaboration is second, (
        "its command runs with the collaboration it was sent under"
    )


async def test_a_finished_run_cannot_be_fed():  # D-11 b
    rec, (_, collaboration) = Recorder(), fakes()
    bus = MessageBus({Replace: rec.handler("h")}, {})
    await bus.handle(command(Replace), collaboration)
    [(_, _, work)] = rec.calls

    with pytest.raises(RuntimeError, match="finished"):
        await work.send(command(Remove))


async def test_a_handle_in_a_task_that_outlives_its_parent_starts_a_run_of_its_own():  # D-11 b
    rec, (_, collaboration) = Recorder(), fakes()
    tasks: list[asyncio.Task[object]] = []
    bus: MessageBus

    async def replace(cmd: Activity, work: Work) -> None:
        tasks.append(asyncio.create_task(bus.handle(command(Remove), collaboration)))

    async def remove(cmd: Activity, work: Work) -> str:
        await work.send(command(Add))
        return "removed"

    bus = MessageBus({Replace: replace, Remove: remove, Add: rec.handler("add")}, {})

    await bus.handle(command(Replace), collaboration)
    [result] = await asyncio.gather(*tasks)

    assert result == "removed", "the late handle ran"
    assert rec.names() == ["add"], "what it queued ran, in its own run"


async def test_the_limit_error_names_the_command_and_the_bus_logs_nothing(caplog):  # TC-31
    (_, collaboration), seen = fakes(), []
    bus: MessageBus

    async def replace(cmd: Activity, work: Work) -> None:
        seen.append(cmd)
        await bus.publish(cmd, work.session)

    async def again(activity: Activity, work: Work) -> None:
        await work.send(activity)

    bus = MessageBus({Replace: replace}, {Replace: [again]}, limits=LimitSettings(max_messages=2))

    with caplog.at_level(logging.DEBUG), pytest.raises(MessageLimitExceeded) as caught:
        await bus.handle(command(Replace), collaboration)

    assert str(caught.value) == f"message limit 2 reached by Replace {seen[0].id}", (
        "class and id of the command, in the exception"
    )
    assert caught.value.limit == 2, "the limit stays an attribute"
    assert not [r for r in caplog.records if r.name == "rdf_persistence.services.messagebus"], (
        "the bus raises; the place that handles the error logs it (PD-9)"
    )


async def test_unit_of_work_without_a_mapper_is_a_runtime_error():  # TC-80a
    rec, (_, collaboration) = Recorder(), fakes()
    bus = MessageBus({Replace: rec.handler("h")}, {})
    await bus.handle(command(Replace), collaboration)

    with pytest.raises(RuntimeError, match="mapper"):
        rec.calls[0][2].unit_of_work()


async def test_unit_of_work_is_on_the_works_session_with_the_buss_mapper():
    mapper, (session, collaboration) = toy_mapper(), fakes()
    rec = Recorder()
    await MessageBus({Replace: rec.handler("h")}, {}, mapper=mapper).handle(
        command(Replace), collaboration
    )

    unit = rec.calls[0][2].unit_of_work()

    assert isinstance(unit, UnitOfWork), "a UnitOfWork"
    assert unit._session is session, "on the work's session and mapper"
    assert unit._mapper is mapper, "on the work's session and mapper"


async def test_every_served_of_a_handlers_work_is_the_one_built_once():
    seen, built, (_, collaboration) = [], [], fakes()
    mapper = SimpleNamespace(served=lambda cmd: built.append(cmd) or object())

    async def handler(cmd: Activity, work: Work) -> None:
        seen.extend([work.served, work.served])

    async def observer(activity: Activity, work: Work) -> None:
        seen.append(work.served)

    bus = MessageBus({Replace: handler}, {Replace: [observer]}, mapper=mapper)
    cmd = command(Replace)
    await bus.handle(cmd, collaboration)
    await bus.publish(cmd, collaboration.session)

    assert built == [cmd], "the Served is built once, by the mapper"
    assert seen[0] is seen[1] is not None, "the handler's work holds one Served, built once"
    assert seen[2] is None, "an observer's work serves none"


async def test_tc36_each_command_run_is_a_handle_span_with_its_class_and_id(spans):  # PD-5
    rec, (_, collaboration) = Recorder(), fakes()
    first, second = command(Replace), command(Remove)

    async def replace(cmd: Activity, work: Work) -> None:
        await work.send(second)

    bus = MessageBus({Replace: replace, Remove: rec.handler("remove")}, {})

    await bus.handle(first, collaboration)

    handles = [s for s in spans() if s.name == "rp.bus.handle"]
    assert [dict(s.attributes) for s in handles] == [
        {"rp.step": "bus-handle", "rp.activity.class": "Replace", "rp.activity.id": first.id},
        {"rp.step": "bus-handle", "rp.activity.class": "Remove", "rp.activity.id": second.id},
    ], "a span per command run, the queued one included"


class Probe(BaseModel):
    count: int


async def test_a_validation_error_quoting_tenant_text_leaves_it_out_of_the_handle_span(spans):
    secret = "secret-tenant-text"  # D-10
    _, collaboration = fakes()

    async def failing(cmd: Activity, work: Work) -> None:
        Probe(count=secret)  # type: ignore[arg-type]

    bus = MessageBus({Replace: failing}, {})
    with pytest.raises(ValidationError) as raised:
        await bus.handle(command(Replace), collaboration)

    assert secret in str(raised.value), "the validation error does quote its input"
    (span,) = [s for s in spans() if s.name == "rp.bus.handle"]
    assert span.status.status_code is StatusCode.ERROR
    assert_no_text_in_spans([span], secret)


async def test_tc37_each_observer_is_an_observe_span_and_a_failing_one_is_error(spans):  # PD-5
    rec, (session, _) = Recorder(), fakes()

    async def failing(activity: Activity, work: Work) -> None:
        raise ValueError("boom")

    bus = MessageBus({}, {Replace: [failing, rec.observer("second")]})
    activity = command(Replace)

    await bus.publish(activity, session)

    observes = [s for s in spans() if s.name == "rp.bus.observe"]
    assert [s.attributes["rp.observer.name"] for s in observes] == [
        failing.__qualname__,
        "second",
    ], "a span per observer"
    assert [s.status.status_code for s in observes] == [StatusCode.ERROR, StatusCode.UNSET], (
        "only the first failed"
    )
    assert dict(observes[0].attributes) == {
        "rp.step": "bus-observe",
        "rp.observer.name": failing.__qualname__,
        "rp.activity.class": "Replace",
        "rp.activity.id": activity.id,
        "error.type": "builtins.ValueError",
    }, "the step, the observer, the activity and the error type"
    assert rec.names() == ["second"], "the second observer ran"
