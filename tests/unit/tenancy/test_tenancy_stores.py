"""Tenants routed by store: ``default`` and the stores wired beside it (tenant-stores PD-2 to PD-5, PD-7, PD-8).

``D`` is the default ``FakeStore``, ``A`` the store wired as ``client-a``. Every test names its TC id.
"""

import logging
from types import SimpleNamespace
from uuid import UUID

import pytest
from rdflib import URIRef

from rdf_persistence import TenantAccess
from rdf_persistence.access.services.generated.rp_access_services import GrantSet
from rdf_persistence.core.domain.exceptions import (
    Conflict,
    NotFound,
    StoreNotWired,
    StoreUnavailable,
    TenantBehind,
)
from rdf_persistence.core.domain.generated import rp_core, rp_tenancy
from rdf_persistence.core.domain.generated.rp_core import Principal
from rdf_persistence.core.domain.generated.rp_tenancy import TenantState
from rdf_persistence.core.domain.sparql import fill, term
from rdf_persistence.iris.domain.layout import graph_iri, system_database_name
from rdf_persistence.iris.services.iris import Iris
from rdf_persistence.persistence.services.mapper import Mapper, UnitOfWork, generated_models
from rdf_persistence.schema.services import vocabulary as v
from rdf_persistence.schema.services.schema import load_schema
from rdf_persistence.schema.services.schema_structure import iri_types
from rdf_persistence.tenancy.services.tenancy import DEFAULT_STORE, Tenancy
from rdf_persistence.testkit import FakeFileStore, FakeStore
from tests.fixtures.library.generated.books import Book
from tests.fixtures.library.generated.library import Library
from tests.fixtures.library.generated.library_access import LibraryAccess
from tests.logs import attributes, records_of
from tests.toy import ADA, SETTINGS, TOY_SCHEMA, dune, library_slots, toy_mapper
from tests.unit.builders import TENANT, tenant_access

CREATOR = Principal(id=ADA)
SYSTEM = system_database_name(SETTINGS.prefix)
PREFIX = "lib-t-"
CLIENT_A = "client-a"
LIBRARY_SCHEMA = "https://example.org/ns/library"
IDS = [str(UUID(int=n)) for n in (1, 2, 3)]
ASK = "ASK { GRAPH $g { ?s ?p ?o } }"
TYPES = iri_types(load_schema(TOY_SCHEMA))


def _drawing(*ids: str):
    """An id source that answers ``ids`` in turn and fails if asked for more."""
    drawn = iter(ids)
    return lambda spec: next(drawn)


def wired(d: FakeStore, files: FakeFileStore, *ids: str, **stores: FakeStore) -> Tenancy:
    """A tenancy on ``d`` with ``stores`` beside it; ``ids`` are the tenant ids it draws, in turn."""
    iris = Iris(SETTINGS, *TYPES, id_source=_drawing(*ids))
    return Tenancy(
        d,
        files,
        SETTINGS,
        mapper=toy_mapper(),
        root_class=Library,
        access_class=LibraryAccess,
        iris=iris,
        stamps=[(LIBRARY_SCHEMA, "1")],
        stores=stores,
    )


@pytest.fixture
async def world() -> SimpleNamespace:
    d, a, files = FakeStore(), FakeStore(), FakeFileStore()
    tenancy = wired(d, files, *IDS, **{CLIENT_A: a})
    await tenancy.ensure_system_database()
    return SimpleNamespace(d=d, a=a, files=files, tenancy=tenancy)


def cold(world: SimpleNamespace, **stores: FakeStore) -> Tenancy:
    """Another instance over the same stores: it has read nothing yet."""
    return wired(world.d, world.files, **stores)


def operations(store: FakeStore) -> int:
    return sum(len(store.sent(operation)) for operation in FakeStore.OPERATIONS)


def tenant_databases(store: FakeStore) -> list[str]:
    return [name for name in store._datasets if name.startswith(PREFIX)]


async def holds(store: FakeStore, database: str, graph: URIRef) -> bool:
    return bool((await store.query(database, fill(ASK, g=term(graph)))).askAnswer)


async def made_on(world: SimpleNamespace, store: str | None = None) -> str:
    kwargs = {} if store is None else {"store": store}
    return (await world.tenancy.create("Ghent", library_slots(), CREATOR, **kwargs)).id


# -- PD-1, PD-2: the record's store name ---------------------------------------------------------------


def test_tc03_a_record_written_without_a_store_name_decodes_with_none() -> None:
    mapper = Mapper(v.metamodel(), generated_models(rp_tenancy, rp_core))
    graph = mapper.to_graph(tenant_access())
    decoded = mapper.from_graph(TenantAccess, TENANT, graph, graph_iri(TENANT))
    assert decoded.store_name is None, "no store name decodes to None, which means default"


# -- PD-3: what the constructor refuses ------------------------------------------------------------


@pytest.mark.parametrize(
    ("stores", "named"),
    [
        ({"default": "A"}, "default"),
        ({"Client": "A"}, "Client"),
        ({"a": "A", "b": "A"}, "b"),
        ({"a": "D"}, "a"),  # the default store's own object
    ],
)
def test_tc05_a_store_name_or_object_the_tenancy_cannot_route_is_refused_naming_the_key(
    stores, named
):
    d, a = FakeStore(), FakeStore()
    objects = {"A": a, "D": d}
    with pytest.raises(ValueError, match=f"'{named}'"):
        Tenancy(
            d,
            FakeFileStore(),
            SETTINGS,
            mapper=toy_mapper(),
            root_class=Library,
            access_class=LibraryAccess,
            stores={name: objects[ref] for name, ref in stores.items()},
        )


def test_tc06_the_stores_are_every_wired_name_with_default_first(world):
    assert list(world.tenancy.stores().items()) == [
        (DEFAULT_STORE, world.d),
        (CLIENT_A, world.a),
    ], "every wired name, default first"


# -- PD-4: routing a tenant ------------------------------------------------------------------------


async def test_tc07_a_record_without_a_store_name_is_on_default_and_costs_one_query(world):
    tenant = await made_on(world)
    other = cold(world)
    before = operations(world.d)
    assert await other.store_of(tenant) is world.d, "a record with no store name is on D"
    assert operations(world.d) == before + 1, "one query for the record"


async def test_tc08_a_tenant_on_another_store_is_found_once_then_from_the_cache(world):
    tenant = await made_on(world, CLIENT_A)
    other = cold(world, **{CLIENT_A: world.a})
    assert await other.store_of(tenant) is world.a, "found from its record"
    before = (operations(world.d), operations(world.a))
    assert await other.store_of(tenant) is world.a, "found again"
    assert (operations(world.d), operations(world.a)) == before, "the second call reads nothing"


async def test_tc09_a_record_naming_a_store_that_is_not_wired_is_refused_naming_it(world):
    b = FakeStore()
    both = wired(world.d, world.files, IDS[0], **{CLIENT_A: world.a, "client-b": b})
    tenant = (await both.create("Ghent", library_slots(), CREATOR, store="client-b")).id
    with pytest.raises(StoreNotWired, match="client-b"):
        await cold(world, **{CLIENT_A: world.a}).store_of(tenant)


async def test_tc10_a_tenant_without_a_record_has_no_store_name(world):
    with pytest.raises(NotFound):
        await world.tenancy.store_name_of(str(Iris(SETTINGS).mint_tenant()))


# -- PD-5: sessions on the tenant's store ----------------------------------------------------------


async def test_tc11_a_session_writes_on_the_store_of_its_tenant(world):
    tenant = await made_on(world, CLIENT_A)
    iris = Iris(SETTINGS, *TYPES)
    book = str(iris.mint_aggregate(tenant, "book", "books"))
    database = world.tenancy.database_of(tenant)
    before = (len(world.d.sent("update")), len(world.d.sent("put_graph")))

    async with world.tenancy.tenant_session(tenant, CREATOR) as session:
        work = UnitOfWork(session, toy_mapper())
        work.add(dune(book))
        await work.commit()

    assert await holds(world.a, database, graph_iri(book)), "the book's graph is on A"
    assert (len(world.d.sent("update")), len(world.d.sent("put_graph"))) == before, "D untouched"
    async with world.tenancy.tenant_session(tenant, CREATOR) as session:
        read = await UnitOfWork(session, toy_mapper()).get(Book, book)
        assert isinstance(read, Book), "the book reads back through the session"


async def test_tc12_a_tenant_behind_is_refused_at_the_call_before_any_read(world):
    tenant = await made_on(world, CLIENT_A)
    world.tenancy.set_aside([tenant])
    before = (operations(world.d), operations(world.a))
    with pytest.raises(TenantBehind, match=tenant):
        world.tenancy.tenant_session(tenant, CREATOR)  # not entered
    assert (operations(world.d), operations(world.a)) == before, "no store was asked"


async def test_tc38_a_record_keeps_its_store_name_through_every_rewrite(world):
    tenant = await made_on(world, CLIENT_A)
    record, version = await world.tenancy.get(tenant)

    version = await world.tenancy.set_grants(
        tenant, GrantSet(grants=record.grants, prohibitions=record.prohibitions), version, CREATOR
    )
    assert (await world.tenancy.get(tenant))[0].store_name == CLIENT_A, "after set_grants"

    version = await world.tenancy.rename(tenant, "Bruges", version, CREATOR)
    assert (await world.tenancy.get(tenant))[0].store_name == CLIENT_A, "after rename"

    world.a.on("drop_dataset", StoreUnavailable("down"))  # the delete stops after it marks
    with pytest.raises(StoreUnavailable):
        await world.tenancy.delete(tenant, version)
    marked, _ = await world.tenancy.get(tenant)
    assert (marked.state, marked.store_name) == (TenantState.DELETING, CLIENT_A), "after delete"


# -- PD-7: create ----------------------------------------------------------------------------------


async def test_tc13_a_tenant_made_without_a_store_is_on_default_and_its_record_names_none(world):
    tenant = await made_on(world)
    record, _ = await world.tenancy.get(tenant)
    name = record.database_name
    iris = Iris(SETTINGS, *TYPES)
    assert name in world.d._datasets, "the database is on D"
    assert tenant_databases(world.a) == [], "A has no tenant database"
    assert await holds(world.d, name, world.tenancy.stamps_graph), "stamped on D"
    assert await holds(world.d, name, iris.meta(tenant)), "the root is on D"
    assert record.store_name is None, "default is never written (PD-2)"


async def test_tc14_a_tenant_made_on_a_store_has_its_database_there_and_its_record_on_default(
    world,
):
    tenant = await made_on(world, CLIENT_A)
    record, _ = await world.tenancy.get(tenant)
    name = record.database_name
    iris = Iris(SETTINGS, *TYPES)
    assert name in world.a._datasets, "the database is on A"
    assert await holds(world.a, name, world.tenancy.stamps_graph), "stamped on A"
    assert await holds(world.a, name, iris.meta(tenant)), "the root is on A"
    assert tenant_databases(world.d) == [], "D has no tenant database"
    assert await holds(world.d, SYSTEM, graph_iri(str(iris.access(tenant)))), "the record is on D"
    assert record.store_name == CLIENT_A, "the record names the store"


async def test_tc15_a_store_that_is_not_wired_refuses_before_anything_is_drawn_or_made():
    d, a, files = FakeStore(), FakeStore(), FakeFileStore()
    tenancy = wired(d, files, **{CLIENT_A: a})  # no id to draw: a draw would fail
    await tenancy.ensure_system_database()
    with pytest.raises(StoreNotWired, match="client-b"):
        await tenancy.create("Ghent", library_slots(), CREATOR, store="client-b")
    assert tenant_databases(d) == [], "no tenant database on D"
    assert tenant_databases(a) == [], "no tenant database on client-a"
    assert files.sent("create_bucket") == [], "no bucket"
    assert await tenancy.tenants() == [], "no record"


async def test_tc16_an_id_whose_database_exists_on_another_store_is_drawn_again(world):
    await world.a.create_dataset(PREFIX + IDS[0].replace("-", ""))
    tenant = await made_on(world)
    assert tenant.endswith(IDS[1]), "the first id is taken on A, so the second is drawn"


async def test_tc40_a_store_that_is_down_stops_a_create_on_another_before_it_makes_anything(world):
    world.a.on("list_datasets", StoreUnavailable("down"))
    with pytest.raises(StoreUnavailable):
        await made_on(world)
    assert tenant_databases(world.d) == [], "no tenant database on D"
    assert world.files.sent("create_bucket") == [], "no bucket"


# -- PD-8: deletion --------------------------------------------------------------------------------


async def test_tc17_a_tenant_is_dropped_from_its_own_store_and_forgotten(world):
    tenant = await made_on(world, CLIENT_A)
    record, version = await world.tenancy.get(tenant)
    on_d = list(world.d._datasets)

    await world.tenancy.delete(tenant, version)

    assert record.database_name not in world.a._datasets, "dropped from A"
    assert list(world.d._datasets) == on_d, "D's databases are unchanged"
    with pytest.raises(NotFound):
        await world.tenancy.store_name_of(tenant)


async def test_tc18_a_deletion_whose_database_is_already_gone_finishes(world):
    tenant = await made_on(world, CLIENT_A)
    record, version = await world.tenancy.get(tenant)
    await world.a.drop_dataset(record.database_name)  # an interrupted run

    await world.tenancy.delete(tenant, version)

    assert record.database_name not in await world.files.list_buckets(PREFIX), "bucket dropped"
    assert await world.tenancy.tenants() == [], "record removed"


async def test_tc41_a_delete_on_a_store_that_is_not_wired_changes_nothing(world):
    tenant = await made_on(world, CLIENT_A)
    _, version = await world.tenancy.get(tenant)
    narrow = cold(world)  # does not wire client-a

    with pytest.raises(StoreNotWired, match=CLIENT_A):
        await narrow.delete(tenant, version)

    assert (await world.tenancy.get(tenant))[0].state == TenantState.ACTIVE, "not marked deleting"


# -- PD-12, PD-14: a failed create drops only what its own call made -----------------------------------


def drawn_name(world: SimpleNamespace, tenant_id: str) -> str:
    """The database and bucket name of the tenant that draws ``tenant_id``."""
    return world.tenancy.database_of(
        str(Iris(SETTINGS, *TYPES, id_source=_drawing(tenant_id)).mint_tenant())
    )


async def test_pd14_a_create_that_conflicts_on_the_bucket_keeps_the_other_tenants_bucket_and_files(
    world,
):
    name = drawn_name(world, IDS[0])
    await world.files.create_bucket(name)  # the winner's, made between this draw and its create
    await world.files.put(name, "scan.pdf", b"%PDF")

    with pytest.raises(Conflict):
        await made_on(world, CLIENT_A)

    assert tenant_databases(world.a) == [], "the database it made is dropped from A"
    assert await world.files.list_buckets(PREFIX) == [name], "the winner's bucket is kept"
    assert await world.files.get(name, "scan.pdf") == b"%PDF", "and its files"
    assert world.files.sent("delete_bucket") == [], "no bucket drop was sent"


async def test_pd12_a_create_that_fails_after_the_database_drops_it_and_the_bucket_it_made(
    world, caplog
):
    world.a.on("update", StoreUnavailable("down"), after=1)  # the root, after the stamp
    with (
        caplog.at_level(logging.WARNING, logger="rdf_persistence.tenancy.services.tenancy"),
        pytest.raises(StoreUnavailable, match="down"),
    ):
        await made_on(world, CLIENT_A)
    assert tenant_databases(world.a) == [], "no database is left on A"
    assert await world.files.list_buckets(PREFIX) == [], "no bucket is left"
    steps = [attributes(r).get("rp.step") for r in caplog.records]
    assert "create-cleanup" not in steps, "a drop that worked is not warned about"


async def test_pd12_a_create_cleanup_that_fails_too_is_logged_and_the_original_error_is_raised(
    world, caplog
):
    world.a.on("update", StoreUnavailable("the root failed"), after=1)
    world.a.on("drop_dataset", StoreUnavailable("the drop failed"))
    with (
        caplog.at_level(logging.WARNING, logger="rdf_persistence.tenancy.services.tenancy"),
        pytest.raises(StoreUnavailable, match="the root failed"),
    ):
        await made_on(world, CLIENT_A)
    [logged] = records_of(caplog, "create-cleanup")
    assert attributes(logged)["rp.resource"] in world.a._datasets, (
        "the logged database is left to the sweep"
    )
