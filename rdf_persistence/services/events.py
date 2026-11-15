"""The event bus port: the commits of a deployment, sent to the others (aggregate-events PD-6).

The relay publishes each activity with an ``EventEnvelope`` that names its tenant, origin and class; a
receiver gets the envelope and the activity's JSON. The implementations live in ``adapters`` (Redis)
and ``testkit`` (in memory).
"""

from collections.abc import Awaitable, Callable
from typing import Protocol

from rdf_persistence.domain.generated.rp_provenance import Activity
from rdf_persistence.domain.generated.service.rp_service import EventEnvelope

CONTEXT_PATH = "/context.jsonld"

Receive = Callable[[EventEnvelope, bytes], Awaitable[None]]


class EventBus(Protocol):
    async def publish(self, envelope: EventEnvelope, body: Activity) -> None:
        """Send the activity; raises when the broker cannot take it."""
        ...

    async def start(self, receive: Receive) -> None:
        """Begin consuming; a message ``receive`` raised on is not acked and comes again."""
        ...

    async def close(self) -> None: ...


def context_link(public_url: str | None) -> str:
    """The JSON-LD context link of an envelope: absolute under a public URL, else relative."""
    return f"{public_url or ''}{CONTEXT_PATH}"
