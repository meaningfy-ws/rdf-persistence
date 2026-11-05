"""Tenancy: each tenant has its own database and bucket, and an access record in the system database (PD-6a, PD-8, PD-9).

Creating a tenant writes the access record last, so a crash leaves only a database or a bucket that no
record names, which the sweep removes; a retry creates a new tenant. Deleting marks the record
``deleting`` first, so the tenant answers as if it did not exist from then on, then drops the database and
the bucket and removes the record; any later attempt, or the sweep, finishes what a crash interrupted.
Work the toolkit does on its own behalf is attributed to ``{base}toolkit``.
"""

from collections.abc import Iterable
from contextlib import suppress
from typing import cast

from pydantic import BaseModel
from rdflib import URIRef
from rdflib.query import ResultRow

from rdf_persistence.domain import vocabulary as v
from rdf_persistence.domain.errors import Conflict, NotFound
from rdf_persistence.domain.generated.rp_access import Grant
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.generated.rp_tenancy import TenantAccess, TenantState
from rdf_persistence.domain.generated.service.rp_service import ServiceSettings, TenantSummary
from rdf_persistence.domain.iris import (
    access_iri,
    mint_tenant_iri,
    system_database_name,
    tenant_iri_of_access,
    tenant_resource_name,
)
from rdf_persistence.domain.sparql import Triple, fill, term
from rdf_persistence.services.files import FileStore
from rdf_persistence.services.mapper import Mapper, UnitOfWork
from rdf_persistence.services.session import Clock, Session, open_session, utc_now
from rdf_persistence.services.store import Store

SELECT_RECORDS = "SELECT ?record ?label ?state WHERE { GRAPH ?graph { ?record $p_state ?state ; $p_label ?label } }"
TOOLKIT_SEGMENT = "toolkit"
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
        self._toolkit = Principal(id=f"{settings.base}{TOOLKIT_SEGMENT}")

    def _system_session(self, tenant: str, principal: Principal):
        return open_session(
            self._store,
            database=self._system,
            tenant_iri=tenant,
            principal=principal,
            clock=self._clock,
        )

    async def ensure_system_database(self) -> None:
        """Create the system database unless it exists (start-up)."""
        if self._system in await self._store.list_datasets():
            return
        with suppress(Conflict):  # another worker created it first
            await self._store.create_dataset(self._system)

    async def create[M: BaseModel](self, label: str, root: M, creator: Principal) -> TenantSummary:
        """Create a tenant: its database and bucket, its root object, and last its access record.

        ``root`` is the tenant's root object; its ``id`` is replaced by the tenant IRI minted here.
        The record gives ``creator`` the settings' ``creator_role`` on the tenant.
        """
        tenant = str(mint_tenant_iri(self._settings.base, self._settings.tenant_segment))
        name = tenant_resource_name(self._settings.prefix, tenant)
        await self._store.create_dataset(name)
        await self._files.create_bucket(name)
        async with open_session(
            self._store, database=name, tenant_iri=tenant, principal=creator, clock=self._clock
        ) as session:
            work = UnitOfWork(session, self._mapper)
            work.add(root.model_copy(update={"id": tenant}))
            await work.commit()
        record = self._access_class(
            id=str(access_iri(tenant)),
            label=label,
            description=RECORD_DESCRIPTION.format(label=label),
            state=TenantState.ACTIVE,
            database_name=name,
            grants=[Grant(assignee=creator.id, target=tenant, role=self._settings.creator_role)],
        )
        async with self._system_session(tenant, creator) as session:
            work = UnitOfWork(session, self._mapper)
            work.add(record)
            await work.commit()
        return TenantSummary(id=tenant, label=label, state=TenantState.ACTIVE)

    async def get(self, tenant: str) -> tuple[TenantAccess, str]:
        """The tenant's access record and its version token.

        Raises:
            NotFound: The tenant has no access record.
        """
        async with self._system_session(tenant, self._toolkit) as session:
            return await self._read(session, tenant)

    async def _read(self, session: Session, tenant: str) -> tuple[TenantAccess, str]:
        graph, version = await session.get_graph(str(access_iri(tenant)))
        return self._mapper.from_graph(self._access_class, str(access_iri(tenant)), graph), version

    async def tenants(self) -> list[TenantSummary]:
        """Every tenant that has an access record, in any state."""
        text = fill(SELECT_RECORDS, p_state=term(v.STATE), p_label=term(v.LABEL))
        states = {iri: TenantState(name) for name, iri in v.TENANT_STATE_IRIS.items()}
        rows = [r for r in await self._store.query(self._system, text) if isinstance(r, ResultRow)]
        return sorted(
            (
                TenantSummary(
                    id=str(tenant_iri_of_access(str(r.record))),
                    label=str(r.label),
                    state=states[URIRef(r.state)],
                )
                for r in rows
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
        async with self._system_session(tenant, self._toolkit) as session:
            record, version = await self._read(session, tenant)
            if record.state == TenantState.ACTIVE.value:
                if version != if_version:
                    raise Conflict(f"the access record of {tenant} is no longer at {if_version}")
                record.state = TenantState.DELETING
                triples = cast(Iterable[Triple], self._mapper.to_graph(record))
                await session.replace_graph(record.id, triples, if_version)
        await self.finish_deletion(tenant)

    async def finish_deletion(self, tenant: str) -> None:
        """Drop the database and the bucket of a ``deleting`` tenant, then remove its record."""
        name = tenant_resource_name(self._settings.prefix, tenant)
        for drop in (self._store.drop_dataset, self._files.delete_bucket):
            with suppress(NotFound):  # an interrupted attempt already dropped it
                await drop(name)
        async with self._system_session(tenant, self._toolkit) as session:
            _, version = await self._read(session, tenant)
            await session.remove(str(access_iri(tenant)), version)
