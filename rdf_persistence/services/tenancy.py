"""Tenancy: each tenant has its own database and bucket, and an access record in the system database (PD-6a, PD-8, PD-9).

Creating a tenant writes the access record last, so a crash leaves only a database or a bucket that no
record names, which the sweep removes; a retry creates a new tenant. Deleting marks the record
``deleting`` first, so the tenant answers as if it did not exist from then on, then drops the database and
the bucket and removes the record; any later attempt, or the sweep, finishes what a crash interrupted.
Work the toolkit does on its own behalf is attributed to ``{base}toolkit``.
"""

import logging
from contextlib import suppress

from pydantic import BaseModel

from rdf_persistence.domain.exceptions import Conflict, NotFound
from rdf_persistence.domain.generated.rp_access import Grant
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.generated.rp_tenancy import TenantAccess, TenantState
from rdf_persistence.domain.generated.service.rp_service import ServiceSettings, TenantSummary
from rdf_persistence.domain.iris import (
    access_iri,
    graph_iri,
    mint_tenant_iri,
    system_database_name,
    tenant_iri_of_access,
    tenant_resource_name,
    toolkit_principal_iri,
)
from rdf_persistence.domain.sparql import fill, term
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.files import FileStore
from rdf_persistence.services.mapper import Mapper, UnitOfWork
from rdf_persistence.services.session import Clock, Session, open_session, utc_now
from rdf_persistence.services.store import Store

log = logging.getLogger(__name__)

# Every graph that holds an access record, whole: the mapper decodes the records from it.
CONSTRUCT_RECORDS = (
    "CONSTRUCT { ?s ?p ?o } WHERE { GRAPH ?graph { ?record $p_state ?state . ?s ?p ?o } }"
)
RECORD_DESCRIPTION = "Who may do what in the tenant {label}."


class Tenancy:
    """Creates, reads and deletes tenants: their databases, buckets and access records."""

    def __init__(
        self,
        store: Store,
        files: FileStore,
        settings: ServiceSettings,
        *,
        mapper: Mapper,
        access_class: type[TenantAccess],
        clock: Clock = utc_now,
    ) -> None:
        self._store = store
        self._files = files
        self._settings = settings
        self._mapper = mapper
        self._access_class = access_class
        self._clock = clock
        self._system = system_database_name(settings.prefix)
        self._toolkit = Principal(id=str(toolkit_principal_iri(settings.base)))

    def _session(self, database: str, tenant: str, principal: Principal):
        return open_session(
            self._store,
            database=database,
            tenant_iri=tenant,
            principal=principal,
            clock=self._clock,
        )

    async def _commit(
        self,
        database: str,
        tenant: str,
        principal: Principal,
        obj: BaseModel,
        if_version: str | None = None,
    ) -> None:
        """Store ``obj`` as a new root, or, given ``if_version``, over the root already there."""
        async with self._session(database, tenant, principal) as session:
            if if_version is None:
                work = UnitOfWork(session, self._mapper)
                work.add(obj)
                await work.commit()
            else:
                await session.replace_graph(
                    str(getattr(obj, "id")),  # noqa: B009 - a root always has an id
                    self._mapper.to_triples(obj),
                    if_version,
                )

    async def ensure_system_database(self) -> bool:
        """Create the system database unless it exists (start-up); True if this call created it."""
        if self._system in await self._store.list_datasets():
            return False
        with suppress(Conflict):  # another worker created it first
            await self._store.create_dataset(self._system)
        return True

    async def create(self, label: str, root: BaseModel, creator: Principal) -> TenantSummary:
        """Create a tenant: its database and bucket, its root object, and last its access record.

        ``root`` is the tenant's root object; its ``id`` is replaced by the tenant IRI minted here.
        The record gives ``creator`` the settings' ``creator_role`` on the tenant. Both objects are
        built and validated before anything is created, so a refused request leaves nothing (PD-8c).

        Raises:
            ValueError: ``label`` or ``root`` is not valid (pydantic's ``ValidationError``).
        """
        tenant = str(mint_tenant_iri(self._settings.base, self._settings.tenant_segment))
        name = tenant_resource_name(self._settings.prefix, tenant)
        record = self._access_class(
            id=str(access_iri(tenant)),
            label=label,
            description=RECORD_DESCRIPTION.format(label=label),
            state=TenantState.ACTIVE,
            database_name=name,
            grants=[Grant(assignee=creator.id, target=tenant, role=self._settings.creator_role)],
        )
        tenant_root = type(root).model_validate(root.model_copy(update={"id": tenant}).model_dump())
        await self._store.create_dataset(name)
        _log_step("create-database", tenant, name)
        await self._files.create_bucket(name)
        _log_step("create-bucket", tenant, name)
        await self._commit(name, tenant, creator, tenant_root)
        await self._commit(self._system, tenant, creator, record)
        _log_step("create-record", tenant, name)
        return TenantSummary(id=tenant, label=label, state=TenantState.ACTIVE)

    async def get(self, tenant: str) -> tuple[TenantAccess, str]:
        """The tenant's access record and its version token.

        Raises:
            NotFound: The tenant has no access record.
        """
        async with self._session(self._system, tenant, self._toolkit) as session:
            return await self._read(session, tenant)

    async def _read(self, session: Session, tenant: str) -> tuple[TenantAccess, str]:
        iri = str(access_iri(tenant))
        graph, graph_name, version = await session.get_graph(iri)
        return self._mapper.from_graph(self._access_class, iri, graph, graph_name), version

    async def _records(self) -> list[TenantAccess]:
        """Every access record, decoded by the mapper from the graphs that hold them."""
        text = fill(CONSTRUCT_RECORDS, p_state=term(v.STATE))
        stored = (await self._store.query(self._system, text)).graph
        if stored is None:
            return []
        iris = sorted({str(record) for record in stored.subjects(v.STATE, None)})
        return [
            self._mapper.from_graph(self._access_class, iri, stored, graph_iri(iri)) for iri in iris
        ]

    async def tenants(self) -> list[TenantSummary]:
        """Every tenant that has an access record, in any state."""
        return sorted(
            (
                TenantSummary(
                    id=str(tenant_iri_of_access(record.id)),
                    label=record.label,
                    state=TenantState(record.state),
                )
                for record in await self._records()
            ),
            key=lambda summary: summary.id,
        )

    async def delete(self, tenant: str, if_version: str) -> None:
        """Delete the tenant: mark it ``deleting``, drop its database and bucket, remove its record.

        A tenant already ``deleting`` is finished whatever ``if_version`` says, since marking it moved
        the version.

        Raises:
            NotFound: The tenant has no access record.
            Conflict: The record is active and is no longer at ``if_version``; nothing changed.
        """
        record, _ = await self.get(tenant)
        if record.state == TenantState.ACTIVE:
            record.state = TenantState.DELETING
            await self._commit(self._system, tenant, self._toolkit, record, if_version)
        await self.finish_deletion(tenant)

    async def finish_deletion(self, tenant: str) -> None:
        """Drop the database and the bucket the record names, then remove the record.

        Raises:
            NotFound: The tenant has no access record.
            Conflict: The record is not ``deleting``; nothing is dropped.
        """
        async with self._session(self._system, tenant, self._toolkit) as session:
            record, version = await self._read(session, tenant)
            if record.state != TenantState.DELETING:
                raise Conflict(f"{tenant} is not deleting: it is {record.state}")
            drops = (
                ("drop-database", self._store.drop_dataset),
                ("drop-bucket", self._files.delete_bucket),
            )
            for step, drop in drops:
                with suppress(NotFound):  # an interrupted attempt already dropped it
                    await drop(record.database_name)
                _log_step(step, tenant, record.database_name)
            await session.remove(record.id, version)
            _log_step("remove-record", tenant, record.database_name)

    async def database_names(self) -> set[str]:
        """The database (and bucket) names the access records store, for every tenant."""
        return {record.database_name for record in await self._records()}


def _log_step(step: str, tenant: str, resource: str) -> None:
    """One step of creating or dropping a tenant's resources, as data an operator can query."""
    log.info(step, extra={"step": step, "tenant": tenant, "resource": resource})
