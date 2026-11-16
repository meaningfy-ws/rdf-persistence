"""The server-sent events of a tenant: access, filter, resume, end (aggregate-events 3.1; PD-11, PD-12).

The stream is read straight off the ASGI app: ``httpx``'s in-process transport waits for the end of a
response, and these responses end only when the follower leaves.
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import APIRouter

from rdf_persistence import GrantSet
from rdf_persistence.domain.generated.rp_access import Action, Grant, Prohibition
from rdf_persistence.domain.generated.rp_provenance import Activity, Generation, Replace
from rdf_persistence.domain.iris import graph_iri
from rdf_persistence.domain.media import PROBLEM_JSON
from rdf_persistence.entrypoints.responses import CONTEXT_REL
from rdf_persistence.entrypoints.sse import add_events_route
from rdf_persistence.services.event_hub import EventHub
from tests.toy_service import DUNE_BODY, TENANT_BODY, ToyService, principal_of
from tests.unit.entrypoints.scene import Scene

TIMEOUT = 3.0
WEEK = timedelta(days=7)
KEEP_ALIVE = 0.05


@dataclass(frozen=True)
class Block:
    """One event of the stream as the wire spells it."""

    id: str | None = None
    event: str | None = None
    data: str | None = None
    comment: str | None = None


def parsed(text: str) -> Block:
    fields: dict[str, str] = {}
    for line in text.split("\n"):
        name, _, value = line.partition(":")
        fields["comment" if name == "" else name] = value.removeprefix(" ")
    return Block(**fields)


class Follow:
    """A client reading the stream of a path off the app: its status, headers, and events as they come."""

    def __init__(self, app, path: str, headers: dict[str, str]) -> None:
        self._app, self._chunks = app, asyncio.Queue()
        self._started, self._leave, self._asked = asyncio.Event(), asyncio.Event(), False
        self._text, self.status, self.headers = "", 0, {}
        raw = [(k.lower().encode(), v.encode()) for k, v in {"host": "test", **headers}.items()]
        self._scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "root_path": "",
            "headers": raw,
            "client": ("c", 1),
            "server": ("test", 80),
        }

    async def _receive(self) -> dict:
        if not self._asked:
            self._asked = True
            return {"type": "http.request", "body": b"", "more_body": False}
        await self._leave.wait()
        return {"type": "http.disconnect"}

    async def _send(self, message: dict) -> None:
        if message["type"] == "http.response.start":
            self.status = message["status"]
            self.headers = {k.decode(): v.decode() for k, v in message["headers"]}
            self._started.set()
        elif message["type"] == "http.response.body":
            self._chunks.put_nowait(message.get("body", b""))
            if not message.get("more_body", False):
                self._chunks.put_nowait(None)

    async def __aenter__(self) -> "Follow":
        self._task = asyncio.ensure_future(self._app(self._scope, self._receive, self._send))
        waiting = asyncio.ensure_future(self._started.wait())
        await asyncio.wait(
            {self._task, waiting}, timeout=TIMEOUT, return_when=asyncio.FIRST_COMPLETED
        )
        waiting.cancel()
        assert self._started.is_set(), "the app did not answer"
        return self

    async def __aexit__(self, *_: object) -> None:
        self._leave.set()
        _, pending = await asyncio.wait({self._task}, timeout=TIMEOUT)
        for task in pending:
            task.cancel()

    async def _block(self) -> str | None:
        """The next whole block of text, ``None`` at the end of the response."""
        while "\n\n" not in self._text:
            chunk = await self._chunks.get()
            if chunk is None:
                return None
            self._text += chunk.decode()
        block, _, self._text = self._text.partition("\n\n")
        return block

    async def take(self, n: int, *, timeout: float = TIMEOUT) -> list[Block]:
        """The next ``n`` events, keep-alive comments skipped; ``TimeoutError`` if they do not come."""

        async def gather() -> list[Block]:
            found: list[Block] = []
            while len(found) < n:
                block = await self._block()
                assert block is not None, f"the stream ended after {len(found)} of {n} events"
                if (event := parsed(block)).comment is None or event.id or event.event:
                    found.append(event)
            return found

        return await asyncio.wait_for(gather(), timeout)

    async def ends(self) -> list[Block]:
        """What is left of the stream, once the server ends it; ``TimeoutError`` if it does not."""

        async def gather() -> list[Block]:
            found: list[Block] = []
            while (block := await self._block()) is not None:
                if (event := parsed(block)).comment is None:
                    found.append(event)
            return found

        return await asyncio.wait_for(gather(), TIMEOUT)


async def listening(hub: EventHub, n: int = 1) -> None:
    """Until ``n`` followers are subscribed to ``hub``: the stream is reading from now on."""

    async def subscribed() -> None:
        while sum(len(queues) for queues in hub._queues.values()) < n:
            await asyncio.sleep(0)

    await asyncio.wait_for(subscribed(), TIMEOUT)


def mount(service: ToyService, prefix: str, **changes) -> str:
    """The route of the tenants' events again, under ``prefix``, with short times; its prefix."""
    router = APIRouter()
    settings = {
        "access_ttl": timedelta(0),
        "keep_alive": KEEP_ALIVE,
        "resume_window": WEEK,
        "clock": lambda: datetime.now(UTC),
        **changes,
    }
    add_events_route(router, service.kit, **settings)
    service.app.include_router(router, prefix=prefix)
    return prefix


@pytest.fixture
def fast(service: ToyService) -> str:
    return mount(service, "/fast")


@pytest.fixture
async def settled(scene: Scene) -> Scene:
    """The scene, with everything it committed already relayed: a follower hears only what follows."""
    await scene.service.kit.relay.run_once()
    return scene


def events_of(scene: Scene, prefix: str = "/fast") -> str:
    return f"{prefix}{scene.tenant}/rp-events"


def follow(scene: Scene, who: str = "rita", prefix: str = "/fast", **headers: str) -> Follow:
    return Follow(scene.service.app, events_of(scene, prefix), {**scene.headers(who), **headers})


async def replace(scene: Scene, path: str, etag: str, label: str) -> str:
    """Replace a book as ada, relay what that commits; the book's new ETag."""
    response = await scene.http.put(
        path,
        json={**DUNE_BODY, "label": label},
        headers=scene.headers("ada", **{"If-Match": etag}),
    )
    assert response.status_code == 200, response.text
    await scene.service.kit.relay.run_once()
    return response.headers["etag"]


async def another_book(scene: Scene) -> tuple[str, str, str]:
    """A second book: ``(IRI, path, ETag)``."""
    made = await scene.http.post(
        f"{scene.tenant}/books", json={**DUNE_BODY, "label": "Emma"}, headers=scene.headers("ada")
    )
    assert made.status_code == 201, made.text
    await scene.service.kit.relay.run_once()
    return made.json()["id"], made.headers["location"], made.headers["etag"]


async def reshape_grants(scene: Scene, edit: Callable[[GrantSet], GrantSet]) -> None:
    held = await scene.http.get(f"{scene.tenant}/grants", headers=scene.headers("ada"))
    scene.access_etag = held.headers["etag"]
    scene.access_etag = await scene.set_grants(edit(GrantSet.model_validate(held.json())))


def with_carol(*, hide: str | None = None) -> Callable[[GrantSet], GrantSet]:
    """Add carol as a reader of the tenant, barred from reading ``hide`` if given."""

    def edit(held: GrantSet) -> GrantSet:
        reader = Grant(assignee=principal_of("carol"), target=held.grants[0].target, role="reader")
        ban = [
            Prohibition(
                assignee=principal_of("carol"), target=str(graph_iri(hide)), action=Action.READ
            )
        ]
        return GrantSet(grants=[*held.grants, reader], prohibitions=ban if hide else None)

    return edit


def without_carol(held: GrantSet) -> GrantSet:
    keep = [g for g in held.grants or [] if g.assignee != principal_of("carol")]
    return GrantSet(grants=keep, prohibitions=None)


async def test_a_reader_hears_the_replace_of_a_book_with_its_id_class_and_json(
    settled: Scene, fast: str
) -> None:  # TC-32
    async with follow(settled) as bob:
        await listening(settled.service.kit.hub)
        await replace(settled, settled.book, settled.book_etag, "Dune Messiah")
        [event] = await bob.take(1)
    assert bob.status == 200, "the stream is served with 200"
    assert bob.headers["content-type"].startswith("text/event-stream"), (
        "the stream is an event stream"
    )
    assert bob.headers["link"] == f'<{settled.service.kit.context_url}>; rel="{CONTEXT_REL}"', (
        "the stream links to the JSON-LD context"
    )
    assert event.event == "Replace", "the class's name"
    sent = Replace.model_validate_json(event.data)
    assert event.id == sent.id, "the activity's IRI"
    assert [g.entity for g in sent.generations] == [settled.book_iri], (
        "the event names the replaced book only"
    )


async def test_the_default_route_is_served_with_the_link_and_no_event_before_a_commit(
    settled: Scene,
) -> None:
    async with follow(settled, prefix="") as bob:
        assert bob.status == 200, "the default route is served"
        assert "link" in bob.headers, "the stream links to the context"
        with pytest.raises(TimeoutError):
            await bob.take(1, timeout=0.2)


async def test_a_reader_barred_from_one_book_hears_only_the_other_books_event(
    settled: Scene, fast: str
) -> None:  # TC-33
    emma_iri, emma, emma_etag = await another_book(settled)
    await reshape_grants(settled, with_carol(hide=settled.book_iri))
    async with follow(settled, "carol") as carol:
        await listening(settled.service.kit.hub)
        await replace(settled, settled.book, settled.book_etag, "Dune Messiah")
        await replace(settled, emma, emma_etag, "Emma 2")
        [event] = await carol.take(1)
    assert [g.entity for g in Replace.model_validate_json(event.data).generations] == [emma_iri], (
        "a barred book's event is not heard"
    )


async def test_a_grant_removed_while_following_ends_the_stream_at_the_next_event(
    settled: Scene, fast: str
) -> None:  # TC-35
    await reshape_grants(settled, with_carol())
    async with follow(settled, "carol") as carol:
        await listening(settled.service.kit.hub)
        await reshape_grants(settled, without_carol)
        await replace(settled, settled.book, settled.book_etag, "Dune Messiah")
        assert await carol.ends() == [], "no event; the stream is over"


async def test_a_grant_removed_while_following_ends_the_stream_at_the_next_keep_alive(
    settled: Scene, fast: str
) -> None:  # TC-35
    await reshape_grants(settled, with_carol())
    async with follow(settled, "carol") as carol:
        await listening(settled.service.kit.hub)
        await reshape_grants(settled, without_carol)
        assert await carol.ends() == [], "no commit, and the stream is over"


async def test_a_full_queue_ends_the_stream_of_the_route(
    settled: Scene, fast: str
) -> None:  # TC-36
    settled.service.kit.hub = EventHub(max_queue=2)
    hub = settled.service.kit.hub
    part = Generation(
        activity="urn:uuid:a",
        at_time=datetime.now(UTC),
        entity=settled.book_iri,
        entity_version="v",
    )
    async with follow(settled) as bob:
        await listening(hub)
        for n in range(3):  # three in a row: the stream has not read
            hub.offer(settled.tenant_iri, Activity(id=f"urn:uuid:a{n}", generations=[part]))
        assert len(await bob.ends()) < 3, "ended by the hub, not at a keep-alive"


async def test_a_reader_whose_queue_filled_resumes_and_gets_every_missed_activity_once(
    settled: Scene, fast: str
) -> None:  # TC-36, D-14
    hub = settled.service.kit.hub
    hub._max_queue = 2
    async with follow(settled) as listener:
        await listening(hub)
        etag = settled.book_etag
        for label in ("One", "Two", "Three", "Four"):
            etag = await replace(settled, settled.book, etag, label)
        made = [Replace.model_validate_json(e.data) for e in await listener.take(4)]
    a1, *missed = made
    async with follow(settled) as bob:
        await listening(hub)
        hub.offer(settled.tenant_iri, a1)
        assert [e.id for e in await bob.take(1)] == [a1.id], "the first event is the first activity"
        for activity in missed:  # in a row: the stream has not read, the queue of two fills
            hub.offer(settled.tenant_iri, activity)
        assert await bob.ends() == [], "it got a1, then the stream ended"
    async with follow(settled, **{"Last-Event-ID": a1.id}) as again:
        assert [e.id for e in await again.take(3)] == [a.id for a in missed], (
            "a resume gets every missed activity in order"
        )


async def test_a_stream_ends_after_its_lifetime_and_a_resume_gets_what_came_after(
    settled: Scene, service: ToyService
) -> None:  # D-20
    now = [datetime.now(UTC)]
    mount(service, "/short", max_lifetime=timedelta(minutes=5), clock=lambda: now[0])
    async with follow(settled, prefix="/short") as bob:
        await listening(service.kit.hub)
        etag = await replace(settled, settled.book, settled.book_etag, "In time")
        [first] = await bob.take(1)
        now[0] += timedelta(minutes=6)
        etag = await replace(settled, settled.book, etag, "Too late")
        assert await bob.ends() == [], "the stream is over at the next wake, and sends nothing more"
    async with follow(settled, prefix="/short", **{"Last-Event-ID": first.id}) as again:
        [late] = await again.take(1)
    assert late.id != first.id, "a resumed stream sends a new activity, not the old one"
    assert late.event == "Replace", "the resumed event is a replace"


# One class for the characters an IRI forbids (a space stands for them); empty and long are boundaries.
@pytest.mark.parametrize("bad", ["a b", "", "x" * 300], ids=["space", "empty", "long"])
async def test_a_last_event_id_that_is_no_activity_id_sends_a_reset_and_the_stream_goes_on(
    settled: Scene, fast: str, bad: str, caplog: pytest.LogCaptureFixture
) -> None:  # D-21
    async with follow(settled, **{"Last-Event-ID": bad}) as bob:
        assert bob.status == 200, "a stream with an unknown last event id is still served"
        [reset] = await bob.take(1)
        assert reset.event == "reset", "an unknown last event id gets a reset event"
        assert reset.id is None, "a reset event carries no id"
        assert reset.data == "", "an empty data line, or an EventSource client drops it (D-10)"
        await listening(settled.service.kit.hub)
        await replace(settled, settled.book, settled.book_etag, "Live")
        [live] = await bob.take(1)
    assert live.event == "Replace", "the live event after a reset is a replace"
    assert not [r for r in caplog.records if r.levelname in ("ERROR", "CRITICAL")], (
        "the reset logs no error"
    )


async def test_a_resume_sends_what_was_relayed_after_the_id_then_live_events_none_twice(
    settled: Scene, fast: str
) -> None:  # TC-37
    async with follow(settled) as listener:
        await listening(settled.service.kit.hub)
        etag = await replace(settled, settled.book, settled.book_etag, "One")
        etag = await replace(settled, settled.book, etag, "Two")
        etag = await replace(settled, settled.book, etag, "Three")
        a1, a2, a3 = [e.id for e in await listener.take(3)]
        async with follow(settled, **{"Last-Event-ID": a1}) as bob:
            assert [e.id for e in await bob.take(2)] == [a2, a3], (
                "a resume sends what was relayed after the id"
            )
            await replace(settled, settled.book, etag, "Four")
            [a4] = await bob.take(1)
    assert a4.id not in (a1, a2, a3), "a resume does not repeat an activity already sent"


async def test_an_activity_relayed_after_the_named_one_is_sent_though_applied_before(
    settled: Scene, fast: str, monkeypatch: pytest.MonkeyPatch
) -> None:  # TC-37a
    kit = settled.service.kit

    async def not_now() -> None:
        return None

    monkeypatch.setattr(kit.relay, "run_once", not_now)  # the commits stay pending
    etag = settled.book_etag
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
    async with follow(settled, **{"Last-Event-ID": second}) as bob:
        [event] = await bob.take(1)
    assert event.id == first, "the event sent is the one relayed after the named id"


async def test_a_resume_does_not_send_what_the_caller_may_not_read(
    settled: Scene, fast: str
) -> None:  # TC-37b
    emma_iri, emma, emma_etag = await another_book(settled)
    await reshape_grants(settled, with_carol(hide=settled.book_iri))
    async with follow(settled, "rita") as witness:
        await listening(settled.service.kit.hub)
        etag = await replace(settled, settled.book, settled.book_etag, "Hidden from carol")
        await replace(settled, emma, emma_etag, "Open to carol")
        a2, a3 = [e.id for e in await witness.take(2)]
        async with follow(settled, "carol", **{"Last-Event-ID": a2}) as carol:
            [event] = await carol.take(1)
            assert event.id == a3, "the event sent is the one the caller may read"
            with pytest.raises(TimeoutError):
                await carol.take(1, timeout=0.2)
    assert etag, "the write that produced the activity returned a version"


async def test_an_id_that_cannot_anchor_a_resume_sends_one_reset_then_the_live_events(
    settled: Scene, fast: str
) -> None:  # TC-38
    async with follow(settled, **{"Last-Event-ID": "urn:uuid:nobody"}) as bob:
        [reset] = await bob.take(1)
        assert reset.event == "reset", "an unanchored resume gets a reset event"
        assert reset.id is None, "a reset event carries no id"
        await listening(settled.service.kit.hub)
        await replace(settled, settled.book, settled.book_etag, "Live")
        [live] = await bob.take(1)
    assert live.event == "Replace", "the live event after the reset is a replace"


async def test_an_id_relayed_before_the_window_sends_a_reset(
    settled: Scene, fast: str, service: ToyService
) -> None:  # TC-38
    mount(service, "/late", clock=lambda: datetime.now(UTC) + timedelta(days=8))
    async with follow(settled) as listener:
        await listening(service.kit.hub)
        await replace(settled, settled.book, settled.book_etag, "Old news")
        [old] = await listener.take(1)
    async with follow(settled, prefix="/late", **{"Last-Event-ID": old.id}) as bob:
        [reset] = await bob.take(1)
    assert reset.event == "reset", "relayed eight days ago, seen from the clock of the route"


async def test_an_id_never_relayed_sends_a_reset(
    settled: Scene, fast: str, monkeypatch: pytest.MonkeyPatch
) -> None:  # TC-38
    kit = settled.service.kit

    async def not_now() -> None:
        return None

    monkeypatch.setattr(kit.relay, "run_once", not_now)
    await settled.http.put(
        settled.book,
        json={**DUNE_BODY, "label": "Pending"},
        headers=settled.headers("ada", **{"If-Match": settled.book_etag}),
    )
    async with kit.session(settled.tenant_iri, kit.tenancy.toolkit.id) as session:
        [(pending, _)] = await session.pending_activities()
    async with follow(settled, **{"Last-Event-ID": pending}) as bob:
        [reset] = await bob.take(1)
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
    settled: Scene, fast: str
) -> None:  # TC-40
    other = await settled.http.post("/libraries", json=TENANT_BODY, headers=settled.headers("ada"))
    elsewhere = other.headers["location"]
    async with Follow(
        settled.service.app, f"/fast{elsewhere}/rp-events", settled.headers("ada")
    ) as ada:
        await listening(settled.service.kit.hub)
        await replace(settled, settled.book, settled.book_etag, "Not for you")
        with pytest.raises(TimeoutError):
            await ada.take(1, timeout=0.3)
