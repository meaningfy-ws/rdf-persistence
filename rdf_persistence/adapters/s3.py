"""The S3 implementation of the ``FileStore`` port (boto3, path-style addressing, for Garage and S3).

boto3 blocks, so every call runs in a worker thread. A bucket is never created implicitly: a
``put`` into a missing bucket raises ``TenantGone``.
"""

import logging
from collections.abc import Callable
from functools import partial
from http import HTTPStatus
from typing import Any

import boto3
from anyio import to_thread
from botocore.client import BaseClient
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError, ParamValidationError

from rdf_persistence.domain.exceptions import (
    Conflict,
    NotFound,
    PersistenceError,
    StoreUnavailable,
    TenantGone,
)
from rdf_persistence.domain.generated.rp_files import BlobEntry

NO_SUCH_BUCKET, NO_SUCH_KEY = "NoSuchBucket", "NoSuchKey"
BUCKET_EXISTS = frozenset({"BucketAlreadyOwnedByYou", "BucketAlreadyExists"})
DEFAULT_REGION = "us-east-1"  # the one region whose create_bucket takes no location constraint
DELETE_BATCH = 1000  # DeleteObjects takes at most this many keys
CONNECT_TIMEOUT_SECONDS, READ_TIMEOUT_SECONDS, MAX_ATTEMPTS = 5, 30, 3
DOT_SEGMENTS = frozenset({".", ".."})
DELETE_CHARACTER = "\x7f"

log = logging.getLogger(__name__)


def _error_code(error: ClientError) -> str:
    return str(error.response.get("Error", {}).get("Code", ""))


def _status(error: ClientError) -> int:
    return int(error.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0))


def _translate(error: ClientError, *, bucket_missing: type[PersistenceError]) -> PersistenceError:
    """Map an S3 error to the toolkit's; ``bucket_missing`` is what a ``NoSuchBucket`` means here."""
    code = _error_code(error)
    if _status(error) >= HTTPStatus.INTERNAL_SERVER_ERROR:
        return StoreUnavailable(f"The object store answered {_status(error)}")
    if code == NO_SUCH_BUCKET:
        return bucket_missing("no such bucket")
    if code == NO_SUCH_KEY:
        return NotFound("no such blob")
    if code in BUCKET_EXISTS:
        return Conflict("the bucket exists")
    log.debug("The object store refused a request: %s", error)
    return StoreUnavailable(f"The object store answered {code or _status(error)}")


def _checked_key(key: str) -> str:
    """``key`` if it is a key the toolkit stores: no ``.`` or ``..`` segment (a path to climb out of a prefix), no control characters."""
    if (
        not key
        or not DOT_SEGMENTS.isdisjoint(key.split("/"))
        or any(ord(c) < ord(" ") or c == DELETE_CHARACTER for c in key)
    ):
        raise ValueError("the key is empty, has a '.' or '..' segment or has a control character")
    return key


class S3FileStore:
    """A ``FileStore`` over an S3-compatible endpoint."""

    def __init__(
        self,
        endpoint: str,
        access_key_id: str,
        secret_access_key: str,
        region: str,
        *,
        client: BaseClient | None = None,
    ) -> None:
        """Connect lazily to ``endpoint``; ``client`` replaces the boto3 client (for tests)."""
        self._region = region
        self._client = client or boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=region,
            config=Config(
                s3={"addressing_style": "path"},
                connect_timeout=CONNECT_TIMEOUT_SECONDS,
                read_timeout=READ_TIMEOUT_SECONDS,
                retries={"max_attempts": MAX_ATTEMPTS},
            ),
        )

    async def _run(
        self,
        call: Callable[..., Any],
        *,
        bucket_missing: type[PersistenceError] = TenantGone,
        **arguments: Any,
    ) -> Any:
        try:
            return await to_thread.run_sync(partial(call, **arguments))
        except ClientError as error:
            raise _translate(error, bucket_missing=bucket_missing) from error
        except ParamValidationError as error:
            raise ValueError("the bucket or key is not one the object store accepts") from error
        except BotoCoreError as error:
            raise StoreUnavailable(f"The object store is unreachable: {error}") from error

    async def create_bucket(self, name: str) -> None:
        extra: dict[str, Any] = {}
        if self._region != DEFAULT_REGION:
            extra["CreateBucketConfiguration"] = {"LocationConstraint": self._region}
        await self._run(self._client.create_bucket, Bucket=name, **extra)

    async def delete_bucket(self, name: str) -> None:
        # S3 refuses to delete a bucket that holds blobs, so empty it page by page first.
        token: str | None = None
        while True:
            page = await self._run(
                self._client.list_objects_v2,
                bucket_missing=NotFound,
                Bucket=name,
                **({"ContinuationToken": token} if token else {}),
            )
            keys = [{"Key": blob["Key"]} for blob in page.get("Contents", [])]
            for start in range(0, len(keys), DELETE_BATCH):
                result = await self._run(
                    self._client.delete_objects,
                    bucket_missing=NotFound,
                    Bucket=name,
                    Delete={"Objects": keys[start : start + DELETE_BATCH]},
                )
                # DeleteObjects answers 200 even when some keys failed; report them, not BucketNotEmpty.
                if failed := result.get("Errors"):
                    listed = ", ".join(f"{e.get('Key')}: {e.get('Code')}" for e in failed)
                    raise StoreUnavailable(f"could not delete blobs of {name}: {listed}")
            token = page.get("NextContinuationToken")
            if not page.get("IsTruncated"):
                break
        await self._run(self._client.delete_bucket, bucket_missing=NotFound, Bucket=name)

    async def list_buckets(self, prefix: str) -> list[str]:
        listing = await self._run(self._client.list_buckets)
        return sorted(b["Name"] for b in listing["Buckets"] if b["Name"].startswith(prefix))

    async def list_blobs(self, bucket: str) -> list[BlobEntry]:
        entries: list[BlobEntry] = []
        token: str | None = None
        while True:
            extra: dict[str, Any] = {"ContinuationToken": token} if token else {}
            page = await self._run(self._client.list_objects_v2, Bucket=bucket, **extra)
            entries += [
                BlobEntry(file_key=blob["Key"], modified=blob["LastModified"])
                for blob in page.get("Contents", [])
            ]
            token = page.get("NextContinuationToken")
            if not page.get("IsTruncated"):
                return entries

    async def put(self, bucket: str, key: str, data: bytes) -> None:
        await self._run(self._client.put_object, Bucket=bucket, Key=_checked_key(key), Body=data)

    async def get(self, bucket: str, key: str) -> bytes:
        checked = _checked_key(key)

        def read() -> bytes:
            return bytes(self._client.get_object(Bucket=bucket, Key=checked)["Body"].read())

        data: bytes = await self._run(read)
        return data

    async def delete(self, bucket: str, key: str) -> None:
        await self._run(self._client.delete_object, Bucket=bucket, Key=_checked_key(key))
