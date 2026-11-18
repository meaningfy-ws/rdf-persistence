"""The in-process hub: per-tenant bounded queues, a full one closed (PD-9; TC-36)."""

import asyncio

from rdf_persistence.core.domain.generated.rp_provenance import Activity
from rdf_persistence.events.services.event_hub import CLOSED, EventHub
from rdf_persistence.events.services.generated.settings.rp_events_settings import EventSettings

TENANT = "https://lib.example/tenant/a"
OTHER = "https://lib.example/tenant/b"


def _activity(n: int) -> Activity:
    return Activity(id=f"https://lib.example/activity/{n}")


def _drain(queue: asyncio.Queue) -> list:
    items = []
    while not queue.empty():
        items.append(queue.get_nowait())
    return items


def test_an_offer_reaches_every_subscriber_of_the_tenant_and_no_other():
    async def scenario():
        hub = EventHub()
        async with (
            hub.subscribe(TENANT) as first,
            hub.subscribe(TENANT) as second,
            hub.subscribe(OTHER) as elsewhere,
        ):
            hub.offer(TENANT, _activity(1))
            return _drain(first), _drain(second), _drain(elsewhere)

    first, second, elsewhere = asyncio.run(scenario())

    assert [a.id for a in first] == [a.id for a in second] == ["https://lib.example/activity/1"], (
        "every subscriber of the tenant gets the offered activity"
    )
    assert elsewhere == [], "a subscriber of another tenant gets nothing"


def test_a_full_queue_is_closed_and_a_reader_of_another_gets_all_of_them():
    async def scenario():
        hub = EventHub(events=EventSettings(hub_queue_size=2))
        async with hub.subscribe(TENANT) as slow, hub.subscribe(TENANT) as fast:
            got = []
            for n in range(3):
                hub.offer(TENANT, _activity(n))
                got.extend(_drain(fast))
            hub.offer(TENANT, _activity(3))  # the closed queue is no longer fed
            return _drain(slow), got + _drain(fast)

    slow, fast = asyncio.run(scenario())

    assert slow[-1] is CLOSED, "the full queue ends with the closing marker"
    assert CLOSED not in fast, "the reader that kept up gets no closing marker"
    assert len(fast) == 4, "the reader that kept up gets every activity"


def test_a_closed_queue_holds_only_the_sentinel():  # D-14
    async def scenario():
        hub = EventHub(events=EventSettings(hub_queue_size=2))
        async with hub.subscribe(TENANT) as queue:
            for n in range(3):
                hub.offer(TENANT, _activity(n))
            return _drain(queue)

    assert asyncio.run(scenario()) == [CLOSED], "no activity after a gap the reader cannot see"


def test_a_closed_queue_ends_its_reader_even_when_it_was_full():  # TC-38
    async def scenario():
        hub = EventHub(events=EventSettings(hub_queue_size=1))
        async with hub.subscribe(TENANT) as queue:
            hub.offer(TENANT, _activity(1))
            hub.offer(TENANT, _activity(2))
            return await asyncio.wait_for(queue.get(), timeout=1)

    assert asyncio.run(scenario()) is CLOSED, (
        "the full queue still ends its reader with the closing marker"
    )


def test_a_subscriber_is_removed_on_exit():
    async def scenario():
        hub = EventHub()
        async with hub.subscribe(TENANT) as queue:
            pass
        hub.offer(TENANT, _activity(1))
        return queue.empty(), hub

    empty, hub = asyncio.run(scenario())

    assert empty, "an offer after the exit does not reach the subscriber's queue"
    assert not hub._queues.get(TENANT), "the subscriber is removed on exit"


def test_a_subscriber_is_removed_when_the_reader_fails():
    async def scenario():
        hub = EventHub()
        try:
            async with hub.subscribe(TENANT):
                raise RuntimeError("client gone")
        except RuntimeError:
            pass
        return hub

    assert not asyncio.run(scenario())._queues.get(TENANT), (
        "the subscriber is removed when its reader fails"
    )
