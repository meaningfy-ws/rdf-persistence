"""S3FileStore against Garage: the shared conformance suite, the round trip and the put after the tenant is gone."""

import hashlib
import os

import pytest

from rdf_persistence.adapters.s3 import S3FileStore
from rdf_persistence.domain.exceptions import StoreUnavailable, TenantGone
from rdf_persistence.testkit.file_store_conformance import CASES, run_case


@pytest.fixture
def files(garage) -> S3FileStore:
    return S3FileStore(garage.endpoint, garage.key_id, garage.secret, garage.region)


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.__name__)
async def test_garage_conforms(case, files):
    await run_case(case, files)


MEGABYTES = 8


async def test_a_multi_megabyte_blob_comes_back_with_the_same_digest(files):
    payload = os.urandom(MEGABYTES * 1024 * 1024)

    async def round_trip(files, bucket):
        await files.put(bucket, "big", payload)
        back = await files.get(bucket, "big")
        assert len(back) == len(payload)
        assert hashlib.sha256(back).digest() == hashlib.sha256(payload).digest()

    await run_case(round_trip, files)


async def test_a_key_that_climbs_is_refused_before_it_reaches_the_object_store(files):
    async def climb(files, bucket):
        with pytest.raises(ValueError, match="key"):
            await files.put(bucket, "a/../b", b"x")

    await run_case(climb, files)


async def test_a_put_after_the_bucket_is_deleted_is_tenant_gone_and_creates_no_bucket(files):
    async def put_after_delete(files, bucket):
        await files.delete_bucket(bucket)
        with pytest.raises(TenantGone):
            await files.put(bucket, "k", b"late")
        assert await files.list_buckets(bucket) == [], "the put created no bucket"
        await files.create_bucket(bucket)  # so that run_case has a bucket to clean up

    await run_case(put_after_delete, files)


async def test_an_unreachable_object_store_is_store_unavailable():
    files = S3FileStore("http://127.0.0.1:1", "id", "secret", "garage")
    with pytest.raises(StoreUnavailable):
        await files.list_buckets("")
