"""The relay, the hub and the event bus wired into the kit and ``install_service`` (aggregate-events 1.6, PD-15)."""

import asyncio

import pytest
from fastapi import FastAPI

from rdf_persistence.domain.generated.rp_provenance import Add
from rdf_persistence.domain.generated.service.rp_service import ServiceSettings
from rdf_persistence.testkit import InMemoryBroker, InMemoryEventBus, wait_until_async
from tests.toy_service import DUNE_BODY, TENANT_BODY, ToyService, principal_of
from tests.unit.entrypoints.test_service_kit import installed, made


def relayed_book(broker: InMemoryBroker) -> list:
    """The messages of the broker once the book of ``made`` is there: its tenant's Add, then its own."""
    return broker.messages[-1:] if len(broker.messages) >= 2 else []


async def test_a_post_reaches_the_broker_within_the_wait() -> None:  # TC-19
    broker = InMemoryBroker()
    toy = ToyService(event_bus=InMemoryEventBus(broker), deployment="here")
    async with toy.app.router.lifespan_context(toy.app), toy.client() as http:
        await made(http, toy.bearer("ada"))
        sent = await wait_until_async(
            lambda: _async(relayed_book(broker)), "the book's Add", poll_seconds=0.01
        )
    envelope, _ = sent[0]
    assert envelope.origin == "here", "the envelope carries this deployment as its origin"
    assert envelope.activity_class.endswith("Add"), "the envelope names the activity class"


async def test_leaving_the_lifespan_ends_the_relay_and_closes_the_bus() -> None:  # TC-20
    broker = InMemoryBroker()
    bus = InMemoryEventBus(broker)
    toy = ToyService(event_bus=bus, deployment="here")
    async with toy.app.router.lifespan_context(toy.app):
        assert bus in broker._buses, "the bus consumes while the app serves"
        (task,) = [t for t in asyncio.all_tasks() if t.get_coro().__qualname__ == "Relay.run"]  # type: ignore[union-attr]
        assert not task.done(), "the relay is still running while the lifespan is open"
    assert task.done(), "the relay task ended"
    assert bus not in broker._buses, "close() was called on the bus"


async def test_with_no_event_bus_the_activity_is_still_relayed_to_the_hub() -> None:  # TC-21
    toy = ToyService()
    async with toy.app.router.lifespan_context(toy.app), toy.client() as http:
        headers = toy.bearer("ada")
        tenant = await http.post("/libraries", json=TENANT_BODY, headers=headers)
        tenant_iri = toy.kit.tenant_iri(tenant.headers["location"].rsplit("/", 1)[1])
        async with toy.kit.hub.subscribe(tenant_iri) as queue:
            await http.post(f"{tenant.headers['location']}/books", json=DUNE_BODY, headers=headers)
            await wait_until_async(
                lambda: _async(not queue.empty()),
                "the relay to offer the activity",
                poll_seconds=0.01,
            )
            activity = queue.get_nowait()
    assert isinstance(activity, Add), "the relay offered the hub an Add"
    entities = [g.entity for g in activity.generations or []]
    assert entities, "the Add generated something"
    assert all(e.startswith(tenant_iri) for e in entities), (
        "and everything it generated is the tenant's"
    )
    assert activity.was_associated_with == [principal_of("ada")], "carried out by the caller"


def test_an_event_bus_without_a_deployment_is_refused() -> None:  # TC-21a
    toy = ToyService()
    settings: ServiceSettings = toy.settings.model_copy(update={"deployment": None})
    with pytest.raises(ValueError, match="deployment"):
        installed(FastAPI(), toy, settings=settings, event_bus=InMemoryEventBus(InMemoryBroker()))


async def test_a_public_url_makes_the_context_of_the_envelope_absolute() -> None:
    broker = InMemoryBroker()
    toy = ToyService(
        event_bus=InMemoryEventBus(broker), deployment="here", public_url="https://lib.example.org"
    )
    async with toy.app.router.lifespan_context(toy.app), toy.client() as http:
        await made(http, toy.bearer("ada"))
        sent = await wait_until_async(
            lambda: _async(relayed_book(broker)), "the book's Add", poll_seconds=0.01
        )
    assert sent[0][0].context == "https://lib.example.org/context.jsonld", (
        "a public URL makes the envelope's context absolute"
    )


async def test_without_a_public_url_the_context_is_relative() -> None:
    broker = InMemoryBroker()
    toy = ToyService(event_bus=InMemoryEventBus(broker), deployment="here")
    async with toy.app.router.lifespan_context(toy.app), toy.client() as http:
        await made(http, toy.bearer("ada"))
        sent = await wait_until_async(
            lambda: _async(relayed_book(broker)), "the book's Add", poll_seconds=0.01
        )
    assert sent[0][0].context == "/context.jsonld", (
        "without a public URL the context stays relative"
    )


def test_a_public_url_with_a_trailing_slash_is_not_a_valid_setting() -> None:
    with pytest.raises(ValueError):
        ServiceSettings(base="https://e.org/", prefix="lib", public_url="https://e.org/")


async def _async(value):
    return value
