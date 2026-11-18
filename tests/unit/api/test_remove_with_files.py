"""Removing a file aggregate with its blobs, over the fakes (live-tenant-sweep PD-10, task 4.1)."""

import logging
from datetime import timedelta
from uuid import UUID

import pytest
from rdflib import RDF, Literal, URIRef

from rdf_persistence.api.services.file_removal import remove_with_files
from rdf_persistence.core.domain.exceptions import Conflict, NotFound, StoreUnavailable
from rdf_persistence.iris.services.iris import Iris
from rdf_persistence.schema.services import vocabulary as v
from rdf_persistence.tenancy.services.tenancy import Tenancy
from rdf_persistence.testkit import FakeFileStore, FakeStore
from tests.fixtures.library.generated.library import Library
from tests.fixtures.library.generated.library_access import LibraryAccess
from tests.logs import attributes
from tests.toy import SETTINGS, library_slots, toy_mapper
from tests.unit.tenancy.test_session_activity import stored_graph
from tests.unit.tenancy.test_tenant_sweep import CREATOR, FILE_KEY, book, make_world


@pytest.fixture
async def world():
    made = await make_world(Iris(SETTINGS), SETTINGS)
    made.scan, made.other = book(made, 2, "scans"), book(made, 3, "scans")
    made.version = await made.commit(made.scan, keys=["k1"])
    await made.blob("k1", timedelta())
    made.remove = lambda iri, version: remove_with_files(
        made.tenancy, made.files, made.tenant, CREATOR, iri, version, toy_mapper()
    )
    made.blobs = lambda: _keys(made)
    return made


async def _keys(world) -> list[str]:
    return [b.file_key for b in await world.files.list_blobs(world.database)]


async def test_the_blob_goes_with_its_aggregate(world):
    await world.remove(world.scan, world.version)
    async with world.session() as s:
        with pytest.raises(NotFound):
            await s.get_graph(world.scan)
    assert await world.blobs() == [], "the blob is removed with its aggregate"


async def test_the_removal_is_recorded_as_a_delete_file(world):  # TC-94
    await world.remove(world.scan, world.version)

    graph = await stored_graph(
        world.store, URIRef(world.iris.provenance(world.tenant)), world.database
    )
    [deletion] = graph.subjects(RDF.type, v.DELETE_FILE)
    assert set(graph.objects(deletion, RDF.type)) == {v.DELETE_FILE, v.REMOVE, v.ACTIVITY}, (
        "the removal is recorded as a file deletion"
    )
    assert list(graph.objects(deletion, v.USED)) == [URIRef(world.scan)], "it used the file"
    [invalidation] = graph.objects(deletion, v.HAS_INVALIDATION)
    assert list(graph.objects(invalidation, v.ENTITY)) == [URIRef(world.scan)], "and removed it"
    assert list(graph.objects(deletion, v.HAS_GENERATION)) == [], "and generated nothing"


async def test_without_a_mapper_the_removal_is_a_plain_remove(world):  # D-11 g
    await remove_with_files(
        world.tenancy, world.files, world.tenant, CREATOR, world.scan, world.version, None
    )

    graph = await stored_graph(
        world.store, URIRef(world.iris.provenance(world.tenant)), world.database
    )
    assert list(graph.subjects(RDF.type, v.DELETE_FILE)) == [], "no file deletion"
    [removal] = graph.subjects(RDF.type, v.REMOVE)
    assert list(graph.objects(removal, v.USED)) == [], "the standard activity names no resource"
    assert await world.blobs() == [], "the blob still goes"


async def test_a_blob_another_aggregate_names_stays(world):
    await world.commit(world.other, keys=["k1"])
    await world.remove(world.scan, world.version)
    assert await world.blobs() == ["k1"], "the blob another aggregate names stays"


async def test_a_failing_blob_delete_still_removes_the_aggregate_and_logs(world, caplog):
    world.files.on("delete", StoreUnavailable("down"))
    with caplog.at_level(logging.WARNING):
        await world.remove(world.scan, world.version)
    async with world.session() as s:
        with pytest.raises(NotFound):
            await s.get_graph(world.scan)
    assert await world.blobs() == ["k1"], "the blob stays when its delete fails"
    assert [attributes(r).get("rp.step") for r in caplog.records] == ["remove-blob-failed"], (
        "the failed delete is logged"
    )


async def test_a_deleted_blob_is_logged(world, caplog):
    with caplog.at_level(logging.INFO):
        await world.remove(world.scan, world.version)
    assert [attributes(r)["rp.step"] for r in caplog.records if "rp.step" in attributes(r)] == [
        "remove-blob"
    ], "the deleted blob is logged"


async def test_a_stale_version_changes_nothing(world):
    with pytest.raises(Conflict):
        await world.remove(world.scan, "stale")
    async with world.session() as s:
        assert (await s.get_graph(world.scan))[2] == world.version, (
            "the stale version leaves the aggregate stored"
        )
    assert await world.blobs() == ["k1"], "the stale version leaves the blob"


async def test_a_missing_aggregate_is_not_found(world):
    with pytest.raises(NotFound):
        await world.remove(world.other, world.version)


async def test_tc27_a_tenant_on_another_store_is_removed_there_with_its_blobs():
    d, a, files = FakeStore(), FakeStore(), FakeFileStore()
    iris = Iris(SETTINGS)
    tenancy = Tenancy(
        d,
        files,
        SETTINGS,
        mapper=toy_mapper(),
        root_class=Library,
        access_class=LibraryAccess,
        iris=iris,
        stores={"client-a": a},
    )
    await tenancy.ensure_system_database()
    tenant = (await tenancy.create("Ghent", library_slots(), CREATOR, store="client-a")).id
    scan = f"{tenant}/scans/{UUID(int=2)}"
    async with tenancy.tenant_session(tenant, CREATOR) as session:
        version = await session.add_graph(scan, [(URIRef(scan), FILE_KEY, Literal("k1"))])
    bucket = tenancy.database_of(tenant)
    await files.put(bucket, "k1", b"bytes")
    updates_on_d = len(d.sent("update"))
    await remove_with_files(tenancy, files, tenant, CREATOR, scan, version, toy_mapper())
    async with tenancy.tenant_session(tenant, CREATOR) as session:
        with pytest.raises(NotFound):
            await session.get_graph(scan)
    assert [b.file_key for b in await files.list_blobs(bucket)] == [], "its blob is deleted"
    assert len(d.sent("update")) == updates_on_d, "nothing was written on D"


async def test_an_aggregate_without_a_file_key_deletes_nothing(world):
    version = await world.commit(world.other)
    await world.remove(world.other, version)
    assert await world.blobs() == ["k1"], "the aggregate without a file key deletes no blob"
