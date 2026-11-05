"""The start-up sweep over the fakes: finish `deleting` tenants, drop unnamed `{prefix}-t-` databases and buckets."""

import pytest

from rdf_persistence.domain.errors import StoreUnavailable
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.iris import tenant_resource_name
from rdf_persistence.services.sweep import sweep
from rdf_persistence.services.tenancy import Tenancy
from rdf_persistence.testkit import FakeFileStore, FakeStore
from tests.fixtures.library.generated.library_access import LibraryAccess
from tests.toy import ADA, SETTINGS, library, toy_mapper

CREATOR = Principal(id=ADA)
ORPHAN = "lib-t-" + "a" * 32
FOREIGN = ["other-t-" + "b" * 32, "lib-system-copy", "lib-tx", "library-t-1", "lib"]


@pytest.fixture
def store() -> FakeStore:
    return FakeStore()


@pytest.fixture
def files() -> FakeFileStore:
    return FakeFileStore()


@pytest.fixture
async def tenancy(store, files) -> Tenancy:
    made = Tenancy(store, files, SETTINGS, mapper=toy_mapper(), access_class=LibraryAccess)
    await made.ensure_system_database()
    return made


async def test_a_database_and_a_bucket_that_no_record_names_are_dropped(tenancy, store, files):
    await store.create_dataset(ORPHAN)
    await files.create_bucket(ORPHAN)
    await sweep(tenancy, store, files, SETTINGS)
    assert ORPHAN not in await store.list_datasets(), "database"
    assert await files.list_buckets(ORPHAN) == [], "bucket"


async def test_a_creation_that_stopped_before_the_record_leaves_nothing_after_the_sweep(
    tenancy, store, files
):
    store.on("update", StoreUnavailable("down"), after=1)  # the access record
    with pytest.raises(StoreUnavailable):
        await tenancy.create("Ghent", library(), CREATOR)
    await sweep(tenancy, store, files, SETTINGS)
    assert await store.list_datasets() == ["lib-system"], "only the system database is left"
    assert await files.list_buckets("") == [], "no bucket is left"


async def test_an_active_tenant_is_left_unchanged(tenancy, store, files):
    kept = await tenancy.create("Ghent", library(), CREATOR)
    name = tenant_resource_name(SETTINGS.prefix, kept.id)
    await store.create_dataset(ORPHAN)
    await sweep(tenancy, store, files, SETTINGS)
    assert (await tenancy.tenants(), name in await store.list_datasets()) == ([kept], True)
    assert await files.list_buckets("lib-t-") == [name]


@pytest.mark.parametrize("name", FOREIGN)
async def test_a_name_without_the_tenant_prefix_is_never_touched(tenancy, store, files, name):
    await store.create_dataset(name)
    await files.create_bucket(name)
    await sweep(tenancy, store, files, SETTINGS)
    assert name in await store.list_datasets(), "database"
    assert name in await files.list_buckets(""), "bucket"


async def test_a_tenant_whose_deletion_stopped_is_finished(tenancy, store, files):
    summary = await tenancy.create("Ghent", library(), CREATOR)
    _, version = await tenancy.get(summary.id)
    store.on("drop_dataset", StoreUnavailable("down"))
    with pytest.raises(StoreUnavailable):
        await tenancy.delete(summary.id, version)
    await sweep(tenancy, store, files, SETTINGS)
    assert await tenancy.tenants() == [], "record"
    assert await store.list_datasets() == ["lib-system"], "database"
    assert await files.list_buckets("") == [], "bucket"


async def test_the_sweep_creates_the_system_database_on_a_first_start(store, files):
    made = Tenancy(store, files, SETTINGS, mapper=toy_mapper(), access_class=LibraryAccess)
    await sweep(made, store, files, SETTINGS)
    assert await store.list_datasets() == ["lib-system"]


async def test_a_second_sweep_changes_nothing(tenancy, store, files):
    await store.create_dataset(ORPHAN)
    await sweep(tenancy, store, files, SETTINGS)
    await sweep(tenancy, store, files, SETTINGS)
    assert await store.list_datasets() == ["lib-system"]
