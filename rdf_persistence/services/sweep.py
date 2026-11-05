"""The start-up sweep: finish interrupted tenant work before serving (PD-6a, error matrix).

It finishes the deletion of every ``deleting`` tenant, then drops each database and bucket named
``{prefix}-t-…`` that no access record names: what a crash during creation leaves. Names without that
prefix are never touched. Run it once, before the service takes requests: a tenant being created at
that moment has a database and no record yet.
"""

import logging

from rdf_persistence.domain.generated.rp_tenancy import TenantState
from rdf_persistence.domain.generated.service.rp_service import ServiceSettings
from rdf_persistence.domain.iris import tenant_name_prefix, tenant_resource_name
from rdf_persistence.services.files import FileStore
from rdf_persistence.services.store import Store
from rdf_persistence.services.tenancy import Tenancy

log = logging.getLogger(__name__)


async def sweep(
    tenancy: Tenancy, store: Store, files: FileStore, settings: ServiceSettings
) -> None:
    """Finish the deletions that stopped and drop the databases and buckets no tenant owns."""
    await tenancy.ensure_system_database()
    for tenant in await tenancy.tenants():
        if tenant.state == TenantState.DELETING.value:
            log.info("finishing the deletion of %s", tenant.id)
            await tenancy.finish_deletion(tenant.id)
    named = {tenant_resource_name(settings.prefix, t.id) for t in await tenancy.tenants()}
    prefix = tenant_name_prefix(settings.prefix)
    for database in _orphans(await store.list_datasets(), prefix, named):
        log.info("dropping the orphan database %s", database)
        await store.drop_dataset(database)
    for bucket in _orphans(await files.list_buckets(prefix), prefix, named):
        log.info("dropping the orphan bucket %s", bucket)
        await files.delete_bucket(bucket)


def _orphans(names: list[str], prefix: str, named: set[str]) -> list[str]:
    """The tenant-prefixed names that no access record names."""
    return [name for name in names if name.startswith(prefix) and name not in named]
