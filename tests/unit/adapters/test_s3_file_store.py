"""S3FileStore's calls and error mapping, against botocore's Stubber (no network)."""

from io import BytesIO

import boto3
import pytest
from botocore.config import Config
from botocore.exceptions import ConnectTimeoutError, EndpointConnectionError
from botocore.response import StreamingBody
from botocore.stub import Stubber

from rdf_persistence.adapters.s3 import S3FileStore
from rdf_persistence.domain.exceptions import (
    Conflict,
    NotFound,
    StoreUnavailable,
    TenantGone,
)
from rdf_persistence.testkit import no_network  # noqa: F401  (fixture)

REGION = "garage"
BUCKET, KEY, URL = "b", "k", "http://s3.test"


@pytest.fixture
def s3(no_network):  # noqa: F811
    client = boto3.client(
        "s3",
        endpoint_url=URL,
        aws_access_key_id="id",
        aws_secret_access_key="secret",
        region_name=REGION,
        config=Config(retries={"max_attempts": 1}),
    )
    with Stubber(client) as stubber:
        yield S3FileStore(URL, "id", "secret", REGION, client=client), stubber


CALLS = {
    "put": ("put_object", lambda files: files.put(BUCKET, KEY, b"x")),
    "get": ("get_object", lambda files: files.get(BUCKET, KEY)),
    "delete": ("delete_object", lambda files: files.delete(BUCKET, KEY)),
    "create_bucket": ("create_bucket", lambda files: files.create_bucket(BUCKET)),
    "list_buckets": ("list_buckets", lambda files: files.list_buckets("")),
}


@pytest.mark.parametrize(
    ("operation", "code", "expected"),
    [
        ("put", "NoSuchBucket", TenantGone),
        ("get", "NoSuchBucket", TenantGone),
        ("delete", "NoSuchBucket", TenantGone),
        ("get", "NoSuchKey", NotFound),
        ("create_bucket", "BucketAlreadyOwnedByYou", Conflict),
        ("create_bucket", "BucketAlreadyExists", Conflict),
        ("put", "InternalError", StoreUnavailable),
        ("get", "AccessDenied", StoreUnavailable),
        ("list_buckets", "InternalError", StoreUnavailable),
    ],
)
async def test_an_s3_error_code_maps_to_the_toolkit_error(s3, operation, code, expected):
    files, stubber = s3
    api_call, call = CALLS[operation]
    stubber.add_client_error(api_call, service_error_code=code)
    with pytest.raises(expected):
        await call(files)


async def test_a_server_error_status_is_store_unavailable_whatever_its_code(s3):
    files, stubber = s3
    stubber.add_client_error("get_object", service_error_code="NoSuchKey", http_status_code=503)
    with pytest.raises(StoreUnavailable):
        await files.get(BUCKET, KEY)


@pytest.mark.parametrize(
    "error",
    [EndpointConnectionError(endpoint_url=URL), ConnectTimeoutError(endpoint_url=URL)],
    ids=type,
)
async def test_a_connection_failure_is_store_unavailable(s3, error):
    files, _ = s3

    def fail(**_):
        raise error

    files._client.meta.events.register("before-call.s3.ListBuckets", fail)
    with pytest.raises(StoreUnavailable):
        await files.list_buckets("")


async def test_get_returns_the_body_bytes(s3):
    files, stubber = s3
    stubber.add_response(
        "get_object", {"Body": StreamingBody(BytesIO(b"abc"), 3)}, {"Bucket": BUCKET, "Key": KEY}
    )
    assert await files.get(BUCKET, KEY) == b"abc"


async def test_a_bucket_is_created_with_the_regions_location_constraint(s3):
    files, stubber = s3
    stubber.add_response(
        "create_bucket",
        {},
        {"Bucket": BUCKET, "CreateBucketConfiguration": {"LocationConstraint": REGION}},
    )
    await files.create_bucket(BUCKET)
    stubber.assert_no_pending_responses()


async def test_buckets_are_listed_by_prefix_in_name_order(s3):
    files, stubber = s3
    stubber.add_response(
        "list_buckets", {"Buckets": [{"Name": n} for n in ("p-2", "other", "p-1")]}
    )
    assert await files.list_buckets("p-") == ["p-1", "p-2"]


async def test_deleting_a_bucket_deletes_every_page_of_its_blobs_then_the_bucket(s3):
    files, stubber = s3
    page = {"Bucket": BUCKET}
    stubber.add_response(
        "list_objects_v2",
        {"Contents": [{"Key": "a"}], "IsTruncated": True, "NextContinuationToken": "t"},
        page,
    )
    stubber.add_response(
        "delete_objects", {}, {"Bucket": BUCKET, "Delete": {"Objects": [{"Key": "a"}]}}
    )
    stubber.add_response(
        "list_objects_v2", {"Contents": [{"Key": "b"}]}, {**page, "ContinuationToken": "t"}
    )
    stubber.add_response(
        "delete_objects", {}, {"Bucket": BUCKET, "Delete": {"Objects": [{"Key": "b"}]}}
    )
    stubber.add_response("delete_bucket", {}, page)
    await files.delete_bucket(BUCKET)
    stubber.assert_no_pending_responses()


async def test_deleting_a_missing_bucket_is_not_found(s3):
    files, stubber = s3
    stubber.add_client_error("list_objects_v2", service_error_code="NoSuchBucket")
    with pytest.raises(NotFound):
        await files.delete_bucket(BUCKET)
