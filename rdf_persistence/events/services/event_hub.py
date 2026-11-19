"""The in-process hub of activities for live subscribers (PD-9).

One set of bounded queues per tenant IRI. ``offer`` never waits: a queue that is full is closed
(removed, and ended by ``CLOSED``), so one slow client cannot stall the relay; it resumes with
``Last-Event-ID`` (PD-12). In process, single instance (DEC-10).
"""

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Protocol

from rdf_persistence.events.services.generated.settings.rp_events_settings import EventSettings
from rdf_persistence.provenance.domain.generated.rp_provenance import Activity

CLOSED = object()  # the sentinel that ends a subscriber's stream


class Offer(Protocol):
    """What the relay needs of a hub: hand it one tenant activity, without waiting."""

    def offer(self, tenant: str, activity: Activity) -> None: ...


class EventHub:
    """Fans each offered activity out to the queues subscribed to its tenant.

    A queue holds ``events.hub_queue_size`` activities (a fresh ``EventSettings`` unless given).
    """

    def __init__(self, events: EventSettings | None = None) -> None:
        self._max_queue = (events or EventSettings()).hub_queue_size
        self._queues: dict[str, set[asyncio.Queue]] = defaultdict(set)

    @asynccontextmanager
    async def subscribe(self, tenant: str) -> AsyncIterator[asyncio.Queue]:
        queue: asyncio.Queue = asyncio.Queue(self._max_queue)
        self._queues[tenant].add(queue)
        try:
            yield queue
        finally:
            self._discard(tenant, queue)

    def offer(self, tenant: str, activity: Activity) -> None:
        for queue in list(self._queues.get(tenant, ())):
            try:
                queue.put_nowait(activity)
            except asyncio.QueueFull:
                self._close(tenant, queue)

    def _close(self, tenant: str, queue: asyncio.Queue) -> None:
        self._discard(tenant, queue)
        # drop all: a reader's last id then precedes everything it missed (D-14)
        while not queue.empty():
            queue.get_nowait()
        queue.put_nowait(CLOSED)

    def _discard(self, tenant: str, queue: asyncio.Queue) -> None:
        queues = self._queues.get(tenant)
        if queues is not None:
            queues.discard(queue)
            if not queues:
                del self._queues[tenant]
