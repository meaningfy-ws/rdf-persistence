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
from rdf_persistence.core.domain.exceptions import (
    MessageLimitExceeded,
    StoreUnavailable,
    TenantBehind,
)
from rdf_persistence.messaging.services.messagebus import Work, command
from rdf_persistence.persistence.services.generated.settings.rp_persistence_settings import (
    LimitSettings,
)
from rdf_persistence.persistence.services.mapper import UnitOfWork
from rdf_persistence.persistence.services.session import Session
from rdf_persistence.provenance.domain.generated.rp_provenance import Activity, Add, Replace
from rdf_persistence.testkit import (
    FakeStore,
    InMemoryBroker,
    InMemoryEventBus,
    wait_until_async,
)
from tests.fixtures.library.domain.generated.templates import Template
from tests.logs import attributes
from tests.toy import toy_mapper
from tests.toy_service import DUNE_BODY, TENANT_BODY, ToyService, made, principal_of

LOGGER = "rdf_persistence.api.entrypoints.kit"


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
        sent = await wait_until_async(
            lambda: _replace_sent(broker), "lib's Replace on the broker", poll_seconds=0.01
        )
        await wait_until_async(
            lambda: _async(there.activities), "cat's observer to run", poll_seconds=0.01
        )
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
    assert world.there.activities[0].id == world.replace.id, (
        "the observer got the other deployment's commit once"
    )
    assert world.there.principals == [world.cat.kit.tenancy.toolkit.id], "a session of the toolkit"
    assert len(world.here.activities) == 1, "lib's observer got it once, in process, not again"


async def test_a_message_of_the_own_origin_is_not_handed_again(world, caplog) -> None:  # TC-24
    caplog.set_level(logging.DEBUG, LOGGER)
    await world.lib.kit.receive(world.envelope, world.replace.model_dump_json().encode())
    assert len(world.here.activities) == 1, (
        "a message of the own origin is not handed to the observer again"
    )
    assert not [r for r in caplog.records if r.levelno > logging.DEBUG], (
        "skipping an own message logs nothing above debug"
    )


async def test_a_kit_without_a_bus_skips_the_message(world, caplog) -> None:
    world.cat.kit.bus = None
    caplog.set_level(logging.DEBUG, LOGGER)
    await sent(world)
    assert len(world.there.activities) == 1, "no more than before"
    assert not [r for r in caplog.records if r.levelno > logging.DEBUG], (
        "a kit without a bus logs nothing above debug"
    )


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
    assert [r.levelno for r in caplog.records if r.levelno > logging.DEBUG] == [logging.WARNING], (
        "a bad message is logged once as a warning"
    )
    await restarted(world)
    assert len(world.there.activities) == 1, "acked: not delivered again"


async def test_a_body_that_does_not_validate_is_logged_without_its_values(
    world, caplog
) -> None:  # #125
    caplog.set_level(logging.DEBUG, LOGGER)
    body = b'{"id": "urn:a:x", "started_at_time": "secret-tenant-text"}'
    await world.cat_bus._deliver((world.envelope, body))  # TC-11
    [record] = [r for r in caplog.records if r.levelno > logging.DEBUG]
    attrs = attributes(record)
    assert record.levelno == logging.WARNING, "one warning"
    assert record.getMessage() == "skipped an event whose class is unknown or whose body is invalid"
    assert attrs["rp.step"] == "receive-invalid-event", "the step"
    assert attrs["error.type"].endswith("ValidationError"), "the kind of failure"
    assert "started_at_time" in str(attrs["rp.error.detail"]), "the field at fault is named"
    assert record.exc_info is None, "no traceback: it would print the values (PD-8)"
    assert "secret-tenant-text" not in caplog.text, (
        "another deployment's data never reaches the log"
    )
    assert "secret-tenant-text" not in f"{record.getMessage()}{attrs}", "nor a message or attribute"


async def test_a_message_naming_a_class_that_is_not_an_activity_is_logged_and_acked(
    world, caplog
) -> None:  # D-19
    caplog.set_level(logging.DEBUG, LOGGER)
    generation = world.cat.kit.view.get_uri("Generation", expand=True)
    await world.cat_bus._deliver(
        (world.envelope.model_copy(update={"activity_class": generation}), b"{}")
    )
    assert [r.levelno for r in caplog.records if r.levelno > logging.DEBUG] == [logging.WARNING], (
        "a message naming a non-activity class is logged once as a warning"
    )
    await restarted(world)
    assert len(world.there.activities) == 1, "acked: not delivered again"


async def test_a_message_for_a_tenant_that_is_not_an_iri_is_logged_and_acked(
    world, caplog
) -> None:  # D-19
    caplog.set_level(logging.DEBUG, LOGGER)
    await sent(world, tenant="not an iri")
    assert len(world.there.activities) == 1, "only the first message reached the observer"
    kit_logs = [r.levelno for r in caplog.records if r.name == LOGGER and r.levelno > logging.DEBUG]
    assert kit_logs == [logging.WARNING], "the skipped message is logged once as a warning"
    await restarted(world)
    assert len(world.there.activities) == 1, "acked: not delivered again"


async def test_a_message_for_a_tenant_this_deployment_lacks_is_logged_and_acked(
    world, caplog
) -> None:  # TC-26
    caplog.set_level(logging.DEBUG, LOGGER)
    lacking = world.cat.kit.tenant_iri(str(uuid.uuid4()))
    await sent(world, tenant=lacking)
    assert len(world.there.activities) == 1, "only the first message reached the observer"
    [record] = [r for r in caplog.records if r.levelno > logging.DEBUG]
    attrs = attributes(record)
    assert record.levelno == logging.WARNING, (
        "the skipped message is logged once as a warning"
    )  # TC-13d
    assert record.getMessage() == "skipped an event of a tenant this deployment lacks"
    assert attrs["rp.step"] == "receive-unknown-tenant", "the step"
    assert attrs["rp.activity.id"] == world.replace.id, "the activity"
    assert attrs["rp.tenant.id"] == lacking, "the tenant, as an attribute"
    assert str(attrs["error.type"]).endswith(("DatabaseGone", "NotFound")), "the kind of failure"
    assert lacking not in record.getMessage(), "the tenant IRI is in no message"
    assert record.exc_info, "the error travels with it"
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
    assert len(world.there.activities) == 1, "only the first message reached the observer"
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
    await wait_until_async(
        lambda: _async(seen.activities), "cat's observer of Add", poll_seconds=0.01
    )
    assert len(seen.activities) == 1, "the application's Add; the tenant's were relayed before"
    assert seen.principals == [world.cat.kit.tenancy.toolkit.id], (
        "the observer saw the toolkit principal"
    )
    assert seen.templates == [[iri]], "a session on the application database"


async def test_an_observer_that_exceeds_the_message_limit_is_logged_at_error_and_acked(
    world, caplog
) -> None:
    async def runaway(activity: Replace, work: Work) -> None:
        raise MessageLimitExceeded(1)

    world.cat.kit.bus = bootstrap(observers={Replace: [runaway]}, mapper=world.cat.kit.mapper)
    await sent(world)
    assert [r.levelno for r in caplog.records if r.name == LOGGER] == [logging.ERROR], (
        "an observer over the limit is logged once at error"
    )
    await restarted(world)
    assert [r.levelno for r in caplog.records if r.name == LOGGER] == [logging.ERROR], "acked"


async def test_a_looping_observer_over_the_limit_leaves_one_error_record_in_the_run(
    world, caplog
) -> None:  # TC-32
    async def replace(cmd: Replace, work: Work) -> None:
        await work.send(command(Replace))

    async def again(activity: Replace, work: Work) -> None:
        await bus.handle(command(Replace), SimpleNamespace(session=work.session))

    bus = bootstrap(
        commands={Replace: replace},
        observers={Replace: [again]},
        limits=LimitSettings(max_messages=3),
        mapper=world.cat.kit.mapper,
    )
    world.cat.kit.bus = bus
    caplog.set_level(logging.DEBUG)
    await sent(world)
    await wait_until_async(
        lambda: _async([r for r in caplog.records if r.levelno >= logging.ERROR]),
        "the message limit to be logged",
        poll_seconds=0.01,
    )
    errors = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert [r.name for r in errors] == [LOGGER], (
        "one record in the run, from the kit that handled it"
    )
    assert errors[0].getMessage() == "an incoming event exceeded the message limit"
    assert attributes(errors[0])["rp.message.limit"] == 3, "the limit"
    assert "message limit 3 reached by Replace" in str(errors[0].exc_info[1]), (
        "the command is named"
    )


async def test_a_failing_observer_and_then_the_limit_leave_one_record_each(
    world, caplog
) -> None:  # TC-12
    async def broken(activity: Replace, work: Work) -> None:
        raise RuntimeError("observer broke")

    async def runaway(activity: Replace, work: Work) -> None:
        raise MessageLimitExceeded(1)

    world.cat.kit.bus = bootstrap(
        observers={Replace: [broken, runaway]}, mapper=world.cat.kit.mapper
    )
    caplog.set_level(logging.DEBUG)
    await sent(world)
    [failed] = [r for r in caplog.records if r.levelno >= logging.ERROR and r.name != LOGGER]
    [limit] = [r for r in caplog.records if r.levelno >= logging.ERROR and r.name == LOGGER]
    assert failed.getMessage() == "an observer failed", "the bus's record, constant"
    assert str(attributes(failed)["rp.observer.name"]).endswith("broken"), "the observer"
    assert attributes(failed)["rp.activity.id"] == world.replace.id, "the activity"
    assert failed.exc_info, "it carries its exception"
    assert failed.exc_info[1].args == ("observer broke",), "the very one"
    assert attributes(limit)["rp.message.limit"] == 1, "the limit record carries the limit"


async def test_a_key_error_while_handing_over_leaves_the_message_unacked(
    world, monkeypatch
) -> None:  # D-8
    async def broken(self, activity_iri: str) -> bool:
        raise KeyError("a lookup that is not a missing tenant")

    monkeypatch.setattr(Session, "is_recorded", broken)
    await sent(world)
    assert len(world.there.activities) == 1, "not handed over"
    monkeypatch.undo()
    await restarted(world)
    assert len(world.there.activities) == 2, "redelivered: the failure was not a skip"


async def test_an_application_activity_without_an_application_class_is_logged_and_acked(
    world, caplog, monkeypatch
) -> None:  # D-6
    def no_application(principal: str):
        raise LookupError("the schema declares no application class")

    monkeypatch.setattr(world.cat.kit, "application_session", no_application)
    caplog.set_level(logging.DEBUG, LOGGER)
    await sent(world, tenant=world.cat.kit.tenancy.application)
    assert len(world.there.activities) == 1, "only the first message reached the observer"
    assert [r.levelno for r in caplog.records if r.levelno > logging.DEBUG] == [logging.WARNING], (
        "the skipped message is logged once as a warning"
    )
    monkeypatch.undo()
    await restarted(world)
    assert len(world.there.activities) == 1, "acked"


@pytest.mark.parametrize(
    ("public_url", "link"),
    [
        ("https://lib.example", "https://lib.example/api/context.jsonld"),
        (None, "/api/context.jsonld"),
    ],
)
async def test_the_envelope_links_the_context_under_the_mount_prefix(
    public_url, link
) -> None:  # D-16
    broker = InMemoryBroker()
    lib = ToyService(
        event_bus=InMemoryEventBus(broker), deployment="lib", mount="/api", public_url=public_url
    )
    async with lib.app.router.lifespan_context(lib.app), lib.client() as http:
        created = await http.post("/api/libraries", json=TENANT_BODY, headers=lib.bearer("ada"))
        assert created.status_code == 201, created.text
        await lib.kit.relay.run_once()
    assert {envelope.context for envelope, _ in broker.messages} == {link}, (
        "every envelope links the context under the mount prefix"
    )
