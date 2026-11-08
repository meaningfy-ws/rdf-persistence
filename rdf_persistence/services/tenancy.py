"""Tenancy: each tenant has its own database and bucket, and an access record in the system database (PD-6a, PD-8, PD-9).

Creating a tenant writes the access record last, so a crash leaves only a database or a bucket that no
record names, which the sweep removes; a retry creates a new tenant. Deleting marks the record
``deleting`` first, so the tenant answers as if it did not exist from then on, then drops the database and
the bucket and removes the record; any later attempt, or the sweep, finishes what a crash interrupted.
Work the toolkit does on its own behalf is attributed to ``{base}toolkit``.
"""

import logging
from collections.abc import Mapping
from contextlib import AbstractAsyncContextManager, suppress
from typing import Any

from pydantic import BaseModel, ValidationError
from rdflib import Graph, URIRef

from rdf_persistence.domain.exceptions import (
    Conflict,
    InvalidBody,
    NotFound,
    PersistenceError,
    StoredDataInvalid,
)
from rdf_persistence.domain.generated.rp_access import Action, Grant
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.generated.rp_tenancy import TenantAccess, TenantState
from rdf_persistence.domain.generated.service.rp_service import (
    CallerAccess,
    GrantSet,
    Page,
    ServiceSettings,
    TenantSummary,
    VerifiedCaller,
)
from rdf_persistence.domain.iris import (
    Iris,
    graph_iri,
    system_database_name,
    toolkit_principal_iri,
)
from rdf_persistence.domain.sparql import fill, term
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.access import AccessRules
from rdf_persistence.services.files import FileStore
from rdf_persistence.services.mapper import Mapper, UnitOfWork
from rdf_persistence.services.schema_structure import internal_predicates, refuse_internal
from rdf_persistence.services.session import Clock, Session, open_session, utc_now
from rdf_persistence.services.store import Store

log = logging.getLogger(__name__)

# Every graph that holds an access record, whole: the mapper decodes the records from it.
CONSTRUCT_RECORDS = (
    "CONSTRUCT { ?s ?p ?o } WHERE { GRAPH ?graph { ?record $p_state ?state . ?s ?p ?o } }"
)
RECORD_DESCRIPTION = "Who may do what in the tenant {label}."
MAX_TENANT_CLASH_DRAWS = 5  # PD-5


class Tenancy:
    """Creates, reads and deletes tenants: their databases, buckets and access records."""

    def __init__(
        self,
        store: Store,
        files: FileStore,
        settings: ServiceSettings,
        *,
        mapper: Mapper,
        root_class: type[BaseModel],
        access_class: type[TenantAccess],
        clock: Clock = utc_now,
        iris: Iris | None = None,
    ) -> None:
        # not DEFAULT_IRIS: resource names need the settings' prefix, which DEFAULT_IRIS lacks (PD-12j)
        self._iris = iris or Iris(settings)
        self._store = store
        self._files = files
        self._settings = settings
        self._mapper = mapper
        self._internal = internal_predicates(mapper.view)
        self._root_class = root_class
        self._access_class = access_class
        self._clock = clock
        self._system = system_database_name(settings.prefix)
        self._toolkit = Principal(id=str(toolkit_principal_iri(settings.base)))

    def _session(
        self, database: str, tenant: str, principal: Principal
    ) -> AbstractAsyncContextManager[Session]:
        return open_session(
            self._store,
            database=database,
            tenant_iri=tenant,
            principal=principal,
            clock=self._clock,
            iris=self._iris,
        )

    def tenant_session(
        self, tenant: str, principal: Principal
    ) -> AbstractAsyncContextManager[Session]:
        """A session on the database of ``tenant`` for ``principal``."""
        return self._session(self._iris.resource_name(tenant), tenant, principal)

    async def _add_root(
        self, database: str, tenant: str, principal: Principal, obj: BaseModel
    ) -> None:
        """Store ``obj`` as a new root."""
        async with self._session(database, tenant, principal) as session:
            work = UnitOfWork(session, self._mapper)
            work.add(obj)
            await work.commit()

    async def _replace_root(
        self, database: str, tenant: str, principal: Principal, obj: BaseModel, if_version: str
    ) -> str:
        """Store ``obj`` over the root already there, if it still has ``if_version``; answers the new version."""
        async with self._session(database, tenant, principal) as session:
            return await session.replace_graph(
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

    async def create(
        self, label: str, root_slots: Mapping[str, Any], creator: Principal
    ) -> TenantSummary:
        """Create a tenant: its database and bucket, its root object, and last its access record.

        ``root_slots`` are the slots of the tenant's root object, whose ``id`` is the tenant IRI
        minted here and whose ``label`` is the tenant's unless the slots give one. The record gives
        ``creator`` the settings' ``creator_role`` on the tenant. Both objects are built and
        validated before anything is created, so a refused request leaves nothing (PD-8c).

        Raises:
            InvalidBody: ``root_slots`` names an ``id`` or sets an ``internal`` slot: the service assigns those.
            ValueError: ``label`` or ``root_slots`` is not valid (pydantic's ``ValidationError``).
        """
        if "id" in root_slots:
            raise InvalidBody("the service assigns the IRI of a new tenant")
        tenant = await self._free_tenant()
        name = self._iris.resource_name(tenant)
        record = self._access_class(
            id=str(self._iris.access(tenant)),
            label=label,
            description=RECORD_DESCRIPTION.format(
                label=label.rstrip(".")
            ),  # the template ends the sentence
            state=TenantState.ACTIVE,
            database_name=name,
            grants=[Grant(assignee=creator.id, target=tenant, role=self._settings.creator_role)],
        )
        tenant_root = self._root_class.model_validate({"label": label, **root_slots, "id": tenant})
        refuse_internal(self._mapper.to_graph(tenant_root), self._internal)
        await self._store.create_dataset(name)
        _log_step("create-database", tenant, name)
        await self._files.create_bucket(name)
        _log_step("create-bucket", tenant, name)
        await self._add_root(name, tenant, creator, tenant_root)
        await self._add_root(self._system, tenant, creator, record)
        _log_step("create-record", tenant, name)
        return TenantSummary(id=tenant, label=label, state=TenantState.ACTIVE)

    async def _free_tenant(self) -> str:
        """A fresh tenant IRI whose access record and resource name nothing uses (PD-5).

        Raises:
            PersistenceError: Every one of ``MAX_TENANT_CLASH_DRAWS`` draws clashed.
        """
        datasets = set(await self._store.list_datasets())
        for _ in range(MAX_TENANT_CLASH_DRAWS):
            tenant = str(self._iris.mint_tenant())
            if self._iris.resource_name(tenant) not in datasets and not (
                self._system in datasets and await self._has_record(tenant)
            ):
                return tenant
        raise PersistenceError("no free tenant id")

    async def _has_record(self, tenant: str) -> bool:
        try:
            await self.get(tenant)
        except NotFound:
            return False
        return True

    async def get(self, tenant: str) -> tuple[TenantAccess, str]:
        """The tenant's access record and its version token.

        Raises:
            NotFound: The tenant has no access record.
        """
        async with self._session(self._system, tenant, self._toolkit) as session:
            return await self._read(session, tenant)

    async def _read(self, session: Session, tenant: str) -> tuple[TenantAccess, str]:
        iri = str(self._iris.access(tenant))
        graph, graph_name, version = await session.get_graph(iri)
        return self._decoded(iri, graph, graph_name), version

    def _decoded(self, iri: str, graph: Graph, graph_name: URIRef) -> TenantAccess:
        """The access record stored at ``iri``.

        Raises:
            StoredDataInvalid: The graph does not hold a valid record; the request is not to blame.
        """
        try:
            return self._mapper.from_graph(self._access_class, iri, graph, graph_name)
        except (ValidationError, ValueError) as error:
            raise StoredDataInvalid(
                f"the access record {iri} cannot be decoded: {error}"
            ) from error

    async def _records(self) -> list[TenantAccess]:
        """Every access record, decoded by the mapper from the graphs that hold them."""
        text = fill(CONSTRUCT_RECORDS, p_state=term(v.STATE))
        stored = (await self._store.query(self._system, text)).graph
        if stored is None:
            return []
        record_iris = sorted({str(record) for record in stored.subjects(v.STATE, None)})
        return [self._decoded(iri, stored, graph_iri(iri)) for iri in record_iris]

    async def rename(self, tenant: str, label: str, if_version: str, principal: Principal) -> str:
        """Give the tenant a new label, in its access record, whose description follows; answers the new version.

        Raises:
            NotFound: The tenant has no access record.
            Conflict: The record is no longer at ``if_version``; nothing changed.
            ValueError: ``label`` is not valid (pydantic's ``ValidationError``).
        """
        record, _ = await self.get(tenant)
        record.label = label
        record.description = RECORD_DESCRIPTION.format(label=label.rstrip("."))
        return await self._replaced(tenant, principal, record, if_version)

    async def set_grants(
        self, tenant: str, grants: GrantSet, if_version: str, principal: Principal
    ) -> str:
        """Replace the grants and the prohibitions of the tenant's access record; answers the new version.

        Raises:
            NotFound: The tenant has no access record.
            Conflict: The record is no longer at ``if_version``; nothing changed.
        """
        record, _ = await self.get(tenant)
        record.grants = grants.grants
        record.prohibitions = grants.prohibitions
        return await self._replaced(tenant, principal, record, if_version)

    async def _replaced(
        self, tenant: str, principal: Principal, record: TenantAccess, if_version: str
    ) -> str:
        return await self._replace_root(self._system, tenant, principal, record, if_version)

    async def tenants(self) -> list[TenantSummary]:
        """Every tenant that has an access record, in any state."""
        return sorted(
            (
                TenantSummary(
                    id=str(self._iris.tenant_of_access(record.id)),
                    label=record.label,
                    state=TenantState(record.state),
                )
                for record in await self._records()
            ),
            key=lambda summary: summary.id,
        )

    async def visible_tenants(
        self, caller: VerifiedCaller, rules: AccessRules, *, limit: int, offset: int
    ) -> Page:
        """One page, ordered by IRI, of the tenants ``caller`` may read, and how many there are in all.

        All the access records are read in one query and the rules are applied to them in memory, so
        the cost in queries does not grow with the number of tenants.

        Raises:
            StoredDataInvalid: A record cannot be decoded.
        """
        visible = [
            TenantSummary(
                id=str(self._iris.tenant_of_access(record.id)),
                label=record.label,
                state=TenantState(record.state),
            )
            for record in await self._records()
            if rules.may(
                caller,
                self._access_of(record),
                str(self._iris.tenant_of_access(record.id)),
                Action.READ,
            )
        ]
        visible.sort(key=lambda summary: summary.id)
        return Page(
            items=visible[offset : offset + limit], total=len(visible), limit=limit, offset=offset
        )

    def _access_of(self, record: TenantAccess) -> CallerAccess:
        """What the access check knows of a tenant, from its whole record."""
        return CallerAccess(
            tenant=str(self._iris.tenant_of_access(record.id)),
            state=record.state,
            grants=record.grants,
            prohibitions=record.prohibitions,
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
            await self._replace_root(self._system, tenant, self._toolkit, record, if_version)
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
