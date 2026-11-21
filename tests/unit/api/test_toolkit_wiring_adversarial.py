"""Adversarial tests of how the kit passes the toolkit settings on (technical-models stage 3, task 3.3, PD-7).

Attacks: 'a group not passed on by the kit'. Every slot of a group the kit consumes is given a value
no default has, and each object the kit builds must show it.
"""

import io
from datetime import timedelta

import pytest

from rdf_persistence.api.entrypoints.generated.settings.rp_api_settings import (
    SseSettings,
    ToolkitSettings,
)
from rdf_persistence.events.services.generated.settings.rp_events_settings import EventSettings
from rdf_persistence.persistence.services.generated.settings.rp_persistence_settings import (
    LimitSettings,
)
from tests.toy_service import TENANT_BODY, ToyService

ODD = ToolkitSettings(
    limits=LimitSettings(
        max_roots=7, max_document_nodes=33, max_manifest_bytes=2048, max_messages=9
    ),
    events=EventSettings(
        hub_queue_size=11, relay_interval_seconds=17.5, publish_timeout_seconds=19.5
    ),
    sse=SseSettings(
        max_lifetime_seconds=123.0,
        access_ttl_seconds=4.5,
        keep_alive_seconds=6.5,
        resume_window_seconds=777.0,
    ),
)


def test_the_kit_keeps_the_toolkit_it_was_given_and_hands_each_group_on() -> None:
    """Invariant: every kit-built object receives the kit's group (``kit.toolkit`` is the given one)."""
    kit = ToyService(toolkit=ODD).kit
    assert kit.toolkit is ODD, "the kit replaced the settings it was given"
    assert kit.mapper.max_roots == 7, "Mapper did not get limits.max_roots"
    assert kit.documents._max_nodes == 33, "Documents did not get limits.max_document_nodes"
    assert kit.hub._max_queue == 11, "EventHub did not get events.hub_queue_size"
    assert kit.relay._interval == 17.5, "Relay did not get events.relay_interval_seconds"
    assert kit.relay._publish_timeout == 19.5, "Relay did not get events.publish_timeout_seconds"


async def test_the_events_route_gets_every_slot_of_the_sse_group(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invariant: the events route receives the kit's ``sse`` (access TTL, keep-alive, window, lifetime)."""
    seen: dict[str, object] = {}

    async def fake_stream(*_args: object, **kwargs: object):
        seen.update(kwargs)
        return
        yield  # an async generator that ends at once

    monkeypatch.setattr("rdf_persistence.api.entrypoints.sse.event_stream", fake_stream)  # X2
    toy = ToyService(toolkit=ODD)
    async with toy.app.router.lifespan_context(toy.app), toy.client() as http:
        made = await http.post("/libraries", json=TENANT_BODY, headers=toy.bearer("ada"))
        path = made.headers["location"]
        response = await http.get(f"{path}/rp-events", headers=toy.bearer("ada"))
    assert response.status_code == 200, response.text
    assert seen["window"] == timedelta(seconds=777), "resume_window_seconds"
    assert seen["access_ttl"] == timedelta(seconds=4.5), "access_ttl_seconds"
    assert seen["keep_alive"] == 6.5, "keep_alive_seconds"
    assert seen["max_lifetime"] == timedelta(seconds=123), "max_lifetime_seconds"


async def test_the_restore_gets_the_limits_group_of_the_kit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invariant: ``kit.restore_tenant`` hands ``tenant_dump.restore`` the kit's ``limits``, not a fresh default."""
    seen: dict[str, object] = {}

    async def fake_restore(*_args: object, **kwargs: object) -> str:
        seen.update(kwargs)
        return "restored"

    monkeypatch.setattr(  # X2
        "rdf_persistence.api.entrypoints.kit.tenant_dump.restore", fake_restore
    )
    kit = ToyService(toolkit=ODD).kit
    await kit.restore_tenant(io.BytesIO(b""), "ada")
    assert seen["limits"] is ODD.limits, "restore was not given the kit's limits"
