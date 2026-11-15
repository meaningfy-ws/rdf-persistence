"""Removing a file aggregate with its blobs, over the fakes (live-tenant-sweep PD-10, task 4.1)."""

import logging
from datetime import timedelta

import pytest
from rdflib import RDF, URIRef

from rdf_persistence.domain.exceptions import Conflict, NotFound, StoreUnavailable
from rdf_persistence.domain.iris import Iris
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.file_removal import remove_with_files
from tests.toy import SETTINGS, toy_mapper
from tests.unit.services.test_session_activity import stored_graph
from tests.unit.services.test_tenant_sweep import CREATOR, book, make_world


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
    assert await world.blobs() == []


async def test_the_removal_is_recorded_as_a_delete_file(world):  # TC-94
    await world.remove(world.scan, world.version)

    graph = await stored_graph(
        world.store, URIRef(world.iris.provenance(world.tenant)), world.database
    )
    [deletion] = graph.subjects(RDF.type, v.DELETE_FILE)
    assert set(graph.objects(deletion, RDF.type)) == {v.DELETE_FILE, v.REMOVE, v.ACTIVITY}
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
    assert await world.blobs() == ["k1"]


async def test_a_failing_blob_delete_still_removes_the_aggregate_and_logs(world, caplog):
    world.files.on("delete", StoreUnavailable("down"))
    with caplog.at_level(logging.WARNING):
        await world.remove(world.scan, world.version)
    async with world.session() as s:
        with pytest.raises(NotFound):
            await s.get_graph(world.scan)
    assert await world.blobs() == ["k1"]
    assert [r.step for r in caplog.records] == ["remove-blob-failed"]


async def test_a_deleted_blob_is_logged(world, caplog):
    with caplog.at_level(logging.INFO):
        await world.remove(world.scan, world.version)
    assert [r.step for r in caplog.records if hasattr(r, "step")] == ["remove-blob"]


async def test_a_stale_version_changes_nothing(world):
    with pytest.raises(Conflict):
        await world.remove(world.scan, "stale")
    async with world.session() as s:
        assert (await s.get_graph(world.scan))[2] == world.version
    assert await world.blobs() == ["k1"]


async def test_a_missing_aggregate_is_not_found(world):
    with pytest.raises(NotFound):
        await world.remove(world.other, world.version)


async def test_an_aggregate_without_a_file_key_deletes_nothing(world):
    version = await world.commit(world.other)
    await world.remove(world.other, version)
    assert await world.blobs() == ["k1"]
