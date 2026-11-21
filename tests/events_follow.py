"""Following a tenant's events over the toy service: what the route tests and the feature share.

The stream is read with the testkit's ``open_event_stream``: ``httpx``'s in-process transport waits for
the end of a response, and these responses end only when the follower leaves.
"""

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter

from rdf_persistence import GrantSet
from rdf_persistence.access.domain.generated.rp_access import Action, Grant, Prohibition
from rdf_persistence.api.entrypoints.generated.settings.rp_api_settings import SseSettings
from rdf_persistence.api.entrypoints.sse import add_events_route
from rdf_persistence.events.services.event_hub import EventHub
from rdf_persistence.iris.domain.layout import graph_iri
from rdf_persistence.testkit import OpenedStream, open_event_stream
from tests.toy_service import DUNE_BODY, ToyService, principal_of
from tests.unit.api.scene import Scene

TIMEOUT = 3.0
# The deadline of ``open_event_stream`` runs from the call, so it also covers the test's own commits; a
# passing stream returns as soon as its events came, so the bound costs nothing when green.
FOLLOW_TIMEOUT = 30.0
WEEK = timedelta(days=7)
KEEP_ALIVE = 0.05


async def listening(hub: EventHub, n: int = 1) -> None:
    """Until ``n`` followers are subscribed to ``hub``: the stream is reading from now on."""

    async def subscribed() -> None:
        while sum(len(queues) for queues in hub._queues.values()) < n:
            await asyncio.sleep(0)

    await asyncio.wait_for(subscribed(), TIMEOUT)


async def drained(hub: EventHub) -> None:
    """Until every follower of ``hub`` has taken what was offered: its first item is dequeued first."""

    async def empty() -> None:
        while any(queue.qsize() for queues in hub._queues.values() for queue in queues):
            await asyncio.sleep(0)

    await asyncio.wait_for(empty(), TIMEOUT)


def opening(
    streams: set[asyncio.Task],
    scene: Scene,
    who: str = "rita",
    prefix: str = "/fast",
    events: int = 0,
    **headers: str,
) -> "asyncio.Task[OpenedStream]":
    """Start reading the tenant's stream as ``who``; await the task for the status, headers and events."""
    task = asyncio.ensure_future(
        open_event_stream(
            scene.service.app,
            events_of(scene, prefix),
            headers={**scene.headers(who), **headers},
            events=events,
            timeout=FOLLOW_TIMEOUT,
        )
    )
    streams.add(task)
    return task


def short_times(**changes) -> SseSettings:
    """The settings of the route with the short times these tests need, ``changes`` on top."""
    return SseSettings(
        **{
            "access_ttl_seconds": 0.001,
            "keep_alive_seconds": KEEP_ALIVE,
            "resume_window_seconds": WEEK.total_seconds(),
            **changes,
        }
    )


def mount(service: ToyService, prefix: str, **changes) -> str:
    """The route of the tenants' events again, under ``prefix``, with short times; its prefix."""
    router = APIRouter()
    settings = {"sse": short_times(), "clock": lambda: datetime.now(UTC), **changes}
    add_events_route(router, service.kit, **settings)
    service.app.include_router(router, prefix=prefix)
    return prefix


def events_of(scene: Scene, prefix: str = "/fast") -> str:
    return f"{prefix}{scene.tenant}/rp-events"


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
