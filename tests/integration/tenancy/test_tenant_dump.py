"""Dump and restore of a tenant against real Fuseki and Garage (tenant-dump-restore 4.1: IT-01 = TC-10, IT-02 = TC-17).

The tenant ``T`` (Ghent) has a book ``B``, a graph ``g`` loaded for ``B``, a graph ``r`` loaded for the root and a scan
``S`` with one blob. The file store is the fake or Garage, as everywhere in the tenancy tests.
"""

import copy
import io
from types import SimpleNamespace

import pytest
from rdflib import URIRef
from rdflib.compare import isomorphic

from rdf_persistence.domain.exceptions import InvalidBody
from rdf_persistence.domain.generated.rp_files import RdfFormat
from rdf_persistence.services.mapper import UnitOfWork
from rdf_persistence.services.session import open_session
from rdf_persistence.services.tenant_dump import dump, restore
from tests.fixtures.library.generated.books import Book
from tests.fixtures.library.generated.scans import Scan
from tests.toy import SETTINGS, dune, library_slots, toy_mapper
from tests.toy_service import SCAN_BODY
from tests.unit.services.test_tenant_dump import (
    BLOB_BYTES,
    RESTORER,
    VIEW,
    iris_of,
    moved,
)
from tests.unit.services.test_tenant_sweep import BOOK_TYPE, CREATOR, TURTLE

SCAN_TYPE = "scan"


@pytest.fixture
async def world(tenancy, store, files) -> SimpleNamespace:
    """``T`` with ``B``, ``g``, ``r`` and ``S`` (blob ``k1``) on the real stores."""
    iris = iris_of(SETTINGS)
    tenant = (await tenancy.create("Ghent", library_slots(), CREATOR)).id
    record, _ = await tenancy.get(tenant)
    world = SimpleNamespace(
        tenancy=tenancy,
        store=store,
        files=files,
        iris=iris,
        tenant=tenant,
        database=record.database_name,
        book=str(iris.mint_aggregate(tenant, BOOK_TYPE, "books")),
        scan=str(iris.mint_aggregate(tenant, SCAN_TYPE, "scans")),
    )
    world.session = lambda: open_session(
        store, database=world.database, tenant_iri=tenant, principal=CREATOR, iris=iris
    )
    async with world.session() as opened:
        world.g = await opened.load_graph(world.book, TURTLE, rdf_format=RdfFormat.TURTLE)
        world.r = await opened.load_graph(tenant, TURTLE, rdf_format=RdfFormat.TURTLE)
        triples = toy_mapper().to_triples(dune(world.book))
        await opened.add_graph(world.book, triples, loaded_graphs=[world.g])
        graph, _, version = await opened.get_graph(tenant)
        await opened.replace_graph(tenant, list(graph), version, loaded_graphs=[world.r])
    async with tenancy.tenant_session(tenant, CREATOR) as opened:
        work = UnitOfWork(opened, toy_mapper())
        work.add(Scan.model_validate({**SCAN_BODY, "id": world.scan, "file_key": "k1"}))
        await work.commit()
    await files.put(world.database, "k1", BLOB_BYTES)
    return world


async def stores_state(world: SimpleNamespace) -> tuple:
    """Everything a restore may create: the databases, the buckets and the tenants with a record."""
    return (
        sorted(await world.store.list_datasets()),
        await world.files.list_buckets(""),
        [t.id for t in await world.tenancy.tenants()],
    )


async def read_book(world: SimpleNamespace, tenant: str, iri: str, who) -> Book:
    async with world.tenancy.tenant_session(tenant, who) as opened:
        return await UnitOfWork(opened, toy_mapper()).get(Book, iri)


async def test_it01_a_tenant_restored_from_its_dump_answers_like_the_original(world):
    out = io.BytesIO()
    await dump(world.tenancy, world.store, world.files, world.iris, VIEW, world.tenant, out)
    summary = await restore(world.tenancy, world.iris, VIEW, io.BytesIO(out.getvalue()), RESTORER)

    new = summary.id
    assert new != world.tenant, "a new tenant"
    assert summary.label == "Ghent", "the original's label"
    book_new = moved(world, world.book, new)
    original = await read_book(world, world.tenant, world.book, CREATOR)
    copied_book = await read_book(world, new, book_new, RESTORER)
    assert copied_book.id == book_new
    assert copied_book.model_dump(exclude={"id", "chapters"}) == original.model_dump(
        exclude={"id", "chapters"}
    ), "the same slot values"
    async with world.tenancy.tenant_session(new, RESTORER) as opened, world.session() as old:
        for owner, load in ((world.book, world.g), (world.tenant, world.r)):
            owner_new, load_new = moved(world, owner, new), moved(world, str(load), new)
            assert await opened.loaded_graphs(owner_new) == [URIRef(load_new)]
            copied = await opened.loaded_graph(owner_new, load_new)
            assert isomorphic(copied, await old.loaded_graph(owner, str(load))), "same triples"
    record, _ = await world.tenancy.get(new)
    assert await world.files.get(record.database_name, "k1") == BLOB_BYTES, "byte for byte"


async def test_it02_a_dump_of_another_schema_version_is_refused_and_creates_nothing(world):
    older = copy.deepcopy(VIEW)
    older.schema.version = "1.0.0"
    newer = copy.deepcopy(VIEW)
    newer.schema.version = "1.1.0"
    out = io.BytesIO()
    await dump(world.tenancy, world.store, world.files, world.iris, older, world.tenant, out)
    before = await stores_state(world)

    with pytest.raises(InvalidBody) as caught:
        await restore(world.tenancy, world.iris, newer, io.BytesIO(out.getvalue()), RESTORER)

    assert "1.0.0" in str(caught.value) and "1.1.0" in str(caught.value)
    assert await stores_state(world) == before, "no database, bucket or record created"
