"""The server-sent events of a tenant: access, filter, resume, end (aggregate-events 3.1; PD-11, PD-12).

The stream is read with the testkit's ``open_event_stream``: ``httpx``'s in-process transport waits for
the end of a response, and these responses end only when the follower leaves.
"""

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest

from rdf_persistence import GrantSet
from rdf_persistence.access.domain.generated.rp_access import Action, Grant, Prohibition
from rdf_persistence.api.entrypoints.responses import CONTEXT_REL
from rdf_persistence.core.domain.media import PROBLEM_JSON
from rdf_persistence.events.services.event_hub import EventHub
from rdf_persistence.events.services.generated.settings.rp_events_settings import EventSettings
from rdf_persistence.iris.services.generated.rp_iris_services import IriPolicy
from rdf_persistence.provenance.domain.generated.rp_provenance import Activity, Generation, Replace
from rdf_persistence.testkit import open_event_stream
from tests.events_follow import (
    FOLLOW_TIMEOUT,
    another_book,
    drained,
    events_of,
    listening,
    mount,
    opening,
    replace,
    reshape_grants,
    short_times,
    with_carol,
)
from tests.scene import Scene
from tests.toy_service import DUNE_BODY, TENANT_BODY, ToyService, principal_of


@pytest.fixture
async def streams() -> AsyncIterator[set[asyncio.Task]]:
    """The streams a test opened; one the test left pending is cancelled and awaited at teardown (PD-8)."""
    opened: set[asyncio.Task] = set()
    yield opened
    for task in opened:
        if not task.done():
            task.cancel()
    await asyncio.gather(*opened, return_exceptions=True)


@pytest.fixture
def fast(service: ToyService) -> str:
    return mount(service, "/fast")


@pytest.fixture
async def settled(scene: Scene) -> Scene:
    """The scene, with everything it committed already relayed: a follower hears only what follows."""
    await scene.service.kit.relay.run_once()
    return scene


def without_carol(held: GrantSet) -> GrantSet:
    keep = [g for g in held.grants or [] if g.assignee != principal_of("carol")]
    return GrantSet(grants=keep, prohibitions=None)


async def test_a_reader_hears_the_replace_of_a_book_with_its_id_class_and_json(
    settled: Scene, fast: str, streams: set[asyncio.Task]
) -> None:  # TC-32
    bob = opening(streams, settled, "rita", "/fast", events=1)
    await listening(settled.service.kit.hub)
    await replace(settled, settled.book, settled.book_etag, "Dune Messiah")
    opened = await bob
    [event] = opened.events
    assert opened.status == 200, "the stream is served with 200"
    assert opened.headers["content-type"].startswith("text/event-stream"), (
        "the stream is an event stream"
    )
    assert opened.headers["link"] == f'<{settled.service.kit.context_url}>; rel="{CONTEXT_REL}"', (
        "the stream links to the JSON-LD context"
    )
    assert event.event == "Replace", "the class's name"
    sent = Replace.model_validate_json(event.data)
    assert event.id == sent.id, "the activity's IRI"
    assert [g.entity for g in sent.generations] == [settled.book_iri], (
        "the event names the replaced book only"
    )


async def test_the_default_route_is_served_with_the_link_and_no_event_before_a_commit(
    settled: Scene, streams: set[asyncio.Task]
) -> None:
    bob = opening(streams, settled, prefix="", events=1)
    await listening(settled.service.kit.hub)
    await replace(settled, settled.book, settled.book_etag, "The first commit")
    opened = await bob
    assert opened.status == 200, "the default route is served"
    assert "link" in opened.headers, "the stream links to the context"
    [first] = opened.events
    assert first.event == "Replace", "the first event is the commit: none came before it"
    assert [g.entity for g in Replace.model_validate_json(first.data).generations] == [
        settled.book_iri
    ], "the first event is the sentinel's own commit, of the book"


async def test_a_reader_barred_from_one_book_hears_only_the_other_books_event(
    settled: Scene, fast: str, streams: set[asyncio.Task]
) -> None:  # TC-33
    emma_iri, emma, emma_etag = await another_book(settled)
    await reshape_grants(settled, with_carol(hide=settled.book_iri))
    carol = opening(streams, settled, "carol", events=1)
    await listening(settled.service.kit.hub)
    await replace(settled, settled.book, settled.book_etag, "Dune Messiah")
    await replace(settled, emma, emma_etag, "Emma 2")
    [event] = (await carol).events
    assert [g.entity for g in Replace.model_validate_json(event.data).generations] == [emma_iri], (
        "a barred book's event is not heard"
    )


async def test_a_grant_removed_while_following_ends_the_stream_at_the_next_event(
    settled: Scene, fast: str, streams: set[asyncio.Task]
) -> None:  # TC-35
    await reshape_grants(settled, with_carol())
    carol = opening(streams, settled, "carol", events=3)  # more than comes
    await listening(settled.service.kit.hub)
    await reshape_grants(settled, without_carol)
    await replace(settled, settled.book, settled.book_etag, "Dune Messiah")
    assert (await carol).events == [], "no event; the stream is over"


async def test_a_grant_removed_while_following_ends_the_stream_at_the_next_keep_alive(
    settled: Scene, streams: set[asyncio.Task]
) -> None:  # TC-35
    # 0.001 s is the least the route allows: the keep-alive comes at once, no wait for it
    idle = mount(settled.service, "/idle", sse=short_times(keep_alive_seconds=0.001))
    await reshape_grants(settled, with_carol())
    carol = opening(streams, settled, "carol", idle, events=3)  # more than comes
    await listening(settled.service.kit.hub)
    await reshape_grants(settled, without_carol)
    assert (await carol).events == [], "no commit, and the stream is over"


async def test_a_full_queue_ends_the_stream_of_the_route(
    settled: Scene, fast: str, streams: set[asyncio.Task]
) -> None:  # TC-36
    settled.service.kit.hub = EventHub(events=EventSettings(hub_queue_size=2))
    hub = settled.service.kit.hub
    part = Generation(
        activity="urn:uuid:a",
        at_time=datetime.now(UTC),
        entity=settled.book_iri,
        entity_version="v",
    )
    bob = opening(streams, settled, events=3)  # more than comes
    await listening(hub)
    for n in range(3):  # three in a row: the stream has not read
        hub.offer(settled.tenant_iri, Activity(id=f"urn:uuid:a{n}", generations=[part]))
    assert len((await bob).events) < 3, "ended by the hub, not at a keep-alive"


async def test_a_reader_whose_queue_filled_resumes_and_gets_every_missed_activity_once(
    settled: Scene, fast: str, streams: set[asyncio.Task]
) -> None:  # TC-36, D-14
    hub = settled.service.kit.hub
    hub._max_queue = 2
    listener = opening(streams, settled, events=4)
    await listening(hub)
    etag = settled.book_etag
    for label in ("One", "Two", "Three", "Four"):
        etag = await replace(settled, settled.book, etag, label)
    made = [Replace.model_validate_json(e.data) for e in (await listener).events]
    a1, *missed = made
    bob = opening(streams, settled, events=3)  # more than comes: the stream ends after a1
    await listening(hub)
    hub.offer(settled.tenant_iri, a1)
    await drained(hub)  # the stream took a1 first
    for activity in missed:  # in a row: the stream has not read, the queue of two fills
        hub.offer(settled.tenant_iri, activity)
    assert [e.id for e in (await bob).events] == [a1.id], "it got a1, then the stream ended"
    again = opening(streams, settled, events=3, **{"Last-Event-ID": a1.id})
    assert [e.id for e in (await again).events] == [a.id for a in missed], (
        "a resume gets every missed activity in order"
    )


async def test_a_stream_ends_after_its_lifetime_and_a_resume_gets_what_came_after(
    settled: Scene, service: ToyService, streams: set[asyncio.Task]
) -> None:  # D-20
    now = [datetime.now(UTC)]
    mount(
        service,
        "/short",
        sse=short_times(max_lifetime_seconds=timedelta(minutes=5).total_seconds()),
        clock=lambda: now[0],
    )
    bob = opening(streams, settled, prefix="/short", events=3)  # more than comes
    await listening(service.kit.hub)
    etag = await replace(settled, settled.book, settled.book_etag, "In time")
    await drained(service.kit.hub)  # the stream took the first event before the clock moves
    now[0] += timedelta(minutes=6)
    etag = await replace(settled, settled.book, etag, "Too late")
    [first] = (await bob).events  # over at the next wake, and nothing more sent
    again = opening(streams, settled, prefix="/short", events=1, **{"Last-Event-ID": first.id})
    [late] = (await again).events
    assert late.id != first.id, "a resumed stream sends a new activity, not the old one"
    assert late.event == "Replace", "the resumed event is a replace"


# Class: the characters an IRI forbids (a space stands for them); empty and long are boundaries.
@pytest.mark.parametrize("bad", ["a b", "", "x" * 300], ids=["space", "empty", "long"])
async def test_a_last_event_id_that_is_no_activity_id_sends_a_reset_and_the_stream_goes_on(
    settled: Scene,
    fast: str,
    bad: str,
    caplog: pytest.LogCaptureFixture,
    streams: set[asyncio.Task],
) -> None:  # D-21
    bob = opening(streams, settled, events=2, **{"Last-Event-ID": bad})
    await listening(settled.service.kit.hub)
    await replace(settled, settled.book, settled.book_etag, "Live")
    opened = await bob
    assert opened.status == 200, "a stream with an unknown last event id is still served"
    reset, live = opened.events
    assert reset.event == "reset", "an unknown last event id gets a reset event"
    assert reset.id is None, "a reset event carries no id"
    assert reset.data == "", "an empty data line, or an EventSource client drops it (D-10)"
    assert live.event == "Replace", "the live event after a reset is a replace"
    assert not [r for r in caplog.records if r.levelname in ("ERROR", "CRITICAL")], (
        "the reset logs no error"
    )


async def test_a_resume_sends_what_was_relayed_after_the_id_then_live_events_none_twice(
    settled: Scene, fast: str, streams: set[asyncio.Task]
) -> None:  # TC-37
    listener = opening(streams, settled, events=3)
    await listening(settled.service.kit.hub)
    etag = await replace(settled, settled.book, settled.book_etag, "One")
    etag = await replace(settled, settled.book, etag, "Two")
    etag = await replace(settled, settled.book, etag, "Three")
    a1, a2, a3 = [e.id for e in (await listener).events]
    bob = opening(streams, settled, events=4, **{"Last-Event-ID": a1})
    witness = opening(streams, settled, "rita", events=2)  # hears the two live events as committed
    await listening(settled.service.kit.hub, 2)  # the replay is sent once it is subscribed
    etag = await replace(settled, settled.book, etag, "Four")
    await replace(settled, settled.book, etag, "Five")
    a4, a5 = [e.id for e in (await witness).events]
    got = [e.id for e in (await bob).events]
    assert got == [a2, a3, a4, a5], "the replay in commit order, then both live events, none twice"
    assert len(set(got)) == 4, "four distinct activities"
    assert a1 not in got, "the named one is not sent again"


async def test_an_activity_relayed_after_the_named_one_is_sent_though_applied_before(
    settled: Scene, fast: str, streams: set[asyncio.Task]
) -> None:  # TC-37a
    kit = settled.service.kit
    etag = settled.book_etag
    async with kit.relay.paused():  # the commits stay pending
        for label in ("Applied first", "Applied second"):
            response = await settled.http.put(
                settled.book,
                json={**DUNE_BODY, "label": label},
                headers=settled.headers("ada", **{"If-Match": etag}),
            )
            etag = response.headers["etag"]
        async with kit.session(settled.tenant_iri, kit.tenancy.toolkit.id) as session:
            first, second = [iri for iri, _ in await session.pending_activities()]
            await session.mark_relayed(second)  # relayed first
            await session.mark_relayed(first)  # relayed last
        bob = opening(streams, settled, events=1, **{"Last-Event-ID": second})
        [event] = (await bob).events
    assert event.id == first, "the event sent is the one relayed after the named id"


async def test_a_resume_does_not_send_what_the_caller_may_not_read(
    settled: Scene, fast: str, streams: set[asyncio.Task]
) -> None:  # TC-37b
    emma_iri, emma, emma_etag = await another_book(settled)
    await reshape_grants(settled, with_carol(hide=settled.book_iri))
    witness = opening(streams, settled, "rita", events=3)
    await listening(settled.service.kit.hub)
    emma_etag = await replace(settled, emma, emma_etag, "Open to carol")  # a1, visible, the anchor
    # a2 is hidden from carol and in her replay; a3, the sentinel, is visible and committed after it
    await replace(settled, settled.book, settled.book_etag, "Hidden from carol")
    await replace(settled, emma, emma_etag, "Sentinel")
    a1, a2, a3 = [e.id for e in (await witness).events]
    carol = opening(streams, settled, "carol", events=1, **{"Last-Event-ID": a1})
    [resumed] = (await carol).events
    assert resumed.id != a2, "the hidden replace, in the replay, is not sent"
    assert resumed.id == a3, "the event sent is the sentinel, the next one the caller may read"
    assert [g.entity for g in Replace.model_validate_json(resumed.data).generations] == [
        emma_iri
    ], "the sentinel replaced the visible book"


@pytest.fixture
async def under_policy() -> AsyncIterator[Scene]:
    """A scene on a service whose activities are placed under the tenant (activity-iri-policy PD-7)."""
    toy = ToyService(iri_policy=IriPolicy(activity_template="{tenant}/activity/{id}"))
    async with toy.app.router.lifespan_context(toy.app), toy.client() as http:
        scene = await Scene.set_up(toy, http)
        await toy.kit.relay.run_once()
        mount(toy, "/fast")
        yield scene


async def test_a_follower_resumes_after_an_activity_iri_of_the_policy(
    under_policy: Scene, streams: set[asyncio.Task]
) -> None:  # PD-7, PD-11
    scene = under_policy
    listener = opening(streams, scene, events=3)
    await listening(scene.service.kit.hub)
    etag = scene.book_etag
    for label in ("One", "Two", "Three"):
        etag = await replace(scene, scene.book, etag, label)
    a1, a2, a3 = [e.id for e in (await listener).events]
    assert a1.startswith(f"{scene.tenant_iri}/activity/"), "the activity sits under the tenant"
    resumed = opening(streams, scene, events=2, **{"Last-Event-ID": a1})
    assert [e.id for e in (await resumed).events] == [a2, a3], (
        "the two later events, once each, in order"
    )
    stale = opening(
        streams, scene, events=1, **{"Last-Event-ID": "urn:uuid:" + a1.rsplit("/", 1)[1]}
    )
    [reset] = (await stale).events
    assert reset.event == "reset", "a urn:uuid id under the policy is reset"


async def test_an_id_that_cannot_anchor_a_resume_sends_one_reset_then_the_live_events(
    settled: Scene, fast: str, streams: set[asyncio.Task]
) -> None:  # TC-38
    bob = opening(streams, settled, events=2, **{"Last-Event-ID": "urn:uuid:nobody"})
    await listening(settled.service.kit.hub)
    await replace(settled, settled.book, settled.book_etag, "Live")
    reset, live = (await bob).events
    assert reset.event == "reset", "an unanchored resume gets a reset event"
    assert reset.id is None, "a reset event carries no id"
    assert live.event == "Replace", "the live event after the reset is a replace"


async def test_an_id_relayed_before_the_window_sends_a_reset(
    settled: Scene, fast: str, service: ToyService, streams: set[asyncio.Task]
) -> None:  # TC-38
    mount(service, "/late", clock=lambda: datetime.now(UTC) + timedelta(days=8))
    listener = opening(streams, settled, events=1)
    await listening(service.kit.hub)
    await replace(settled, settled.book, settled.book_etag, "Old news")
    [old] = (await listener).events
    bob = opening(streams, settled, prefix="/late", events=1, **{"Last-Event-ID": old.id})
    [reset] = (await bob).events
    assert reset.event == "reset", "relayed eight days ago, seen from the clock of the route"


async def test_an_id_never_relayed_sends_a_reset(
    settled: Scene, fast: str, streams: set[asyncio.Task]
) -> None:  # TC-38
    kit = settled.service.kit
    async with kit.relay.paused():  # the commit stays pending, so the id is never relayed
        await settled.http.put(
            settled.book,
            json={**DUNE_BODY, "label": "Pending"},
            headers=settled.headers("ada", **{"If-Match": settled.book_etag}),
        )
        async with kit.session(settled.tenant_iri, kit.tenancy.toolkit.id) as session:
            [(pending, _)] = await session.pending_activities()
        bob = opening(streams, settled, events=1, **{"Last-Event-ID": pending})
        [reset] = (await bob).events
    assert reset.event == "reset", "an unknown id gets a reset event"


async def test_a_caller_barred_from_reading_the_tenant_gets_a_403_problem_and_no_stream(
    settled: Scene, fast: str
) -> None:  # TC-39
    reader = Grant(assignee=principal_of("dan"), target=settled.tenant_iri, role="reader")
    ban = Prohibition(assignee=principal_of("dan"), target=settled.tenant_iri, action=Action.READ)
    await reshape_grants(
        settled, lambda held: GrantSet(grants=[*held.grants, reader], prohibitions=[ban])
    )
    response = await settled.http.get(events_of(settled), headers=settled.headers("dan"))
    assert response.status_code == 403, "a caller barred from the tenant gets 403"
    assert response.headers["content-type"] == PROBLEM_JSON, "the refusal is a problem document"


async def test_no_token_is_a_401_problem(settled: Scene, fast: str) -> None:
    response = await settled.http.get(events_of(settled))
    assert response.status_code == 401, "a call without a token gets 401"
    assert response.headers["content-type"] == PROBLEM_JSON, "the refusal is a problem document"


async def test_the_follower_of_another_tenant_hears_nothing(
    settled: Scene, fast: str, streams: set[asyncio.Task]
) -> None:  # TC-40
    other = await settled.http.post("/libraries", json=TENANT_BODY, headers=settled.headers("ada"))
    elsewhere = other.headers["location"]
    ada = asyncio.ensure_future(
        open_event_stream(
            settled.service.app,
            f"/fast{elsewhere}/rp-events",
            headers=settled.headers("ada"),
            events=1,
            timeout=FOLLOW_TIMEOUT,
        )
    )
    streams.add(ada)
    await listening(settled.service.kit.hub)
    await replace(settled, settled.book, settled.book_etag, "Not for you")
    made = await settled.http.post(
        f"{elsewhere}/books",
        json={**DUNE_BODY, "label": "Sentinel"},
        headers=settled.headers("ada"),
    )  # visible to ada there, committed after the other tenant's replace
    assert made.status_code == 201, made.text
    await settled.service.kit.relay.run_once()
    [first] = (await ada).events
    assert [g.entity for g in Activity.model_validate_json(first.data).generations] == [
        made.json()["id"]
    ], "the first event is the sentinel: nothing of the other tenant came before it"
