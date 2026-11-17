"""Tenants on two real Fuseki servers: a tenant's database is on the store its record names (tenant-stores PD-11).

The default store is the session's Fuseki, ``client-a`` the second one (``fuseki_b``). Each test has its own prefix
and drops what it made on both servers.
"""

from collections.abc import AsyncIterator
from types import SimpleNamespace

import pytest
from rdflib import URIRef

from rdf_persistence import FusekiStore
from rdf_persistence.domain.exceptions import DatabaseGone
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.sparql import fill, term
from rdf_persistence.services.iris import Iris, graph_iri, tenant_resource_name
from rdf_persistence.services.mapper import UnitOfWork
from rdf_persistence.services.schema import load_schema
from rdf_persistence.services.schema_structure import iri_types
from rdf_persistence.services.store import Store
from rdf_persistence.services.sweep import sweep
from rdf_persistence.services.tenancy import DEFAULT_STORE, Tenancy
from rdf_persistence.testkit import FakeFileStore
from tests.fixtures.library.generated.library import Library
from tests.fixtures.library.generated.library_access import LibraryAccess
from tests.toy import ADA, SETTINGS, TOY_SCHEMA, dune, library_slots, toy_mapper
from tests.toy_service import drop_databases, unique_prefix

CREATOR = Principal(id=ADA)
CLIENT_A = "client-a"
ASK = "ASK { GRAPH $g { ?s ?p ?o } }"
TYPES = iri_types(load_schema(TOY_SCHEMA))


@pytest.fixture
async def world(store, fuseki_b) -> AsyncIterator[SimpleNamespace]:
    """A tenancy with the session's Fuseki as default and the second one as ``client-a``."""
    settings = SETTINGS.model_copy(update={"prefix": unique_prefix()})
    files = FakeFileStore()
    async with FusekiStore(fuseki_b.url, fuseki_b.user, fuseki_b.password) as other:
        tenancy = Tenancy(
            store,
            files,
            settings,
            mapper=toy_mapper(),
            root_class=Library,
            access_class=LibraryAccess,
            stores={CLIENT_A: other},
        )
        await tenancy.ensure_system_database()
        yield SimpleNamespace(tenancy=tenancy, d=store, a=other, files=files, settings=settings)
        await drop_databases(store, settings.prefix)
        await drop_databases(other, settings.prefix)


async def made_with_book(world, store: str) -> tuple[str, URIRef]:
    """A tenant on ``store`` with a book in it: the tenant's id and the book's graph IRI."""
    tenant = (await world.tenancy.create("Ghent", library_slots(), CREATOR, store=store)).id
    book = str(Iris(world.settings, *TYPES).mint_aggregate(tenant, "book", "books"))
    async with world.tenancy.tenant_session(tenant, CREATOR) as session:
        work = UnitOfWork(session, toy_mapper())
        work.add(dune(book))
        await work.commit()
    return tenant, graph_iri(book)


async def holds(store: Store, database: str, graph: URIRef) -> bool:
    return bool((await store.query(database, fill(ASK, g=term(graph)))).askAnswer)


async def test_tc36_each_book_is_on_its_own_server_only(world):
    on_default, book_d = await made_with_book(world, DEFAULT_STORE)
    on_a, book_a = await made_with_book(world, CLIENT_A)
    db_d = tenant_resource_name(world.settings.prefix, on_default)
    db_a = tenant_resource_name(world.settings.prefix, on_a)

    assert db_d in await world.d.list_datasets(), "default holds its tenant's database"
    assert db_d not in await world.a.list_datasets(), "client-a does not"
    assert db_a in await world.a.list_datasets(), "client-a holds its tenant's database"
    assert db_a not in await world.d.list_datasets(), "default does not"
    assert await holds(world.d, db_d, book_d), "the default book is on default"
    assert await holds(world.a, db_a, book_a), "the client-a book is on client-a"
    with pytest.raises(DatabaseGone):  # the other server has no such database to ask
        await holds(world.a, db_d, book_d)
    with pytest.raises(DatabaseGone):
        await holds(world.d, db_a, book_a)


async def test_tc37_a_sweep_drops_the_orphan_on_the_second_server_and_keeps_its_tenant(world):
    tenant, book = await made_with_book(world, CLIENT_A)
    kept = tenant_resource_name(world.settings.prefix, tenant)
    await world.a.create_dataset(f"{world.settings.prefix}-t-{'0' * 32}")  # an orphan: no record

    await sweep(world.tenancy, world.d, world.files, world.settings)

    left = [n for n in await world.a.list_datasets() if n.startswith(f"{world.settings.prefix}-t-")]
    assert left == [kept], "client-a: only the active tenant's database"
    assert await holds(world.a, kept, book), "the tenant's book is unchanged"
