"""Tenancy over the fakes: create writes the access record last, delete marks `deleting` first (PD-6a, PD-8, PD-9)."""

import logging
from datetime import UTC, datetime

import pytest
from rdflib import Literal

from rdf_persistence.domain.exceptions import (
    Conflict,
    InvalidBody,
    NotFound,
    StoredDataInvalid,
    StoreUnavailable,
)
from rdf_persistence.domain.generated.rp_access import Action, Grant, Prohibition
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.generated.rp_tenancy import TenantState
from rdf_persistence.domain.generated.service.rp_service import GrantSet
from rdf_persistence.domain.iris import system_database_name, tenant_resource_name
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.access import AccessRules, load_role_definitions
from rdf_persistence.services.mapper import UnitOfWork
from rdf_persistence.services.session import open_session
from rdf_persistence.services.tenancy import Tenancy
from rdf_persistence.testkit import FakeFileStore, FakeStore
from tests.fixtures.library.generated.library import Library
from tests.fixtures.library.generated.library_access import LibraryAccess
from tests.toy import ADA, BOB, ROLES, SETTINGS, caller, library_slots, toy_mapper

ODRL = "http://www.w3.org/ns/odrl/2/"
NOW = datetime(2026, 11, 5, 9, 0, tzinfo=UTC)
CREATOR = Principal(id=ADA)
SYSTEM = system_database_name(SETTINGS.prefix)
PREFIX = "lib-t-"
ROOT_LABEL = "CONSTRUCT { ?s ?p ?o } WHERE { GRAPH ?g { ?s ?p ?o } }"


@pytest.fixture
def store() -> FakeStore:
    return FakeStore()


@pytest.fixture
def files() -> FakeFileStore:
    return FakeFileStore()


@pytest.fixture
async def tenancy(store, files) -> Tenancy:
    made = Tenancy(
        store,
        files,
        SETTINGS,
        mapper=toy_mapper(),
        root_class=Library,
        access_class=LibraryAccess,
        clock=lambda: NOW,
    )
    await made.ensure_system_database()
    return made


async def tenant_databases(store: FakeStore) -> list[str]:
    return [name for name in await store.list_datasets() if name.startswith(PREFIX)]


async def test_the_system_database_is_created_once_and_the_call_says_whether_it_made_it(
    store, files
):
    made = Tenancy(
        store, files, SETTINGS, mapper=toy_mapper(), root_class=Library, access_class=LibraryAccess
    )
    assert (await made.ensure_system_database(), await made.ensure_system_database()) == (
        True,
        False,
    )
    assert await store.list_datasets() == [SYSTEM]


async def test_create_makes_a_database_and_a_bucket_named_after_the_tenant(tenancy, store, files):
    summary = await tenancy.create("Ghent", library_slots(), CREATOR)
    name = tenant_resource_name(SETTINGS.prefix, summary.id)
    assert await tenant_databases(store) == [name], "the database"
    assert await files.list_buckets(PREFIX) == [name], "the bucket"


async def test_create_answers_an_active_summary_under_the_consumers_base(tenancy):
    summary = await tenancy.create("Ghent", library_slots(), CREATOR)
    assert (summary.label, summary.state) == ("Ghent", TenantState.ACTIVE.value)
    assert summary.id.startswith(f"{SETTINGS.base}{SETTINGS.tenant_segment}/"), "a minted IRI"


async def test_create_stores_the_root_object_under_the_tenant_iri(tenancy, store):
    summary = await tenancy.create("Ghent", library_slots("Ghent"), CREATOR)
    name = tenant_resource_name(SETTINGS.prefix, summary.id)
    async with open_session(
        store, database=name, tenant_iri=summary.id, principal=CREATOR
    ) as session:
        root = await UnitOfWork(session, toy_mapper()).get(Library, summary.id)
    assert (root.city, root.creator) == ("Ghent", ADA), "the root keeps the creator's tracking"


async def test_create_grants_the_creator_role_on_the_tenant_to_the_creator(tenancy):
    summary = await tenancy.create("Ghent", library_slots(), CREATOR)
    record, _ = await tenancy.get(summary.id)
    assert record.grants == [Grant(assignee=ADA, target=summary.id, role="librarian")]
    assert (record.state, record.label, record.id) == (
        TenantState.ACTIVE.value,
        "Ghent",
        f"{summary.id}/access",
    )


@pytest.mark.parametrize(
    ("label", "description"),
    [
        ("Ghent", "Who may do what in the tenant Ghent."),
        ("St. Mary.", "Who may do what in the tenant St. Mary."),
        ("Wait...", "Who may do what in the tenant Wait."),
        (".", "Who may do what in the tenant ."),
    ],
)
async def test_the_record_description_ends_in_one_period(tenancy, label, description):
    summary = await tenancy.create(label, library_slots(), CREATOR)
    record, _ = await tenancy.get(summary.id)
    assert record.description == description


async def test_the_record_names_the_database(tenancy):
    summary = await tenancy.create("Ghent", library_slots(), CREATOR)
    record, _ = await tenancy.get(summary.id)
    assert record.database_name == tenant_resource_name(SETTINGS.prefix, summary.id)


async def test_a_retry_after_a_failure_creates_a_new_tenant(tenancy, store):
    store.on("update", StoreUnavailable("down"), after=1)
    with pytest.raises(StoreUnavailable):
        await tenancy.create("Ghent", library_slots(), CREATOR)
    retried = await tenancy.create("Ghent", library_slots(), CREATOR)
    assert [t.id for t in await tenancy.tenants()] == [retried.id], "only the retry has a record"
    assert len(await tenant_databases(store)) == 2, "the orphan waits for the sweep"


@pytest.mark.parametrize(
    ("failing", "operation", "after", "databases", "buckets"),
    [
        ("store", "create_dataset", 0, 0, 0),
        ("files", "create_bucket", 0, 1, 0),
        ("store", "update", 0, 1, 1),  # the root object
        ("store", "update", 1, 1, 1),  # the access record
    ],
    ids=["no database", "no bucket", "no root object", "no access record"],
)
async def test_a_failure_at_any_step_leaves_no_access_record(
    tenancy, store, files, failing, operation, after, databases, buckets
):
    {"store": store, "files": files}[failing].on(operation, StoreUnavailable("down"), after=after)
    with pytest.raises(StoreUnavailable):
        await tenancy.create("Ghent", library_slots(), CREATOR)
    assert await tenancy.tenants() == [], "the record is written last"
    assert len(await tenant_databases(store)) == databases, "databases left"
    assert len(await files.list_buckets(PREFIX)) == buckets, "buckets left"


async def test_the_access_record_is_written_after_the_bucket_and_the_root(tenancy, store, files):
    summary = await tenancy.create("Ghent", library_slots(), CREATOR)
    name = tenant_resource_name(SETTINGS.prefix, summary.id)
    assert files.sent("create_bucket") == [name]
    assert store.sent("create_dataset") == [SYSTEM, name]
    updates = store.sent("update")
    assert (f"{summary.id}/meta" in updates[0], f"{summary.id}/access/graph" in updates[1]) == (
        True,
        True,
    ), "root first, access record second"


async def test_tenants_lists_every_record_with_its_state(tenancy):
    first = await tenancy.create("Ghent", library_slots(), CREATOR)
    second = await tenancy.create("Bruges", library_slots(), CREATOR)
    listed = await tenancy.tenants()
    assert sorted((t.id, t.label, t.state) for t in listed) == sorted(
        (t.id, t.label, TenantState.ACTIVE.value) for t in (first, second)
    )


async def test_delete_drops_the_database_the_bucket_and_the_record(tenancy, store, files):
    summary = await tenancy.create("Ghent", library_slots(), CREATOR)
    _, version = await tenancy.get(summary.id)
    await tenancy.delete(summary.id, version)
    assert await tenant_databases(store) == [], "database"
    assert await files.list_buckets(PREFIX) == [], "bucket"
    assert await tenancy.tenants() == [], "record"
    with pytest.raises(NotFound):
        await tenancy.get(summary.id)


async def test_delete_marks_the_record_deleting_before_it_drops_anything(tenancy, store):
    summary = await tenancy.create("Ghent", library_slots(), CREATOR)
    _, version = await tenancy.get(summary.id)
    store.on("drop_dataset", StoreUnavailable("down"))
    with pytest.raises(StoreUnavailable):
        await tenancy.delete(summary.id, version)
    record, _ = await tenancy.get(summary.id)
    assert record.state == TenantState.DELETING.value, "the mark survives the failure"
    assert len(await tenant_databases(store)) == 1, "nothing was dropped yet"


async def test_a_later_delete_finishes_a_deleting_tenant_even_with_a_stale_version(
    tenancy, store, files
):
    summary = await tenancy.create("Ghent", library_slots(), CREATOR)
    _, version = await tenancy.get(summary.id)
    store.on("drop_dataset", StoreUnavailable("down"))
    with pytest.raises(StoreUnavailable):
        await tenancy.delete(summary.id, version)
    await tenancy.delete(summary.id, version)  # the version moved when it was marked
    assert (await tenant_databases(store), await files.list_buckets(PREFIX)) == ([], [])
    assert await tenancy.tenants() == []


async def test_delete_finishes_when_the_database_or_the_bucket_is_already_gone(
    tenancy, store, files
):
    summary = await tenancy.create("Ghent", library_slots(), CREATOR)
    name = tenant_resource_name(SETTINGS.prefix, summary.id)
    await store.drop_dataset(name)
    await files.delete_bucket(name)
    _, version = await tenancy.get(summary.id)
    await tenancy.delete(summary.id, version)
    assert await tenancy.tenants() == []


async def test_delete_with_a_stale_version_conflicts_and_changes_nothing(tenancy, store):
    summary = await tenancy.create("Ghent", library_slots(), CREATOR)
    with pytest.raises(Conflict):
        await tenancy.delete(summary.id, "not-the-version")
    record, _ = await tenancy.get(summary.id)
    assert record.state == TenantState.ACTIVE.value
    assert len(await tenant_databases(store)) == 1


async def test_delete_of_an_unknown_tenant_is_not_found(tenancy):
    with pytest.raises(NotFound):
        await tenancy.delete(f"{SETTINGS.base}libraries/00000000-0000-4000-8000-000000000000", "v")


async def test_a_label_the_record_refuses_creates_nothing(tenancy, store, files):
    with pytest.raises(ValueError, match="label"):
        await tenancy.create("x" * 201, library_slots(), CREATOR)
    assert store.sent("create_dataset") == [SYSTEM], "no tenant database was asked for"
    assert files.sent("create_bucket") == [], "no bucket was asked for"
    assert await tenancy.tenants() == []


async def test_finish_deletion_refuses_a_tenant_that_is_not_deleting_and_drops_nothing(
    tenancy, store, files
):
    summary = await tenancy.create("Ghent", library_slots(), CREATOR)
    with pytest.raises(Conflict, match="deleting"):
        await tenancy.finish_deletion(summary.id)
    assert len(await tenant_databases(store)) == 1, "database"
    assert len(await files.list_buckets(PREFIX)) == 1, "bucket"
    assert [t.id for t in await tenancy.tenants()] == [summary.id], "record"
    assert store.sent("drop_dataset") == [], "nothing was dropped"


async def test_finish_deletion_of_an_unknown_tenant_is_not_found_and_drops_nothing(tenancy, store):
    with pytest.raises(NotFound):
        await tenancy.finish_deletion(
            f"{SETTINGS.base}libraries/00000000-0000-4000-8000-000000000000"
        )
    assert store.sent("drop_dataset") == []


STORED = "lib-t-" + "d" * 32


async def rename_database(tenancy, store, files, tenant: str) -> str:
    """Make the record name ``STORED`` as its database, as if the prefix had been another one."""
    await store.create_dataset(STORED)
    await files.create_bucket(STORED)
    async with open_session(
        store, database=SYSTEM, tenant_iri=tenant, principal=CREATOR
    ) as session:
        work = UnitOfWork(session, toy_mapper())
        record = await work.get(LibraryAccess, f"{tenant}/access")
        record.database_name = STORED
        work.add(record)
        await work.commit()
    return tenant_resource_name(SETTINGS.prefix, tenant)


async def test_delete_drops_the_database_and_bucket_the_record_names_and_not_a_derived_name(
    tenancy, store, files
):
    summary = await tenancy.create("Ghent", library_slots(), CREATOR)
    derived = await rename_database(tenancy, store, files, summary.id)
    _, version = await tenancy.get(summary.id)
    await tenancy.delete(summary.id, version)
    assert STORED not in await store.list_datasets(), "the recorded database is dropped"
    assert STORED not in await files.list_buckets(PREFIX), "and its bucket"
    assert derived in await store.list_datasets(), "the derived name is not the record's business"
    assert derived in await files.list_buckets(PREFIX)


@pytest.mark.filterwarnings(
    "ignore:Pydantic serializer warnings:UserWarning"
)  # the invalid root is the point
async def test_a_root_the_model_refuses_creates_nothing(tenancy, store, files):
    broken = {**library_slots(), "city": 5}
    with pytest.raises(ValueError, match="city"):
        await tenancy.create("Ghent", broken, CREATOR)
    assert store.sent("create_dataset") == [SYSTEM], "no tenant database was asked for"
    assert files.sent("create_bucket") == [], "no bucket was asked for"


async def test_each_create_and_drop_step_is_logged_with_the_tenant_and_resource_as_data(
    tenancy, caplog
):
    with caplog.at_level(logging.INFO):
        summary = await tenancy.create("Ghent", library_slots(), CREATOR)
        _, version = await tenancy.get(summary.id)
        await tenancy.delete(summary.id, version)
    name = tenant_resource_name(SETTINGS.prefix, summary.id)
    steps = [(r.step, r.tenant, r.resource) for r in caplog.records if hasattr(r, "step")]
    assert steps == [
        ("create-database", summary.id, name),
        ("create-bucket", summary.id, name),
        ("create-record", summary.id, name),
        ("drop-database", summary.id, name),
        ("drop-bucket", summary.id, name),
        ("remove-record", summary.id, name),
    ]


# --- changing the access record: the label and the grants (task 5.2) ---------------------------

BEN = Principal(id="https://example.org/people/ben")


async def test_rename_replaces_the_label_and_answers_the_new_version(tenancy):
    summary = await tenancy.create("Ghent", library_slots(), CREATOR)
    _, version = await tenancy.get(summary.id)
    new_version = await tenancy.rename(summary.id, "Bruges", version, BEN)
    record, stored = await tenancy.get(summary.id)
    assert (record.label, stored) == ("Bruges", new_version), (
        "the record holds the new label and version"
    )
    assert new_version != version, "a commit writes a fresh version"


async def test_rename_keeps_the_description_in_step_with_the_label(tenancy):
    summary = await tenancy.create("Ghent", library_slots(), CREATOR)
    _, version = await tenancy.get(summary.id)
    await tenancy.rename(summary.id, "Bruges", version, BEN)
    record, _ = await tenancy.get(summary.id)
    assert "Bruges" in record.description and "Ghent" not in record.description, (
        "the description is derived from the label"
    )


async def test_rename_with_a_stale_version_conflicts_and_changes_nothing(tenancy):
    summary = await tenancy.create("Ghent", library_slots(), CREATOR)
    _, version = await tenancy.get(summary.id)
    await tenancy.rename(summary.id, "Bruges", version, BEN)
    with pytest.raises(Conflict):
        await tenancy.rename(summary.id, "Antwerp", version, BEN)
    assert (await tenancy.get(summary.id))[0].label == "Bruges", "the stale rename left the label"


async def test_set_grants_replaces_the_grants_and_the_prohibitions(tenancy):
    summary = await tenancy.create("Ghent", library_slots(), CREATOR)
    _, version = await tenancy.get(summary.id)
    grants = GrantSet(
        grants=[Grant(assignee=BEN.id, target=summary.id, role="reader")],
        prohibitions=[Prohibition(assignee=BEN.id, target=summary.id, action=Action.DELETE)],
    )
    await tenancy.set_grants(summary.id, grants, version, CREATOR)
    record, _ = await tenancy.get(summary.id)
    assert [g.assignee for g in record.grants or []] == [BEN.id], "the creator's grant is replaced"
    assert [p.action for p in record.prohibitions or []] == [Action.DELETE.value], (
        "prohibitions too"
    )


async def test_set_grants_with_a_stale_version_conflicts(tenancy):
    summary = await tenancy.create("Ghent", library_slots(), CREATOR)
    _, version = await tenancy.get(summary.id)
    await tenancy.rename(summary.id, "Bruges", version, CREATOR)
    with pytest.raises(Conflict):
        await tenancy.set_grants(summary.id, GrantSet(), version, CREATOR)


async def test_an_empty_grant_set_leaves_no_grants(tenancy):
    summary = await tenancy.create("Ghent", library_slots(), CREATOR)
    _, version = await tenancy.get(summary.id)
    await tenancy.set_grants(summary.id, GrantSet(), version, CREATOR)
    record, _ = await tenancy.get(summary.id)
    assert not record.grants, "nothing is left"
    assert not record.prohibitions, "nothing is left"


# --- the tenants a caller may read, in one query -------------------------------------------------


def rules() -> AccessRules:
    return AccessRules(load_role_definitions(ROLES))


async def test_the_visible_tenants_are_those_the_caller_may_read_paged_by_iri(tenancy, store):
    made = [await tenancy.create(f"Library {n}", library_slots(), CREATOR) for n in range(3)]
    before = len(store.sent("query"))
    mine = await tenancy.visible_tenants(caller(), rules(), limit=2, offset=1)
    assert len(store.sent("query")) - before == 1, "one query, however many tenants"
    assert mine.total == 3, "all the caller may read"
    assert (mine.limit, mine.offset) == (2, 1), "the position of the page"
    assert [t.id for t in mine.items] == sorted(t.id for t in made)[1:3], "ordered by IRI"


async def test_a_tenant_the_caller_has_no_grant_in_is_not_visible(tenancy):
    await tenancy.create("Ghent", library_slots(), CREATOR)
    page = await tenancy.visible_tenants(caller(principal=BOB), rules(), limit=50, offset=0)
    assert (page.items, page.total) == ([], 0), "an outsider sees nothing"


async def test_a_global_role_sees_every_tenant(tenancy):
    await tenancy.create("Ghent", library_slots(), CREATOR)
    page = await tenancy.visible_tenants(
        caller("admin", principal=BOB), rules(), limit=50, offset=0
    )
    assert page.total == 1, "the system-level reader reads all"


async def test_a_tenant_being_deleted_is_not_visible(tenancy):
    made = await tenancy.create("Ghent", library_slots(), CREATOR)
    record, version = await tenancy.get(made.id)
    record.state = TenantState.DELETING
    await tenancy._replace_root(SYSTEM, made.id, CREATOR, record, version)
    assert (await tenancy.visible_tenants(caller(), rules(), limit=50, offset=0)).total == 0


async def test_a_record_that_cannot_be_decoded_is_a_stored_data_fault_not_a_bad_request(
    tenancy, store
):
    made = await tenancy.create("Ghent", library_slots(), CREATOR)
    access = f"{made.id}/access"
    await store.update(
        SYSTEM,
        f"INSERT DATA {{ GRAPH <{access}/graph> {{ <{access}> <{v.GRANTS}> [ <{ODRL}target> <{made.id}> ] }} }}",
    )
    with pytest.raises(StoredDataInvalid):
        await tenancy.get(made.id)
    with pytest.raises(StoredDataInvalid):
        await tenancy.visible_tenants(caller(), rules(), limit=50, offset=0)


async def test_the_slots_of_a_root_may_not_choose_the_tenants_iri(tenancy, store, files):
    with pytest.raises(InvalidBody, match="assigns"):
        await tenancy.create("Ghent", {**library_slots(), "id": "https://evil.example/t"}, CREATOR)
    assert files.sent("create_bucket") == [], "nothing was created"


async def test_the_label_of_the_tenant_is_the_roots_unless_the_slots_give_one(tenancy, store):
    slots = {k: v for k, v in library_slots().items() if k != "label"}
    summary = await tenancy.create("Ghent", slots, CREATOR)
    root = (await store.query(tenant_resource_name(SETTINGS.prefix, summary.id), ROOT_LABEL)).graph
    assert root is not None and Literal("Ghent") in set(root.objects()), "the tenant's label"
