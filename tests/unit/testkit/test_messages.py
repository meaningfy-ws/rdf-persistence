"""``testkit.RecordingObserver``: an observer that keeps the activities it got (message-bus PD-22)."""

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast

from rdf_persistence.core.domain.generated.rp_provenance import Activity, Add, Replace
from rdf_persistence.services.messagebus import MessageBus, Work, _name
from rdf_persistence.testkit import RecordingObserver

NOW = datetime(2026, 11, 15, 10, 0, tzinfo=UTC)


class ShelvedReplace(Replace):
    """A consumer's subclass of a standard activity."""


def activity(cls: type[Activity], n: int) -> Activity:
    return cls(id=f"https://example.org/activity/{n}", started_at_time=NOW, ended_at_time=NOW)


WORK = cast(Work, SimpleNamespace(name="work"))


async def test_it_records_the_activities_in_call_order() -> None:
    observer = RecordingObserver()
    first, second = activity(Replace, 1), activity(Add, 2)

    await observer(first, WORK)
    await observer(second, WORK)

    assert observer.activities == [first, second], "activities are recorded in call order"


async def test_of_keeps_the_instances_of_a_class_including_subclasses() -> None:
    observer = RecordingObserver()
    plain, shelved, added = activity(Replace, 1), activity(ShelvedReplace, 2), activity(Add, 3)
    for item in (plain, shelved, added):
        await observer(item, WORK)

    assert observer.of(Replace) == [plain, shelved], (
        "of a class keeps its instances and its subclasses'"
    )
    assert observer.of(ShelvedReplace) == [shelved], "of a subclass keeps only that subclass"
    assert observer.of(Add) == [added], "of another class keeps only its own"


async def test_a_bus_publish_reaches_it() -> None:
    observer = RecordingObserver()
    bus = MessageBus(commands={}, observers={Activity: [observer]})
    shelved = activity(ShelvedReplace, 1)
    session = cast(Any, SimpleNamespace(name="session"))

    await bus.publish(shelved, session)

    assert observer.activities == [shelved], "a bus publish reaches the observer"


def test_its_name_in_a_log_is_readable() -> None:
    assert "RecordingObserver" in _name(RecordingObserver()), (
        "the observer's name is readable in a log"
    )
