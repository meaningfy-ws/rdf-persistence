"""Application data against a real Fuseki (app-level-data PD-6 to PD-10; IT-01 to IT-04).

The toy service starts through its lifespan (policy guard, application database, sweep). ``A`` is the
application IRI, ``T`` a tenant, ``Tpl`` a ``Template`` (application class), ``B`` a ``Book`` (tenant class).
"""

from collections.abc import AsyncIterator

import pytest

from rdf_persistence import Conflict, FusekiStore, InvalidIri, UnitOfWork
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.iris import application_database_name, graph_iri
from rdf_persistence.services.sweep import sweep
from tests.fixtures.library.generated.books import Book
from tests.fixtures.library.generated.templates import Template
from tests.toy import ADA, dune, library_slots, template, toy_mapper
from tests.toy_service import ToyService, drop_databases, unique_prefix

CREATOR = Principal(id=ADA)


@pytest.fixture
async def toy(store: FusekiStore) -> AsyncIterator[ToyService]:
    """The toy service started against Fuseki under a prefix of its own; its databases are dropped after."""
    prefix = unique_prefix()
    service = ToyService(store, prefix=prefix)
    try:
        async with service.app.router.lifespan_context(service.app):
            yield service
    finally:
        await drop_databases(store, prefix)


def app_database(toy: ToyService) -> str:
    return application_database_name(toy.settings.prefix)


async def holds(store: FusekiStore, database: str, iri: str) -> bool:
    asked = await store.query(database, f"ASK {{ GRAPH <{graph_iri(iri)}> {{ ?s ?p ?o }} }}")
    return bool(asked.askAnswer)


async def add_tpl(toy: ToyService) -> str:
    iri = toy.kit.application_iri(Template)
    async with toy.kit.application_session(ADA) as session:
        work = UnitOfWork(session, toy_mapper())
        work.add(template(iri))
        await work.commit()
    return iri


async def test_it01_an_application_aggregate_is_read_back_through_a_new_session(toy, store):
    iri = await add_tpl(toy)
    async with toy.kit.application_session(ADA) as session:
        read = await UnitOfWork(session, toy_mapper()).get(Template, iri)
    sent = template(iri)
    kept = {"id", "label", "description"}
    assert read.model_dump(include=kept) == sent.model_dump(include=kept), "read back equal"
    assert app_database(toy) in await store.list_datasets(), "the application database exists"
    assert await holds(store, app_database(toy), iri), "the graph is in it"


async def test_it02_two_replaces_at_the_same_version_conflict(toy):
    iri = await add_tpl(toy)
    async with (
        toy.kit.application_session(ADA) as first,
        toy.kit.application_session(ADA) as second,
    ):
        one, other = UnitOfWork(first, toy_mapper()), UnitOfWork(second, toy_mapper())
        mine, theirs = await one.get(Template, iri), await other.get(Template, iri)
        mine.label, theirs.label = "First", "Second"
        one.add(mine)
        other.add(theirs)
        await one.commit()
        with pytest.raises(Conflict):
            await other.commit()
    async with toy.kit.application_session(ADA) as session:
        stored = await UnitOfWork(session, toy_mapper()).get(Template, iri)
    assert stored.label == "First", "the stored label is the first commit's"


async def test_it03_the_tenants_listing_and_the_sweep_leave_application_data_alone(toy, store):
    tenant = (await toy.kit.tenancy.create("Ghent", library_slots(), CREATOR)).id
    book = str(toy.kit.iris.mint_aggregate(tenant, "Book", "books"))
    async with toy.kit.session(tenant, ADA) as session:
        work = UnitOfWork(session, toy_mapper())
        work.add(dune(book))
        await work.commit()
    tpl = await add_tpl(toy)
    async with toy.kit.session(tenant, ADA) as session:
        listed = await session.find(Book)
    await sweep(toy.kit.tenancy, store, toy.files, toy.settings)
    assert listed == [book], "the listing holds only B"
    assert app_database(toy) in await store.list_datasets(), "the application database survives"
    assert await holds(store, app_database(toy), tpl), "Tpl survives the sweep"


async def test_it04_a_tenant_aggregate_is_refused_by_the_application_session(toy, store):
    book = str(toy.kit.iris.mint_aggregate(toy.kit.iris.application, "Book", "books"))
    with pytest.raises(InvalidIri):
        async with toy.kit.application_session(ADA) as session:
            work = UnitOfWork(session, toy_mapper())
            work.add(dune(book))
            await work.commit()
    assert not await holds(store, app_database(toy), book), (
        "no graph of B in the application database"
    )
