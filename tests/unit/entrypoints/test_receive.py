"""What a deployment does with a message another deployment published (aggregate-events 2.2, PD-10; TC-24 to TC-28, TC-27a).

Two toy services, ``lib`` and ``cat``, share one broker and one fake store. ``lib`` replaces a book and
relays it; ``cat`` has an observer of ``Replace``. A message that raises is not acked: the fake bus
delivers it again when the bus is started again.
"""

import logging
import uuid
from types import SimpleNamespace

import pytest

from rdf_persistence import bootstrap
from rdf_persistence.domain.exceptions import (
    MessageLimitExceeded,
    StoreUnavailable,
    TenantBehind,
)
from rdf_persistence.domain.generated.rp_provenance import Activity, Add, Replace
from rdf_persistence.services.mapper import UnitOfWork
from rdf_persistence.services.messagebus import Work
from rdf_persistence.testkit import (
    FakeStore,
    InMemoryBroker,
    InMemoryEventBus,
    wait_until_async,
)
from tests.fixtures.library.generated.templates import Template
from tests.toy import toy_mapper
from tests.toy_service import DUNE_BODY, ToyService, principal_of
from tests.unit.entrypoints.test_service_kit import made

LOGGER = "rdf_persistence.entrypoints.kit"


class Seen:
    """An observer that keeps each activity and the principal of the session it was given."""

    def __init__(self) -> None:
        self.activities: list[Activity] = []
        self.principals: list[str] = []
        self.templates: list[list[str]] = []

    async def __call__(self, activity: Activity, work: Work) -> None:
        self.activities.append(activity)
        self.principals.append(work.session.principal.id)


class SeenTemplates(Seen):
    """As ``Seen``, and the templates its session finds: only an application session may ask."""

    async def __call__(self, activity: Activity, work: Work) -> None:
        await super().__call__(activity, work)
        self.templates.append(await work.session.find(Template))


def with_bus(service: ToyService, observed: type[Activity], seen: Seen | None = None) -> Seen:
    """Give the service's kit a bus whose one observer is returned."""
    seen = seen or Seen()
    service.kit.bus = bootstrap(observers={observed: [seen]}, mapper=service.kit.mapper)
    return seen


@pytest.fixture
async def world():
    """``lib`` has made a tenant and a book and replaced it; its relay has run; ``cat`` was listening."""
    store, broker = FakeStore(), InMemoryBroker()
    lib_bus, cat_bus = InMemoryEventBus(broker), InMemoryEventBus(broker)
    lib = ToyService(store=store, event_bus=lib_bus, deployment="lib")
    cat = ToyService(store=store, event_bus=cat_bus, deployment="cat")
    here, there = with_bus(lib, Replace), with_bus(cat, Replace)
    # only lib serves (its lifespan runs its relay): cat's relay would publish lib's commits too
    await cat_bus.start(cat.kit.receive)
    async with lib.app.router.lifespan_context(lib.app), lib.client() as http:
        headers = lib.bearer("ada")
        path, book, etag = await made(http, headers)
        replaced = await http.put(book, json=DUNE_BODY, headers={**headers, "If-Match": etag})
        assert replaced.status_code == 200, replaced.text
        sent = await wait_until_async(lambda: _replace_sent(broker), "lib's Replace on the broker")
        await wait_until_async(lambda: _async(there.activities), "cat's observer to run")
        yield SimpleNamespace(
            store=store, broker=broker, lib=lib, cat=cat, lib_bus=lib_bus, cat_bus=cat_bus,
            here=here, there=there, tenant=sent[0].tenant, envelope=sent[0],
            replace=Replace.model_validate_json(sent[1]),
        )  # fmt: skip
    await cat_bus.close()


async def _async(value):
    return value


async def _replace_sent(broker: InMemoryBroker):
    return next((m for m in broker.messages if m[0].activity_class.endswith("Replace")), None)


async def restarted(world) -> None:
    """The consumer of ``cat`` stops and starts: what it did not ack comes again."""
    await world.cat_bus.close()
    await world.cat_bus.start(world.cat.kit.receive)


async def sent(world, **changes) -> None:
    """``lib`` publishes the replace again, with the envelope changed by ``changes``."""
    envelope = world.envelope.model_copy(update=changes)
    await world.lib_bus.publish(envelope, world.replace)


async def test_a_commit_of_another_deployment_reaches_the_observer_once_with_the_toolkits_session(
    world,
) -> None:  # TC-24
    assert len(world.there.activities) == 1, "cat's observer got it once"
    assert world.there.activities[0].id == world.replace.id
    assert world.there.principals == [world.cat.kit.tenancy.toolkit.id], "a session of the toolkit"
    assert len(world.here.activities) == 1, "lib's observer got it once, in process, not again"


async def test_a_message_of_the_own_origin_is_not_handed_again(world, caplog) -> None:  # TC-24
    caplog.set_level(logging.DEBUG, LOGGER)
    await world.lib.kit.receive(world.envelope, world.replace.model_dump_json().encode())
    assert len(world.here.activities) == 1
    assert not [r for r in caplog.records if r.levelno > logging.DEBUG]


async def test_a_kit_without_a_bus_skips_the_message(world, caplog) -> None:
    world.cat.kit.bus = None
    caplog.set_level(logging.DEBUG, LOGGER)
    await sent(world)
    assert len(world.there.activities) == 1, "no more than before"
    assert not [r for r in caplog.records if r.levelno > logging.DEBUG]


@pytest.mark.parametrize(
    ("changes", "body"),
    [
        ({"activity_class": "http://nowhere.example/Nope"}, None),
        ({}, b'{"not": "an activity"}'),
    ],
    ids=["unknown class", "body that does not validate"],
)
async def test_a_message_of_an_unknown_class_or_a_bad_body_is_logged_and_acked(
    world, caplog, changes, body
) -> None:  # TC-25
    caplog.set_level(logging.DEBUG, LOGGER)
    envelope = world.envelope.model_copy(update=changes)
    payload = body or world.replace.model_dump_json().encode()
    await world.cat_bus._deliver((envelope, payload))
    assert len(world.there.activities) == 1, "no observer ran"
    assert [r.levelno for r in caplog.records if r.levelno > logging.DEBUG] == [logging.WARNING]
    await restarted(world)
    assert len(world.there.activities) == 1, "acked: not delivered again"


async def test_a_message_for_a_tenant_this_deployment_lacks_is_logged_and_acked(
    world, caplog
) -> None:  # TC-26
    caplog.set_level(logging.DEBUG, LOGGER)
    await sent(world, tenant=world.cat.kit.tenant_iri(str(uuid.uuid4())))
    assert len(world.there.activities) == 1
    assert [r.levelno for r in caplog.records if r.levelno > logging.DEBUG] == [logging.WARNING]
    await restarted(world)
    assert len(world.there.activities) == 1, "acked"


async def test_a_store_that_is_unavailable_leaves_the_message_unacked(world) -> None:  # TC-27
    world.store.on("query", StoreUnavailable("the store is down"))
    await sent(world)
    assert len(world.there.activities) == 1, "not handed over"
    await restarted(world)
    assert len(world.there.activities) == 2, "redelivered when the bus starts again"


async def test_a_tenant_that_is_behind_leaves_the_message_unacked(world) -> None:  # TC-27a
    world.cat.kit.tenancy.set_aside([world.tenant])
    await sent(world)
    assert len(world.there.activities) == 1
    with pytest.raises(TenantBehind):
        await world.cat.kit.receive(world.envelope, world.replace.model_dump_json().encode())
    world.cat.kit.tenancy.set_aside([])
    await restarted(world)
    assert len(world.there.activities) == 2, "redelivered once the migration is done"


async def test_an_application_activity_reaches_the_observer_with_an_application_session(
    world,
) -> None:  # TC-28
    seen = with_bus(world.cat, Add, SeenTemplates())
    kit = world.lib.kit
    await kit.tenancy.ensure_application_database()
    iri = kit.application_iri(Template)
    async with kit.application_session(principal_of("eve")) as session:
        work = UnitOfWork(session, toy_mapper())
        work.add(Template(id=iri, label="a template"))
        await work.commit()
    await wait_until_async(lambda: _async(seen.activities), "cat's observer of Add")
    assert len(seen.activities) == 1, "the application's Add; the tenant's were relayed before"
    assert seen.principals == [world.cat.kit.tenancy.toolkit.id]
    assert seen.templates == [[iri]], "a session on the application database"


async def test_an_observer_that_exceeds_the_message_limit_is_logged_at_error_and_acked(
    world, caplog
) -> None:
    async def runaway(activity: Replace, work: Work) -> None:
        raise MessageLimitExceeded(1)

    world.cat.kit.bus = bootstrap(observers={Replace: [runaway]}, mapper=world.cat.kit.mapper)
    await sent(world)
    assert [r.levelno for r in caplog.records if r.name == LOGGER] == [logging.ERROR]
    await restarted(world)
    assert [r.levelno for r in caplog.records if r.name == LOGGER] == [logging.ERROR], "acked"
