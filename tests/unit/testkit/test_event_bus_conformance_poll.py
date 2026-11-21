"""The event-bus conformance kit polls at the caller's interval (PD-15, ``rp-testkit`` delta)."""

import asyncio
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from rdf_persistence.events.services.events import Receive
from rdf_persistence.events.services.generated.rp_events_services import EventEnvelope
from rdf_persistence.provenance.domain.generated.rp_provenance import Activity
from rdf_persistence.testkit import InMemoryBroker, InMemoryEventBus, bootstrap
from rdf_persistence.testkit.event_bus_conformance import (
    a_message_reaches_every_started_bus,
    run_case,
)

DELIVERY_DELAY_SECONDS = 0.1


class DelayedBus:
    """A bus that returns from ``publish`` at once and delivers a little later."""

    def __init__(self, wrapped: InMemoryEventBus) -> None:
        self.wrapped = wrapped
        self._deliveries: set[asyncio.Task[None]] = set()

    async def publish(self, envelope: EventEnvelope, body: Activity) -> None:
        async def deliver() -> None:
            await asyncio.sleep(DELIVERY_DELAY_SECONDS)
            await self.wrapped.publish(envelope, body)

        task = asyncio.create_task(deliver())
        self._deliveries.add(task)
        task.add_done_callback(self._deliveries.discard)

    async def start(self, receive: Receive) -> None:
        await self.wrapped.start(receive)

    async def close(self) -> None:
        for task in self._deliveries:
            task.cancel()
        await self.wrapped.close()


class DelayedPair:
    """The whole ``BusPair`` over the in-memory fake, each bus delivering late."""

    def __init__(self) -> None:
        broker = InMemoryBroker()
        self.a = DelayedBus(InMemoryEventBus(broker))
        self.b = DelayedBus(InMemoryEventBus(broker))

    @asynccontextmanager
    async def failing(self, bus: DelayedBus) -> AsyncIterator[None]:
        bus.wrapped.fail_next_publish()
        yield


async def test_a_fast_poll_ends_a_delivery_case_before_one_default_interval():
    started = time.monotonic()
    await run_case(a_message_reaches_every_started_bus, DelayedPair(), poll_seconds=0.02)
    assert time.monotonic() - started < bootstrap.POLL_SECONDS, (
        "the case waited in default-interval steps"
    )


async def test_a_case_run_without_poll_seconds_still_passes():
    await run_case(a_message_reaches_every_started_bus, DelayedPair())
