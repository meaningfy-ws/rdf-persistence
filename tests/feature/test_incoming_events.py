"""Steps of ``incoming_events.feature``: two toy deployments on one broker (aggregate-events 2.2).

The scenario is the one of requirement "Incoming events reach the message bus" of ``rp-events``.
Only the first deployment serves, so its relay is the only one that publishes.
"""

import asyncio
from contextlib import AsyncExitStack

import pytest
from pytest_bdd import given, scenarios, then, when

from rdf_persistence import bootstrap
from rdf_persistence.domain.generated.rp_provenance import Replace
from rdf_persistence.testkit import (
    FakeStore,
    InMemoryBroker,
    InMemoryEventBus,
    RecordingObserver,
    wait_until_async,
)
from tests.toy_service import DUNE_BODY, ToyService
from tests.unit.entrypoints.test_service_kit import made

scenarios("incoming_events.feature")


class Run:
    """One scenario: the two deployments, their observers, and a loop to drive them."""

    def __init__(self) -> None:
        self.loop = asyncio.new_event_loop()
        self.stack = AsyncExitStack()
        self.broker = InMemoryBroker()
        self.store = FakeStore()
        self.first_bus, self.second_bus = (
            InMemoryEventBus(self.broker),
            InMemoryEventBus(self.broker),
        )
        self.first = ToyService(self.store, event_bus=self.first_bus, deployment="lib")
        self.second = ToyService(self.store, event_bus=self.second_bus, deployment="cat")
        self.first_saw, self.second_saw = RecordingObserver(), RecordingObserver()

    def run(self, work):
        return self.loop.run_until_complete(work)

    def close(self) -> None:
        self.run(self.stack.aclose())
        self.loop.close()

    async def replace_a_book(self) -> None:
        await self.second_bus.start(self.second.kit.receive)
        await self.stack.enter_async_context(self.first.app.router.lifespan_context(self.first.app))
        async with self.first.client() as http:
            headers = self.first.bearer("ada")
            _, book, etag = await made(http, headers)
            await http.put(book, json=DUNE_BODY, headers={**headers, "If-Match": etag})
        await wait_until_async(self._second_heard, "the second deployment's observer")

    async def _second_heard(self) -> list:
        return self.second_saw.of(Replace)


@pytest.fixture
def run():
    scenario = Run()
    yield scenario
    scenario.close()


@given("two deployments share one broker and one library store")
def _two_deployments(run: Run) -> None:
    run.first.kit.bus = bootstrap(observers={Replace: [run.first_saw]}, mapper=run.first.kit.mapper)


@given("the second deployment has an observer of replacements")
def _observer(run: Run) -> None:
    run.second.kit.bus = bootstrap(
        observers={Replace: [run.second_saw]}, mapper=run.second.kit.mapper
    )


@when("the first deployment replaces a book")
def _replace(run: Run) -> None:
    run.run(run.replace_a_book())


@then("the second deployment's observer receives the replacement once")
def _second_once(run: Run) -> None:
    assert len(run.second_saw.of(Replace)) == 1


@then("the first deployment's own observer received it once")
def _first_once(run: Run) -> None:
    assert len(run.first_saw.of(Replace)) == 1
