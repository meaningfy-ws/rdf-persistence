"""The stream of one follower: filter, access re-read, resume, keep-alive, end (aggregate-events 3.1; PD-11, PD-12)."""

import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import pytest
from rdflib import Graph

from rdf_persistence.domain.exceptions import Forbidden, NotFound
from rdf_persistence.domain.generated.rp_provenance import Activity, Generation
from rdf_persistence.services.event_hub import EventHub
from rdf_persistence.services.event_stream import KEEP_ALIVE, RESET, event_stream

TENANT = "https://lib.example/tenant/t"
DUNE = "https://lib.example/book/dune"
EMMA = "https://lib.example/book/emma"
AT = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)
WEEK = timedelta(days=7)
TIMEOUT = 2.0


def activity(n: int, entity: str = DUNE) -> Activity:
    iri = f"https://lib.example/activity/a{n}"
    part = Generation(activity=iri, at_time=AT, entity=entity, entity_version=f"{entity}#{n}")
    return Activity(id=iri, generations=[part])


def all_readable(_: str) -> bool:
    return True


def all_but(*hidden: str) -> Callable[[str], bool]:
    return lambda iri: iri not in hidden


class Clock:
    def __init__(self) -> None:
        self.now = AT

    def __call__(self) -> datetime:
        return self.now


class Refreshes:
    """The access re-reader: counts its calls; answers what ``answer`` says, or raises it."""

    def __init__(self, answer: Callable[[str], bool] | Exception = all_readable) -> None:
        self.answer = answer
        self.calls = 0

    async def __call__(self) -> Callable[[str], bool]:
        self.calls += 1
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


class FakeSession:
    """A session that knows what ``relayed_since`` answers, and may offer to the hub while it reads."""

    def __init__(self, found: list[Activity] | None, during: Callable[[], None] = lambda: None):
        self.found, self.during, self.asked = found, during, []

    async def relayed_since(self, iri, window, now):
        self.asked.append((iri, window, now))
        self.during()
        return None if self.found is None else [(a.id, Graph()) for a in self.found]


def opener(session: FakeSession):
    @asynccontextmanager
    async def open_session() -> AsyncIterator[FakeSession]:
        yield session

    return open_session


def decoding(*known: Activity) -> Callable[[str, Graph], Activity]:
    by_iri = {a.id: a for a in known}
    return lambda iri, _graph: by_iri[iri]


def streaming(hub: EventHub, **given):
    wiring = {
        "may_read": all_readable,
        "refresh": Refreshes(),
        "open_session": opener(FakeSession([])),
        "decode": decoding(),
        "last_event_id": None,
        "window": WEEK,
        "access_ttl": timedelta(seconds=1),
        "keep_alive": 30.0,
        "clock": Clock(),
    }
    return event_stream(hub, TENANT, **{**wiring, **given})


async def next_of(stream) -> object:
    return await asyncio.wait_for(anext(stream), TIMEOUT)


async def until_subscribed(hub: EventHub) -> None:
    while not hub._queues:
        await asyncio.sleep(0)


async def first_of(stream, hub: EventHub) -> asyncio.Task:
    """Start waiting for the stream's next item, once it is subscribed."""
    task = asyncio.ensure_future(next_of(stream))
    await until_subscribed(hub)
    return task


async def test_a_live_activity_is_sent_with_the_parts_the_caller_may_read():  # TC-34
    hub = EventHub()
    stream = streaming(hub, may_read=all_but(EMMA))
    waiting = await first_of(stream, hub)
    both = activity(1).model_copy(
        update={"generations": activity(1).generations + activity(2, EMMA).generations}
    )
    hub.offer(TENANT, both)
    sent = await waiting
    assert isinstance(sent, Activity)
    assert [g.entity for g in sent.generations] == [DUNE], "one generation, the hidden one gone"
    await stream.aclose()


async def test_an_activity_with_no_visible_part_is_not_sent():  # TC-33
    hub = EventHub()
    stream = streaming(hub, may_read=all_but(DUNE))
    waiting = await first_of(stream, hub)
    hub.offer(TENANT, activity(1, DUNE))
    hub.offer(TENANT, activity(2, EMMA))
    sent = await waiting
    assert isinstance(sent, Activity) and sent.id == activity(2).id, "the other book's only"
    await stream.aclose()


async def test_the_events_of_another_tenant_are_not_heard():  # TC-40
    hub = EventHub()
    stream = streaming(hub, keep_alive=0.01)
    waiting = await first_of(stream, hub)
    hub.offer("https://lib.example/tenant/other", activity(1))
    assert await waiting == KEEP_ALIVE, "nothing but a keep-alive"
    await stream.aclose()


async def test_access_is_re_read_when_the_last_read_is_older_than_the_ttl_and_not_before():
    hub, clock, refresh = EventHub(), Clock(), Refreshes()
    stream = streaming(hub, clock=clock, refresh=refresh)
    waiting = await first_of(stream, hub)
    hub.offer(TENANT, activity(1))
    await waiting
    assert refresh.calls == 0, "fresh at connect"
    clock.now += timedelta(seconds=1)
    hub.offer(TENANT, activity(2))
    await next_of(stream)
    assert refresh.calls == 1, "a second later: re-read"
    hub.offer(TENANT, activity(3))
    await next_of(stream)
    assert refresh.calls == 1, "and fresh again"
    await stream.aclose()


async def test_what_the_caller_may_read_follows_the_latest_read_of_the_access():
    hub, clock = EventHub(), Clock()
    refresh = Refreshes(all_but(DUNE))  # a Prohibition arrived
    stream = streaming(hub, clock=clock, refresh=refresh)
    waiting = await first_of(stream, hub)
    clock.now += timedelta(seconds=2)
    hub.offer(TENANT, activity(1, DUNE))
    hub.offer(TENANT, activity(2, EMMA))
    sent = await waiting
    assert isinstance(sent, Activity) and sent.id == activity(2).id
    await stream.aclose()


@pytest.mark.parametrize("error", [Forbidden("no"), NotFound("gone")])
async def test_a_failed_re_read_before_an_event_ends_the_stream(error):  # TC-35
    hub, clock = EventHub(), Clock()
    stream = streaming(hub, clock=clock, refresh=Refreshes(error))
    waiting = await first_of(stream, hub)
    clock.now += timedelta(seconds=2)
    hub.offer(TENANT, activity(1))
    with pytest.raises(StopAsyncIteration):
        await waiting


async def test_a_failed_re_read_before_a_keep_alive_ends_the_stream():  # TC-35
    hub, clock = EventHub(), Clock()
    stream = streaming(hub, clock=clock, refresh=Refreshes(Forbidden("no")), keep_alive=0.01)
    waiting = await first_of(stream, hub)
    clock.now += timedelta(seconds=2)
    with pytest.raises(StopAsyncIteration):
        await waiting


async def test_a_re_read_that_fails_otherwise_is_not_swallowed():
    hub, clock = EventHub(), Clock()
    stream = streaming(hub, clock=clock, refresh=Refreshes(OSError("store down")))
    waiting = await first_of(stream, hub)
    clock.now += timedelta(seconds=2)
    hub.offer(TENANT, activity(1))
    with pytest.raises(OSError):
        await waiting


async def test_an_idle_stream_sends_a_keep_alive():
    hub = EventHub()
    stream = streaming(hub, keep_alive=0.01)
    assert await next_of(stream) == KEEP_ALIVE
    await stream.aclose()


async def test_a_full_queue_ends_the_stream():  # TC-36 (the hub's own test shows another subscriber keeps all)
    hub = EventHub(max_queue=2)
    stream = streaming(hub)
    waiting = await first_of(stream, hub)
    for n in (1, 2, 3):  # three in a row: the reader has not run
        hub.offer(TENANT, activity(n))

    async def rest() -> list:
        return [await waiting] + [item async for item in stream]

    got = await asyncio.wait_for(rest(), TIMEOUT)  # it ends by itself, not at the keep-alive
    assert all(isinstance(item, Activity) for item in got)
    assert len(got) < 3, "what it missed is not sent: it resumes with Last-Event-ID"


async def test_the_stream_without_a_last_event_id_opens_no_session():
    hub = EventHub()
    session = FakeSession([])
    stream = streaming(hub, open_session=opener(session), keep_alive=0.01)
    await next_of(stream)
    assert session.asked == []
    await stream.aclose()


async def test_a_resume_sends_what_was_relayed_since_then_the_live_events_none_twice():  # TC-37
    hub, clock = EventHub(), Clock()
    a2, a3, a4 = activity(2), activity(3), activity(4)
    # the relay offers a3 while the stream reads (it is in the buffer too), and a4 right after
    session = FakeSession([a2, a3], during=lambda: hub.offer(TENANT, a3))
    stream = streaming(
        hub,
        open_session=opener(session),
        decode=decoding(a2, a3, a4),
        last_event_id="https://lib.example/activity/a1",
        clock=clock,
    )
    assert (await next_of(stream)).id == a2.id
    assert (await next_of(stream)).id == a3.id
    hub.offer(TENANT, a4)
    assert (await next_of(stream)).id == a4.id, "a3 is not repeated from the buffer"
    assert session.asked == [("https://lib.example/activity/a1", WEEK, AT)]
    await stream.aclose()


async def test_an_activity_relayed_during_the_read_but_not_found_by_it_is_sent_once():  # TC-37a
    hub = EventHub()
    a0 = activity(0)
    session = FakeSession([], during=lambda: hub.offer(TENANT, a0))
    stream = streaming(hub, open_session=opener(session), last_event_id="x")
    assert (await next_of(stream)).id == a0.id
    await stream.aclose()


async def test_a_resume_filters_what_it_sends_and_does_not_send_it_live_either():  # TC-37b
    hub = EventHub()
    a2, a3 = activity(2, DUNE), activity(3, EMMA)
    session = FakeSession([a2, a3], during=lambda: hub.offer(TENANT, a2))
    stream = streaming(
        hub,
        may_read=all_but(DUNE),
        open_session=opener(session),
        decode=decoding(a2, a3),
        last_event_id="x",
    )
    assert (await next_of(stream)).id == a3.id, "a2 is about a book the caller may not read"
    await stream.aclose()


async def test_an_unknown_or_expired_id_sends_a_reset_then_the_live_events():  # TC-38
    hub = EventHub()
    stream = streaming(hub, open_session=opener(FakeSession(None)), last_event_id="gone")
    assert await next_of(stream) == RESET
    waiting = asyncio.ensure_future(next_of(stream))
    await asyncio.sleep(0)
    hub.offer(TENANT, activity(1))
    assert (await waiting).id == activity(1).id
    await stream.aclose()


async def test_the_subscription_ends_with_the_stream():
    hub = EventHub()
    stream = streaming(hub, keep_alive=0.01)
    await next_of(stream)
    await stream.aclose()
    assert not hub._queues
