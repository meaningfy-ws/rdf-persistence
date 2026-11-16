"""The relay: publishes every pending activity at least once, in store order per database (PD-3, PD-5).

One round visits the application database and every active tenant that is not ``behind``, each in a
``try`` of its own. Per database the pending activities go out in order: decode, publish, replace the
mark, offer to the hub. A failed publish stops that database for the round, so nothing overtakes it.
"""

import asyncio
import contextlib
import logging
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

from linkml_runtime.utils.schemaview import SchemaView
from pydantic import ValidationError
from rdflib import Graph

from rdf_persistence.domain.exceptions import DatabaseGone
from rdf_persistence.domain.generated.rp_provenance import Activity
from rdf_persistence.domain.generated.rp_tenancy import TenantState
from rdf_persistence.domain.generated.service.rp_service import EventEnvelope
from rdf_persistence.services.decoding import decode_activity, error_text
from rdf_persistence.services.event_hub import Offer
from rdf_persistence.services.events import EventBus
from rdf_persistence.services.mapper import GeneratedModels, Mapper
from rdf_persistence.services.session import Session
from rdf_persistence.services.tenancy import Tenancy

log = logging.getLogger(__name__)

Decoded = tuple[str, Activity | Exception]
Opener = Callable[[], AbstractAsyncContextManager[Session]]


def chain_order(items: list[Decoded]) -> list[Decoded]:
    """``items`` with each activity after the pending one that generated a version it invalidated;
    otherwise in the order given (PD-5: the chain settles what the store clock leaves tied)."""
    made = {
        (part.entity, part.entity_version): iri
        for iri, activity in items
        if isinstance(activity, Activity)
        for part in activity.generations or ()
    }
    by_iri = dict(items)
    placed: set[str] = set()
    ordered: list[Decoded] = []
    for first in by_iri:
        stack = [first]
        while stack:
            iri = stack[-1]
            waiting = [] if iri in placed else _before(by_iri[iri], made, iri, placed, stack)
            if waiting:
                stack.extend(waiting)
                continue
            if iri not in placed:
                placed.add(iri)
                ordered.append((iri, by_iri[iri]))
            stack.pop()
    return ordered


def _before(
    activity: Activity | Exception,
    made: dict[tuple[str, str], str],
    iri: str,
    placed: set[str],
    stack: list[str],
) -> list[str]:
    """The pending activities that must go out before ``activity``, not yet placed or on the stack."""
    if not isinstance(activity, Activity):
        return []
    found = (made.get((p.entity, p.entity_version)) for p in activity.invalidations or ())
    return [i for i in found if i and i != iri and i not in placed and i not in stack]


class Relay:
    """Publishes the pending activities of every database to the bus and offers them to the hub."""

    def __init__(
        self,
        tenancy: Tenancy,
        view: SchemaView,
        models: GeneratedModels,
        mapper: Mapper,
        bus: EventBus | None,
        hub: Offer | None,
        *,
        deployment: str,
        context: str,
        interval: float = 5.0,
        publish_timeout: float = 10.0,
    ) -> None:
        self._tenancy = tenancy
        self._view = view
        self._models = models
        self._mapper = mapper
        self._bus = bus
        self._hub = hub
        self._deployment = deployment
        self._context = context
        self._interval = interval
        self._publish_timeout = publish_timeout
        self._wake = asyncio.Event()
        self._lock = asyncio.Lock()

    def wake(self) -> None:
        """Ask for a round now; any number of wakes during a round make one more round."""
        self._wake.set()

    async def run(self) -> None:
        """Round after round, each on a wake or after ``interval``, until cancelled."""
        while True:
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._wake.wait(), self._interval)
            self._wake.clear()
            try:
                await self.run_once()
            except Exception:
                log.exception("a relay round failed")

    async def run_once(self) -> None:
        """One round over every database, never overlapping another."""
        async with self._lock:
            for tenant, opener, offers in await self._targets():
                await self._relay_database(tenant, opener, offers)

    async def _targets(self) -> list[tuple[str, Opener, bool]]:
        """(tenant IRI, how to open its session, whether the hub is offered its activities)."""
        toolkit = self._tenancy.toolkit
        found: list[tuple[str, Opener, bool]] = []
        if self._tenancy.application_database is not None:
            found.append(
                (
                    self._tenancy.application,
                    lambda: self._tenancy.application_session(toolkit),
                    False,
                )
            )
        for summary in await self._tenancy.tenants():
            if summary.state == TenantState.ACTIVE and summary.id not in self._tenancy.behind:
                found.append((summary.id, self._tenant_opener(summary.id), True))
        return found

    def _tenant_opener(self, tenant: str) -> Opener:
        return lambda: self._tenancy.tenant_session(tenant, self._tenancy.toolkit)

    async def _relay_database(self, tenant: str, opener: Opener, offers: bool) -> None:
        try:
            async with opener() as session:
                await self._drain(session, tenant, offers)
        except DatabaseGone:
            log.debug("the database of %s is gone; skipped this round", tenant)
        except Exception:
            log.exception("the relay failed on the database of %s; skipped this round", tenant)

    async def _drain(self, session: Session, tenant: str, offers: bool) -> None:
        for iri, activity in chain_order(self._decoded(await session.pending_activities())):
            if isinstance(activity, Exception):
                # a validation error's traceback would print the record's values
                trace = None if isinstance(activity, ValidationError) else activity
                log.error(
                    "the pending activity %s cannot be decoded: %s",
                    iri,
                    error_text(activity),
                    exc_info=trace,
                )
                await session.mark_failed(iri)
            elif not await self._publish(tenant, activity):
                return
            else:
                await session.mark_relayed(iri)
                if offers and self._hub is not None:
                    self._hub.offer(tenant, activity)

    def _decoded(self, pending: list[tuple[str, Graph]]) -> list[Decoded]:
        found: list[Decoded] = []
        for iri, graph in pending:
            try:
                found.append(
                    (iri, decode_activity(self._view, self._models, self._mapper, iri, graph))
                )
            except (LookupError, ValueError) as error:
                found.append((iri, error))
        return found

    async def _publish(self, tenant: str, activity: Activity) -> bool:
        """Whether the activity went out (or there is no bus); a failure is logged and ends the database's round."""
        if self._bus is None:
            return True
        envelope = EventEnvelope(
            tenant=tenant,
            origin=self._deployment,
            activity_class=self._view.get_uri(type(activity).__name__, expand=True),
            context=self._context,
        )
        try:
            async with asyncio.timeout(
                self._publish_timeout
            ):  # a hung broker must not freeze the relay (D-18)
                await self._bus.publish(envelope, activity)
        except Exception:  # noqa: BLE001 -- the relay must outlive a failed publish: logged, retried next round
            log.warning("publishing %s failed; retried next round", activity.id, exc_info=True)
            return False
        return True
