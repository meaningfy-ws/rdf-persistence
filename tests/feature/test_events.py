"""Steps of ``events.feature``: the toy library and its relay over the fakes (aggregate-events 1.7).

Scenario to requirement of ``rp-events``: the first two scenarios are "A committed change is pending
publication atomically", the next two "Events reach the bus at least once, in order per aggregate"; the last two (aggregate-events 3.2) are
"Server-sent events respect access", run through the real route on the toy service.
Nothing sleeps: the relay is driven by ``run_once``.
"""

import asyncio
import io
from contextlib import AsyncExitStack
from types import SimpleNamespace

import pytest
from pytest_bdd import given, scenarios, then, when

from rdf_persistence import generated_models
from rdf_persistence.core.domain.exceptions import Conflict
from rdf_persistence.core.domain.generated.rp_provenance import Replace
from rdf_persistence.events.services.events import context_link
from rdf_persistence.events.services.relay import Relay
from rdf_persistence.iris.services.iris import Iris
from rdf_persistence.schema.services.schema import load_schema
from rdf_persistence.tenancy.services.tenant_dump import dump, restore
from rdf_persistence.testkit import InMemoryBroker, InMemoryEventBus
from tests.toy import MODULES, SETTINGS, TOY_SCHEMA, toy_mapper
from tests.toy_service import ToyService
from tests.unit.entrypoints.scene import Scene
from tests.unit.entrypoints.test_events_route import (
    Block,
    Follow,
    another_book,
    follow,
    listening,
    mount,
    replace,
    reshape_grants,
    with_carol,
)
from tests.unit.events.test_relay import add_one, book, commit, pending, triples
from tests.unit.tenancy.test_pending_mark import RESTORER, TOY_CHAINS
from tests.unit.tenancy.test_tenant_dump import BASE_STAMPS
from tests.unit.tenancy.test_tenant_sweep import make_world

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
    assert after == lib.before, "nothing new was committed since the last look"


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
    assert lib.run(pending(lib.world, lib.restored)) == [], (
        "the restored tenant has nothing pending"
    )
    lib.run(lib.relay().run_once())
    assert [e for e, _ in lib.broker.messages if e.tenant == lib.restored] == [], (
        "the restored tenant's messages were not sent again"
    )


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
    assert [e.activity_class.rsplit("#", 1)[-1] for e, _ in lib.received] == ["Add"], (
        "the received message is an Add"
    )
    assert lib.iri in lib.received[0][1].decode(), "the received message names the library's IRI"


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
    assert [r.generations[0].entity_version for r in replaces] == lib.versions, (
        "the replaces arrive oldest version first"
    )


class Following:
    """A scenario of the events route: the toy service, its scene, and the streams the steps hold open."""

    def __init__(self) -> None:
        self.loop = asyncio.new_event_loop()
        self.stack = AsyncExitStack()
        self.scene: Scene
        self.stream: Follow
        self.heard: list[Block] = []
        self.first_id = ""
        self.etag = ""
        self.other_iri = self.other = self.other_etag = ""

    def run(self, work):
        return self.loop.run_until_complete(work)

    def close(self) -> None:
        self.run(self.stack.aclose())
        self.loop.close()

    async def open(self) -> None:
        service = ToyService()
        await self.stack.enter_async_context(service.app.router.lifespan_context(service.app))
        http = await self.stack.enter_async_context(service.client())
        mount(service, "/fast")
        self.scene = await Scene.set_up(service, http)
        await service.kit.relay.run_once()  # a follower hears only what follows

    async def follow(self, who: str, **headers: str) -> Follow:
        stream = follow(self.scene, who, **headers)
        await self.stack.enter_async_context(stream)
        return stream


@pytest.fixture
def following():
    made = Following()
    yield made
    made.close()


@given("a reader with a Prohibition of read on one book, following the tenant's events")
def _barred_reader(following):
    async def go():
        await following.open()
        scene = following.scene
        following.other_iri, following.other, following.other_etag = await another_book(scene)
        await reshape_grants(scene, with_carol(hide=scene.book_iri))
        following.stream = await following.follow("carol")
        await listening(scene.service.kit.hub)

    following.run(go())


@when("that book and another are replaced")
def _replace_both(following):
    async def go():
        scene = following.scene
        await replace(scene, scene.book, scene.book_etag, "Dune Messiah")
        await replace(scene, following.other, following.other_etag, "Emma 2")

    following.run(go())


@then("the reader receives the other book's event only")
def _only_the_other(following):
    async def go():
        [event] = await following.stream.take(1)
        with pytest.raises(TimeoutError):
            await following.stream.take(1, timeout=0.2)
        return event

    event = following.run(go())
    assert [g.entity for g in Replace.model_validate_json(event.data).generations] == [
        following.other_iri
    ], "the reader hears only the other book"


@given("a reader whose stream ended after event A, and two later commits")
def _ended_after_a(following):
    async def go():
        await following.open()
        scene = following.scene
        async with follow(scene) as first:
            await listening(scene.service.kit.hub)
            following.etag = await replace(scene, scene.book, scene.book_etag, "A")
            [a] = await first.take(1)
        following.first_id = a.id
        following.etag = await replace(scene, scene.book, following.etag, "Later one")
        following.etag = await replace(scene, scene.book, following.etag, "Later two")

    following.run(go())


@when("the reader reconnects with Last-Event-ID A within 7 days")
def _reconnect(following):
    async def go():
        following.stream = await following.follow("rita", **{"Last-Event-ID": following.first_id})
        following.heard = await following.stream.take(2)
        scene = following.scene
        await replace(scene, scene.book, following.etag, "Live")
        following.heard += await following.stream.take(1)

    following.run(go())


@then("the reader receives the two later events, each once, then live events")
def _resumed(following):
    ids = [e.id for e in following.heard]
    assert len(ids) == 3, "two later events and a live one, none twice"
    assert len(set(ids)) == 3, "two later events and a live one, none twice"
    assert following.first_id not in ids, "the resumed stream does not repeat the first event"
    assert [e.event for e in following.heard] == ["Replace"] * 3, (
        "the resumed stream carries the three later replaces"
    )
