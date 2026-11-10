"""S3FileStore's calls and error mapping, against botocore's Stubber (no network)."""

from datetime import UTC, datetime
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
from rdf_persistence.domain.generated.rp_files import BlobEntry
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


async def test_a_blob_the_store_failed_to_delete_stops_the_bucket_delete(s3):
    files, stubber = s3
    page = {"Bucket": BUCKET}
    stubber.add_response("list_objects_v2", {"Contents": [{"Key": "a"}]}, page)
    stubber.add_response(
        "delete_objects",
        {"Errors": [{"Key": "a", "Code": "AccessDenied", "Message": "no"}]},
        {"Bucket": BUCKET, "Delete": {"Objects": [{"Key": "a"}]}},
    )
    with pytest.raises(StoreUnavailable, match="a: AccessDenied"):
        await files.delete_bucket(BUCKET)


async def test_deleting_a_missing_bucket_is_not_found(s3):
    files, stubber = s3
    stubber.add_client_error("list_objects_v2", service_error_code="NoSuchBucket")
    with pytest.raises(NotFound):
        await files.delete_bucket(BUCKET)


# --- input the caller got wrong is not an outage (PD-28a) ------------------------------------------

BAD_KEYS = [
    "a/../b",
    "..",
    "../x",
    "a/..",
    "a/./b",
    "./a",
    "a/.",
    ".",
    "a\x00b",
    "a\nb",
    "a\x7fb",
    "",
]
ORDINARY_KEYS = ["a..b", "..x", "x/..y/z", "folder/ä b+c.bin"]


@pytest.mark.parametrize("key", BAD_KEYS, ids=repr)
@pytest.mark.parametrize("operation", ["put", "get", "delete"])
async def test_a_key_that_climbs_or_holds_a_control_character_is_refused_before_any_request(
    s3, operation, key
):
    files, stubber = s3
    calls = {
        "put": lambda: files.put(BUCKET, key, b"x"),
        "get": lambda: files.get(BUCKET, key),
        "delete": lambda: files.delete(BUCKET, key),
    }
    with pytest.raises(ValueError, match="key"):
        await calls[operation]()
    stubber.assert_no_pending_responses()


@pytest.mark.parametrize("key", ORDINARY_KEYS)
async def test_a_key_with_dots_inside_a_segment_is_a_key(s3, key):
    files, stubber = s3
    stubber.add_response("put_object", {}, {"Bucket": BUCKET, "Key": key, "Body": b"x"})
    await files.put(BUCKET, key, b"x")


@pytest.mark.parametrize("bucket", ["", "a/b", "Not Valid"])
async def test_a_bucket_name_boto_refuses_is_the_callers_error_not_an_outage(no_network, bucket):  # noqa: F811
    files = S3FileStore(
        URL, "id", "secret", REGION
    )  # a real client: the stubber looks before boto does
    with pytest.raises(ValueError, match="bucket"):
        await files.put(bucket, KEY, b"x")


def test_the_timeouts_are_five_seconds_to_connect_and_thirty_to_read():
    config = S3FileStore("http://s3.test", "id", "secret", REGION)._client.meta.config
    assert (config.connect_timeout, config.read_timeout) == (5, 30)


async def test_list_blobs_follows_every_page_and_keeps_the_modified_time(s3):
    files, stubber = s3
    first, second = datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 2, tzinfo=UTC)
    stubber.add_response(
        "list_objects_v2",
        {
            "IsTruncated": True,
            "NextContinuationToken": "t",
            "Contents": [{"Key": "a", "LastModified": first}],
        },
        {"Bucket": BUCKET},
    )
    stubber.add_response(
        "list_objects_v2",
        {"IsTruncated": False, "Contents": [{"Key": "b", "LastModified": second}]},
        {"Bucket": BUCKET, "ContinuationToken": "t"},
    )
    assert await files.list_blobs(BUCKET) == [
        BlobEntry(file_key="a", modified=first),
        BlobEntry(file_key="b", modified=second),
    ]
    stubber.assert_no_pending_responses()


async def test_a_truncated_page_without_a_token_ends_the_listing(s3):
    files, stubber = s3
    first = datetime(2026, 1, 1, tzinfo=UTC)
    page = {"IsTruncated": True, "Contents": [{"Key": "a", "LastModified": first}]}
    stubber.add_response("list_objects_v2", page, {"Bucket": BUCKET})
    assert await files.list_blobs(BUCKET) == [BlobEntry(file_key="a", modified=first)]
    stubber.assert_no_pending_responses()


async def test_list_blobs_of_an_empty_bucket_is_empty(s3):
    files, stubber = s3
    stubber.add_response("list_objects_v2", {"IsTruncated": False}, {"Bucket": BUCKET})
    assert await files.list_blobs(BUCKET) == []


async def test_list_blobs_of_a_missing_bucket_is_tenant_gone(s3):
    files, stubber = s3
    stubber.add_client_error("list_objects_v2", service_error_code="NoSuchBucket")
    with pytest.raises(TenantGone):
        await files.list_blobs(BUCKET)
