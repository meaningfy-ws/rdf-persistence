"""Steps of ``events.feature``: the toy library and its relay over the fakes (aggregate-events 1.7).

Scenario to requirement of ``rp-events``: the first two scenarios are "A committed change is pending
publication atomically", the last two "Events reach the bus at least once, in order per aggregate".
Nothing sleeps: the relay is driven by ``run_once``.
"""

import asyncio
import io
from types import SimpleNamespace

import pytest
from pytest_bdd import given, scenarios, then, when

from rdf_persistence import generated_models
from rdf_persistence.domain.exceptions import Conflict
from rdf_persistence.domain.generated.rp_provenance import Replace
from rdf_persistence.domain.iris import Iris
from rdf_persistence.services.events import context_link
from rdf_persistence.services.relay import Relay
from rdf_persistence.services.schema import load_schema
from rdf_persistence.services.tenant_dump import dump, restore
from rdf_persistence.testkit import InMemoryBroker, InMemoryEventBus
from tests.toy import MODULES, SETTINGS, TOY_SCHEMA, toy_mapper
from tests.unit.services.test_pending_mark import RESTORER, TOY_CHAINS
from tests.unit.services.test_relay import add_one, book, commit, pending, triples
from tests.unit.services.test_tenant_dump import BASE_STAMPS
from tests.unit.services.test_tenant_sweep import make_world

scenarios("events.feature")

DEPLOYMENT = "deployment-a"
CONTEXT = context_link("https://lib.example")
VIEW = load_schema(TOY_SCHEMA)


class Run:
    """One scenario: a toy tenant over the fakes, a relay, a subscriber, and what the steps saw."""

    def __init__(self) -> None:
        self.loop = asyncio.new_event_loop()
        self.world: SimpleNamespace
        self.broker = InMemoryBroker()
        self.received: list[tuple] = []
        self.iri = ""
        self.versions: list[str] = []
        self.before: list[str] = []
        self.restored = ""

    def run(self, work):
        return self.loop.run_until_complete(work)

    def relay(self) -> Relay:
        return Relay(
            self.world.tenancy,
            VIEW,
            generated_models(*MODULES),
            toy_mapper(),
            InMemoryEventBus(self.broker),
            None,
            deployment=DEPLOYMENT,
            context=CONTEXT,
        )

    async def build(self, stamps=()) -> None:
        self.world = await make_world(Iris(SETTINGS), SETTINGS, stamps)
        await self.relay().run_once()  # the tenant's own creation is not under test

    async def subscribe(self) -> None:
        async def receive(envelope, body: bytes) -> None:
            self.received.append((envelope, body))

        await InMemoryEventBus(self.broker).start(receive)


@pytest.fixture
def lib():
    made = Run()
    yield made
    made.loop.close()


@given("a stored book and a session holding an old version of it")
def _stale_session(lib):
    async def go():
        await lib.build()
        lib.iri = book(lib.world, lib.world.tenant)
        async with commit(lib.world, lib.world.tenant) as session:
            old = await session.add_graph(lib.iri, triples(lib.iri))
            await session.replace_graph(lib.iri, triples(lib.iri), old)
            lib.versions = [old]
            lib.before = await pending(lib.world, lib.world.tenant)

    lib.run(go())


@when("the session's replace is refused as stale")
def _refused(lib):
    async def go():
        async with commit(lib.world, lib.world.tenant) as session:
            with pytest.raises(Conflict):
                await session.replace_graph(lib.iri, triples(lib.iri), lib.versions[0])

    lib.run(go())


@then("no activity is pending for that replace")
def _nothing_new(lib):
    after = lib.run(pending(lib.world, lib.world.tenant))
    assert len(lib.before) == 2, "the add and the replace that applied are pending"
    assert after == lib.before


@given("a tenant dump holding a pending activity")
def _dump(lib):
    async def go():
        await lib.build(BASE_STAMPS)
        world = lib.world
        lib.iri = book(world, world.tenant)
        async with commit(world, world.tenant) as session:
            await session.add_graph(lib.iri, triples(lib.iri))
        assert await pending(world, world.tenant), "the dump is taken with an activity pending"
        out = io.BytesIO()
        await dump(world.tenancy, world.store, world.files, world.iris, VIEW, world.tenant, out)
        lib.dump = out.getvalue()

    lib.run(go())


@when("the dump is restored as a new tenant")
def _restore(lib):
    world = lib.world
    summary = lib.run(
        restore(
            world.tenancy,
            world.iris,
            VIEW,
            io.BytesIO(lib.dump),
            RESTORER,
            max_bytes=1 << 30,
            chains=TOY_CHAINS,
        )
    )
    lib.restored = summary.id


@then("the restored activity is not pending")
def _restored_not_pending(lib):
    assert lib.run(pending(lib.world, lib.restored)) == []
    lib.run(lib.relay().run_once())
    assert [e for e, _ in lib.broker.messages if e.tenant == lib.restored] == []


@given("a book commit whose activity is pending")
def _pending_commit(lib):
    async def go():
        await lib.build()
        await lib.subscribe()
        lib.iri = await add_one(lib.world, lib.world.tenant)

    lib.run(go())


@when("the service stops and starts again")
def _restart(lib):
    lib.run(lib.relay().run_once())


@then("a subscriber receives that activity")
def _received(lib):
    assert [e.activity_class.rsplit("#", 1)[-1] for e, _ in lib.received] == ["Add"]
    assert lib.iri in lib.received[0][1].decode()


@given("two replaces of one book, both pending")
def _two_replaces(lib):
    async def go():
        await lib.build()
        await lib.subscribe()
        lib.iri = book(lib.world, lib.world.tenant)
        async with commit(lib.world, lib.world.tenant) as session:
            version = await session.add_graph(lib.iri, triples(lib.iri))
            for _ in range(2):
                version = await session.replace_graph(lib.iri, triples(lib.iri), version)
                lib.versions.append(version)

    lib.run(go())


@when("the relay publishes them")
def _publish(lib):
    lib.run(lib.relay().run_once())


@then("the replace that generated the older version arrives first")
def _older_first(lib):
    replaces = [
        Replace.model_validate_json(body)
        for e, body in lib.received
        if e.activity_class.endswith("Replace")
    ]
    assert [r.generations[0].entity_version for r in replaces] == lib.versions
