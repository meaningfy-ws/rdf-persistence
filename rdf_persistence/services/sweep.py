"""The start-up sweep: finish interrupted tenant work before serving (PD-6a, error matrix).

It finishes the deletion of every ``deleting`` tenant, then drops each database and bucket named
``{prefix}-t-…`` that no access record names (by the ``database_name`` the record stores): what a crash
during creation leaves. Names without that prefix are never touched. It drops nothing when the system
database had to be created or holds no access record while tenant resources exist: the records are
missing, which does not make the tenants orphans (PD-8c). Run it once, before the service takes
requests: a tenant being created at that moment has a database and no record yet.
"""

import logging

from rdf_persistence.domain.generated.rp_tenancy import TenantState
from rdf_persistence.domain.generated.service.rp_service import ServiceSettings
from rdf_persistence.domain.iris import tenant_name_prefix
from rdf_persistence.services.files import FileStore
from rdf_persistence.services.store import Store
from rdf_persistence.services.tenancy import Tenancy

log = logging.getLogger(__name__)


async def sweep(
    tenancy: Tenancy, store: Store, files: FileStore, settings: ServiceSettings
) -> None:
    """Finish the deletions that stopped and drop the databases and buckets no tenant owns."""
    created = await tenancy.ensure_system_database()
    records = await tenancy.tenants()
    prefix = tenant_name_prefix(settings.prefix)
    if created or not records:
        present = await _tenant_resources(store, files, prefix)
        if present:
            log.warning(
                "sweep skipped: no access records on file while tenant resources exist; nothing dropped",
                extra={"step": "skip-sweep", "system_created": created, "resources": present},
            )
            return
    for tenant in records:
        if tenant.state == TenantState.DELETING:
            log.info(
                "finishing the interrupted deletion of a tenant",
                extra={"step": "finish-deletion", "tenant": tenant.id},
            )
            await tenancy.finish_deletion(tenant.id)
    await _drop_orphans(store, files, prefix, await tenancy.database_names())


async def _tenant_resources(store: Store, files: FileStore, prefix: str) -> list[str]:
    """The databases and buckets named ``{prefix}-t-…``."""
    databases = [n for n in await store.list_datasets() if n.startswith(prefix)]
    return sorted([*databases, *await files.list_buckets(prefix)])


async def _drop_orphans(store: Store, files: FileStore, prefix: str, named: set[str]) -> None:
    for database in _orphans(await store.list_datasets(), prefix, named):
        log.info(
            "dropping an orphan database",
            extra={"step": "drop-orphan-database", "resource": database},
        )
        await store.drop_dataset(database)
    for bucket in _orphans(await files.list_buckets(prefix), prefix, named):
        log.info(
            "dropping an orphan bucket", extra={"step": "drop-orphan-bucket", "resource": bucket}
        )
        await files.delete_bucket(bucket)


def _orphans(names: list[str], prefix: str, named: set[str]) -> list[str]:
    """The tenant-prefixed names that no access record names."""
    return [name for name in names if name.startswith(prefix) and name not in named]
