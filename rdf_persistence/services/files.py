"""The file-store port (PD-1): adapters implement it, tenancy and the file services use it.

Every method is async. A bucket is one tenant's file space, named as in ``domain.iris``; a blob is
kept byte for byte under a key the caller makes up (a random one, per the file-store spec).
"""

from typing import Protocol


class FileStore(Protocol):
    """An object store with buckets, over S3 or in memory."""

    async def create_bucket(self, name: str) -> None:
        """Create an empty bucket. Raises ``Conflict`` if it exists."""
        ...

    async def delete_bucket(self, name: str) -> None:
        """Delete a bucket and every blob in it. Raises ``NotFound`` if it does not exist."""
        ...

    async def list_buckets(self, prefix: str) -> list[str]:
        """The names of the buckets that start with ``prefix``, in name order."""
        ...

    async def put(self, bucket: str, key: str, data: bytes) -> None:
        """Store ``data`` under ``key``; never creates the bucket.

        Raises:
            TenantGone: The bucket does not exist.
            StoreUnavailable: The object store is unreachable or failed.
        """
        ...

    async def get(self, bucket: str, key: str) -> bytes:
        """The exact bytes stored under ``key``.

        Raises:
            TenantGone: The bucket does not exist.
            NotFound: The bucket holds no blob under ``key``.
        """
        ...

    async def delete(self, bucket: str, key: str) -> None:
        """Delete the blob; deleting a blob that is not there succeeds. Raises ``TenantGone`` as ``get`` does."""
        ...
