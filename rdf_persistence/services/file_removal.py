"""Removing a file aggregate together with the blobs only it names (live-tenant-sweep PD-10)."""

import logging

from rdf_persistence.domain.exceptions import PersistenceError
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.files import FileStore
from rdf_persistence.services.tenancy import Tenancy

log = logging.getLogger(__name__)


async def remove_with_files(
    tenancy: Tenancy, files: FileStore, tenant: str, principal: Principal, iri: str, if_version: str
) -> None:
    """Remove the aggregate ``iri`` at ``if_version``, then delete from the tenant's bucket the blobs
    it named in ``rp:fileKey`` that no other graph names. A blob that cannot be deleted is logged and
    left for the live-tenant sweep.

    Raises:
        NotFound: The aggregate has no graph, or the tenant has no access record.
        Conflict: The aggregate is not at ``if_version``; nothing changed.
    """
    access, _ = await tenancy.get(tenant)
    async with tenancy.tenant_session(tenant, principal) as session:
        graph, _, _ = await session.get_graph(iri)
        keys = {str(k) for k in graph.objects(predicate=v.FILE_KEY)}
        await session.remove(iri, if_version)  # refuses a stale version with nothing changed
        orphans = keys - await session.named_file_keys(keys)
    for key in sorted(orphans):
        await _delete_blob(files, access.database_name, tenant, key)


async def _delete_blob(files: FileStore, bucket: str, tenant: str, key: str) -> None:
    try:
        await files.delete(bucket, key)
    except (PersistenceError, ValueError):
        log.warning(
            "a blob could not be deleted; the live-tenant sweep removes it later",
            extra={"step": "remove-blob-failed", "tenant": tenant, "resource": key},
            exc_info=True,
        )
    else:
        log.info(
            "removed the blob of a removed aggregate",
            extra={"step": "remove-blob", "tenant": tenant, "resource": key},
        )
