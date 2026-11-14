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
from typing import TYPE_CHECKING

from rdflib import Literal, URIRef

from rdf_persistence.domain.exceptions import MigrationFailed, PersistenceError, StoredDataInvalid
from rdf_persistence.domain.generated.rp_tenancy import TenantState
from rdf_persistence.domain.generated.service.rp_service import Migration
from rdf_persistence.domain.sparql import fill, term
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.migrations import (
    Chain,
    first_version,
    migration_request,
    pending_from,
)
from rdf_persistence.services.store import Store
from rdf_persistence.services.yaml_files import SHOWN

if (
    TYPE_CHECKING
):  # Tenancy imports this module to stamp what it creates; the runner needs it as a type only
    from rdf_persistence.services.tenancy import Tenancy

log = logging.getLogger(__name__)

SchemaChain = tuple[str, Chain]  # the schema id and its chain

SELECT_STAMPS = "SELECT ?schema ?version WHERE { GRAPH $graph { ?schema $p_stamp ?version } }"
# The first writer wins: the stamp is inserted only if the schema has none (as the IRI policy record is).
INSERT_STAMP = (
    "INSERT { GRAPH $graph { $schema $p_stamp $version } } "
    "WHERE { FILTER NOT EXISTS { GRAPH $graph { $schema $p_stamp ?any } } }"
)


async def stamps(store: Store, database: str, stamps_graph: URIRef) -> dict[str, str]:
    """The version each schema's data follows in ``database``: schema id to version.

    Raises:
        StoredDataInvalid: One schema has two stamps; the message names both versions.
    """
    text = fill(SELECT_STAMPS, graph=term(stamps_graph), p_stamp=term(v.DATA_SCHEMA_VERSION))
    versions: dict[str, set[str]] = {}
    for row in await store.query(database, text):
        versions.setdefault(str(row.schema), set()).add(str(row.version))  # type: ignore[union-attr]
    for schema, found in versions.items():
        if len(found) > 1:
            both = " and ".join(f'"{version}"' for version in sorted(found))
            raise StoredDataInvalid(f"{database} holds two stamps of {schema}: {both}")
    return {schema: next(iter(found)) for schema, found in versions.items()}


async def stamp_if_none(
    store: Store, database: str, stamps_graph: URIRef, schema_id: str, version: str
) -> None:
    """Stamp ``database`` with ``version`` for ``schema_id`` unless it has a stamp for it: first writer wins."""
    text = fill(
        INSERT_STAMP,
        graph=term(stamps_graph),
        schema=term(URIRef(schema_id)),
        p_stamp=term(v.DATA_SCHEMA_VERSION),
        version=term(Literal(version)),
    )
    await store.update(database, text)


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


async def migrate_shared(tenancy: "Tenancy", store: Store, chains: Sequence[SchemaChain]) -> None:
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
    tenancy: "Tenancy", store: Store, chains: Sequence[SchemaChain]
) -> set[str]:
    """Migrate every tenant but those ``deleting``, in IRI order; answers the tenants set aside (PD-11).

    ``tenancy.behind`` is emptied first and then holds the tenants whose migration failed, each logged
    at ERROR (step ``migrate-tenant``). The next tenant runs after a failure.
    """
    tenancy.behind.clear()
    for tenant in await tenancy.tenants():
        if tenant.state == TenantState.DELETING:
            continue
        try:
            await migrate_database(
                store, tenancy.database_of(tenant.id), chains, tenancy.stamps_graph
            )
        except MigrationFailed as error:
            log.error(str(error), extra=_failure("migrate-tenant", error, tenant=tenant.id))
            tenancy.behind.add(tenant.id)
    return set(tenancy.behind)


def _failure(step: str, error: MigrationFailed, **where: str) -> dict[str, str]:
    return {"step": step, **where, "migration": error.migration, "cause": error.cause}


async def _shared_databases(tenancy: "Tenancy", store: Store) -> list[str]:
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
            known = ", ".join(f'"{known}"' for known in chain[0])
            raise _failed(
                database,
                schema_id,
                None,
                f'the stamp "{version}" is not one of the versions {known}',
            )
        if not pending:
            return
        version = await _apply(store, database, schema_id, pending[0], stamps_graph)


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
    store: Store, database: str, schema_id: str, migration: Migration, stamps_graph: URIRef
) -> str:
    """Send the request of ``migration`` and answer the stamp read back; it must have moved (PD-7)."""
    try:
        await store.update(database, migration_request(migration, stamps_graph))
    except PersistenceError as error:
        raise _failed(database, schema_id, migration, error) from error
    version = await _read_stamp(store, database, schema_id, stamps_graph, migration)
    if version is None or version == migration.from_version:
        after = "no stamp" if version is None else f'the stamp is still "{version}"'
        raise _failed(database, schema_id, migration, f"after the request {after}")
    log.info(
        "migrated a database",
        extra={"step": "migrate", "database": database, "migration": _name(schema_id, migration)},
    )
    return version


def _name(schema_id: str, migration: Migration | None) -> str:
    if migration is None:
        return f"the stamp of {schema_id}"
    return f"{migration.from_version}__{migration.to_version} of {schema_id}"


def _failed(
    database: str, schema_id: str, migration: Migration | None, cause: object
) -> MigrationFailed:
    name, why = _name(schema_id, migration), str(cause)[:SHOWN]
    return MigrationFailed(f"cannot migrate {database}: {name}: {why}", migration=name, cause=why)
