"""Removing a file aggregate with its blobs, over the fakes (live-tenant-sweep PD-10, task 4.1)."""

import logging
from datetime import timedelta

import pytest

from rdf_persistence.domain.exceptions import Conflict, NotFound, StoreUnavailable
from rdf_persistence.domain.iris import Iris
from rdf_persistence.services.file_removal import remove_with_files
from tests.toy import SETTINGS
from tests.unit.services.test_tenant_sweep import CREATOR, book, make_world


@pytest.fixture
async def world():
    made = await make_world(Iris(SETTINGS), SETTINGS)
    made.scan, made.other = book(made, 2, "scans"), book(made, 3, "scans")
    made.version = await made.commit(made.scan, keys=["k1"])
    await made.blob("k1", timedelta())
    made.remove = lambda iri, version: remove_with_files(
        made.tenancy, made.files, made.tenant, CREATOR, iri, version
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
