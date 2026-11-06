"""S3FileStore against Garage: the shared conformance suite, the round trip and the put after the tenant is gone."""

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


async def test_a_blob_put_into_a_bucket_is_read_back_exactly(files):
    async def round_trip(files, bucket):
        await files.put(bucket, "k", b"\x00\x01payload")
        assert await files.get(bucket, "k") == b"\x00\x01payload"

    await run_case(round_trip, files)


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
