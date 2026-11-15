"""Adversarial tests of the outbox and the relay (aggregate-events stage 1; PD-1 to PD-5, PD-14, PD-16, RISK-7).

The world is the relay tests': two tenants of the toy library and the application database over the
fakes; nothing sleeps. A test marked ``xfail(strict=True)`` is a finding: the code does not do what
the design says. The fake store applies one update at a time and has no real clock, so a race
between two stores' writers cannot be shown here; what is shown are interleavings the relay itself
allows (a commit made while a round is publishing, a cancel mid-publish, a tenant made mid-round).
"""

import asyncio
import json
import logging
from types import SimpleNamespace

import pytest

from rdf_persistence.domain.generated.rp_workflow import Transition
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.relay import chain_order
from rdf_persistence.services.session import open_session
from rdf_persistence.testkit import InMemoryBroker, InMemoryEventBus, wait_until_async
from tests.toy import ApproveBook, library_slots, toy_mapper
from tests.unit.services import test_relay
from tests.unit.services.test_relay import (
    CREATOR,
    LOGGER,
    LONG_AGO,
    NOW,
    RecordingOffer,
    add_one,
    add_replace_remove,
    book,
    classes,
    commit,
    insert_in_provenance,
    pending,
    sent,
    triples,
)

world = test_relay.world  # the relay tests' fixture, shared
APPROVE = "urn:uuid:5c0f5f4a-8d0a-4c1e-9d55-0e5bb1b6c1a1"


class HookedBus(InMemoryEventBus):
    """A bus that runs ``before`` once, at the start of its first publish (a commit mid-round, say)."""

    def __init__(self, broker: InMemoryBroker, before) -> None:
        super().__init__(broker)
        self._before = before

    async def publish(self, envelope, body) -> None:
        before, self._before = self._before, None
        if before is not None:
            await before()
        await super().publish(envelope, body)


class DownBus(InMemoryEventBus):
    """A bus that always raises for ``tenant``."""

    def __init__(self, broker: InMemoryBroker, tenant: str) -> None:
        super().__init__(broker)
        self._tenant = tenant

    async def publish(self, envelope, body) -> None:
        if envelope.tenant == self._tenant:
            raise ConnectionError("this tenant's stream is down")
        await super().publish(envelope, body)


async def _truth(value: bool) -> bool:
    return value


def ids(world: SimpleNamespace, tenant: str | None = None) -> list[str]:
    return [i for _, _, i in sent(world, tenant)]


# -- commits and tenants that appear while a round runs ------------------------------------------


async def test_a_commit_made_while_a_round_publishes_is_published_once_by_the_next_round(world):
    async def commit_meanwhile():
        await add_one(world, world.tenant)

    await add_one(world, world.tenant)
    relay = world.relay(HookedBus(world.broker, commit_meanwhile))
    await relay.run_once()
    assert len(ids(world)) == 1, "the late commit was not in this round's read"
    assert len(await pending(world, world.tenant)) == 1, "its mark was not replaced unseen"
    await relay.run_once()
    await relay.run_once()
    assert len(ids(world)) == len(set(ids(world))) == 2
    assert await pending(world, world.tenant) == []


async def test_a_tenant_created_while_a_round_publishes_is_visited_by_the_next_round(world):
    made: list[str] = []

    async def create_meanwhile():
        made.append((await world.tenancy.create("Antwerp", library_slots(), CREATOR)).id)

    await add_one(world, world.tenant)
    relay = world.relay(HookedBus(world.broker, create_meanwhile))
    await relay.run_once()
    assert sent(world, made[0]) == [], "listed before it existed: not visited this round"
    await relay.run_once()
    assert len(sent(world, made[0])) >= 1, "its own creation activities go out next round"
    assert len(ids(world)) == len(set(ids(world))), "nothing twice"


async def test_wake_from_inside_a_publish_makes_exactly_one_more_round(world):
    await add_one(world, world.tenant)
    rounds: list[int] = []
    relay = world.relay(interval=3600)
    real = world.tenancy.tenants

    async def tenants():
        rounds.append(1)
        return await real()

    world.tenancy.tenants = tenants
    first = HookedBus(world.broker, lambda: _wake_thrice(relay))
    relay._bus = first
    task = asyncio.create_task(relay.run())
    try:
        relay.wake()
        await wait_until_async(lambda: _truth(len(rounds) == 2), "the second round")
        for _ in range(10):
            await asyncio.sleep(0)
        assert len(rounds) == 2
    finally:
        task.cancel()


async def _wake_thrice(relay) -> None:
    for _ in range(3):
        relay.wake()


# -- cancel and restart --------------------------------------------------------------------------


async def test_a_round_cancelled_mid_publish_loses_nothing_and_a_restart_publishes_it(world):
    inside, never = asyncio.Event(), asyncio.Event()

    async def block():
        inside.set()
        await never.wait()

    await add_one(world, world.tenant)
    relay = world.relay(HookedBus(world.broker, block), interval=3600)
    task = asyncio.create_task(relay.run())
    relay.wake()
    await inside.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert world.broker.messages == []
    assert len(await pending(world, world.tenant)) == 1, "still pending"
    await relay.run_once()  # the lock was released by the cancel
    assert len(ids(world)) == 1
    assert await pending(world, world.tenant) == []


async def test_a_cancel_after_publish_before_the_mark_publishes_again_with_the_same_id(world):
    await add_one(world, world.tenant)
    inside, never = asyncio.Event(), asyncio.Event()
    real = world.store.update

    async def update(dataset, sparql):
        if v.PENDING_SINCE.n3() in sparql and "DELETE" in sparql:
            inside.set()
            await never.wait()
        return await real(dataset, sparql)

    world.store.update = update
    relay = world.relay(interval=3600)
    task = asyncio.create_task(relay.run_once())
    await inside.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    world.store.update = real
    await world.relay().run_once()
    assert len(ids(world)) == 2
    assert len(set(ids(world))) == 1, "at least once, the same id"


# -- one tenant failing forever ------------------------------------------------------------------


async def test_a_tenant_whose_stream_is_down_forever_never_holds_back_the_others(world, caplog):
    relay = world.relay(DownBus(world.broker, world.tenant))
    for _ in range(3):
        await add_one(world, world.tenant)
        await add_one(world, world.second)
        with caplog.at_level(logging.WARNING, logger=LOGGER):
            await relay.run_once()
    assert sent(world, world.tenant) == []
    assert len(ids(world, world.second)) == 3
    assert len(await pending(world, world.tenant)) == 3
    assert {r.levelno for r in caplog.records} == {logging.WARNING}


async def test_the_messages_of_an_aggregate_keep_their_order_across_rounds_after_a_failure(world):
    iri = book(world, world.tenant)
    async with commit(world, world.tenant) as session:
        version = await session.add_graph(iri, triples(iri))
    world.bus.fail_next_publish()
    relay = world.relay()
    await relay.run_once()
    assert world.broker.messages == []
    async with commit(world, world.tenant) as session:
        version = await session.replace_graph(iri, triples(iri), version)
    await relay.run_once()
    async with commit(world, world.tenant) as session:
        await session.remove(iri, version)
    await relay.run_once()
    assert classes(world, world.tenant) == [str(v.ADD), str(v.REPLACE), str(v.REMOVE)]


# -- a long backlog ------------------------------------------------------------------------------


async def test_a_long_backlog_goes_out_in_one_round_in_store_order_each_once(world):
    made = [await add_one(world, world.tenant) for _ in range(40)]
    await world.relay().run_once()
    out = ids(world, world.tenant)
    assert len(out) == len(set(out)) == 40
    assert await pending(world, world.tenant) == []
    bodies = [json.loads(b) for e, b in world.broker.messages if e.tenant == world.tenant]
    assert len(made) == len(bodies)


# -- poison records ------------------------------------------------------------------------------


def poison(name: str, body: str) -> str:
    return f"<urn:a:{name}> a <{v.ADD}> ; <{v.PENDING_SINCE}> {LONG_AGO} ; {body} ."


@pytest.mark.parametrize(
    "body",
    [
        f"<{v.HAS_GENERATION}> <urn:part:missing>",
        f"<{v.HAS_GENERATION}> 'not a node'",
        f"<{v.HAS_INVALIDATION}> <urn:part:missing>",
        f"<{v.ACTIVITY_STARTED}> 'not a time'",
    ],
    ids=["generation-missing", "generation-literal", "invalidation-missing", "bad-time"],
)
async def test_a_malformed_pending_activity_is_given_up_and_the_database_goes_on(world, body):
    await insert_in_provenance(world, world.tenant, poison("bad", body))
    await add_one(world, world.tenant)
    await world.relay().run_once()
    assert len(ids(world, world.tenant)) == 1, "the sound activity went out"
    assert "urn:a:bad" not in ids(world)
    assert await pending(world, world.tenant) == []


@pytest.mark.parametrize("typing", ["", "a 'Add' ;", "a <https://example.org/ns/library#Book> ;"])
async def test_a_pending_record_of_no_activity_type_is_given_up_not_published(world, typing):
    await insert_in_provenance(
        world, world.tenant, f"<urn:a:odd> {typing} <{v.PENDING_SINCE}> {LONG_AGO} ."
    )
    await add_one(world, world.tenant)
    await world.relay().run_once()
    assert "urn:a:odd" not in ids(world), "a record that is no activity is never published"
    assert len(ids(world, world.tenant)) == 1
    assert await pending(world, world.tenant) == []


@pytest.mark.parametrize(
    "mark",
    ["'yesterday'", '"2001-01-01T00:00:00"^^<http://www.w3.org/2001/XMLSchema#dateTime>'],
    ids=["string", "naive-datetime"],
)
async def test_a_pending_mark_that_is_not_a_time_does_not_stall_the_database(world, mark):
    await add_one(world, world.tenant)
    await insert_in_provenance(
        world, world.tenant, f"<urn:a:odd> a <{v.ADD}> ; <{v.PENDING_SINCE}> {mark} ."
    )
    await world.relay().run_once()
    assert len(ids(world, world.tenant)) >= 1, "the sound activity is not held back by a bad mark"


async def test_an_activity_marked_pending_twice_is_published_once_and_fully_unmarked(world):
    await add_one(world, world.tenant)
    graph = world.iris.provenance(world.tenant)
    await world.store.update(
        world.database,
        f"INSERT {{ GRAPH <{graph}> {{ ?a <{v.PENDING_SINCE}> {LONG_AGO} }} }} "
        f"WHERE {{ GRAPH <{graph}> {{ ?a <{v.PENDING_SINCE}> ?t }} }}",
    )
    relay = world.relay()
    await relay.run_once()
    await relay.run_once()
    assert len(ids(world, world.tenant)) == 1
    assert await pending(world, world.tenant) == []


def test_a_cycle_in_the_version_chain_still_returns_every_activity_once():
    from rdf_persistence.domain.generated.rp_provenance import Generation, Invalidation, Replace

    def replace(iri: str, invalidates: str, generates: str) -> Replace:
        part = {"activity": iri, "at_time": NOW, "entity": "urn:e:book"}
        return Replace(
            id=iri,
            generations=[Generation(**part, entity_version=generates)],
            invalidations=[Invalidation(**part, entity_version=invalidates)],
        )

    items = [
        ("a", replace("a", "v2", "v1")),
        ("b", replace("b", "v1", "v2")),
        ("self", replace("self", "s", "s")),
    ]
    assert sorted(i for i, _ in chain_order(items)) == ["a", "b", "self"]


# -- consumer subclass ---------------------------------------------------------------------------


async def test_a_consumer_subclass_is_published_in_its_own_class_with_its_own_slots(world):
    iri = book(world, world.tenant)
    command = toy_mapper().served(ApproveBook(id=APPROVE, used_resource=iri))
    async with commit(world, world.tenant) as session:
        await session.add_graph(iri, triples(iri), served=command)
    await world.relay().run_once()
    [(envelope, body)] = [m for m in world.broker.messages if json.loads(m[1])["id"] == APPROVE]
    assert envelope.activity_class == "https://example.org/ns/library#ApproveBook"
    assert json.loads(body)["used_resource"] == iri


async def test_a_served_transition_is_published_in_its_class(world):
    iri = book(world, world.tenant)
    command = toy_mapper().served(Transition(id=APPROVE, used_resource=iri))
    async with commit(world, world.tenant) as session:
        await session.add_graph(iri, triples(iri), served=command)
    await world.relay().run_once()
    [envelope] = [e for e, b in world.broker.messages if json.loads(b)["id"] == APPROVE]
    assert envelope.activity_class == str(v.TRANSITION)


# -- who is visited, who is marked ---------------------------------------------------------------


async def test_the_system_database_is_listed_from_but_never_asked_for_pending_activities(world):
    # a round reads the tenant list there; it holds no activities and is never written
    asked: set[str] = set()
    written: set[str] = set()
    real_query, real_update = world.store.query, world.store.update

    async def query(dataset, sparql):
        if str(v.PENDING_SINCE) in sparql:
            asked.add(dataset)
        return await real_query(dataset, sparql)

    async def update(dataset, sparql):
        written.add(dataset)
        return await real_update(dataset, sparql)

    await add_one(world, world.tenant)
    world.store.query, world.store.update = query, update
    await world.relay().run_once()
    world.store.query, world.store.update = real_query, real_update
    assert world.tenancy.system_database not in asked | written
    assert world.database in asked


async def test_a_session_that_does_not_record_leaves_nothing_for_the_relay(world):
    iri = book(world, world.tenant)
    async with open_session(
        world.store,
        database=world.database,
        tenant_iri=world.tenant,
        principal=CREATOR,
        iris=world.iris,
        record_activities=False,
    ) as session:
        await session.add_graph(iri, triples(iri))
    await world.relay().run_once()
    assert sent(world, world.tenant) == []


async def test_a_hub_that_raises_after_the_mark_delays_the_rest_but_loses_nothing(world, caplog):
    class Raising(RecordingOffer):
        def offer(self, tenant, activity) -> None:
            super().offer(tenant, activity)
            if len(self.offered) == 1:
                raise RuntimeError("a bad offer")

    hub = Raising()
    await add_replace_remove(world, world.tenant)
    relay = world.relay(world.bus, hub)
    with caplog.at_level(logging.ERROR, logger=LOGGER):
        await relay.run_once()
    await relay.run_once()
    assert classes(world, world.tenant) == [str(v.ADD), str(v.REPLACE), str(v.REMOVE)]
    assert len(set(ids(world))) == 3, "no activity twice"


# -- plumbing outside the provenance graph -------------------------------------------------------


async def test_a_plumbing_triple_planted_in_a_data_graph_is_not_an_activity_to_relay(world):
    stray = f"<urn:a:stray> <{v.PENDING_SINCE}> {LONG_AGO} ."
    await world.store.update(world.database, f"INSERT DATA {{ GRAPH <urn:g:other> {{ {stray} }} }}")
    await world.relay().run_once()
    assert "urn:a:stray" not in ids(world)
