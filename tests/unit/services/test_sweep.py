"""The start-up sweep over the fakes: finish `deleting` tenants, drop unnamed `{prefix}-t-` databases and buckets."""

import logging
from types import SimpleNamespace

import pytest
from rdflib import Graph

from rdf_persistence.domain.exceptions import NotFound, StoreNotWired, StoreUnavailable
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.iris import system_database_name, tenant_resource_name
from rdf_persistence.services.mapper import UnitOfWork
from rdf_persistence.services.session import open_session
from rdf_persistence.services.sweep import sweep
from rdf_persistence.services.tenancy import Tenancy
from rdf_persistence.testkit import FakeFileStore, FakeStore, assert_isomorphic
from tests.fixtures.library.generated.library import Library
from tests.fixtures.library.generated.library_access import LibraryAccess
from tests.toy import ADA, SETTINGS, library_slots, toy_mapper

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
    made = Tenancy(
        store, files, SETTINGS, mapper=toy_mapper(), root_class=Library, access_class=LibraryAccess
    )
    await made.ensure_system_database()
    return made


@pytest.fixture
async def kept(tenancy):
    """A tenant that is alive: with a record on file the sweep may judge the other names orphans."""
    return await tenancy.create("Ghent", library_slots(), CREATOR)


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
        await tenancy.create("Bruges", library_slots(), CREATOR)
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
    assert await tenancy.tenants() == [kept], "the active tenant is still listed"
    assert name in await store.list_datasets(), "the active tenant keeps its database"
    assert await files.list_buckets("lib-t-") == [name], "the active tenant keeps its bucket"
    after = (await root_graph(store, kept.id), await tenancy.get(kept.id))
    assert len(before[0]) > 0, "the root object was there to compare"
    assert_isomorphic(after[0], before[0])
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
    made = Tenancy(
        store, files, SETTINGS, mapper=toy_mapper(), root_class=Library, access_class=LibraryAccess
    )
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
    assert "no access records" in caplog.text, "the sweep says it found no access records"


@pytest.mark.parametrize("name", FOREIGN)
async def test_a_name_without_the_tenant_prefix_is_never_touched(tenancy, store, files, name):
    await store.create_dataset(name)
    await files.create_bucket(name)
    await sweep(tenancy, store, files, SETTINGS)
    assert name in await store.list_datasets(), "database"
    assert name in await files.list_buckets(""), "bucket"


async def test_a_tenant_whose_deletion_stopped_is_finished(tenancy, store, files):
    summary = await tenancy.create("Ghent", library_slots(), CREATOR)
    _, version = await tenancy.get(summary.id)
    store.on("drop_dataset", StoreUnavailable("down"))
    with pytest.raises(StoreUnavailable):
        await tenancy.delete(summary.id, version)
    await sweep(tenancy, store, files, SETTINGS)
    assert await tenancy.tenants() == [], "record"
    assert await store.list_datasets() == ["lib-system"], "database"
    assert await files.list_buckets("") == [], "bucket"


async def test_the_sweep_creates_the_system_database_on_a_first_start(store, files):
    made = Tenancy(
        store, files, SETTINGS, mapper=toy_mapper(), root_class=Library, access_class=LibraryAccess
    )
    await sweep(made, store, files, SETTINGS)
    assert await store.list_datasets() == ["lib-system"], (
        "the first start creates the system database"
    )


async def test_a_second_sweep_changes_nothing(tenancy, store, files, kept):
    await store.create_dataset(ORPHAN)
    await sweep(tenancy, store, files, SETTINGS)
    once = sorted(await store.list_datasets())
    await sweep(tenancy, store, files, SETTINGS)
    assert sorted(await store.list_datasets()) == once, (
        "a second sweep leaves the datasets as they were"
    )


async def test_each_orphan_drop_is_logged_with_the_name_as_structured_data(
    tenancy, store, files, kept, caplog
):
    await store.create_dataset(ORPHAN)
    await files.create_bucket(ORPHAN)
    with caplog.at_level(logging.INFO):
        await sweep(tenancy, store, files, SETTINGS)
    dropped = {(r.step, r.resource) for r in caplog.records if hasattr(r, "step")}
    assert dropped == {("drop-orphan-database", ORPHAN), ("drop-orphan-bucket", ORPHAN)}, (
        "each orphan drop is logged with its name"
    )


# -- tenants on several stores (tenant-stores PD-6): ``D`` is the default store, ``A`` is ``client-a`` --

CLIENT_A = "client-a"
ORPHAN_D = "lib-t-" + "d" * 32
ORPHAN_A = "lib-t-" + "e" * 32


def wired(d, files, **stores) -> Tenancy:
    return Tenancy(
        d,
        files,
        SETTINGS,
        mapper=toy_mapper(),
        root_class=Library,
        access_class=LibraryAccess,
        stores=stores,
    )


@pytest.fixture
async def two():
    """``D`` and ``A`` under one tenancy; ``T`` lives on ``A``."""
    d, a, files = FakeStore(), FakeStore(), FakeFileStore()
    tenancy = wired(d, files, **{CLIENT_A: a})
    await tenancy.ensure_system_database()
    tenant = await tenancy.create("Ghent", library_slots(), CREATOR, store=CLIENT_A)
    return SimpleNamespace(d=d, a=a, files=files, tenancy=tenancy, tenant=tenant)


async def make_deleting(two, label: str, store: str) -> str:
    """A tenant on ``store`` whose deletion stopped at the drop; answers its database name."""
    summary = await two.tenancy.create(label, library_slots(), CREATOR, store=store)
    _, version = await two.tenancy.get(summary.id)
    two.tenancy.stores()[store].on("drop_dataset", StoreUnavailable("down"))
    with pytest.raises(StoreUnavailable):
        await two.tenancy.delete(summary.id, version)
    return tenant_resource_name(SETTINGS.prefix, summary.id)


async def test_tc21_an_orphan_is_dropped_from_whichever_store_holds_it(two):
    held = tenant_resource_name(SETTINGS.prefix, two.tenant.id)
    await two.a.create_dataset(ORPHAN_A)
    await two.d.create_dataset(ORPHAN_D)
    await sweep(two.tenancy, two.d, two.files, SETTINGS)
    assert await two.a.list_datasets() == [held], "A keeps T, drops its orphan"
    assert await two.d.list_datasets() == ["lib-system"], "D drops its orphan"


async def test_tc22_unwired_stores_stop_the_sweep_before_anything_is_dropped(two):
    b, c = FakeStore(), FakeStore()
    full = wired(two.d, two.files, **{CLIENT_A: two.a, "client-b": b, "client-c": c})
    await full.create("Bruges", library_slots(), CREATOR, store="client-b")
    await full.create("Ypres", library_slots(), CREATOR, store="client-c")
    deleting = await make_deleting(two, "Mons", CLIENT_A)
    await two.d.create_dataset(ORPHAN_D)
    narrow = wired(two.d, two.files, **{CLIENT_A: two.a})
    with pytest.raises(StoreNotWired, match="client-b, client-c"):
        await sweep(narrow, two.d, two.files, SETTINGS)
    assert deleting in await two.a.list_datasets(), "the deleting tenant's database is still there"
    assert ORPHAN_D in await two.d.list_datasets(), "the orphan is still there"
    assert two.a.sent("drop_dataset") == [deleting], "only the failed attempt of the setup"
    assert two.d.sent("drop_dataset") == [], "D was sent no drop"


async def test_tc23_a_new_system_database_skips_the_sweep_across_stores(caplog):
    d, a, files = FakeStore(), FakeStore(), FakeFileStore()
    made = wired(d, files, **{CLIENT_A: a})
    await a.create_dataset(ORPHAN_A)
    with caplog.at_level(logging.WARNING):
        await sweep(made, d, files, SETTINGS)
    assert ORPHAN_A in await a.list_datasets(), "the orphan on A is kept"
    assert a.sent("drop_dataset") == [], "A was sent no drop"
    assert d.sent("drop_dataset") == [], "D was sent no drop"
    assert "no access records" in caplog.text, "the operator is told why"


async def test_tc24_a_deletion_is_finished_on_the_store_of_the_tenant(two):
    deleting = await make_deleting(two, "Mons", CLIENT_A)
    before = list(await two.d.list_datasets())
    await sweep(two.tenancy, two.d, two.files, SETTINGS)
    assert deleting not in await two.a.list_datasets(), "dropped from A"
    assert [t.id for t in await two.tenancy.tenants()] == [two.tenant.id], "its record is gone"
    assert await two.d.list_datasets() == before, "D is as it was"
    assert two.d.sent("drop_dataset") == [], "D was sent no drop"


async def test_tc25_a_store_that_is_down_stops_the_sweep_before_anything_is_finished(two):
    deleting = await make_deleting(two, "Mons", "default")
    await two.d.create_dataset(ORPHAN_D)
    two.a.on("list_datasets", StoreUnavailable("down"))
    with pytest.raises(StoreUnavailable):
        await sweep(two.tenancy, two.d, two.files, SETTINGS)
    assert {deleting, ORPHAN_D} <= set(await two.d.list_datasets()), "nothing was dropped from D"


async def test_tc42_an_orphan_dropped_meanwhile_does_not_stop_the_sweep(two):
    first, second = "lib-t-" + "1" * 32, "lib-t-" + "2" * 32
    await two.d.create_dataset(first)
    await two.d.create_dataset(second)
    two.d.on("drop_dataset", NotFound("dropped meanwhile"))  # the fake leaves `first` in place
    await sweep(two.tenancy, two.d, two.files, SETTINGS)
    assert two.d.sent("drop_dataset") == [first, second], "the sweep went on to the next orphan"
    assert second not in await two.d.list_datasets(), "the second orphan is gone"


async def test_tc43_a_tenant_database_on_another_store_is_reported_and_left_alone(caplog):
    d, a, files = FakeStore(), FakeStore(), FakeFileStore()
    made = wired(d, files, **{CLIENT_A: a})
    await made.ensure_system_database()
    summary = await made.create("Ghent", library_slots(), CREATOR)  # recorded on default
    name = tenant_resource_name(SETTINGS.prefix, summary.id)
    await d.drop_dataset(name)
    await a.create_dataset(name)  # found on A
    before = (len(d.sent("drop_dataset")), len(a.sent("drop_dataset")))
    with caplog.at_level(logging.ERROR):
        await sweep(made, d, files, SETTINGS)
    [logged] = [r for r in caplog.records if getattr(r, "step", "") == "misplaced-tenant"]
    assert (logged.tenant, logged.recorded_store, logged.found_store) == (
        summary.id,
        "default",
        CLIENT_A,
    ), "the log names the tenant, the recorded store and the one it was found on"
    assert (len(d.sent("drop_dataset")), len(a.sent("drop_dataset"))) == before, "nothing dropped"
    assert name in await a.list_datasets(), "the database on A is left alone"


async def test_pd13_the_sweep_reads_the_records_in_one_query_however_many_tenants_there_are(
    tenancy, store, files, kept
):
    before = len(store.sent("query"))
    await sweep(tenancy, store, files, SETTINGS)
    with_one = len(store.sent("query")) - before
    for label in ("Bruges", "Ypres"):
        await tenancy.create(label, library_slots(), CREATOR)
    before = len(store.sent("query"))

    await sweep(tenancy, store, files, SETTINGS)

    assert len(store.sent("query")) - before == with_one, "three tenants cost what one costs"
