"""A store wrapper that holds one request between its reads and its update, so a test can make another
writer act in that window on a real Fuseki (dependent-aggregates RISK-1, A-13). Not collected as tests.

A request reads first (discovery, the part's ``ASK``) and sends one update last; the wrapper holds that
update until the test releases it. No sleep: two events carry the hand-over.
"""

import asyncio

from rdflib.query import Result

from rdf_persistence.persistence.services.store import Store

WAIT_SECONDS = 30.0


class PausingStore:
    """Delegates to ``store``; its first ``update`` announces itself and waits to be released."""

    def __init__(self, store: Store) -> None:
        self._store = store
        self._armed = True
        self._reached = asyncio.Event()
        self._released = asyncio.Event()

    def __getattr__(self, name: str):
        return getattr(self._store, name)

    async def query(self, dataset: str, sparql: str) -> Result:
        return await self._store.query(dataset, sparql)

    async def update(self, dataset: str, sparql: str) -> None:
        if self._armed:
            self._armed = False
            self._reached.set()
            await self._released.wait()
        await self._store.update(dataset, sparql)

    async def paused(self, work: asyncio.Task) -> None:
        """Return once ``work`` waits at its update; fail, naming ``work``, if it ended or stalled first."""
        waiter = asyncio.ensure_future(self._reached.wait())
        await asyncio.wait(
            {work, waiter}, return_when=asyncio.FIRST_COMPLETED, timeout=WAIT_SECONDS
        )
        waiter.cancel()
        assert self._reached.is_set(), f"the request never reached its update: {work!r}"

    def release(self) -> None:
        """Let the held update go."""
        self._released.set()
