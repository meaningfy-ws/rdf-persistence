"""The ``EventBus`` conformance suite: one set of cases, run against the fake and against Redis.

Each case takes a ``BusPair``: two buses on one broker, and ``failing(bus)``, a context manager in
which ``bus.publish`` raises (the fake flags it; Redis stops its broker). Run a case with
``run_case``, which closes both buses afterwards. A divergence between the fake and Redis is a bug
in the fake.
"""

import contextlib
from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from typing import Protocol

import pytest

from rdf_persistence.domain.generated.rp_provenance import Activity, Replace
from rdf_persistence.domain.generated.service.rp_service import EventEnvelope
from rdf_persistence.services.events import EventBus
from rdf_persistence.testkit.bootstrap import wait_until_async

ENVELOPE = EventEnvelope(
    tenant="https://example.org/tenants/t",
    origin="lib",
    activity_class="https://meaningfy.ws/ns/rdf-persistence#Replace",
    context="https://lib.example/context.jsonld",
)
BODY = Replace(id="https://example.org/activities/a1")
OTHER_BODY = Replace(id="https://example.org/activities/a2")


class BusPair(Protocol):
    a: EventBus
    b: EventBus

    def failing(self, bus: EventBus) -> AbstractAsyncContextManager[None]: ...


class Inbox:
    """What a receiver got; ``fail`` makes it raise instead of keep."""

    def __init__(self) -> None:
        self.got: list[tuple[EventEnvelope, bytes]] = []
        self.fail = False

    async def __call__(self, envelope: EventEnvelope, body: bytes) -> None:
        if self.fail:
            raise RuntimeError("the receiver failed")
        self.got.append((envelope, body))

    async def has(self, count: int) -> None:
        async def probe() -> bool:
            return len(self.got) >= count

        await wait_until_async(probe, f"{count} message(s) received")


Case = Callable[[BusPair], Awaitable[None]]


async def a_message_reaches_every_started_bus(pair: BusPair) -> None:
    inbox_a, inbox_b = Inbox(), Inbox()
    await pair.a.start(inbox_a)
    await pair.b.start(inbox_b)
    await pair.a.publish(ENVELOPE, BODY)
    await inbox_a.has(1)
    await inbox_b.has(1)
    for inbox in (inbox_a, inbox_b):
        envelope, body = inbox.got[0]
        assert envelope == ENVELOPE
        assert Replace.model_validate_json(body) == BODY


async def a_receiver_that_raised_gets_the_message_again_on_restart(pair: BusPair) -> None:
    inbox_a, inbox_b = Inbox(), Inbox()
    await pair.a.start(inbox_a)
    await pair.b.start(inbox_b)
    inbox_b.fail = True
    await pair.a.publish(ENVELOPE, BODY)
    await inbox_a.has(1)
    inbox_b.fail = False
    await pair.b.close()
    await pair.b.start(inbox_b)
    await inbox_b.has(1)
    assert Replace.model_validate_json(inbox_b.got[0][1]) == BODY
    assert len(inbox_a.got) == 1, "the other bus did not get it again"


async def a_failed_publish_raises_and_the_next_succeeds(pair: BusPair) -> None:
    inbox = Inbox()
    await pair.b.start(inbox)
    async with pair.failing(pair.a):
        with pytest.raises(Exception):  # noqa: B017 (the error type is the broker's own)
            await pair.a.publish(ENVELOPE, BODY)
    await pair.a.publish(ENVELOPE, OTHER_BODY)
    await inbox.has(1)
    assert Activity.model_validate_json(inbox.got[0][1]).id == OTHER_BODY.id


CASES: tuple[Case, ...] = (
    a_message_reaches_every_started_bus,
    a_receiver_that_raised_gets_the_message_again_on_restart,
    a_failed_publish_raises_and_the_next_succeeds,
)


async def run_case(case: Case, pair: BusPair) -> None:
    """Run one case on the pair, then close both buses."""
    try:
        await case(pair)
    finally:
        for bus in (pair.a, pair.b):
            with contextlib.suppress(Exception):
                await bus.close()
