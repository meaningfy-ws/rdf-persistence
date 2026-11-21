"""Tenants routed by store, attacked: failure mid-write, a second instance, erased records, limits (tenant-stores stage 1).

``D`` is the default ``FakeStore``, ``A`` the store wired as ``client-a``. A failing test is a FINDING and is kept
``xfail(strict=True)`` with its evidence in the reason, for the lead to decide (none is open).
"""

import logging
from types import SimpleNamespace

import pytest
from rdflib import URIRef

from rdf_persistence.access.domain.generated.rp_tenancy import TenantState
from rdf_persistence.core.domain.exceptions import (
    DatabaseGone,
    NotFound,
    PersistenceError,
    StoreNotWired,
    StoreUnavailable,
)
from rdf_persistence.iris.domain.layout import graph_iri
from rdf_persistence.iris.services.iris import Iris
from rdf_persistence.tenancy.services.migration_runner import migrate_tenants
from rdf_persistence.tenancy.services.sweep import sweep
from rdf_persistence.tenancy.services.tenancy import DEFAULT_STORE, Tenancy
from rdf_persistence.testkit import FakeFileStore, FakeStore
from tests.dump_helpers import LIBRARY_SCHEMA
from tests.fixtures.library.domain.generated.library import Library
from tests.fixtures.library.domain.generated.library_access import LibraryAccess
from tests.logs import attributes
from tests.migration_helpers import LIB, chain_of, migration, rename
from tests.tenancy_world import CREATOR
from tests.toy import SETTINGS, library_slots, toy_mapper
from tests.unit.tenancy.tenancy_helpers import (
    CLIENT_A,
    IDS,
    PREFIX,
    SYSTEM,
    TYPES,
    cold,
    made_on,
    operations,
    tenant_databases,
    wired,
)

OLD = URIRef("https://example.org/ns/library#old")
NEW = URIRef("https://example.org/ns/library#new")
RP_STORE_NAME = "https://meaningfy.ws/ns/rdf-persistence#storeName"
DOWN = StoreUnavailable("down")


class Racing(FakeStore):
    """A store that runs ``then`` once, right after its next ``create_dataset``: another writer acts in the gap."""

    def __init__(self) -> None:
        super().__init__()
        self.then = None

    async def create_dataset(self, name):
        await super().create_dataset(name)
        if self.then is not None:
            act, self.then = self.then, None
            await act()


@pytest.fixture
async def world() -> SimpleNamespace:
    d, a, files = FakeStore(), FakeStore(), FakeFileStore()
    tenancy = wired(d, files, *IDS, **{CLIENT_A: a})
    await tenancy.ensure_system_database()
    return SimpleNamespace(d=d, a=a, files=files, tenancy=tenancy)


def swept(world: SimpleNamespace, tenancy: Tenancy | None = None):
    return sweep(tenancy or cold(world, **{CLIENT_A: world.a}), world.d, world.files, SETTINGS)


async def erase_store_name(world: SimpleNamespace, tenant: str) -> None:
    """What a writer that does not know ``store_name`` does to a record (RISK-5)."""
    graph = graph_iri(str(Iris(SETTINGS, *TYPES).access(tenant)))
    await world.d.update(
        SYSTEM, f"DELETE WHERE {{ GRAPH <{graph}> {{ ?s <{RP_STORE_NAME}> ?o }} }}"
    )
    assert (await cold(world, **{CLIENT_A: world.a}).get(tenant))[0].store_name is None, (
        "the cold instance reads the record without a store name"
    )


# -- a failure in the middle of a create on A ------------------------------------------------------


@pytest.mark.parametrize("failing_update", [0, 1], ids=["the stamp", "the root"])
async def test_a_create_on_a_that_fails_after_the_database_leaves_no_record_and_drops_it_from_a(
    world, failing_update
):
    survivor = await made_on(world)
    world.a.on("update", DOWN, after=failing_update)
    with pytest.raises(StoreUnavailable):
        await made_on(world, CLIENT_A)
    assert tenant_databases(world.a) == [], "the create dropped its database from A (PD-12)"
    assert [t.id for t in await world.tenancy.tenants()] == [survivor], "no record for it"
    assert len(await world.files.list_buckets(PREFIX)) == 1, "only the survivor's bucket is left"


async def test_a_create_whose_record_write_fails_on_d_leaves_a_database_on_a_that_the_sweep_drops(
    world,
):
    survivor = await made_on(world)  # a live tenant on D: the sweep may judge orphans
    world.d.on("update", DOWN)
    with pytest.raises(StoreUnavailable):
        await world.tenancy.create("Bruges", library_slots(), CREATOR, store=CLIENT_A)
    assert len(tenant_databases(world.a)) == 1, (
        "the failed create leaves one database on the other store"
    )
    with pytest.raises(NotFound):
        await world.tenancy.store_name_of(
            str(Iris(SETTINGS, *TYPES, id_source=lambda spec: IDS[1]).mint_tenant())
        )

    await swept(world)

    assert tenant_databases(world.a) == [], "the sweep drops the database on the other store"
    assert [t.id for t in await world.tenancy.tenants()] == [survivor], (
        "the live tenant is untouched"
    )


async def test_a_failed_create_is_retried_on_the_same_instance_and_lands_on_the_other_store(world):
    world.a.on("create_dataset", DOWN)
    with pytest.raises(StoreUnavailable):
        await made_on(world, CLIENT_A)
    tenant = await made_on(world)  # a fresh draw, on D
    assert (await world.tenancy.store_name_of(tenant)) == DEFAULT_STORE, (
        "the retried create lands on the default store"
    )
    assert tenant_databases(world.a) == [], "the other store keeps no database"


async def test_a_create_that_loses_the_race_for_an_id_leaves_no_database_on_a_that_the_sweep_keeps():
    """Two instances draw the same id before either creates (X on A, Y on D); X loses on the shared bucket."""
    d, a, files = FakeStore(), Racing(), FakeFileStore()
    x = wired(d, files, IDS[0], **{CLIENT_A: a})
    y = wired(d, files, IDS[0])
    await x.ensure_system_database()

    async def y_creates():
        await y.create("Ghent", library_slots(), CREATOR)

    a.then = y_creates  # after X made its database on A, before its bucket
    with pytest.raises(PersistenceError):
        await x.create("Bruges", library_slots(), CREATOR, store=CLIENT_A)

    await sweep(wired(d, files, **{CLIENT_A: a}), d, files, SETTINGS)

    assert [n for n in a._datasets if n.startswith(PREFIX)] == [], (
        "a database named like Y's tenant stays on A"
    )


# -- two instances over the same stores -------------------------------------------------------------


async def test_a_cold_instance_serves_and_deletes_what_another_created_on_a(world):
    tenant = await made_on(world, CLIENT_A)
    other = cold(world, **{CLIENT_A: world.a})
    record, version = await other.get(tenant)
    async with other.tenant_session(tenant, CREATOR) as session:
        assert session is not None, "the cold instance serves the session"
    await other.delete(tenant, version)
    assert tenant_databases(world.a) == [], "the other store keeps no database"
    assert await other.tenants() == [], "no tenant is listed"


async def test_an_instance_that_cached_a_tenant_deleted_by_another_answers_database_gone_and_writes_nowhere(
    world,
):
    tenant = await made_on(world, CLIENT_A)
    assert await world.tenancy.store_name_of(tenant) == CLIENT_A, (
        "the instance cached the store the tenant was created on"
    )  # cached
    other = cold(world, **{CLIENT_A: world.a})
    _, version = await other.get(tenant)
    await other.delete(tenant, version)

    with pytest.raises(DatabaseGone):
        async with world.tenancy.tenant_session(tenant, CREATOR) as session:
            await session.get_graph(tenant)
    assert tenant_databases(world.a) == tenant_databases(world.d) == [], (
        "no database is left on either store"
    )


async def test_the_sweep_of_a_cold_instance_finishes_a_deletion_another_instance_stopped_on_a(
    world,
):
    tenant = await made_on(world, CLIENT_A)
    _, version = await world.tenancy.get(tenant)
    world.a.on("drop_dataset", DOWN)
    with pytest.raises(StoreUnavailable):
        await world.tenancy.delete(tenant, version)
    assert (await world.tenancy.get(tenant))[0].state == TenantState.DELETING, (
        "the record is still being deleted"
    )

    await swept(world)

    assert tenant_databases(world.a) == [], "the other store keeps no database"
    assert await world.files.list_buckets(PREFIX) == [], "no bucket is left"
    assert await world.tenancy.tenants() == [], "no tenant is listed"


async def test_a_finish_deletion_on_an_instance_that_lost_the_store_changes_nothing_and_keeps_the_record(
    world,
):
    tenant = await made_on(world, CLIENT_A)
    _, version = await world.tenancy.get(tenant)
    world.a.on("drop_dataset", DOWN)
    with pytest.raises(StoreUnavailable):
        await world.tenancy.delete(tenant, version)
    narrow = cold(world)

    with pytest.raises(StoreNotWired, match=CLIENT_A):
        await narrow.finish_deletion(tenant)

    assert len(tenant_databases(world.a)) == 1, "the failed finish leaves the database"
    assert len(await world.files.list_buckets(PREFIX)) == 1, "the bucket is not dropped either"
    assert (await narrow.get(tenant))[0].state == TenantState.DELETING, (
        "the failed finish keeps the record deleting"
    )


async def test_the_sweep_of_an_instance_that_does_not_wire_a_store_stops_before_changing_anything(
    world,
):
    gone = await made_on(world, CLIENT_A)
    _, version = await world.tenancy.get(gone)
    world.a.on("drop_dataset", DOWN)
    with pytest.raises(StoreUnavailable):
        await world.tenancy.delete(gone, version)
    orphan = PREFIX + "orphan1"
    await world.d.create_dataset(orphan)
    before = (len(world.d.sent("drop_dataset")), len(world.a.sent("drop_dataset")))

    with pytest.raises(StoreNotWired, match=CLIENT_A):
        await swept(world, cold(world))

    assert (len(world.d.sent("drop_dataset")), len(world.a.sent("drop_dataset"))) == before, (
        "the sweep dropped nothing on either store"
    )
    assert orphan in world.d._datasets, "the orphan is not dropped"


# -- RISK-5: a record that lost its store name -------------------------------------------------------


async def test_a_record_that_lost_its_store_name_is_reported_and_its_database_on_a_survives_the_sweep(
    world, caplog
):
    tenant = await made_on(world, CLIENT_A)
    name = (await world.tenancy.get(tenant))[0].database_name
    await erase_store_name(world, tenant)

    with caplog.at_level(logging.ERROR):
        await swept(world)

    assert name in world.a._datasets, "the tenant's database is kept"
    steps = [
        (a["rp.step"], a["rp.tenant.id"], a["rp.store.name"], a["rp.store.found_name"])
        for a in map(attributes, caplog.records)
        if a.get("rp.step") == "misplaced-tenant"
    ]
    assert ("misplaced-tenant", tenant, DEFAULT_STORE, CLIENT_A) in steps, (
        "the misplaced tenant is reported with both store names"
    )


async def test_a_tenant_whose_store_name_was_erased_answers_not_found_on_a_session(world):
    tenant = await made_on(world, CLIENT_A)
    await erase_store_name(world, tenant)
    other = cold(world, **{CLIENT_A: world.a})
    with pytest.raises(PersistenceError):
        async with other.tenant_session(tenant, CREATOR) as session:
            await session.get_graph(tenant)


async def test_a_deleting_record_that_lost_its_store_name_is_finished_on_d_and_its_database_on_a_goes_with_the_next_sweep(
    world,
):
    """RISK-5 on a deletion: the drop goes to D, the record goes; the database on A is an orphan for the next sweep."""
    survivor = await made_on(world)  # with no record on file the sweep drops nothing
    tenant = await made_on(world, CLIENT_A)
    name = (await world.tenancy.get(tenant))[0].database_name
    _, version = await world.tenancy.get(tenant)
    world.a.on("drop_dataset", DOWN)
    with pytest.raises(StoreUnavailable):
        await world.tenancy.delete(tenant, version)
    await erase_store_name(world, tenant)

    await swept(
        world
    )  # first sweep: the record is finished on D; the name was recorded when it began
    assert [t.id for t in await world.tenancy.tenants()] == [survivor], (
        "only the survivor is listed"
    )
    await swept(world)  # second sweep: no record names the survivor on A any more

    assert name not in world.a._datasets, "the second sweep drops it as an orphan"


# -- what the sweep does and does not touch -----------------------------------------------------------


async def test_the_no_records_guard_sees_a_tenant_resource_that_is_only_on_a(world):
    leftover = PREFIX + "leftover"
    await world.a.create_dataset(leftover)
    before = len(world.a.sent("drop_dataset"))

    await swept(world)

    assert leftover in world.a._datasets, "no record on file: nothing is judged an orphan"
    assert len(world.a.sent("drop_dataset")) == before, "nothing is dropped on the other store"


async def test_a_database_without_the_tenant_prefix_is_never_dropped_on_any_store(world):
    await made_on(world)  # a live tenant: orphans are judged
    for store in (world.d, world.a):
        await store.create_dataset("someone-elses")
        await store.create_dataset(
            "lib-x-" + "1" * 6
        )  # the application prefix is not the tenant one
    orphan = PREFIX + "orphan1"
    await world.a.create_dataset(orphan)

    await swept(world)

    assert orphan not in world.a._datasets, "the database without the prefix is never dropped"
    for store in (world.d, world.a):
        assert {"someone-elses", "lib-x-111111"} <= set(store._datasets), (
            "the other databases are kept"
        )


async def test_an_orphan_that_shares_the_name_of_a_recorded_database_on_the_other_store_is_kept(
    world,
):
    tenant = await made_on(world, CLIENT_A)
    name = (await world.tenancy.get(tenant))[0].database_name
    await world.d.create_dataset(
        name
    )  # same name, wrong store: judged by name across stores (RISK-4)

    await swept(world)

    assert name in world.a._datasets, "the orphan with a recorded name on the other store is kept"
    assert name in world.d._datasets, "the recorded database on the default store is kept"


async def test_the_sweep_drops_an_orphan_on_each_store_and_only_the_orphans(world):
    live_d, live_a = await made_on(world), await made_on(world, CLIENT_A)
    names = {(await world.tenancy.get(t))[0].database_name for t in (live_d, live_a)}
    await world.d.create_dataset(PREFIX + "orphand")
    await world.a.create_dataset(PREFIX + "orphana")

    await swept(world)

    assert set(tenant_databases(world.d)) | set(tenant_databases(world.a)) == names, (
        "the orphans of both stores are dropped"
    )


async def test_a_sweep_whose_store_is_down_changes_nothing_on_the_other_store(world):
    await made_on(world)
    orphan = PREFIX + "orphand"
    await world.d.create_dataset(orphan)
    world.a.on("list_datasets", DOWN)

    with pytest.raises(StoreUnavailable):
        await swept(world)

    assert orphan in world.d._datasets, "the orphan on the working store is kept"
    assert world.d.sent("drop_dataset") == [], "nothing is dropped on the working store"


# -- the constructor and the wiring ------------------------------------------------------------------


def stores_of(name: str) -> Tenancy:
    return Tenancy(
        FakeStore(),
        FakeFileStore(),
        SETTINGS,
        mapper=toy_mapper(),
        root_class=Library,
        access_class=LibraryAccess,
        stores={name: FakeStore()},
    )


@pytest.mark.parametrize("name", ["a", "a" * 32, "a-", "a-b-c", "z9", "a" + "0" * 31])
def test_a_store_name_at_the_limits_of_the_pattern_is_wired(name):
    assert list(stores_of(name).stores()) == [DEFAULT_STORE, name], (
        "a store name at the limit is wired"
    )


# equivalence classes: uppercase (A; Default), punctuation (a_b; a.b, a/b), whitespace (a b; a\n, " a");
# the empty, the long, the digit-first, the dash-first and the non-ASCII names are boundaries of the pattern
@pytest.mark.parametrize("name", ["", "a" * 33, "A", "1a", "-a", "a_b", "a b", "é"])
def test_a_store_name_outside_the_pattern_is_refused_naming_it(name):
    with pytest.raises(ValueError, match="store"):
        stores_of(name)


def test_a_caller_that_changes_the_stores_it_was_given_does_not_change_the_wiring():
    given = {"client-a": FakeStore()}
    tenancy = Tenancy(
        FakeStore(),
        FakeFileStore(),
        SETTINGS,
        mapper=toy_mapper(),
        root_class=Library,
        access_class=LibraryAccess,
        stores=given,
    )
    given["client-b"] = FakeStore()
    given.pop("client-a")
    assert list(tenancy.stores()) == [DEFAULT_STORE, "client-a"], (
        "changing the given stores does not change the wiring"
    )


def test_a_caller_that_changes_what_stores_answers_does_not_change_the_wiring():
    tenancy = stores_of("client-a")
    answered = tenancy.stores()
    answered["client-b"] = FakeStore()
    answered.pop("client-a")
    assert list(tenancy.stores()) == [DEFAULT_STORE, "client-a"], (
        "changing what stores answers does not change the wiring"
    )


# -- restore and migrate -----------------------------------------------------------------------------


async def test_migrate_tenants_sets_aside_the_tenant_on_a_store_that_is_down_and_migrates_the_others(
    world, tmp_path
):
    on_d, on_a = await made_on(world), await made_on(world, CLIENT_A)
    chain = chain_of(
        tmp_path, LIBRARY_SCHEMA, migration(LIB, "1", "2", rename(OLD, NEW)), current="2"
    )
    world.a.on("update", DOWN)

    aside = await migrate_tenants(world.tenancy, world.d, [(LIBRARY_SCHEMA, chain)])

    assert aside == {on_a}, "the tenant on the store that is down is set aside"
    assert on_d not in aside, "the tenant on the working store is not set aside"
    assert world.tenancy.behind == {on_a}, "the instance remembers the set-aside tenant"


async def test_migrate_tenants_on_an_instance_that_does_not_wire_a_store_stops_with_the_tenant_not_set_aside(
    world, tmp_path
):
    tenant = await made_on(world, CLIENT_A)
    chain = chain_of(tmp_path, LIBRARY_SCHEMA, current="1")
    narrow = cold(world)
    with pytest.raises(StoreNotWired, match=CLIENT_A):
        await migrate_tenants(narrow, world.d, [(LIBRARY_SCHEMA, chain)])
    assert tenant not in narrow.behind, "the tenant is not set aside when the store is not wired"


async def test_every_tenant_is_migrated_on_its_own_store_and_not_on_the_other(world, tmp_path):
    await made_on(world)
    await made_on(world, CLIENT_A)
    chain = chain_of(tmp_path, LIBRARY_SCHEMA, current="1")
    before = (operations(world.d), operations(world.a))
    assert await migrate_tenants(world.tenancy, world.d, [(LIBRARY_SCHEMA, chain)]) == set(), (
        "no tenant is left to migrate on the other store"
    )
    after = (operations(world.d), operations(world.a))
    assert after[1] > before[1], "A is read"
    assert not [q for q in world.a.sent("query") if SYSTEM in q], "A never sees the system database"
