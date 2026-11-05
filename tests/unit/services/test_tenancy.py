"""Tenancy over the fakes: create writes the access record last, delete marks `deleting` first (PD-6a, PD-8, PD-9)."""

from datetime import UTC, datetime

import pytest

from rdf_persistence.domain.errors import Conflict, NotFound, StoreUnavailable
from rdf_persistence.domain.generated.rp_access import Grant
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.generated.rp_tenancy import TenantState
from rdf_persistence.domain.iris import system_database_name, tenant_resource_name
from rdf_persistence.services.mapper import UnitOfWork
from rdf_persistence.services.session import open_session
from rdf_persistence.services.tenancy import Tenancy
from rdf_persistence.testkit import FakeFileStore, FakeStore
from tests.fixtures.library.generated.library import Library
from tests.fixtures.library.generated.library_access import LibraryAccess
from tests.toy import ADA, SETTINGS, library, toy_mapper

NOW = datetime(2026, 11, 5, 9, 0, tzinfo=UTC)
CREATOR = Principal(id=ADA)
SYSTEM = system_database_name(SETTINGS.prefix)
PREFIX = "lib-t-"


@pytest.fixture
def store() -> FakeStore:
    return FakeStore()


@pytest.fixture
def files() -> FakeFileStore:
    return FakeFileStore()


@pytest.fixture
async def tenancy(store, files) -> Tenancy:
    made = Tenancy(
        store, files, SETTINGS, mapper=toy_mapper(), access_class=LibraryAccess, clock=lambda: NOW
    )
    await made.ensure_system_database()
    return made


async def tenant_databases(store: FakeStore) -> list[str]:
    return [name for name in await store.list_datasets() if name.startswith(PREFIX)]


async def test_the_system_database_is_created_once(store, files):
    made = Tenancy(store, files, SETTINGS, mapper=toy_mapper(), access_class=LibraryAccess)
    await made.ensure_system_database()
    await made.ensure_system_database()
    assert await store.list_datasets() == [SYSTEM]


async def test_create_makes_a_database_and_a_bucket_named_after_the_tenant(tenancy, store, files):
    summary = await tenancy.create("Ghent", library(), CREATOR)
    name = tenant_resource_name(SETTINGS.prefix, summary.id)
    assert await tenant_databases(store) == [name], "the database"
    assert await files.list_buckets(PREFIX) == [name], "the bucket"


async def test_create_answers_an_active_summary_under_the_consumers_base(tenancy):
    summary = await tenancy.create("Ghent", library(), CREATOR)
    assert (summary.label, summary.state) == ("Ghent", TenantState.ACTIVE.value)
    assert summary.id.startswith(f"{SETTINGS.base}{SETTINGS.tenant_segment}/"), "a minted IRI"


async def test_create_stores_the_root_object_under_the_tenant_iri(tenancy, store):
    summary = await tenancy.create("Ghent", library(city="Ghent"), CREATOR)
    name = tenant_resource_name(SETTINGS.prefix, summary.id)
    async with open_session(
        store, database=name, tenant_iri=summary.id, principal=CREATOR
    ) as session:
        root = await UnitOfWork(session, toy_mapper()).get(Library, summary.id)
    assert (root.city, root.creator) == ("Ghent", ADA), "the root keeps the creator's tracking"


async def test_create_grants_the_creator_role_on_the_tenant_to_the_creator(tenancy):
    summary = await tenancy.create("Ghent", library(), CREATOR)
    record, _ = await tenancy.get(summary.id)
    assert record.grants == [Grant(assignee=ADA, target=summary.id, role="librarian")]
    assert (record.state, record.label, record.id) == (
        TenantState.ACTIVE.value,
        "Ghent",
        f"{summary.id}/access",
    )


async def test_the_record_names_the_database(tenancy):
    summary = await tenancy.create("Ghent", library(), CREATOR)
    record, _ = await tenancy.get(summary.id)
    assert record.database_name == tenant_resource_name(SETTINGS.prefix, summary.id)


async def test_a_retry_after_a_failure_creates_a_new_tenant(tenancy, store):
    store.on("update", StoreUnavailable("down"), after=1)
    with pytest.raises(StoreUnavailable):
        await tenancy.create("Ghent", library(), CREATOR)
    retried = await tenancy.create("Ghent", library(), CREATOR)
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
        await tenancy.create("Ghent", library(), CREATOR)
    assert await tenancy.tenants() == [], "the record is written last"
    assert len(await tenant_databases(store)) == databases, "databases left"
    assert len(await files.list_buckets(PREFIX)) == buckets, "buckets left"


async def test_the_access_record_is_written_after_the_bucket_and_the_root(tenancy, store, files):
    summary = await tenancy.create("Ghent", library(), CREATOR)
    name = tenant_resource_name(SETTINGS.prefix, summary.id)
    assert files.sent("create_bucket") == [name]
    assert store.sent("create_dataset") == [SYSTEM, name]
    updates = store.sent("update")
    assert (f"{summary.id}/meta" in updates[0], f"{summary.id}/access/graph" in updates[1]) == (
        True,
        True,
    ), "root first, access record second"


async def test_tenants_lists_every_record_with_its_state(tenancy):
    first = await tenancy.create("Ghent", library(), CREATOR)
    second = await tenancy.create("Bruges", library(), CREATOR)
    listed = await tenancy.tenants()
    assert sorted((t.id, t.label, t.state) for t in listed) == sorted(
        (t.id, t.label, TenantState.ACTIVE.value) for t in (first, second)
    )


async def test_delete_drops_the_database_the_bucket_and_the_record(tenancy, store, files):
    summary = await tenancy.create("Ghent", library(), CREATOR)
    _, version = await tenancy.get(summary.id)
    await tenancy.delete(summary.id, version)
    assert await tenant_databases(store) == [], "database"
    assert await files.list_buckets(PREFIX) == [], "bucket"
    assert await tenancy.tenants() == [], "record"


async def test_delete_marks_the_record_deleting_before_it_drops_anything(tenancy, store):
    summary = await tenancy.create("Ghent", library(), CREATOR)
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
    summary = await tenancy.create("Ghent", library(), CREATOR)
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
    summary = await tenancy.create("Ghent", library(), CREATOR)
    name = tenant_resource_name(SETTINGS.prefix, summary.id)
    await store.drop_dataset(name)
    await files.delete_bucket(name)
    _, version = await tenancy.get(summary.id)
    await tenancy.delete(summary.id, version)
    assert await tenancy.tenants() == []


async def test_delete_with_a_stale_version_conflicts_and_changes_nothing(tenancy, store):
    summary = await tenancy.create("Ghent", library(), CREATOR)
    with pytest.raises(Conflict):
        await tenancy.delete(summary.id, "not-the-version")
    record, _ = await tenancy.get(summary.id)
    assert record.state == TenantState.ACTIVE.value
    assert len(await tenant_databases(store)) == 1


async def test_delete_of_an_unknown_tenant_is_not_found(tenancy):
    with pytest.raises(NotFound):
        await tenancy.delete(f"{SETTINGS.base}libraries/00000000-0000-4000-8000-000000000000", "v")
