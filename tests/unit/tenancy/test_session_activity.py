"""Every commit records one activity in its own update request, and hands it to a hook (message-bus
PD-6 to PD-10; TC-22 to TC-40d).

``B1``, ``B2``, ``B3`` are books of the toy tenant. The provenance graph is ``iris.provenance(TENANT)``.
"""

import io
import logging
from collections.abc import AsyncIterator

import pytest
from rdflib import RDF, Graph, Literal, URIRef

from rdf_persistence.core.domain.exceptions import Conflict, InvalidIri
from rdf_persistence.iris.domain.layout import application_database_name
from rdf_persistence.iris.services.generated.rp_iris_services import IriPolicy
from rdf_persistence.iris.services.iris import DEFAULT_IRIS, Iris
from rdf_persistence.persistence.services.session import Session
from rdf_persistence.provenance.domain.generated.rp_provenance import Activity, Add, Remove, Replace
from rdf_persistence.provenance.services.provenance import Served
from rdf_persistence.schema.services import vocabulary as v
from rdf_persistence.tenancy.services.tenant_dump import dump, restore
from rdf_persistence.testkit import FakeStore, assert_isomorphic
from rdf_persistence.testkit.fakes import FAKE_DATABASE
from tests.dump_helpers import BASE_STAMPS, RESTORER, TOY_CHAINS, VIEW
from tests.logs import attributes
from tests.tenancy_world import CREATOR, make_world
from tests.toy import ADA, BOB, BOOK_CLASS, SETTINGS, TENANT, ShelveBooks, template, toy_mapper
from tests.toy_service import ToyService
from tests.unit.activity_helpers import (
    B1,
    B2,
    B3,
    PROVENANCE,
    SHELF_CLASS,
    Hook,
    X,
    activities,
    book,
    events,
    only_activity,
    opened,
    stored_graph,
)


def shape(activity: Activity) -> dict:
    """The activity as plain values, parts compared without order (PD-4)."""
    return {
        **activity.model_dump(exclude={"generations", "invalidations"}),
        "type": type(activity).__name__,
        "generations": events(activity.generations),
        "invalidations": events(activity.invalidations),
    }


@pytest.fixture
async def store() -> FakeStore:
    fake = FakeStore()
    await fake.create_dataset(FAKE_DATABASE)
    return fake


@pytest.fixture
async def session(store) -> AsyncIterator[Session]:
    async with opened(store) as s:
        yield s


# -- TC-22 to TC-26: the standard activity --------------------------------------------------------


async def test_tc22_an_add_records_one_add_for_the_principal_with_one_generation(store, session):
    version = await session.add_graph(B1, book(B1))
    activity = await only_activity(store)
    assert type(activity) is Add, "typed rp:Add"
    stored = await stored_graph(store, PROVENANCE)
    assert {*stored.objects(URIRef(activity.id), RDF.type)} == {v.ADD, v.ACTIVITY}, (
        "and prov:Activity"
    )
    assert activity.was_associated_with == [ADA], "the session's principal"
    assert activity.started_at_time < activity.ended_at_time, "start before end"
    assert events(activity.generations) == [(B1, str(BOOK_CLASS), version)], (
        "the book at its new version"
    )
    assert activity.invalidations is None, "no invalidation"
    assert {p.at_time for p in activity.generations} == {activity.ended_at_time}, (
        "atTime is the end"
    )
    assert not [*stored.triples((URIRef(B1), None, None))], "no statement about the book itself"
    assert not [*stored.triples((None, URIRef("http://purl.org/dc/terms/title"), None))], "no title"


async def test_tc23_a_replace_records_one_replace_with_a_generation_and_an_invalidation(
    store, session
):
    v1 = await session.add_graph(B1, book(B1))
    v2 = await session.replace_graph(B1, book(B1), v1)
    replace = (await activities(store))[-1]
    assert type(replace) is Replace, "typed rp:Replace"
    assert events(replace.generations) == [(B1, str(BOOK_CLASS), v2)], "the new version generated"
    assert events(replace.invalidations) == [(B1, str(BOOK_CLASS), v1)], (
        "the old version invalidated"
    )


async def test_tc24_a_remove_records_one_remove_with_the_version_it_removed(store, session):
    v1 = await session.add_graph(B1, book(B1))
    await session.remove(B1, v1)
    remove = (await activities(store))[-1]
    assert type(remove) is Remove, "typed rp:Remove"
    assert remove.generations is None, "nothing generated"
    assert events(remove.invalidations) == [(B1, str(BOOK_CLASS), v1)], "the removed version"
    assert [type(a) for a in await activities(store)] == [Add, Remove], "the Add is still there"


async def test_tc25_a_transaction_of_two_adds_records_one_add_with_two_generations(store, session):
    async with session.transaction() as transaction:
        one = await transaction.add_graph(B1, book(B1))
        two = await transaction.add_graph(B2, book(B2))
    activity = await only_activity(store)
    assert type(activity) is Add, "every change is an add"
    assert events(activity.generations) == sorted(
        [(B1, str(BOOK_CLASS), one), (B2, str(BOOK_CLASS), two)]
    ), "one generation each"


async def test_tc26_a_mixed_transaction_records_one_plain_activity(store, session):
    v1 = await session.add_graph(B1, book(B1))
    async with session.transaction() as transaction:
        v3 = await transaction.add_graph(B3, book(B3))
        await transaction.remove(B1, v1)
    mixed = (await activities(store))[-1]
    assert events(mixed.generations) == [(B3, str(BOOK_CLASS), v3)], "the added book is generated"
    assert events(mixed.invalidations) == [(B1, str(BOOK_CLASS), v1)], (
        "the removed book is invalidated"
    )
    stored = await stored_graph(store, PROVENANCE)
    assert {*stored.objects(URIRef(mixed.id), RDF.type)} == {v.ACTIVITY}, "prov:Activity only"
    assert type(mixed) is Activity, "read as the plain class"
    assert (len(mixed.generations), len(mixed.invalidations)) == (1, 1), "one of each"


# -- TC-27, TC-28: nothing is recorded when nothing is written ------------------------------------


async def test_tc27_a_refused_replace_leaves_the_provenance_graph_as_it_was(store, session):
    v1 = await session.add_graph(B1, book(B1))
    await session.replace_graph(B1, book(B1), v1)
    before = await stored_graph(store, PROVENANCE)
    with pytest.raises(Conflict):
        await session.replace_graph(B1, book(B1), v1)
    assert_isomorphic(await stored_graph(store, PROVENANCE), before)


async def test_tc28_an_empty_transaction_sends_nothing_and_records_nothing(store, session):
    async with session.transaction():
        pass
    assert store.sent("update") == [], "no request"
    assert await activities(store) == [], "no activity"


async def test_tc28_a_transaction_that_only_requires_a_graph_sends_nothing(store, session):
    await session.add_graph(B1, book(B1))
    sent = len(store.sent("update"))
    async with session.transaction() as transaction:
        transaction._require_present(B1)
    assert len(store.sent("update")) == sent, "no request for the requirement"
    assert len(await activities(store)) == 1, "only the add's activity"


# -- TC-29 to TC-31, TC-40c: a served command -----------------------------------------------------


async def test_tc29_a_served_command_is_the_activity_and_the_session_overwrites_its_principal(
    store, session
):
    v1 = await session.add_graph(B1, book(B1))
    served = toy_mapper().served(Replace(id=X, was_associated_with=[BOB]))
    async with session.transaction(served=served) as transaction:
        await transaction.replace_graph(B1, book(B1), v1)
    replace = (await activities(store))[-1]
    assert replace.id == X, "the command's IRI"
    assert replace.was_associated_with == [ADA], (
        "the principal comes from the session, not the command"
    )
    stored = await stored_graph(store, PROVENANCE)
    assert {*stored.objects(URIRef(X), RDF.type)} == {v.REPLACE, v.ACTIVITY}, "its types"


async def test_tc30_a_second_commit_under_the_same_activity_iri_is_a_conflict_naming_it(
    store, session
):
    v1 = await session.add_graph(B1, book(B1))
    async with session.transaction(served=toy_mapper().served(Replace(id=X))) as transaction:
        v2 = await transaction.replace_graph(B1, book(B1), v1)
    with pytest.raises(Conflict, match=X):
        async with session.transaction(served=toy_mapper().served(Replace(id=X))) as transaction:
            await transaction.replace_graph(B1, book(B1), v2)
    _, _, version = await session.get_graph(B1)
    assert version == v2, "the book is as the first commit left it"
    assert [a.id for a in await activities(store)].count(X) == 1, "one activity X"


async def test_tc31_a_served_command_serves_one_transaction_and_the_second_sends_nothing(
    store, session
):
    v1 = await session.add_graph(B1, book(B1))
    served = toy_mapper().served(Replace(id=X))
    async with session.transaction(served=served) as transaction:
        v2 = await transaction.replace_graph(B1, book(B1), v1)
    sent = len(store.sent("update"))
    with pytest.raises(RuntimeError, match=X):
        async with session.transaction(served=served) as transaction:
            await transaction.replace_graph(B1, book(B1), v2)
    assert len(store.sent("update")) == sent, "no request for the second"


async def test_tc40c_a_stale_replace_with_a_fresh_id_names_the_book_and_not_the_activity(
    store, session
):
    v1 = await session.add_graph(B1, book(B1))
    await session.replace_graph(B1, book(B1), v1)
    with pytest.raises(Conflict) as refused:
        async with session.transaction(served=toy_mapper().served(Replace(id=X))) as transaction:
            await transaction.replace_graph(B1, book(B1), v1)
    assert B1 in str(refused.value), "the existing reason first"
    assert X not in str(refused.value), "the activity is not blamed"
    assert X not in [a.id for a in await activities(store)], "nothing recorded"


# -- TC-32, TC-33: which sessions record ----------------------------------------------------------


async def test_tc32_a_session_that_does_not_record_writes_no_provenance_graph(store):
    # about the unrecorded path itself (record_activities=False)
    async with opened(store, record_activities=False) as session:
        await session.add_graph(B1, book(B1))
    assert len(await stored_graph(store, PROVENANCE)) == 0, "no provenance graph"


async def test_tc33_a_tenant_is_created_in_the_tenant_database_only_as_far_as_activities_go():
    world = await make_world(Iris(SETTINGS), SETTINGS)
    system = world.tenancy.system_database
    asked = await world.store.query(system, f"ASK {{ GRAPH ?g {{ ?s a <{v.ACTIVITY}> }} }}")
    assert not asked.askAnswer, "the system database records no activity"
    found = await activities(world.store, world.iris.provenance(world.tenant), world.database)
    assert [(type(a), a.was_associated_with) for a in found] == [(Add, [CREATOR.id])], (
        "one add of the root, by the creator"
    )
    assert events(found[0].generations)[0][0] == world.tenant, "the entity is the tenant root"


# -- TC-34 to TC-36: the hook ---------------------------------------------------------------------


async def test_tc34_the_hook_gets_the_stored_record_and_the_session_once_after_the_commit(store):
    hook = Hook()
    async with opened(store, on_commit=hook) as session:
        v1 = await session.add_graph(B1, book(B1))
        await session.replace_graph(B1, book(B1), v1)
        replace, given = hook.calls[-1]
        assert len(hook.calls) == 2, "once per commit"
        assert given is session, "with the session"
    stored = (await activities(store))[-1]
    assert type(replace) is Replace, "a Replace"
    assert shape(replace) == shape(stored), "equal to the record read through the mapper"


async def test_tc35_a_hook_that_raises_is_logged_and_the_commit_stands(store, caplog):
    async def failing(activity: Activity, session: Session) -> None:
        raise RuntimeError("hook broke")

    async with opened(store, on_commit=failing) as session:
        with caplog.at_level(logging.ERROR, logger="rdf_persistence.persistence.services.session"):
            version = await session.add_graph(B1, book(B1))
    assert version, "the commit returned"
    [record] = caplog.records  # TC-13b
    assert attributes(record)["rp.activity.id"] == (await only_activity(store)).id, (
        "the error names the activity"
    )
    assert record.getMessage() == "on_commit failed", "and says what failed"
    assert attributes(record)["rp.step"] == "commit-hook-failed", "at which step"
    assert record.exc_info, "with the exception"
    assert "hook broke" in str(record.exc_info[1]), "the hook's"


async def test_tc36_a_refused_commit_does_not_call_the_hook(store):
    hook = Hook()
    async with opened(store, on_commit=hook) as session:
        v1 = await session.add_graph(B1, book(B1))
        await session.replace_graph(B1, book(B1), v1)
        calls = len(hook.calls)
        with pytest.raises(Conflict):
            await session.replace_graph(B1, book(B1), v1)
    assert len(hook.calls) == calls, "no call for the refused commit"


async def test_a_hook_is_not_called_when_the_request_failed_in_the_store(store):
    hook = Hook()
    async with opened(store, on_commit=hook) as session:
        await session.add_graph(B1, book(B1))
        with pytest.raises(Conflict, match="already exists"):
            await session.add_graph(B1, book(B1))
    assert len(hook.calls) == 1, "only the first add"


# -- TC-37 to TC-40d: shapes of change ------------------------------------------------------------


async def test_tc37_a_remove_with_dependents_records_the_target_only(store):
    comments = [str(DEFAULT_IRIS.mint_aggregate(TENANT, "Comment", "comments")) for _ in range(2)]
    async with opened(store, dependents=[(v.ANNOTATION, v.HAS_TARGET)]) as session:
        v1 = await session.add_graph(B1, book(B1))
        for comment in comments:
            await session.add_graph(
                comment,
                [
                    (URIRef(comment), RDF.type, v.ANNOTATION),
                    (URIRef(comment), v.HAS_TARGET, URIRef(B1)),
                ],
            )
        await session.remove(B1, v1)
    remove = (await activities(store))[-1]
    assert type(remove) is Remove, "one rp:Remove"
    assert events(remove.invalidations) == [(B1, str(BOOK_CLASS), v1)], "one invalidation: the book"
    for comment in comments:
        assert len(await stored_graph(store, URIRef(comment))) == 0, "the comment is gone"


async def test_tc38_a_one_add_commit_is_one_request_with_one_more_operation_before_the_release(
    store, session
):
    await session.add_graph(B1, book(B1))
    (request,) = store.sent("update")
    operations = request.split(";\n")
    assert len(operations) == 4, "guard, write, activity, release"
    assert f"GRAPH <{PROVENANCE}>" in operations[2], (
        "the activity is the operation before the release"
    )
    assert operations[3].startswith("DELETE"), "the release is last"


async def test_tc39_a_replace_of_the_tenant_root_records_the_tenant_iri_as_the_entity(
    store, session
):
    root = [(URIRef(TENANT), RDF.type, URIRef("https://example.org/ns/library#Library"))]
    v1 = await session.add_graph(TENANT, root)
    await session.replace_graph(TENANT, root, v1)
    replace = (await activities(store))[-1]
    assert [e[0] for e in events(replace.generations)] == [TENANT], "the tenant IRI"
    assert [e[0] for e in events(replace.invalidations)] == [TENANT], "invalidated too"


async def test_tc40_a_restored_tenant_carries_the_activities_of_the_original():
    world = await make_world(Iris(SETTINGS), SETTINGS, BASE_STAMPS)
    for _ in range(2):  # with the creation of the tenant, three activities
        iri = str(world.iris.mint_aggregate(world.tenant, "Book", "books"))
        async with world.session() as session:
            await session.add_graph(iri, book(iri))
    provenance = world.iris.provenance(world.tenant)
    original = await activities(world.store, provenance, world.database)
    assert len(original) == 3, "three activities to carry"
    out = io.BytesIO()
    await dump(world.tenancy, world.store, world.files, world.iris, VIEW, world.tenant, out)
    summary = await restore(
        world.tenancy,
        world.iris,
        VIEW,
        io.BytesIO(out.getvalue()),
        RESTORER,
        max_bytes=1 << 30,
        chains=TOY_CHAINS,
    )
    record, _ = await world.tenancy.get(summary.id)
    found = await activities(world.store, world.iris.provenance(summary.id), record.database_name)
    assert [a.id for a in found] == [a.id for a in original], "the same three activities"
    new_id, old_id = world.iris.tenant_id_of(summary.id), world.iris.tenant_id_of(world.tenant)
    entities = {e[0] for a in found for e in events(a.generations)}
    assert all(new_id in e and old_id not in e for e in entities), (
        "entity IRIs under the new tenant"
    )


async def test_tc40a_a_root_with_no_type_has_no_entity_class_and_the_hook_gets_a_valid_model(store):
    hook = Hook()
    async with opened(store, on_commit=hook) as session:
        await session.add_graph(
            B1, [(URIRef(B1), URIRef("http://purl.org/dc/terms/title"), v.ENTITY)]
        )
    activity = await only_activity(store)
    assert [p.entity_class for p in activity.generations] == [None], "no class recorded"
    (given, _) = hook.calls[0]
    assert shape(given) == shape(activity), "the hook's model is the stored one"


async def test_tc40b_a_replace_that_changes_the_class_invalidates_the_old_and_generates_the_new(
    store, session
):
    typed = lambda cls: [(URIRef(B1), RDF.type, URIRef(cls))]  # noqa: E731
    v1 = await session.add_graph(B1, typed(str(BOOK_CLASS)))
    v2 = await session.replace_graph(B1, typed(SHELF_CLASS), v1)
    replace = (await activities(store))[-1]
    assert events(replace.invalidations) == [(B1, str(BOOK_CLASS), v1)], "the old class"
    assert events(replace.generations) == [(B1, SHELF_CLASS, v2)], "the new class"


async def test_a_root_of_several_classes_names_the_first_in_sorted_order(store, session):
    triples = [(URIRef(B1), RDF.type, URIRef(c)) for c in (SHELF_CLASS, str(BOOK_CLASS))]
    await session.add_graph(B1, triples)
    activity = await only_activity(store)
    assert [p.entity_class for p in activity.generations] == [str(BOOK_CLASS)], (
        "Book sorts before Shelf"
    )


async def test_tc40d_an_application_aggregate_is_recorded_in_the_application_provenance_graph():
    world = await make_world(Iris(SETTINGS), SETTINGS)
    await world.tenancy.ensure_application_database()
    iri = str(world.iris.mint_aggregate(str(world.iris.application), "Template", "templates"))
    async with world.tenancy.application_session(CREATOR) as session:
        await session.add_graph(iri, list(toy_mapper().to_triples(template(iri))))
    found = await activities(
        world.store,
        world.iris.provenance(str(world.iris.application)),
        application_database_name(SETTINGS.prefix),
    )
    assert [type(a) for a in found] == [Add], "one add"
    assert events(found[0].generations)[0][0] == iri, "of the template"


# -- activity-iri-policy PD-5, PD-6: the commit places its activity under the policy ----------------

PLACED = "{tenant}/activity/{id}"
UUID_OF_COMMAND = "5c0f5f4a-8d0a-4c1e-9d55-0e5bb1b6c002"
COMMAND_ID = f"urn:uuid:{UUID_OF_COMMAND}"
FOREIGN = f"https://foreign.example/x/activity/{UUID_OF_COMMAND}"
OTHER_TENANT = "https://example.org/libraries/0a0a0a0a"


def placing() -> Iris:
    """The kit's ``Iris`` of the toy service under the activity template ``{tenant}/activity/{id}``."""
    return ToyService(iri_policy=IriPolicy(activity_template=PLACED)).kit.iris


async def all_iris(store: FakeStore) -> set[str]:
    """Every IRI in any graph of the tenant database, as subject, predicate or object."""
    text = "CONSTRUCT { ?s ?p ?o } WHERE { GRAPH ?g { ?s ?p ?o } }"
    graph = (await store.query(FAKE_DATABASE, text)).graph or Graph()
    return {str(t) for triple in graph for t in triple if isinstance(t, URIRef)}


def shelving(note: str = "top shelf") -> Served:
    return toy_mapper().served(ShelveBooks(id=COMMAND_ID, shelf_note=note))


async def test_a_commit_under_an_activity_template_records_its_activity_under_the_tenant(store):
    placed = f"{TENANT}/activity/{UUID_OF_COMMAND}"
    hook = Hook()
    seen: list[bool] = []

    async def on_commit(activity, session) -> None:
        seen.append(await session.is_recorded(placed))
        await hook(activity, session)

    async with (
        opened(store, iris=placing(), on_commit=on_commit) as session,
        session.transaction(served=shelving()) as transaction,
    ):
        await transaction.add_graph(B1, book(B1))
    stored = await stored_graph(store, PROVENANCE)
    assert (await only_activity(store)).id == placed, "the activity is at the tenant's template"
    assert not [i for i in await all_iris(store) if i.startswith("urn:uuid:")], (
        "no provisional IRI in any graph of the tenant database"
    )
    assert [a.id for a, _ in hook.calls] == [placed], "on_commit sees the placed IRI"
    assert seen == [True], "is_recorded sees the placed IRI when on_commit runs"
    assert {*stored.subjects(None, Literal("top shelf"))} == {URIRef(placed)}, (
        "the command's own triples are about the placed IRI"
    )
    named = {str(o) for _, _, o in stored.triples((None, v.PART_ACTIVITY, None))}
    assert named == {placed}, "every generation names the placed IRI as its activity"


async def test_every_invalidation_of_a_placed_activity_names_it(store):
    placed = f"{TENANT}/activity/{UUID_OF_COMMAND}"
    async with opened(store, iris=placing()) as session:
        v1 = await session.add_graph(B1, book(B1))
        async with session.transaction(served=shelving()) as transaction:
            await transaction.replace_graph(B1, book(B1), v1)
    activity = (await activities(store))[-1]
    assert activity.id == placed, "the replace is the placed activity"
    parts = [*(activity.generations or []), *(activity.invalidations or [])]
    assert len(parts) == 2, "one generation and one invalidation"
    assert {p.activity for p in parts} == {placed}, "each part names the placed IRI"


async def test_a_commit_without_a_command_records_an_activity_under_the_template(store):
    async with opened(store, iris=placing()) as session:
        await session.add_graph(B1, book(B1))
    activity = await only_activity(store)
    assert activity.id.startswith(f"{TENANT}/activity/"), "placed under the tenant"
    assert placing().activity_uuid(activity.id), "with a UUID"
    assert {p.activity for p in activity.generations} == {activity.id}, "the parts name it"


async def test_a_second_commit_of_the_same_served_command_is_refused_as_today(store):
    served = shelving()
    async with opened(store, iris=placing()) as session:
        v1 = await session.add_graph(B1, book(B1))
        async with session.transaction(served=served) as transaction:
            v2 = await transaction.replace_graph(B1, book(B1), v1)
        with pytest.raises(RuntimeError, match=COMMAND_ID):
            async with session.transaction(served=served) as transaction:
                await transaction.replace_graph(B1, book(B1), v2)
        with pytest.raises(Conflict, match=f"{TENANT}/activity/{UUID_OF_COMMAND}"):
            async with session.transaction(served=shelving("again")) as transaction:
                await transaction.replace_graph(B1, book(B1), v2)
    assert served.activity.id == COMMAND_ID, "the served command is never changed"


async def test_session_activity_iri_is_what_the_commit_records(store):
    async with opened(store, iris=placing()) as session:
        expected = session.activity_iri(COMMAND_ID)
        async with session.transaction(served=shelving()) as transaction:
            await transaction.add_graph(B1, book(B1))
        assert expected == f"{TENANT}/activity/{UUID_OF_COMMAND}", "the template's IRI"
        assert (await only_activity(store)).id == expected, "what the commit recorded"
        assert session.activity_iri(expected) == expected, "a placed IRI stays itself"


@pytest.mark.parametrize(
    "given",
    [
        FOREIGN,
        f"{OTHER_TENANT}/activity/{UUID_OF_COMMAND}",
        "https://example.org/not-an-activity",
    ],
    ids=["foreign", "another-tenants-placed-iri", "no-activity-iri"],
)
async def test_session_activity_iri_refuses_a_foreign_activity(store, given):
    iris = placing()
    assert iris.activity_uuid(FOREIGN) == UUID_OF_COMMAND, "activity_uuid alone accepts it"
    async with opened(store, iris=iris) as session:
        with pytest.raises(ValueError, match="activity"):
            session.activity_iri(given)


async def test_without_a_template_the_activity_is_the_command_id(store):
    async with opened(store) as session:
        assert session.activity_iri(COMMAND_ID) == COMMAND_ID, "the default policy changes nothing"
        async with session.transaction(served=shelving()) as transaction:
            await transaction.add_graph(B1, book(B1))
    assert (await only_activity(store)).id == COMMAND_ID, "recorded as the command's id"


async def test_a_hand_made_aggregate_at_an_activity_iri_is_refused(store):
    iri = f"{TENANT}/activity/{UUID_OF_COMMAND}"
    async with opened(store, iris=placing()) as session:
        sent = len(store.sent("update"))
        with pytest.raises(InvalidIri):
            await session.add_graph(iri, book(iri))
    assert len(store.sent("update")) == sent, "nothing written"
