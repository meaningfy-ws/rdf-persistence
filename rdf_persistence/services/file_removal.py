"""Removing a file aggregate together with the blobs only it names (live-tenant-sweep PD-10)."""

import logging

from rdf_persistence.domain.exceptions import PersistenceError
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.generated.rp_files import DeleteFile
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.files import FileStore
from rdf_persistence.services.generated.telemetry.rp_telemetry import LogContext
from rdf_persistence.services.mapper import Mapper
from rdf_persistence.services.provenance import new_activity_id
from rdf_persistence.services.telemetry import log_extra
from rdf_persistence.services.tenancy import Tenancy

log = logging.getLogger(__name__)


async def remove_with_files(
    tenancy: Tenancy,
    files: FileStore,
    tenant: str,
    principal: Principal,
    iri: str,
    if_version: str,
    mapper: Mapper | None = None,
) -> None:
    """Remove the aggregate ``iri`` at ``if_version``, then delete from the tenant's bucket the blobs
    it named in ``rp:fileKey`` that no other graph names. A blob that cannot be deleted is logged and
    left for the live-tenant sweep. The removal's activity is a ``DeleteFile``, built with ``mapper``;
    without one it is the standard ``Remove``.

    Raises:
        NotFound: The aggregate has no graph, or the tenant has no access record.
        Conflict: The aggregate is not at ``if_version``; nothing changed.
    """
    access, _ = await tenancy.get(tenant)
    async with tenancy.tenant_session(tenant, principal) as session:
        graph, _, _ = await session.get_graph(iri)
        keys = {str(k) for k in graph.objects(predicate=v.FILE_KEY)}
        served = None
        if mapper is not None:
            served = mapper.served(DeleteFile(id=new_activity_id(), used_resource=iri))
        # a stale version is refused with nothing changed
        await session.remove(iri, if_version, served=served)
        orphans = keys - await session.named_file_keys(keys)
    for key in sorted(orphans):
        await _delete_blob(files, access.database_name, tenant, key)


async def _delete_blob(files: FileStore, bucket: str, tenant: str, key: str) -> None:
    try:
        await files.delete(bucket, key)
    except (PersistenceError, ValueError):
        log.warning(
            "a blob could not be deleted; the live-tenant sweep removes it later",
            extra=log_extra(LogContext(step="remove-blob-failed", tenant_id=tenant, resource=key)),
            exc_info=True,
        )
    else:
        log.info(
            "removed the blob of a removed aggregate",
            extra=log_extra(LogContext(step="remove-blob", tenant_id=tenant, resource=key)),
        )
