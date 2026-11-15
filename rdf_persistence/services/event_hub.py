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

from rdf_persistence.domain.generated.rp_provenance import Activity

CLOSED = object()  # the sentinel that ends a subscriber's stream


class Offer(Protocol):
    """What the relay needs of a hub: hand it one tenant activity, without waiting."""

    def offer(self, tenant: str, activity: Activity) -> None: ...


class EventHub:
    """Fans each offered activity out to the queues subscribed to its tenant."""

    def __init__(self, max_queue: int = 1000) -> None:
        self._max_queue = max_queue
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
        while queue.full():  # make room: the reader is told the stream ended, not what it missed
            queue.get_nowait()
        queue.put_nowait(CLOSED)

    def _discard(self, tenant: str, queue: asyncio.Queue) -> None:
        queues = self._queues.get(tenant)
        if queues is not None:
            queues.discard(queue)
            if not queues:
                del self._queues[tenant]
