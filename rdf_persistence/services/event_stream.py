"""The stream of one follower of a tenant: what it is sent, in what order, and when it ends (PD-11, PD-12).

The route adapts it to server-sent events. The stream subscribes to the hub first, so nothing relayed
while it reads the history is lost; it then sends the history it is asked for, the buffer without what
that sent, and live activities. Each is cut to what the caller may read, by the access as it was read
at most ``access_ttl`` ago.
"""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from datetime import datetime, timedelta
from typing import Final, Literal, Protocol

from rdflib import Graph

from rdf_persistence.core.domain.exceptions import Forbidden, NotFound
from rdf_persistence.core.domain.generated.rp_provenance import Activity
from rdf_persistence.provenance.services.provenance import is_activity_id
from rdf_persistence.provenance.services.visible_part import visible_part
from rdf_persistence.services.event_hub import CLOSED, EventHub

MayRead = Callable[[str], bool]


RESET: Final = (
    "reset"  # the id the follower resumed from is unknown or too old: it reloads, then follows
)
KEEP_ALIVE: Final = (
    "keep-alive"  # nothing happened for ``keep_alive``: a comment keeps the connection open
)
Signal = Literal["reset", "keep-alive"]


class Reader(Protocol):
    """What the stream asks of a session."""

    async def relayed_since(
        self, iri: str, window: timedelta, now: datetime
    ) -> list[tuple[str, Graph]] | None: ...


async def event_stream(
    hub: EventHub,
    tenant: str,
    *,
    may_read: MayRead,
    refresh: Callable[[], Awaitable[MayRead]],
    open_session: Callable[[], AbstractAsyncContextManager[Reader]],
    decode: Callable[[str, Graph], Activity],
    last_event_id: str | None,
    window: timedelta,
    access_ttl: timedelta,
    keep_alive: float,
    max_lifetime: timedelta,
    clock: Callable[[], datetime],
) -> AsyncIterator[Activity | Signal]:
    """What the follower of ``tenant`` is sent, until the hub closes its queue or its access is gone.

    ``may_read`` is what the caller may read now; ``refresh`` reads the access again (and checks the
    caller may still read the tenant) and answers the new predicate. It is called before an event or
    a keep-alive when the last read is ``access_ttl`` old or older; if it raises ``Forbidden`` or
    ``NotFound`` the stream ends. ``last_event_id`` is the activity IRI to resume after, if any; one
    that is not an activity id is unknown (``RESET``). The stream ends at the first wake (an activity or
    a keep-alive) after ``max_lifetime``, so a token that expired or was revoked is not outlived (D-20);
    the follower resumes with its last id.
    """
    access = _Access(may_read, refresh, access_ttl, clock)
    deadline = clock() + max_lifetime
    sent: set[str] = set()
    try:
        async with hub.subscribe(tenant) as queue:
            if last_event_id is not None:
                resumed = _resumed(open_session, decode, access, sent, last_event_id, window, clock)
                async for item in resumed:
                    yield item
            async for current in _live(
                queue, access, sent, keep_alive, lambda: clock() >= deadline
            ):
                yield current
    except (Forbidden, NotFound):
        return


async def _resumed(
    open_session: Callable[[], AbstractAsyncContextManager[Reader]],
    decode: Callable[[str, Graph], Activity],
    access: "_Access",
    sent: set[str],
    last_event_id: str,
    window: timedelta,
    clock: Callable[[], datetime],
) -> AsyncIterator[Activity | Signal]:
    """What was relayed since ``last_event_id``, filtered, or ``RESET``; every id read goes in ``sent``."""
    found = None
    if is_activity_id(
        last_event_id
    ):  # a client-sent header: anything else is simply unknown (D-21)
        async with open_session() as session:
            found = await session.relayed_since(last_event_id, window, clock())
    if found is None:
        yield RESET
    for iri, graph in found or []:
        sent.add(iri)
        if (seen := visible_part(decode(iri, graph), await access.current())) is not None:
            yield seen


async def _live(
    queue: asyncio.Queue,
    access: "_Access",
    sent: set[str],
    keep_alive: float,
    expired: Callable[[], bool],
) -> AsyncIterator[Activity | Signal]:
    """The buffer and then the live activities not already ``sent``, filtered; ends when the hub closes."""
    while True:
        try:
            item = await asyncio.wait_for(queue.get(), keep_alive)
        except TimeoutError:
            if expired():
                return
            await access.current()
            yield KEEP_ALIVE
            continue
        if item is CLOSED or expired():
            return
        if item.id not in sent and (seen := visible_part(item, await access.current())):
            yield seen


class _Access:
    """What the caller may read, as of the last read of its access, which it renews when it is old."""

    def __init__(
        self,
        may_read: MayRead,
        refresh: Callable[[], Awaitable[MayRead]],
        ttl: timedelta,
        clock: Callable[[], datetime],
    ) -> None:
        self._may_read, self._refresh, self._ttl, self._clock = may_read, refresh, ttl, clock
        self._read_at = clock()

    async def current(self) -> MayRead:
        if self._clock() - self._read_at >= self._ttl:
            self._may_read = await self._refresh()
            self._read_at = self._clock()
        return self._may_read
