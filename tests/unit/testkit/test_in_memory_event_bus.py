"""The in-memory event bus: the conformance suite (TC-07 to TC-09) and what the fake adds."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest

from rdf_persistence.events.services.generated.rp_events_services import EventEnvelope
from rdf_persistence.provenance.domain.generated.rp_provenance import Activity
from rdf_persistence.testkit import InMemoryBroker, InMemoryEventBus
from rdf_persistence.testkit.event_bus_conformance import CASES, run_case


class FakePair:
    """Two buses on one broker; the fake fails a bus by flagging it."""

    def __init__(self) -> None:
        broker = InMemoryBroker()
        self.a, self.b = InMemoryEventBus(broker), InMemoryEventBus(broker)

    @asynccontextmanager
    async def failing(self, bus: InMemoryEventBus) -> AsyncIterator[None]:
        bus.fail_next_publish()
        yield


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.__name__)
async def test_the_in_memory_bus_conforms(case):
    await run_case(case, FakePair())


async def test_the_broker_keeps_every_sent_message_as_envelope_and_json():
    broker = InMemoryBroker()
    envelope = EventEnvelope(
        tenant="http://t", origin="lib", activity_class="http://c", context="/context.jsonld"
    )
    body = Activity(id="http://a")
    await InMemoryEventBus(broker).publish(envelope, body)
    assert broker.messages == [(envelope, b'{"id":"http://a"}')], (
        "the broker keeps each message as envelope and JSON body"
    )
