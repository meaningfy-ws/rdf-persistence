"""The start-up sweep against a real Fuseki and the parametrised file store: a crash during creation."""

import pytest
from rdflib.compare import isomorphic

from rdf_persistence.domain.exceptions import StoreUnavailable
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.iris import system_database_name, tenant_resource_name
from rdf_persistence.services.sweep import sweep
from rdf_persistence.services.tenancy import Tenancy
from tests.fixtures.library.generated.library import Library
from tests.fixtures.library.generated.library_access import LibraryAccess
from tests.toy import ADA, library_slots, toy_mapper

CREATOR = Principal(id=ADA)
FOREIGN = "other-t-" + "c" * 32


class CrashAfterBucket:
    """A file store that creates the bucket and then fails: the process died at that step."""

    def __init__(self, inner):
        self._inner = inner

    def __getattr__(self, name):
        return getattr(self._inner, name)

    async def create_bucket(self, name: str) -> None:
        await self._inner.create_bucket(name)
        raise StoreUnavailable("the process died")


class CannotDrop:
    """A store that cannot drop a database: the process died while deleting."""

    def __init__(self, inner):
        self._inner = inner

    def __getattr__(self, name):
        return getattr(self._inner, name)

    async def drop_dataset(self, name: str) -> None:
        raise StoreUnavailable("the process died")


async def test_a_crash_during_creation_leaves_orphans_that_the_next_start_up_drops(
    tenancy, store, files, settings
):
    kept = await tenancy.create("Ghent", library_slots(), CREATOR)
    crashing = Tenancy(
        store,
        CrashAfterBucket(files),
        settings,
        mapper=toy_mapper(),
        root_class=Library,
        access_class=LibraryAccess,
    )
    with pytest.raises(StoreUnavailable):
        await crashing.create("Bruges", library_slots(), CREATOR)
    mine = [n for n in await store.list_datasets() if n.startswith(f"{settings.prefix}-t-")]
    assert len(mine) == 2, "the crashed tenant's database exists beside the kept one"
    await sweep(tenancy, store, files, settings)
    kept_name = tenant_resource_name(settings.prefix, kept.id)
    left = [n for n in await store.list_datasets() if n.startswith(f"{settings.prefix}-t-")]
    assert left == [kept_name], "databases: only the active tenant's"
    assert await files.list_buckets(f"{settings.prefix}-t-") == [kept_name], "buckets"
    assert [t.id for t in await tenancy.tenants()] == [kept.id], "the active tenant is unchanged"


async def test_a_database_and_bucket_of_another_service_are_left_alone(
    tenancy, store, files, settings
):
    await tenancy.create("Ghent", library_slots(), CREATOR)  # with a record on file the sweep runs
    await store.create_dataset(FOREIGN)
    await files.create_bucket(FOREIGN)
    try:
        await sweep(tenancy, store, files, settings)
        assert FOREIGN in await store.list_datasets(), "database"
        assert FOREIGN in await files.list_buckets(""), "bucket"
    finally:
        await store.drop_dataset(FOREIGN)
        await files.delete_bucket(FOREIGN)


async def test_the_sweep_finishes_a_deletion_the_process_did_not(tenancy, store, files, settings):
    summary = await tenancy.create("Ghent", library_slots(), CREATOR)
    _, version = await tenancy.get(summary.id)
    dying = Tenancy(
        CannotDrop(store),
        files,
        settings,
        mapper=toy_mapper(),
        root_class=Library,
        access_class=LibraryAccess,
    )
    with pytest.raises(StoreUnavailable):
        await dying.delete(summary.id, version)
    await sweep(tenancy, store, files, settings)
    name = tenant_resource_name(settings.prefix, summary.id)
    assert name not in await store.list_datasets(), "database"
    assert await files.list_buckets(name) == [], "bucket"
    assert await tenancy.tenants() == [], "record"


async def test_a_lost_system_database_does_not_make_the_tenants_orphans(
    tenancy, store, files, settings
):
    kept = await tenancy.create("Ghent", library_slots(), CREATOR)
    name = tenant_resource_name(settings.prefix, kept.id)
    await store.drop_dataset(system_database_name(settings.prefix))  # the records are gone
    await sweep(tenancy, store, files, settings)
    assert name in await store.list_datasets(), "the tenant's database is still there"
    assert await files.list_buckets(name) == [name], "and its bucket"


async def test_an_active_tenant_keeps_its_root_graph_record_version_and_blob(
    tenancy, store, files, settings
):
    kept = await tenancy.create("Ghent", library_slots(), CREATOR)
    name = tenant_resource_name(settings.prefix, kept.id)
    await files.put(name, "scan.pdf", b"%PDF")
    query = f"CONSTRUCT {{ ?s ?p ?o }} WHERE {{ GRAPH <{kept.id}/meta> {{ ?s ?p ?o }} }}"
    root_before = (await store.query(name, query)).graph
    _, version_before = await tenancy.get(kept.id)
    await store.create_dataset(f"{settings.prefix}-t-{'e' * 32}")  # an orphan to drop
    await sweep(tenancy, store, files, settings)
    root_after = (await store.query(name, query)).graph
    _, version_after = await tenancy.get(kept.id)
    assert len(root_before) > 0, "there was a root object to compare"
    assert isomorphic(root_after, root_before), "the root graph is the same"
    assert version_after == version_before, "the access record is at the same version"
    assert await files.get(name, "scan.pdf") == b"%PDF", "the blob is the same"
