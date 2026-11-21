"""SPIKE-1 (DEC-4, S-3 to S-5): an aggregate root may itself be an ``Activity``.

``Review`` is the toy's root that is ``is_a: Activity``. Its own graph keeps the review; the commit's
activity is a separate ``Add`` recorded in the provenance graph, so the two never meet (PD-26, PD-34).
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest
from rdflib import URIRef

from rdf_persistence import generated_models
from rdf_persistence.events.services.event_hub import EventHub
from rdf_persistence.events.services.events import context_link
from rdf_persistence.events.services.relay import Relay
from rdf_persistence.iris.services.iris import Iris
from rdf_persistence.persistence.services.mapper import UnitOfWork
from rdf_persistence.provenance.domain.generated.rp_provenance import Add
from rdf_persistence.schema.services.schema import load_schema
from rdf_persistence.testkit import FakeStore
from rdf_persistence.testkit.fakes import FAKE_DATABASE
from tests.fixtures.library.domain.generated.books_activities import Review
from tests.tenancy_world import CREATOR, make_world
from tests.toy import ADA, MODULES, SETTINGS, TENANT, TOY_SCHEMA, toy_mapper
from tests.unit.activity_helpers import (
    PROVENANCE,
    events,
    only_activity,
    opened,
    stored_graph,
)

REVIEW_CLASS = "https://example.org/ns/library#Review"
STARTED = datetime(2026, 11, 20, 9, 0, tzinfo=UTC)
REVIEW_IRI = f"{TENANT}/reviews/{UUID(int=1)}"


def a_review() -> Review:
    return Review(
        id=REVIEW_IRI,
        label="A review",
        description="A review of Dune.",
        started_at_time=STARTED,
    )


@pytest.fixture
async def store() -> FakeStore:
    fake = FakeStore()
    await fake.create_dataset(FAKE_DATABASE)
    return fake


async def commit_review(store: FakeStore) -> None:
    async with opened(store) as session:
        work = UnitOfWork(session, toy_mapper())
        work.add(a_review())
        await work.commit()


async def test_s3_committing_a_review_records_one_separate_add_generating_the_review(store) -> None:
    await commit_review(store)
    recorded = await only_activity(store)
    assert type(recorded) is Add, "the commit's activity is typed rp:Add"
    assert recorded.id.startswith("urn:uuid:"), "with a fresh urn:uuid: id"
    assert recorded.id != REVIEW_IRI, "that is not the review's own id"
    stored = await stored_graph(store, PROVENANCE)
    assert not [*stored.triples((URIRef(REVIEW_IRI), None, None))], (
        "the provenance graph holds nothing about the review itself"
    )
    assert len(recorded.generations or []) == 1, "one generation"
    assert [(e, c) for e, c, _ in events(recorded.generations)] == [(REVIEW_IRI, REVIEW_CLASS)], (
        "of the review, as lib:Review"
    )


async def test_s4_a_review_reads_back_equal_with_its_start_time(store) -> None:
    await commit_review(store)
    async with opened(store) as session:
        read = await UnitOfWork(session, toy_mapper()).get(Review, REVIEW_IRI)
    stamps = {"created", "creator", "modified", "contributor"}  # Tracked: the toolkit fills them
    assert read.model_dump(exclude=stamps) == a_review().model_dump(exclude=stamps), (
        "the stored review is the one that was added"
    )
    assert read.creator == ADA, "and the toolkit stamped its creator"
    assert read.started_at_time == STARTED, "its started_at_time is kept"


async def test_s5_the_event_hub_is_offered_exactly_one_add_for_the_commit() -> None:
    world = await make_world(Iris(SETTINGS), SETTINGS)
    await world.tenancy.ensure_application_database()
    hub = EventHub()
    relay = Relay(
        world.tenancy,
        load_schema(TOY_SCHEMA),
        generated_models(*MODULES),
        toy_mapper(),
        None,
        hub,
        deployment="deployment-a",
        context=context_link("https://lib.example"),
    )
    await relay.run_once()  # the tenant's own creation is not under test
    async with hub.subscribe(world.tenant) as queue:
        async with world.tenancy.tenant_session(world.tenant, CREATOR) as session:
            work = UnitOfWork(session, toy_mapper())
            work.add(a_review().model_copy(update={"id": f"{world.tenant}/reviews/{UUID(int=1)}"}))
            await work.commit()
        await relay.run_once()
        offered = []
        while not queue.empty():
            offered.append(queue.get_nowait())
    assert [type(a) for a in offered] == [Add], "one activity offered, an Add"
    assert offered[0].id.startswith("urn:uuid:"), "the commit's activity, not the review"
    assert len(offered[0].generations or []) == 1, "generating the one review"
