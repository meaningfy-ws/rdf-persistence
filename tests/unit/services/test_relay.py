"""The relay: publishes every pending activity at least once, in store order per database
(aggregate-events 1.5; PD-3, PD-5; TC-10 to TC-18a).

The world is the sweep tests': two tenants of the toy library and the application database, over the
fakes. Faults are injected by wrapping the store, the bus or ``Tenancy.tenants``; nothing sleeps.
"""

import asyncio
import json
import logging
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from opentelemetry import trace
from opentelemetry.trace import StatusCode

from rdf_persistence import generated_models
from rdf_persistence.core.domain.exceptions import StoreUnavailable
from rdf_persistence.core.domain.generated.rp_provenance import Generation, Invalidation, Replace
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.events import context_link
from rdf_persistence.services.generated.settings.rp_settings import EventSettings
from rdf_persistence.services.iris import Iris
from rdf_persistence.services.relay import Relay, chain_order
from rdf_persistence.services.schema import load_schema
from rdf_persistence.services.session import open_session
from rdf_persistence.testkit import InMemoryBroker, InMemoryEventBus, wait_until_async
from tests.logs import attributes
from tests.toy import MODULES, SETTINGS, TOY_SCHEMA, dune, library_slots, template, toy_mapper
from tests.unit.services.test_tenant_sweep import CREATOR, make_world

DEPLOYMENT = "deployment-a"
CONTEXT = context_link("https://lib.example")
LOGGER = "rdf_persistence.services.relay"
VIEW = load_schema(TOY_SCHEMA)
NOW = datetime(2026, 11, 15, 9, 0, tzinfo=UTC)
LONG_AGO = '"2001-01-01T00:00:00Z"^^<http://www.w3.org/2001/XMLSchema#dateTime>'


class RecordingOffer:
    def __init__(self) -> None:
        self.offered: list[tuple[str, str]] = []

    def offer(self, tenant: str, activity) -> None:
        self.offered.append((tenant, activity.id))


class FlakyBus(InMemoryEventBus):
    """A bus whose ``fails_at``-th publish of ``tenant`` raises, once."""

    def __init__(self, broker: InMemoryBroker, tenant: str, fails_at: int) -> None:
        super().__init__(broker)
        self._tenant, self._fails_at, self._seen = tenant, fails_at, 0

    async def publish(self, envelope, body) -> None:
        if envelope.tenant == self._tenant:
            self._seen += 1
            if self._seen == self._fails_at:
                raise ConnectionError("the broker is down")
        await super().publish(envelope, body)


@pytest.fixture
async def world() -> SimpleNamespace:
    made = await make_world(Iris(SETTINGS), SETTINGS)
    made.second = (await made.tenancy.create("Bruges", library_slots(), CREATOR)).id
    made.app_iri = str(made.iris.application)
    await made.tenancy.ensure_application_database()
    made.broker = InMemoryBroker()
    made.bus = InMemoryEventBus(made.broker)
    made.relay = lambda bus="default", hub=None, **kw: Relay(
        made.tenancy,
        VIEW,
        generated_models(*MODULES),
        toy_mapper(),
        made.bus if bus == "default" else bus,
        hub,
        deployment=DEPLOYMENT,
        context=CONTEXT,
        **kw,
    )
    await made.relay(None).run_once()  # the roots the tenants were created with are not under test
    return made


def book(world: SimpleNamespace, tenant: str) -> str:
    return str(world.iris.mint_aggregate(tenant, "Book", "books"))


def triples(iri: str) -> list:
    return list(toy_mapper().to_triples(dune(iri)))


def commit(world: SimpleNamespace, tenant: str):
    return world.tenancy.tenant_session(tenant, CREATOR)


async def add_replace_remove(world: SimpleNamespace, tenant: str) -> str:
    iri = book(world, tenant)
    async with commit(world, tenant) as session:
        version = await session.add_graph(iri, triples(iri))
        version = await session.replace_graph(iri, triples(iri), version)
        await session.remove(iri, version)
    return iri


async def add_one(world: SimpleNamespace, tenant: str) -> str:
    iri = book(world, tenant)
    async with commit(world, tenant) as session:
        await session.add_graph(iri, triples(iri))
    return iri


async def pending(world: SimpleNamespace, tenant: str, application: bool = False) -> list[str]:
    opened = (
        world.tenancy.application_session(world.tenancy.toolkit)
        if application
        else world.tenancy.tenant_session(tenant, world.tenancy.toolkit)
    )
    async with opened as session:
        return [iri for iri, _ in await session.pending_activities()]


def sent(world: SimpleNamespace, tenant: str | None = None) -> list[tuple[str, str, str]]:
    """(tenant, class IRI, activity id) of every message, in publication order."""
    return [
        (e.tenant, e.activity_class, json.loads(body)["id"])
        for e, body in world.broker.messages
        if tenant in (None, e.tenant)
    ]


def classes(world: SimpleNamespace, tenant: str) -> list[str]:
    return [c for _, c, _ in sent(world, tenant)]


async def pin_equal_marks(world: SimpleNamespace, tenant: str) -> None:
    graph = world.iris.provenance(tenant)
    await world.store.update(
        world.tenancy.database_of(tenant),
        f"DELETE {{ GRAPH <{graph}> {{ ?a <{v.PENDING_SINCE}> ?t }} }} "
        f"INSERT {{ GRAPH <{graph}> {{ ?a <{v.PENDING_SINCE}> {LONG_AGO} }} }} "
        f"WHERE {{ GRAPH <{graph}> {{ ?a <{v.PENDING_SINCE}> ?t }} }}",
    )


async def insert_in_provenance(world: SimpleNamespace, tenant: str, body: str) -> None:
    graph = world.iris.provenance(tenant)
    await world.store.update(
        world.tenancy.database_of(tenant), f"INSERT DATA {{ GRAPH <{graph}> {{ {body} }} }}"
    )


# -- TC-10 to TC-13: the plain path, order, restart, a lost mark ---------------------------------


async def test_tc10_each_commit_is_published_in_order_with_its_envelope_then_marked(world):
    await add_replace_remove(world, world.tenant)
    await world.relay().run_once()
    assert classes(world, world.tenant) == [str(v.ADD), str(v.REPLACE), str(v.REMOVE)], (
        "the commits are published in order"
    )
    assert {(e.tenant, e.origin, e.context) for e, _ in world.broker.messages} == {
        (world.tenant, DEPLOYMENT, CONTEXT)
    }, "every message carries the tenant, the origin and the context"
    assert await pending(world, world.tenant) == [], "none is pending"
    relayed = await world.store.query(
        world.database,
        f"SELECT ?a WHERE {{ GRAPH <{world.iris.provenance(world.tenant)}> {{ ?a <{v.RELAYED_AT}> ?t }} }}",
    )
    assert {i for _, _, i in sent(world)} <= {str(row[0]) for row in relayed}, (
        "every published activity was marked relayed"
    )


async def test_tc11_equal_marks_are_settled_by_the_version_chain(world):
    await add_replace_remove(world, world.tenant)
    await pin_equal_marks(world, world.tenant)
    await world.relay().run_once()
    assert classes(world, world.tenant) == [str(v.ADD), str(v.REPLACE), str(v.REMOVE)], (
        "equal marks are settled by the version chain"
    )


def test_tc11_a_replace_goes_after_the_activity_that_generated_the_version_it_invalidated():
    def replace(iri: str, invalidates: str, generates: str) -> Replace:
        part = {"activity": iri, "at_time": NOW, "entity": "urn:e:book"}
        return Replace(
            id=iri,
            generations=[Generation(**part, entity_version=generates)],
            invalidations=[Invalidation(**part, entity_version=invalidates)],
        )

    second = replace("urn:a:a-second-by-iri-first", "v1", "v2")
    first = replace("urn:a:z-first-by-chain", "v0", "v1")
    other = ValueError("poison")
    ordered = chain_order([("a", second), ("o", other), ("z", first)])
    assert [iri for iri, _ in ordered] == ["z", "a", "o"], "z first; the rest keep their order"


def test_a_long_chain_in_reverse_is_ordered_without_recursion():
    def link(n: int) -> Replace:
        part = {"activity": f"urn:a:{n}", "at_time": NOW, "entity": "urn:e:book"}
        return Replace(
            id=f"urn:a:{n}",
            generations=[Generation(**part, entity_version=f"v{n + 1}")],
            invalidations=[Invalidation(**part, entity_version=f"v{n}")],
        )

    reversed_chain = [(str(n), link(n)) for n in reversed(range(3000))]
    assert [iri for iri, _ in chain_order(reversed_chain)] == [str(n) for n in range(3000)], (
        "the long reversed chain is put in order"
    )


async def test_tc11a_store_order_wins_over_the_clients_clock(world):
    iri = book(world, world.tenant)

    def at(hour: int):
        return open_session(
            world.store,
            database=world.database,
            tenant_iri=world.tenant,
            principal=CREATOR,
            clock=lambda: NOW.replace(hour=hour),
            iris=world.iris,
        )

    async with at(9) as session:
        version = await session.add_graph(iri, triples(iri))
    async with at(11) as session:
        await session.remove(iri, version)
    async with at(10) as session:  # the add read its clock before the remove's: earlier
        await session.add_graph(iri, triples(iri))
    await world.relay().run_once()
    assert classes(world, world.tenant) == [str(v.ADD), str(v.REMOVE), str(v.ADD)], (
        "the store order wins over the client's clock"
    )


async def test_tc12_a_fresh_relay_publishes_what_an_earlier_one_never_got_to(world):
    await add_one(world, world.tenant)
    world.relay()  # the one that "crashed" before its first round
    await world.relay().run_once()
    assert classes(world, world.tenant) == [str(v.ADD)], (
        "the fresh relay publishes the activity the earlier one never reached"
    )


async def test_tc13_a_lost_mark_publishes_the_activity_again_with_the_same_id(world):
    await add_one(world, world.tenant)
    world.store.on("update", StoreUnavailable("the mark was lost"))
    await world.relay().run_once()  # published, then the mark's update fails
    await world.relay().run_once()
    ids = [i for _, _, i in sent(world, world.tenant)]
    assert len(ids) == 2, "the activity was published twice"
    assert ids[0] == ids[1], "both publications carry the same id"
    assert await pending(world, world.tenant) == [], "nothing is left pending"


# -- TC-14, TC-15, TC-15a: a failing broker, tenants not visited, a poison record ----------------


async def test_tc14_a_failed_publish_stops_that_database_only_and_order_is_kept(world, caplog):
    await add_replace_remove(world, world.tenant)
    await add_one(world, world.second)
    world.bus = FlakyBus(world.broker, world.tenant, fails_at=2)
    relay = world.relay(world.bus)
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        await relay.run_once()
    assert classes(world, world.tenant) == [str(v.ADD)], (
        "only the first activity went out before the failure"
    )
    assert classes(world, world.second) == [str(v.ADD)], "the other tenant went on"
    assert len(await pending(world, world.tenant)) == 2, "both activities stay pending"
    [record] = caplog.records
    assert record.levelno == logging.WARNING, "the failure is logged as a warning"  # TC-13a
    assert record.getMessage() == "publishing an activity failed; retried next round"
    assert attributes(record)["rp.step"] == "relay-publish-failed", "the step"
    assert attributes(record)["rp.tenant.id"] == world.tenant, "the tenant"
    assert attributes(record)["rp.activity.id"], "the activity"
    assert record.exc_info, "with its exception"
    await relay.run_once()
    assert classes(world, world.tenant) == [str(v.ADD), str(v.REPLACE), str(v.REMOVE)], (
        "the later round publishes all in order"
    )


class HangingBus(InMemoryEventBus):
    """A bus whose publish for ``tenant`` never returns."""

    def __init__(self, broker: InMemoryBroker, tenant: str) -> None:
        super().__init__(broker)
        self._tenant = tenant

    async def publish(self, envelope, body) -> None:
        if envelope.tenant == self._tenant:
            await asyncio.Event().wait()
        await super().publish(envelope, body)


async def test_d18_a_publish_that_hangs_times_out_and_stops_that_database_only(world, caplog):
    await add_one(world, world.tenant)
    await add_one(world, world.second)
    relay = world.relay(
        HangingBus(world.broker, world.tenant),
        events=EventSettings(publish_timeout_seconds=0.05),
    )
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        await asyncio.wait_for(relay.run_once(), 5)
    assert classes(world, world.tenant) == [], "nothing went out, nothing marked"
    assert classes(world, world.second) == [str(v.ADD)], "the other tenant went on"
    assert len(await pending(world, world.tenant)) == 1, "retried next round"
    assert [r.levelno for r in caplog.records] == [logging.WARNING], (
        "the timeout is logged as a warning"
    )


async def _deleting(world):
    access, version = await world.tenancy.get(world.tenant)
    await world.tenancy.delete(world.tenant, version)


async def _behind(world):
    world.tenancy.set_aside([world.tenant])


async def _gone(world):
    await world.store.drop_dataset(world.tenancy.database_of(world.tenant))


@pytest.mark.parametrize("setup", [_deleting, _behind, _gone])
async def test_tc15_a_tenant_not_to_be_visited_is_skipped_and_the_others_go_on(
    world, setup, caplog
):
    await add_one(world, world.tenant)
    await add_one(world, world.second)
    await setup(world)
    with caplog.at_level(logging.DEBUG, logger=LOGGER):
        await world.relay().run_once()
    assert sent(world, world.tenant) == [], "the skipped tenant gets nothing"
    assert classes(world, world.second) == [str(v.ADD)], "the other tenant is published"
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING], (
        "the skipped tenant is not logged as a failure"
    )


async def test_tc15_a_database_that_is_gone_is_logged_at_debug(world, caplog):
    await _gone(world)
    with caplog.at_level(logging.DEBUG, logger=LOGGER):
        await world.relay().run_once()
    [record] = caplog.records  # TC-13a
    assert record.levelno == logging.DEBUG, "the gone database is logged at debug"
    assert attributes(record)["rp.tenant.id"] == world.tenant, "the tenant"
    assert attributes(record)["rp.step"] == "relay-database-gone", "the step"
    assert world.tenant not in record.getMessage(), "the tenant is no part of the message"


async def test_tc15a_a_poison_record_is_given_up_and_the_next_one_is_published(world, caplog):
    await insert_in_provenance(
        world,
        world.tenant,
        f"<urn:a:poison> a <urn:x:NoSuchClass> ; <{v.PENDING_SINCE}> {LONG_AGO} .",
    )
    await add_one(world, world.tenant)
    with caplog.at_level(logging.ERROR, logger=LOGGER):
        await world.relay().run_once()
    assert classes(world, world.tenant) == [str(v.ADD)], (
        "the poison record is skipped and the next one is published"
    )
    assert [r.levelno for r in caplog.records] == [logging.ERROR], (
        "the poison record is logged as an error"
    )
    assert caplog.records[0].exc_info, "logged with its traceback (#125)"
    failed = await world.store.query(
        world.database,
        f"ASK {{ GRAPH <{world.iris.provenance(world.tenant)}> {{ <urn:a:poison> <{v.PUBLICATION_FAILED}> ?t }} }}",
    )
    assert failed.askAnswer, "the poison record is given up in the store"
    assert await pending(world, world.tenant) == [], "nothing is left pending"


# -- TC-16: one database failing, a round failing ------------------------------------------------


async def test_tc16_a_store_that_fails_for_one_tenant_does_not_stop_the_others(
    world, monkeypatch, caplog
):
    await add_one(world, world.tenant)
    await add_one(world, world.second)
    bad = world.tenancy.database_of(world.tenant)
    real = world.store.query

    async def query(dataset, sparql):
        if dataset == bad:
            raise StoreUnavailable("the store fails for one tenant")
        return await real(dataset, sparql)

    monkeypatch.setattr(world.store, "query", query)
    with caplog.at_level(logging.DEBUG, logger=LOGGER):
        await world.relay().run_once()
    assert sent(world, world.tenant) == [], "the failing tenant gets nothing"
    assert classes(world, world.second) == [str(v.ADD)], "the other tenant is published"
    [record] = caplog.records
    assert record.levelno == logging.ERROR, "the failure is logged as an error"
    assert record.exc_info, "with the traceback"
    assert attributes(record)["rp.step"] == "relay-database-failed", "the step"
    assert attributes(record)["rp.tenant.id"] == world.tenant, "the tenant"


async def test_tc16_the_loop_survives_a_failed_round_and_publishes_after_a_wake(
    world, monkeypatch, caplog
):
    await add_one(world, world.tenant)
    real = world.tenancy.tenants
    calls = []

    async def tenants():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("a round fails as a whole")
        return await real()

    monkeypatch.setattr(world.tenancy, "tenants", tenants)
    relay = world.relay(events=EventSettings(relay_interval_seconds=3600))
    task = asyncio.create_task(relay.run())
    try:
        with caplog.at_level(logging.ERROR, logger=LOGGER):
            relay.wake()
            await wait_until_async(
                lambda: _truth(len(caplog.records) == 1), "the failed round", poll_seconds=0.01
            )
        assert caplog.records[0].exc_info, "the failure carries its exception"
        assert attributes(caplog.records[0])["rp.step"] == "relay-round-failed", "the step"
        relay.wake()
        await wait_until_async(
            lambda: _truth(len(world.broker.messages) == 1), "a publication", poll_seconds=0.01
        )
    finally:
        task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


async def _truth(value: bool) -> bool:
    return value


# -- TC-17, TC-18: no mark, no bus ---------------------------------------------------------------


async def test_tc17_an_activity_recorded_without_a_mark_is_never_published(world):
    await add_one(world, world.tenant)
    graph = world.iris.provenance(world.tenant)
    await world.store.update(
        world.database,
        f"DELETE WHERE {{ GRAPH <{graph}> {{ ?a <{v.PENDING_SINCE}> ?t }} }}",
    )
    await world.relay().run_once()
    assert world.broker.messages == [], "an activity without a mark is never published"


async def test_tc18_with_no_bus_the_activity_is_relayed_and_offered_once(world):
    hub = RecordingOffer()
    await add_one(world, world.tenant)
    relay = world.relay(None, hub)
    await relay.run_once()
    await relay.run_once()
    assert await pending(world, world.tenant) == [], "the activity is no longer pending"
    assert [t for t, _ in hub.offered] == [world.tenant], (
        "the hub is offered the tenant's activity once"
    )


async def test_an_application_activity_is_published_under_the_application_and_never_offered(
    world,
):
    hub = RecordingOffer()
    iri = str(world.iris.mint_aggregate(world.app_iri, "Template", "templates"))
    async with world.tenancy.application_session(CREATOR) as session:
        await session.add_graph(iri, list(toy_mapper().to_triples(template(iri))))
    await world.relay(world.bus, hub).run_once()
    assert [(t, c) for t, c, _ in sent(world)] == [(world.app_iri, str(v.ADD))], (
        "the application activity is published under the application"
    )
    assert hub.offered == [], "the hub is not offered the application activity"
    assert await pending(world, world.app_iri, application=True) == [], (
        "the application activity is no longer pending"
    )


async def test_a_hub_is_offered_each_published_tenant_activity_in_order(world):
    hub = RecordingOffer()
    await add_replace_remove(world, world.tenant)
    await world.relay(world.bus, hub).run_once()
    assert [i for _, i in hub.offered] == [i for _, _, i in sent(world)], (
        "the hub is offered each published activity in order"
    )
    assert {t for t, _ in hub.offered} == {world.tenant}, (
        "the hub is offered only the tenant's activities"
    )


# -- TC-18a: wakes and rounds --------------------------------------------------------------------


async def test_tc18a_wakes_during_a_round_cause_exactly_one_more_round(world, monkeypatch):
    real = world.tenancy.tenants
    started, release, rounds = asyncio.Event(), asyncio.Event(), []

    async def tenants():
        rounds.append(1)
        started.set()
        if len(rounds) == 1:
            await release.wait()
        return await real()

    monkeypatch.setattr(world.tenancy, "tenants", tenants)
    relay = world.relay(events=EventSettings(relay_interval_seconds=3600))
    task = asyncio.create_task(relay.run())
    try:
        relay.wake()
        await started.wait()
        for _ in range(3):
            relay.wake()
        release.set()
        await wait_until_async(
            lambda: _truth(len(rounds) == 2), "the second round", poll_seconds=0.01
        )
        for _ in range(10):
            await asyncio.sleep(0)  # let a third round happen, if one would
        assert len(rounds) == 2, "the wakes during a round cause one more round"
    finally:
        task.cancel()


async def test_rounds_never_overlap(world, monkeypatch):
    real = world.tenancy.tenants
    inside = peak = 0

    async def tenants():
        nonlocal inside, peak
        inside += 1
        peak = max(peak, inside)
        await asyncio.sleep(0)
        try:
            return await real()
        finally:
            inside -= 1

    monkeypatch.setattr(world.tenancy, "tenants", tenants)
    relay = world.relay()
    await asyncio.gather(relay.run_once(), relay.run_once(), relay.run_once())
    assert peak == 1, "two rounds never overlap"


# -- TC-34, TC-35: the spans of a round (otel-observability PD-5) ---------------------------------


async def test_tc34_a_round_is_a_root_span_with_a_database_span_per_database(world, spans):
    with trace.get_tracer("test").start_as_current_span("outer") as outer:
        await world.relay().run_once()

    by_name: dict[str, list] = {}
    for span in spans():
        by_name.setdefault(span.name, []).append(span)
    [round_span] = by_name["rp.relay.round"]
    assert round_span.parent is None, "the round starts a trace of its own"
    assert round_span.context.trace_id != outer.get_span_context().trace_id, "not outer's trace"
    assert dict(round_span.attributes) == {"rp.step": "relay-round"}, "the round's step"
    databases = by_name["rp.relay.database"]
    assert {s.attributes["rp.tenant.id"] for s in databases} == {
        world.app_iri,
        world.tenant,
        world.second,
    }, "one span per database: the application's and each tenant's"
    assert all(s.parent.span_id == round_span.context.span_id for s in databases), (
        "round's children"
    )
    assert all(s.attributes["rp.step"] == "relay-database" for s in databases), "the step"


async def test_tc35_a_failed_database_is_error_the_round_is_not_and_the_next_tenant_goes(
    world, spans, monkeypatch
):
    await add_one(world, world.tenant)
    await add_one(world, world.second)
    bad = world.tenancy.database_of(world.tenant)
    real = world.store.query

    async def query(dataset, sparql):
        if dataset == bad:
            raise StoreUnavailable("the store fails for one tenant")
        return await real(dataset, sparql)

    monkeypatch.setattr(world.store, "query", query)
    await world.relay().run_once()

    finished = spans()
    [round_span] = [s for s in finished if s.name == "rp.relay.round"]
    assert round_span.status.status_code is StatusCode.UNSET, "the round swallowed the failure"
    failed = [s for s in finished if s.status.status_code is StatusCode.ERROR]
    assert [(s.name, s.attributes["rp.tenant.id"]) for s in failed] == [
        ("rp.relay.database", world.tenant)
    ], "only the failed database's span is ERROR"
    assert classes(world, world.second) == [str(v.ADD)], "the next tenant is still relayed"
