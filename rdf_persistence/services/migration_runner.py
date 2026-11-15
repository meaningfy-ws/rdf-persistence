"""The migration runner: each database is brought to the running schema's version at start-up (PD-7, PD-9 to PD-11).

A database records, per schema id, the version its data follows (the stamp, PD-2). For each chain, the
toolkit's first, the runner stamps a database that has none with the chain's first version (PD-10), then
sends one request per pending migration (``migration_request``: the steps, the token rotation and the
stamp move, each guarded by the ``from`` stamp), and reads the stamp back. ``to``, or any later version
of the chain, means the migration is done, whoever did it, and the runner goes on from the stamp it read
(PD-7). The shared databases (system, application) stop start-up when a migration fails; a tenant is set
aside, in ``Tenancy.behind``, and the next one runs (PD-11).

``chains`` is a sequence of ``(schema id, Chain)``, the toolkit's schema first. A plain pair: a record
class would be a hand-written model.
"""

import logging
from collections.abc import Sequence
from typing import cast

from rdflib import Dataset, URIRef

from rdf_persistence.domain.exceptions import InvalidBody, MigrationFailed, PersistenceError
from rdf_persistence.domain.generated.rp_tenancy import TenantState
from rdf_persistence.domain.generated.service.rp_service import Migration
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.migrations import (
    Chain,
    SchemaChain,
    first_version,
    migration_request,
    pending_from,
    stamp_if_none,
    stamp_problems,
    stamps,
    versions,
)
from rdf_persistence.services.store import Store
from rdf_persistence.services.tenancy import Tenancy
from rdf_persistence.services.yaml_files import SHOWN, shown

log = logging.getLogger(__name__)


async def migrate_database(
    store: Store, database: str, chains: Sequence[SchemaChain], stamps_graph: URIRef
) -> None:
    """Bring ``database`` to the last version of every chain, in the order given.

    Raises:
        MigrationFailed: The store failed, the stamp is unknown to the chain or doubled, or it did not
            move; the message names the database, the migration and the cause. What an earlier
            migration of the chain did stays (it was its own request).
    """
    for schema_id, chain in chains:
        await _migrate_schema(store, database, schema_id, chain, stamps_graph)


async def migrate_shared(tenancy: Tenancy, store: Store, chains: Sequence[SchemaChain]) -> None:
    """Migrate the system database, then the application database when it exists (PD-9); it creates none.

    Raises:
        MigrationFailed: A migration failed; it is logged at ERROR (step ``migrate-shared``) first.
    """
    for database in await _shared_databases(tenancy, store):
        try:
            await migrate_database(store, database, chains, tenancy.stamps_graph)
        except MigrationFailed as error:
            log.error(str(error), extra=_failure("migrate-shared", error, database=database))
            raise


async def migrate_tenants(
    tenancy: Tenancy, store: Store, chains: Sequence[SchemaChain]
) -> set[str]:
    """Migrate every tenant but those ``deleting``, in IRI order; answers the tenants set aside (PD-11).

    ``store`` is the default store; each tenant is migrated on the store its record names, routed
    through ``tenancy`` (tenant-stores PD-6).

    Raises:
        StoreNotWired: A tenant's record names a store that is not wired; this is a configuration
            fault, not a failed migration, so the tenant is not set aside and the run stops.

    The tenants whose migration failed are each logged at ERROR (step ``migrate-tenant``) and, once
    the run ends, replace ``tenancy.behind`` (``set_aside``): until then the previous set stays in
    force. The next tenant runs after a failure.
    """
    failed: set[str] = set()
    for tenant in await tenancy.tenants():
        if tenant.state == TenantState.DELETING:
            continue
        home = await tenancy.store_of(
            tenant.id
        )  # outside the try: StoreNotWired is not a failed migration
        try:
            await migrate_database(
                home, tenancy.database_of(tenant.id), chains, tenancy.stamps_graph
            )
        except MigrationFailed as error:
            log.error(str(error), extra=_failure("migrate-tenant", error, tenant=tenant.id))
            failed.add(tenant.id)
    tenancy.set_aside(failed)
    return failed


def migrate_dataset(dataset: Dataset, chains: Sequence[SchemaChain], stamps_graph: URIRef) -> None:
    """Bring a parsed dump to the last version of every chain, in memory, in the order given (PD-15).

    The migrations are the store's: each is ``migration_request``'s text, applied through ``Dataset.update``,
    and the stamp read back must have moved forward as it must in the store. ``dataset`` is changed in place;
    on a refusal it may be half migrated, so a caller drops it.

    Raises:
        InvalidBody: The stamps graph is not one stamp per schema of ``chains``, each a version of its chain
            (``stamp_problems``), or a migration's request fails on the dataset or leaves the stamp behind;
            the message names the migration.
    """
    wanted = {schema_id: versions(chain) for schema_id, chain in chains}
    if problems := stamp_problems(dataset.graph(stamps_graph), wanted):
        raise InvalidBody(f"the dump's stamps graph is not a version of each schema: {problems}")
    for schema_id, chain in chains:
        _migrate_in_memory(dataset, schema_id, chain, stamps_graph)


def _migrate_in_memory(
    dataset: Dataset, schema_id: str, chain: Chain, stamps_graph: URIRef
) -> None:
    version = _held(dataset, schema_id, stamps_graph)
    # a later version each round, as in the store (PD-23); the stamp is a version of the chain, checked above
    while version is not None and (pending := pending_from(chain, version)):
        migration = pending[0]
        request = migration_request(migration, stamps_graph)  # a defect in our own text escapes
        try:
            dataset.update(request)
        except (RecursionError, MemoryError):
            raise
        except (
            Exception
        ) as error:  # rdflib raises bare Exception, re.error, TypeError, ValueError at run time
            raise _refused(schema_id, migration, error) from error
        version = _held(dataset, schema_id, stamps_graph)
        if problem := _not_forward(version, migration, versions(chain)):
            raise _refused(schema_id, migration, f"after the request {problem}")


def _held(dataset: Dataset, schema_id: str, stamps_graph: URIRef) -> str | None:
    value = dataset.graph(stamps_graph).value(URIRef(schema_id), v.DATA_SCHEMA_VERSION)
    return None if value is None else str(value)


def _refused(schema_id: str, migration: Migration, cause: object) -> InvalidBody:
    return InvalidBody(
        f"the dump cannot be migrated: {_name(schema_id, migration)}: {shown(str(cause))}"
    )


def _failure(step: str, error: MigrationFailed, **where: str) -> dict[str, str]:
    return {
        "step": step,
        **where,
        "schema": error.schema,
        "migration": error.migration,
        "cause": error.cause,
    }


async def _shared_databases(tenancy: Tenancy, store: Store) -> list[str]:
    databases = [tenancy.system_database]
    application = tenancy.application_database
    if application is not None and application in await store.list_datasets():
        databases.append(application)
    return databases


async def _migrate_schema(
    store: Store, database: str, schema_id: str, chain: Chain, stamps_graph: URIRef
) -> None:
    version = await _stamp_of(store, database, schema_id, chain, stamps_graph)
    while True:
        pending = pending_from(chain, version)
        if pending is None:
            known = ", ".join(repr(known) for known in versions(chain))
            raise _failed(
                database,
                schema_id,
                None,
                f"the stamp {version!r} is not one of the versions {known}",
            )
        if not pending:
            return
        # Each round ends at a later version of the finite chain or fails, so the loop ends (PD-23).
        version = await _apply(store, database, schema_id, pending[0], chain, stamps_graph)


async def _stamp_of(
    store: Store, database: str, schema_id: str, chain: Chain, stamps_graph: URIRef
) -> str:
    """The stamp of ``schema_id``; a database with none is stamped with the chain's first version first (PD-10)."""
    version = await _read_stamp(store, database, schema_id, stamps_graph)
    if version is None:
        try:
            await stamp_if_none(store, database, stamps_graph, schema_id, first_version(chain))
        except PersistenceError as error:
            raise _failed(database, schema_id, None, error) from error
        version = await _read_stamp(store, database, schema_id, stamps_graph)
    if version is None:
        raise _failed(database, schema_id, None, "there is no stamp after it was written")
    return version


async def _read_stamp(
    store: Store,
    database: str,
    schema_id: str,
    stamps_graph: URIRef,
    migration: Migration | None = None,
) -> str | None:
    try:
        return (await stamps(store, database, stamps_graph)).get(schema_id)
    except PersistenceError as error:
        raise _failed(database, schema_id, migration, error) from error


async def _apply(
    store: Store,
    database: str,
    schema_id: str,
    migration: Migration,
    chain: Chain,
    stamps_graph: URIRef,
) -> str:
    """Send the request of ``migration`` and answer the stamp read back: ``to`` or a later version (PD-7, PD-23)."""
    try:
        await store.update(database, migration_request(migration, stamps_graph))
    except PersistenceError as error:
        raise _failed(database, schema_id, migration, error) from error
    version = await _read_stamp(store, database, schema_id, stamps_graph, migration)
    if problem := _not_forward(version, migration, versions(chain)):
        raise _failed(database, schema_id, migration, f"after the request {problem}")
    log.info(
        "migrated a database",
        extra={
            "step": "migrate",
            "database": database,
            "schema": schema_id,
            "migration": _name(schema_id, migration),
        },
    )
    return cast(str, version)  # _not_forward answered a problem for None


def _not_forward(version: str | None, migration: Migration, ordered: Sequence[str]) -> str | None:
    """What is wrong with the stamp read back, or None when it is ``to`` or a later version of the chain."""
    if version is None:
        return "there is no stamp"
    if version not in ordered:
        return f"the stamp {version!r} is not one of the chain's versions"
    if ordered.index(version) < ordered.index(migration.to_version):
        return (
            f"the stamp {version!r} went backwards (the migration ends at {migration.to_version!r})"
        )
    return None


def _name(schema_id: str, migration: Migration) -> str:
    return f"{migration.from_version}__{migration.to_version} of {schema_id}"


def _failed(
    database: str, schema_id: str, migration: Migration | None, cause: object
) -> MigrationFailed:
    """``migration`` names the migration (empty when the failure is of the stamp alone); the schema goes apart."""
    what = _name(schema_id, migration) if migration else f"the stamp of {schema_id}"
    why = str(cause)[:SHOWN]
    return MigrationFailed(
        f"cannot migrate {database}: {what}: {why}",
        schema=schema_id,
        migration=_name(schema_id, migration) if migration else "",
        cause=why,
    )
