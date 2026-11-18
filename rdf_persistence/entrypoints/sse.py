"""``GET {prefix}/{tenant_segment}/{t}/rp-events``: a tenant's activities as server-sent events (aggregate-events PD-11, PD-12).

The route checks ``read`` on the tenant and adapts ``events.services.event_stream`` to the wire: ``id`` is the
activity's IRI, ``event`` its class's name, ``data`` its JSON. The stream is the service's; this module
only names the times it runs by.
"""

from collections.abc import AsyncIterator, Callable
from datetime import datetime, timedelta
from http import HTTPMethod
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from fastapi.sse import EventSourceResponse, ServerSentEvent

from rdf_persistence.access.services.generated.rp_access_services import (
    CallerAccess,
    VerifiedCaller,
)
from rdf_persistence.core.domain.generated.rp_access import Action
from rdf_persistence.core.domain.generated.rp_provenance import Activity
from rdf_persistence.entrypoints.kit import ServiceKit
from rdf_persistence.entrypoints.negotiation import LAST_EVENT_ID, LINK
from rdf_persistence.entrypoints.openapi import TenantOpenApi
from rdf_persistence.entrypoints.responses import CONTEXT_REL
from rdf_persistence.events.services.event_stream import (
    KEEP_ALIVE,
    RESET,
    MayRead,
    Signal,
    event_stream,
)
from rdf_persistence.persistence.services.decoding import decode_activity
from rdf_persistence.persistence.services.session import utc_now
from rdf_persistence.services.generated.settings.rp_settings import SseSettings

EVENTS_ROUTE = (
    "rp-events"  # under the toolkit's reserved prefix, so no aggregate can shadow it (D-15)
)


def _sent(item: Activity | Signal) -> ServerSentEvent:
    if item == RESET:
        # an empty data line: an EventSource dispatches no event that has no data field at all
        return ServerSentEvent(event=RESET, raw_data="")
    if item == KEEP_ALIVE:
        return ServerSentEvent(comment=KEEP_ALIVE)
    assert isinstance(item, Activity)
    return ServerSentEvent(
        id=item.id, event=type(item).__name__, raw_data=item.model_dump_json(exclude_none=True)
    )


def add_events_route(
    router: APIRouter,
    kit: ServiceKit,
    *,
    sse: SseSettings | None = None,
    clock: Callable[[], datetime] = utc_now,
) -> None:
    """Add the events route of a tenant to ``router``.

    ``sse`` (a fresh ``SseSettings`` unless given) says how old the caller's access may be before it
    is read again (``access_ttl_seconds``), the seconds of silence before a comment is sent
    (``keep_alive_seconds``), how far back a ``Last-Event-ID`` may be resumed from
    (``resume_window_seconds``) and how long a stream lives before the client must reconnect with a
    fresh token (``max_lifetime_seconds``, D-20); ``clock`` is where "now" comes from.
    """
    sse = sse or SseSettings()
    gate = kit.gate
    path = f"/{kit.settings.tenant_segment}/{{t}}/{EVENTS_ROUTE}"

    def link_to_context(response: Response) -> None:
        """A dependency: the generator body runs after the headers are taken, so the header is set before it."""
        response.headers[LINK] = f'<{kit.context_url}>; rel="{CONTEXT_REL}"'

    async def events(
        request: Request,
        caller: Annotated[VerifiedCaller, Depends(gate.caller)],
        access: Annotated[CallerAccess, Depends(gate.tenant(Action.READ))],
        _: Annotated[None, Depends(link_to_context)],
    ) -> AsyncIterator[ServerSentEvent]:
        tenant = access.tenant
        last_event_id = request.headers.get(LAST_EVENT_ID)

        def readable_by(held: CallerAccess) -> MayRead:
            return lambda iri: kit.rules.may(caller, held, iri, Action.READ)

        async def refresh() -> MayRead:
            return readable_by(await gate.check(caller, tenant, tenant, Action.READ))

        stream = event_stream(
            kit.hub,
            tenant,
            may_read=readable_by(access),
            refresh=refresh,
            open_session=lambda: kit.session(tenant, caller.principal),
            decode=lambda iri, graph: decode_activity(kit.view, kit.models, kit.mapper, iri, graph),
            last_event_id=last_event_id,
            window=timedelta(seconds=sse.resume_window_seconds),
            access_ttl=timedelta(seconds=sse.access_ttl_seconds),
            keep_alive=sse.keep_alive_seconds,
            max_lifetime=timedelta(seconds=sse.max_lifetime_seconds),
            clock=clock,
        )
        async for item in stream:
            yield _sent(item)

    TenantOpenApi(kit.documents.tenant_root).events().add_to(
        router, path, HTTPMethod.GET, events, name=EVENTS_ROUTE, response_class=EventSourceResponse
    )
