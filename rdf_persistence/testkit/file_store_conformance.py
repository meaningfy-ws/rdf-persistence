"""The ``FileStore`` conformance suite: one set of cases, run against the fake and against Garage.

Each case takes a file store and the name of a fresh bucket. A divergence between the fake and
Garage is a bug in the fake. Run a case with ``run_case``, which creates the bucket and deletes it
(and any ``<bucket>-*`` the case made) afterwards.
"""

import uuid
from collections.abc import Awaitable, Callable

import pytest

from rdf_persistence.domain.exceptions import Conflict, NotFound, TenantGone
from rdf_persistence.services.files import FileStore

KEY = "blob"
AWKWARD_KEY = "folder/ä b+c.bin"
BINARY = b"\x00\xff bytes \r\n"

Case = Callable[[FileStore, str], Awaitable[None]]


async def blob_comes_back_byte_for_byte(files: FileStore, bucket: str) -> None:
    await files.put(bucket, KEY, BINARY)
    assert await files.get(bucket, KEY) == BINARY


async def empty_blob_round_trips(files: FileStore, bucket: str) -> None:
    await files.put(bucket, KEY, b"")
    assert await files.get(bucket, KEY) == b""


async def key_with_special_characters_round_trips(files: FileStore, bucket: str) -> None:
    await files.put(bucket, AWKWARD_KEY, BINARY)
    assert await files.get(bucket, AWKWARD_KEY) == BINARY


async def put_replaces_the_blob(files: FileStore, bucket: str) -> None:
    await files.put(bucket, KEY, b"old")
    await files.put(bucket, KEY, b"new")
    assert await files.get(bucket, KEY) == b"new"


async def missing_blob_is_not_found(files: FileStore, bucket: str) -> None:
    with pytest.raises(NotFound):
        await files.get(bucket, KEY)


async def deleted_blob_is_gone_and_deleting_it_again_is_harmless(
    files: FileStore, bucket: str
) -> None:
    await files.put(bucket, KEY, b"x")
    await files.delete(bucket, KEY)
    await files.delete(bucket, KEY)
    with pytest.raises(NotFound):
        await files.get(bucket, KEY)


async def existing_bucket_is_conflict(files: FileStore, bucket: str) -> None:
    with pytest.raises(Conflict):
        await files.create_bucket(bucket)


async def buckets_are_listed_by_prefix_in_name_order(files: FileStore, bucket: str) -> None:
    second, first = f"{bucket}-b", f"{bucket}-a"
    await files.create_bucket(second)
    await files.create_bucket(first)
    assert await files.list_buckets(f"{bucket}-") == [first, second]
    assert await files.list_buckets(bucket) == [bucket, first, second], "the prefix is a prefix"


async def deleting_a_bucket_removes_its_blobs_and_the_bucket(files: FileStore, bucket: str) -> None:
    for key in (KEY, AWKWARD_KEY):
        await files.put(bucket, key, b"x")
    await files.delete_bucket(bucket)
    assert await files.list_buckets(bucket) == [], "the bucket is gone"
    with pytest.raises(TenantGone):
        await files.get(bucket, KEY)


async def deleting_a_missing_bucket_is_not_found(files: FileStore, bucket: str) -> None:
    with pytest.raises(NotFound):
        await files.delete_bucket(f"{bucket}-missing")


async def object_operations_on_a_missing_bucket_are_tenant_gone_and_create_nothing(
    files: FileStore, bucket: str
) -> None:
    missing = f"{bucket}-missing"
    with pytest.raises(TenantGone):
        await files.put(missing, KEY, b"x")
    with pytest.raises(TenantGone):
        await files.get(missing, KEY)
    with pytest.raises(TenantGone):
        await files.delete(missing, KEY)
    assert await files.list_buckets(missing) == [], "no bucket was created"


CASES: tuple[Case, ...] = (
    blob_comes_back_byte_for_byte,
    empty_blob_round_trips,
    key_with_special_characters_round_trips,
    put_replaces_the_blob,
    missing_blob_is_not_found,
    deleted_blob_is_gone_and_deleting_it_again_is_harmless,
    existing_bucket_is_conflict,
    buckets_are_listed_by_prefix_in_name_order,
    deleting_a_bucket_removes_its_blobs_and_the_bucket,
    deleting_a_missing_bucket_is_not_found,
    object_operations_on_a_missing_bucket_are_tenant_gone_and_create_nothing,
)


async def run_case(case: Case, files: FileStore) -> None:
    """Run one case in a fresh bucket, then delete it and every ``<bucket>-*`` the case left."""
    bucket = f"conf-{uuid.uuid4().hex}"
    await files.create_bucket(bucket)
    try:
        await case(files, bucket)
    finally:
        for name in await files.list_buckets(bucket):
            await files.delete_bucket(name)
