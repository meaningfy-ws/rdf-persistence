"""The start-up sweep: finish interrupted tenant work before serving (PD-6a, error matrix; tenant-stores PD-6).

Tenants live on the stores their access records name. The sweep first reads the records, then refuses to
go on when a record names a store that is not wired (``StoreNotWired``), then lists the databases of every
wired store (a ``StoreUnavailable`` stops it here, before anything is finished or dropped). A record whose
database is absent from its own store but present on another is logged at ERROR (``misplaced-tenant``) and
left alone.

It then finishes the deletion of every ``deleting`` tenant, and drops each database and bucket named
``{prefix}-t-…`` that no access record names (by the ``database_name`` the record stores), on whichever
store holds it: what a crash during creation leaves. Names without that prefix are never touched. It
drops nothing when the system database had to be created or holds no access record while tenant
resources exist: the records are missing, which does not make the tenants orphans (PD-8c). Run it once,
before the service takes requests: a tenant being created at that moment has a database and no record yet.
"""

import logging
from contextlib import suppress

from rdf_persistence.core.domain.exceptions import NotFound, StoreNotWired
from rdf_persistence.core.domain.generated.rp_tenancy import TenantAccess, TenantState
from rdf_persistence.core.services.generated.rp_core_services import LogContext
from rdf_persistence.core.services.telemetry import log_extra, traced
from rdf_persistence.files.services.files import FileStore
from rdf_persistence.iris.domain.layout import tenant_name_prefix
from rdf_persistence.iris.services.generated.rp_iris_services import ServiceSettings
from rdf_persistence.persistence.services.store import Store
from rdf_persistence.tenancy.services.tenancy import Tenancy, store_name_in

log = logging.getLogger(__name__)


async def sweep(
    tenancy: Tenancy, store: Store, files: FileStore, settings: ServiceSettings
) -> None:
    """Finish the deletions that stopped and drop the databases and buckets no tenant owns.

    The tenants are routed to their stores through ``tenancy``, whose wired stores are the ones swept
    (``tenancy.stores()``). ``store`` is unused, kept for compatibility.

    Raises:
        StoreNotWired: Records name stores that are not wired (all named, sorted); nothing was changed.
        StoreUnavailable: A wired store cannot list its databases; nothing was changed.
    """
    with traced("rp.sweep", LogContext(step="sweep")):
        await _sweep(tenancy, files, settings)


async def _sweep(tenancy: Tenancy, files: FileStore, settings: ServiceSettings) -> None:
    created = await tenancy.ensure_system_database()
    # one query for every record (PD-13), by tenant IRI in order
    found = {tenancy.tenant_of(record): record for record in await tenancy.access_records()}
    records = dict(sorted(found.items()))
    stores = tenancy.stores()
    _refuse_unwired(records, stores)
    listed = {name: await wired.list_datasets() for name, wired in stores.items()}
    _report_misplaced(records, listed)
    prefix = tenant_name_prefix(settings.prefix)
    if created or not records:
        present = await _tenant_resources(listed, files, prefix)
        if present:
            log.warning(
                "sweep skipped: no access records on file while tenant resources exist; nothing dropped",
                extra=log_extra(
                    LogContext(step="skip-sweep", system_created=created, resources=present)
                ),
            )
            return
    for tenant, record in records.items():
        if record.state == TenantState.DELETING:
            log.info(
                "finishing the interrupted deletion of a tenant",
                extra=log_extra(LogContext(step="finish-deletion", tenant_id=tenant)),
            )
            await tenancy.finish_deletion(tenant)
    named = {record.database_name for record in records.values()}
    await _drop_orphans(stores, listed, files, prefix, named)


def _refuse_unwired(records: dict[str, TenantAccess], stores: dict[str, Store]) -> None:
    unwired = sorted({store_name_in(r) for r in records.values()} - stores.keys())
    if unwired:
        raise StoreNotWired(f"the records name stores that are not wired: {', '.join(unwired)}")


def _report_misplaced(records: dict[str, TenantAccess], listed: dict[str, list[str]]) -> None:
    for tenant, record in records.items():
        if record.database_name in listed[store_name_in(record)]:
            continue
        for found, names in listed.items():
            if record.database_name in names:
                log.error(
                    "the database of a tenant is on another store than its record names; left alone",
                    extra=log_extra(
                        LogContext(
                            step="misplaced-tenant",
                            tenant_id=tenant,
                            store_name=store_name_in(record),
                            found_store_name=found,
                        )
                    ),
                )


async def _tenant_resources(
    listed: dict[str, list[str]], files: FileStore, prefix: str
) -> list[str]:
    """The databases (of every store) and buckets named ``{prefix}-t-…``."""
    databases = [n for names in listed.values() for n in names if n.startswith(prefix)]
    return sorted([*databases, *await files.list_buckets(prefix)])


async def _drop_orphans(
    stores: dict[str, Store],
    listed: dict[str, list[str]],
    files: FileStore,
    prefix: str,
    named: set[str],
) -> None:
    for name, wired in stores.items():
        for database in _orphans(listed[name], prefix, named):
            log.info(
                "dropping an orphan database",
                extra=log_extra(
                    LogContext(step="drop-orphan-database", db_namespace=database, store_name=name)
                ),
            )
            with suppress(NotFound):  # dropped meanwhile
                await wired.drop_dataset(database)
    for bucket in _orphans(await files.list_buckets(prefix), prefix, named):
        log.info(
            "dropping an orphan bucket",
            extra=log_extra(LogContext(step="drop-orphan-bucket", resource=bucket)),
        )
        with suppress(NotFound):
            await files.delete_bucket(bucket)


def _orphans(names: list[str], prefix: str, named: set[str]) -> list[str]:
    """The tenant-prefixed names that no access record names."""
    return [name for name in names if name.startswith(prefix) and name not in named]
