"""Spec rp-testkit: the testkit opens a tenant's event stream in-process (PD-2 to PD-5).

The four scenarios run against the toy service's own events route, through the public name only
(``assert_public_imports`` checks this very file).
"""

import asyncio
import json
import re

import pytest

from rdf_persistence.testkit import assert_public_imports, open_event_stream
from tests.events_follow import TIMEOUT
from tests.scene import Scene

# The deadline runs from the call, so it also covers the commits made after starting the task.
FOLLOW_TIMEOUT = 30.0
SHORT = 0.5


def test_this_file_uses_only_public_names() -> None:
    assert_public_imports(__file__)


@pytest.fixture
async def settled(scene: Scene) -> Scene:
    """The scene, with everything it committed already relayed: a follower hears only what follows."""
    await scene.service.kit.relay.run_once()
    return scene


def events_of(scene: Scene) -> str:
    return f"{scene.tenant}/rp-events"


async def listening(scene: Scene) -> None:
    """Until one follower is subscribed to the hub: the stream is reading from now on."""

    async def subscribed() -> None:
        while not any(scene.service.kit.hub._queues.values()):
            await asyncio.sleep(0)

    await asyncio.wait_for(subscribed(), TIMEOUT)


async def test_a_reader_follows_the_stream(settled: Scene) -> None:
    opened = await open_event_stream(
        settled.service.app, events_of(settled), headers=settled.headers("rita"), timeout=TIMEOUT
    )
    assert opened.status == 200
    assert opened.headers["content-type"].startswith("text/event-stream")


async def test_one_event_is_returned_with_the_activity_iri_as_its_id(settled: Scene) -> None:
    stream = asyncio.ensure_future(
        open_event_stream(
            settled.service.app,
            events_of(settled),
            headers=settled.headers("rita"),
            events=1,
            timeout=FOLLOW_TIMEOUT,
        )
    )
    try:
        await listening(settled)
        replaced = await settled.http.put(
            settled.book,
            json={**(await settled.http.get(settled.book, headers=settled.headers("ada"))).json()},
            headers=settled.headers("ada", **{"If-Match": settled.book_etag}),
        )
        assert replaced.status_code == 200, replaced.text
        await settled.service.kit.relay.run_once()
        opened = await stream
    finally:
        stream.cancel()
        await asyncio.gather(stream, return_exceptions=True)
    [event] = opened.events
    assert event.event == "Replace"
    data = json.loads(event.data)
    assert event.id == data["id"], "the activity's IRI"
    assert [g["entity"] for g in data["generations"]] == [settled.book_iri], (
        "the event's data names the replaced book"
    )


async def test_a_caller_with_no_right_on_the_tenant_gets_404_without_waiting(
    settled: Scene,
) -> None:
    opened = await open_event_stream(
        settled.service.app,
        events_of(settled),
        headers=settled.headers("omar"),
        events=1,
        timeout=SHORT,
    )
    assert opened.status == 404, "returned, not raised, though an event was asked for"
    assert opened.events == []


async def test_a_silent_stream_raises_a_timeout_naming_the_url(settled: Scene) -> None:
    url = events_of(settled)
    with pytest.raises(TimeoutError, match=re.escape(url)):
        await open_event_stream(
            settled.service.app, url, headers=settled.headers("rita"), events=1, timeout=SHORT
        )
