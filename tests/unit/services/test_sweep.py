"""The start-up sweep over the fakes: finish `deleting` tenants, drop unnamed `{prefix}-t-` databases and buckets."""

import logging

import pytest
from rdflib import Graph
from rdflib.compare import isomorphic

from rdf_persistence.domain.exceptions import StoreUnavailable
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.iris import system_database_name, tenant_resource_name
from rdf_persistence.services.mapper import UnitOfWork
from rdf_persistence.services.session import open_session
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


@pytest.fixture
async def kept(tenancy):
    """A tenant that is alive: with a record on file the sweep may judge the other names orphans."""
    return await tenancy.create("Ghent", library(), CREATOR)


async def test_a_database_and_a_bucket_that_no_record_names_are_dropped(
    tenancy, store, files, kept
):
    await store.create_dataset(ORPHAN)
    await files.create_bucket(ORPHAN)
    await sweep(tenancy, store, files, SETTINGS)
    assert ORPHAN not in await store.list_datasets(), "database"
    assert await files.list_buckets(ORPHAN) == [], "bucket"


async def test_a_creation_that_stopped_before_the_record_leaves_only_the_kept_tenant_after_the_sweep(
    tenancy, store, files, kept
):
    store.on("update", StoreUnavailable("down"), after=1)  # the access record
    with pytest.raises(StoreUnavailable):
        await tenancy.create("Bruges", library(), CREATOR)
    await sweep(tenancy, store, files, SETTINGS)
    name = tenant_resource_name(SETTINGS.prefix, kept.id)
    assert sorted(await store.list_datasets()) == sorted(["lib-system", name]), "databases"
    assert await files.list_buckets("") == [name], "buckets"


async def root_graph(store, tenant: str) -> Graph:
    query = f"CONSTRUCT {{ ?s ?p ?o }} WHERE {{ GRAPH <{tenant}/meta> {{ ?s ?p ?o }} }}"
    return (await store.query(tenant_resource_name(SETTINGS.prefix, tenant), query)).graph


async def test_an_active_tenant_is_left_unchanged(tenancy, store, files, kept):
    name = tenant_resource_name(SETTINGS.prefix, kept.id)
    await files.put(name, "scan.pdf", b"%PDF")
    before = (await root_graph(store, kept.id), await tenancy.get(kept.id))
    await store.create_dataset(ORPHAN)
    await sweep(tenancy, store, files, SETTINGS)
    assert (await tenancy.tenants(), name in await store.list_datasets()) == ([kept], True)
    assert await files.list_buckets("lib-t-") == [name]
    after = (await root_graph(store, kept.id), await tenancy.get(kept.id))
    assert len(before[0]) > 0, "the root object was there to compare"
    assert isomorphic(after[0], before[0]), "the root graph is the same"
    assert after[1][1] == before[1][1], "the access record is at the same version"
    assert await files.get(name, "scan.pdf") == b"%PDF", "the blob is the same"


async def test_the_sweep_judges_by_the_database_name_the_record_stores(tenancy, store, files, kept):
    async with open_session(
        store, database=system_database_name(SETTINGS.prefix), tenant_iri=kept.id, principal=CREATOR
    ) as session:
        work = UnitOfWork(session, toy_mapper())
        record = await work.get(LibraryAccess, f"{kept.id}/access")
        record.database_name = ORPHAN
        work.add(record)
        await work.commit()
    derived = tenant_resource_name(SETTINGS.prefix, kept.id)
    await store.create_dataset(ORPHAN)
    await files.create_bucket(ORPHAN)
    await sweep(tenancy, store, files, SETTINGS)
    assert ORPHAN in await store.list_datasets(), "the recorded name is kept"
    assert ORPHAN in await files.list_buckets(""), "also as a bucket"
    assert derived not in await store.list_datasets(), "what no record names is dropped"


async def test_the_sweep_drops_nothing_when_it_had_to_create_the_system_database(
    store, files, caplog
):
    made = Tenancy(store, files, SETTINGS, mapper=toy_mapper(), access_class=LibraryAccess)
    await store.create_dataset(ORPHAN)
    await files.create_bucket(ORPHAN)
    with caplog.at_level(logging.WARNING):
        await sweep(made, store, files, SETTINGS)
    assert ORPHAN in await store.list_datasets(), "database"
    assert ORPHAN in await files.list_buckets(""), "bucket"
    assert store.sent("drop_dataset") == [], "nothing was dropped"
    assert "no access records" in caplog.text, "the operator is told why"


async def test_the_sweep_drops_nothing_when_there_is_no_access_record_at_all(
    tenancy, store, files, caplog
):
    await store.create_dataset(ORPHAN)
    await files.create_bucket(ORPHAN)
    with caplog.at_level(logging.WARNING):
        await sweep(tenancy, store, files, SETTINGS)
    assert ORPHAN in await store.list_datasets(), "database"
    assert ORPHAN in await files.list_buckets(""), "bucket"
    assert files.sent("delete_bucket") == [], "no bucket was deleted"
    assert "no access records" in caplog.text


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


async def test_a_second_sweep_changes_nothing(tenancy, store, files, kept):
    await store.create_dataset(ORPHAN)
    await sweep(tenancy, store, files, SETTINGS)
    once = sorted(await store.list_datasets())
    await sweep(tenancy, store, files, SETTINGS)
    assert sorted(await store.list_datasets()) == once


async def test_each_orphan_drop_is_logged_with_the_name_as_structured_data(
    tenancy, store, files, kept, caplog
):
    await store.create_dataset(ORPHAN)
    await files.create_bucket(ORPHAN)
    with caplog.at_level(logging.INFO):
        await sweep(tenancy, store, files, SETTINGS)
    dropped = {(r.step, r.resource) for r in caplog.records if hasattr(r, "step")}
    assert dropped == {("drop-orphan-database", ORPHAN), ("drop-orphan-bucket", ORPHAN)}
