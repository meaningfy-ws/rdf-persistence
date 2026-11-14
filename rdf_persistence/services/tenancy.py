"""Tenancy: each tenant has its own database and bucket, and an access record in the system database (PD-6a, PD-8, PD-9).

Creating a tenant writes the access record last, so a crash leaves only a database or a bucket that no
record names, which the sweep removes; a retry creates a new tenant. Deleting marks the record
``deleting`` first, so the tenant answers as if it did not exist from then on, then drops the database and
the bucket and removes the record; any later attempt, or the sweep, finishes what a crash interrupted.
Work the toolkit does on its own behalf is attributed to ``{base}toolkit``.
"""

import inspect
import logging
from collections.abc import Callable, Iterable, Mapping, Sequence
from contextlib import AbstractAsyncContextManager, suppress
from typing import Any

from pydantic import BaseModel, ValidationError
from rdflib import Dataset, Graph, URIRef

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
from rdf_persistence.domain.media import N_QUADS
from rdf_persistence.domain.sparql import Triple, fill, term
from rdf_persistence.domain.tenant_move import check_graphs, rewrite
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.access import AccessRules
from rdf_persistence.services.files import FileStore
from rdf_persistence.services.listing import Listings
from rdf_persistence.services.mapper import Mapper, UnitOfWork
from rdf_persistence.services.schema_structure import (
    LABEL,
    aggregate_keys,
    internal_predicates,
    refuse_internal,
)
from rdf_persistence.services.session import Clock, Session, open_session, utc_now
from rdf_persistence.services.store import Store

log = logging.getLogger(__name__)

# Every graph that holds an access record, whole: the mapper decodes the records from it.
ASK_RECORDS = "ASK { GRAPH ?graph { ?record $p_state ?state } }"
CONSTRUCT_RECORDS = (
    "CONSTRUCT { ?s ?p ?o } WHERE { GRAPH ?graph { ?record $p_state ?state . ?s ?p ?o } }"
)
RECORD_DESCRIPTION = "Who may do what in the tenant {label}."
MAX_TENANT_CLASH_DRAWS = 5  # PD-5

# A consumer's rule on a tenant write: it refuses by raising ``InvalidBody`` (422, the message is the detail) and
# returns otherwise. Run in order before the write; the first refusal stops it and nothing is written.
GrantValidator = Callable[[GrantSet, GrantSet, Principal], None]  # old, new, who
RootValidator = Callable[
    [BaseModel | None, BaseModel, Principal], None
]  # old (None on create), new, who


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
        listings: Listings | None = None,
        grant_validators: Sequence[GrantValidator] = (),
        root_validators: Sequence[RootValidator] = (),
    ) -> None:
        # not DEFAULT_IRIS: resource names need the settings' prefix, which DEFAULT_IRIS lacks (PD-12j)
        self._iris = iris or Iris(settings)
        self._listings = listings
        self._store = store
        self._files = files
        self._settings = settings
        self._mapper = mapper
        self._internal = internal_predicates(mapper.view)
        self._keys = aggregate_keys(mapper.view)
        self._root_class = root_class
        self._access_class = access_class
        self._clock = clock
        self._system = system_database_name(settings.prefix)
        self._grant_validators = _plain(grant_validators)
        self._root_validators = _plain(root_validators)
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
            listings=self._listings,
            keys=self._keys,
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

    @property
    def system_database(self) -> str:
        """The name of the system database."""
        return self._system

    async def has_access_records(self) -> bool:
        """True when any graph of the system database holds an access record, found by type and not through the IRI policy."""
        result = await self._store.query(self._system, fill(ASK_RECORDS, p_state=term(v.STATE)))
        return bool(result.askAnswer)

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
        minted here and whose ``label`` is the tenant's: the slots may leave it out or repeat it. The record gives
        ``creator`` the settings' ``creator_role`` on the tenant. Both objects are built and
        validated before anything is created, so a refused request leaves nothing (PD-8c).

        Raises:
            InvalidBody: ``root_slots`` names an ``id`` or sets an ``internal`` slot: the service assigns those;
                or gives a ``label`` other than ``label``: a tenant has one label (PD-3); or a root
                validator refuses the new root.
            ValueError: ``label`` or ``root_slots`` is not valid (pydantic's ``ValidationError``).
        """
        if "id" in root_slots:
            raise InvalidBody("the service assigns the IRI of a new tenant")
        if root_slots.get(LABEL, label) != label:
            raise InvalidBody("the label of a tenant's root is the tenant's")
        tenant = await self._free_tenant()
        name = self._iris.resource_name(tenant)
        record = self._new_record(tenant, name, label, creator)
        tenant_root = self._root_class.model_validate({**root_slots, LABEL: label, "id": tenant})
        refuse_internal(self._mapper.to_graph(tenant_root), self._internal)
        _run_validators(self._root_validators, None, tenant_root, creator)
        await self._store.create_dataset(name)
        _log_step("create-database", tenant, name)
        await self._files.create_bucket(name)
        _log_step("create-bucket", tenant, name)
        await self._add_root(name, tenant, creator, tenant_root)
        await self._add_root(self._system, tenant, creator, record)
        _log_step("create-record", tenant, name)
        return TenantSummary(id=tenant, label=label, state=TenantState.ACTIVE)

    def _new_record(self, tenant: str, name: str, label: str, creator: Principal) -> TenantAccess:
        """The access record of a new tenant: active, granting ``creator`` the settings' ``creator_role`` and no one else."""
        return self._access_class(
            id=str(self._iris.access(tenant)),
            label=label,
            description=RECORD_DESCRIPTION.format(
                label=label.rstrip(".")
            ),  # the template ends the sentence
            state=TenantState.ACTIVE,
            database_name=name,
            grants=[Grant(assignee=creator.id, target=tenant, role=self._settings.creator_role)],
        )

    async def restore(
        self,
        parsed: Dataset,
        source_tenant_id: str,
        blobs: Iterable[tuple[str, bytes]],
        creator: Principal,
    ) -> TenantSummary:
        """Create a new tenant out of a dump: its database holding the quads of ``parsed``, its bucket holding
        ``blobs``, and last its access record, which grants ``creator`` the creator role (tenant-dump-restore PD-6, PD-13).

        ``parsed`` holds the dumped tenant ``source_tenant_id``'s quads. This draws the new tenant, moves the quads
        to it (``tenant_move.rewrite``), refuses graphs the IRI policy does not mint for it and a root that does not
        decode or that a root validator refuses, all before anything is created. The new tenant's label is the
        root's. ``blobs`` is read one item at a time, as each is put. Once the database exists, any failure up to
        the vanished check (``blobs`` raising included) drops the database and the bucket as far as it can (a failed
        drop is logged, step ``restore-cleanup``, and left to the start-up sweep) and raises the original error. The
        record is written after that: if its write fails, the database and the bucket stay for the start-up sweep.

        Raises:
            InvalidBody: A quad is in the default graph or a foreign graph, or the root does not decode or a root
                validator refuses it; or ``blobs`` raises it.
            Conflict: The drawn tenant id was taken between the draw and the create; retry.
            PersistenceError: No free tenant id, or the new database or bucket was dropped (a start-up sweep
                elsewhere) before the record.
        """
        tenant = await self._free_tenant()
        data = rewrite(
            parsed, self._settings.base, source_tenant_id, self._iris.tenant_id_of(tenant)
        )
        check_graphs(data, tenant, self._iris)
        label = self._vet_restored_root(tenant, data.graph(self._iris.meta(tenant)), creator)
        name = self._iris.resource_name(tenant)
        record = self._new_record(tenant, name, label, creator)
        await self._store.create_dataset(name)
        _log_step("create-database", tenant, name)
        try:
            await self._files.create_bucket(name)
            _log_step("create-bucket", tenant, name)
            await self._store.import_quads(name, data.serialize(format=N_QUADS).encode())
            for key, payload in blobs:
                await self._files.put(name, key, payload)
            if (
                name not in await self._store.list_datasets()
                or name not in await self._files.list_buckets(name)
            ):
                raise PersistenceError(
                    "the new tenant's database or bucket vanished during the restore"
                )
        except Exception:
            await self._drop_restored(tenant, name)
            raise
        await self._add_root(self._system, tenant, creator, record)
        _log_step("create-record", tenant, name)
        return TenantSummary(id=tenant, label=label, state=TenantState.ACTIVE)

    async def _drop_restored(self, tenant: str, name: str) -> None:
        """Best effort: drop what a failed restore created; what stays is the start-up sweep's."""
        for drop in (self._store.drop_dataset, self._files.delete_bucket):
            try:
                await drop(name)
            except NotFound:  # never created, or already dropped
                pass
            except Exception:
                log.warning(
                    "a failed restore could not drop %s",
                    name,
                    exc_info=True,
                    extra={"step": "restore-cleanup", "tenant": tenant, "resource": name},
                )

    def _vet_restored_root(self, tenant: str, graph: Graph, restorer: Principal) -> str:
        """The label of the root of ``tenant`` in ``graph`` (its meta graph), once it decodes and the root validators
        accept it as a new root made by ``restorer``; the new tenant's label is this one (tenant-dump-restore PD-5).

        Raises:
            InvalidBody: The root does not decode, or a root validator refuses it.
        """
        try:
            root = self._mapper.from_graph(self._root_class, tenant, graph, self._iris.meta(tenant))
            _run_validators(self._root_validators, None, root, restorer)
        except ValueError as error:  # pydantic's ValidationError is one; InvalidBody is not
            raise InvalidBody(f"the dump's root cannot be restored: {error}") from error
        return str(getattr(root, LABEL))

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
        """Give the tenant a new label, in its root and in its access record, whose description follows; answers the record's new version.

        The record's version is checked and the label validated first, so a stale or invalid rename
        writes nothing. The root is written before the record: a failure between the two leaves the
        root renamed and the record not, and the same rename repeated writes both (PD-3).

        Raises:
            NotFound: The tenant has no access record.
            Conflict: The record is no longer at ``if_version``; the record is unchanged.
            ValueError: ``label`` is not valid (pydantic's ``ValidationError``).
        """
        record, version = await self.get(tenant)
        if version != if_version:
            raise Conflict(f"{tenant} was changed by someone else since it was read")
        record.label = label  # validates the label before anything is written
        record.description = RECORD_DESCRIPTION.format(label=label.rstrip("."))
        await self._relabel_root(tenant, label, principal)
        return await self._replaced(tenant, principal, record, if_version)

    async def _relabel_root(self, tenant: str, label: str, principal: Principal) -> None:
        """Store ``label`` in the tenant's root, under the root's own version."""
        async with self.tenant_session(tenant, principal) as session:
            work = UnitOfWork(session, self._mapper)
            root = await work.get(self._root_class, tenant)
            old = root.model_copy(deep=True)
            setattr(root, LABEL, label)  # every root is Described and has a label
            _run_validators(self._root_validators, old, root, principal)
            work.add(root)
            await work.commit()

    async def vet_root(self, tenant: str, triples: Iterable[Triple], principal: Principal) -> None:
        """Refuse a replacement body of the tenant's root that gives the tenant another label than its record has (PD-3), or that a root validator refuses.

        Raises:
            NotFound: The tenant has no access record.
            InvalidBody: The body's label is not the record's, or a root validator refuses the body.
        """
        record, _ = await self.get(tenant)
        graph = Graph()
        for triple in triples:
            graph.add(triple)
        refused = InvalidBody("the label of a tenant is changed through its label route")
        try:
            sent = self._mapper.from_graph(self._root_class, tenant, graph, graph_iri(tenant))
        except ValueError as error:  # no statement about the tenant, or no label to decode
            raise refused from error
        # the mapper reads one value of a single-valued slot: two labels would pass as the first
        labels = set(graph.objects(URIRef(tenant), v.predicate(LABEL)))
        if len(labels) != 1 or getattr(sent, LABEL) != record.label:
            raise refused
        if self._root_validators:
            async with self.tenant_session(tenant, principal) as session:
                stored = await UnitOfWork(session, self._mapper).get(self._root_class, tenant)
            # the replace keeps the stored root's internal slots (Aggregates.replace), so old and new compare like for like
            for statement in self._mapper.to_graph(stored):
                if statement[1] in self._internal:
                    graph.add(statement)
            sent = self._mapper.from_graph(self._root_class, tenant, graph, graph_iri(tenant))
            _run_validators(self._root_validators, stored, sent, principal)

    async def set_grants(
        self, tenant: str, grants: GrantSet, if_version: str, principal: Principal
    ) -> str:
        """Replace the grants and the prohibitions of the tenant's access record; answers the new version.

        Raises:
            NotFound: The tenant has no access record.
            Conflict: The record is no longer at ``if_version``; nothing changed.
            InvalidBody: A grant validator refuses ``grants``; nothing changed.
        """
        record, _ = await self.get(tenant)
        _run_validators(
            self._grant_validators,
            GrantSet(grants=record.grants, prohibitions=record.prohibitions),
            grants,
            principal,
        )
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
        visible = []
        for record in await self._records():
            access = self._access_of(record)
            actions = rules.allowed_actions(caller, access, access.tenant)
            if Action.READ in actions:
                visible.append(
                    TenantSummary(
                        id=access.tenant,
                        label=record.label,
                        state=TenantState(record.state),
                        allowed_actions=actions,
                    )
                )
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


def _plain(validators: Sequence[Callable[..., None]]) -> tuple[Callable[..., None], ...]:
    """``validators`` as a tuple, refusing a coroutine function: it would never be awaited, so it would always pass."""
    kept = tuple(validators)
    for validator in kept:
        if inspect.iscoroutinefunction(validator) or inspect.iscoroutinefunction(
            getattr(validator, "__call__", None)  # noqa: B004 - a callable object's own method
        ):
            raise TypeError(f"a validator is a plain function, not async: {validator!r}")
    return kept


def _run_validators(
    validators: Sequence[Callable[..., None]], old: Any, new: Any, who: Any
) -> None:
    """Run ``validators`` in order on copies of ``old`` and ``new``; the first to refuse stops the write.

    Validators only refuse: what they do to their arguments is never written. ``InvalidBody`` and pydantic's
    ``ValidationError`` pass as they are (422). A validator that returns anything, or raises anything else (a
    toolkit error or an ``HTTPException`` included), is a bug in it: ``TypeError``, or ``RuntimeError`` chained to
    the error, both a 500.
    """
    for validator in validators:
        try:
            result: object = validator(
                None if old is None else old.model_copy(deep=True), new.model_copy(deep=True), who
            )
        except (InvalidBody, ValidationError):
            raise
        except Exception as error:
            raise RuntimeError(f"a validator raised {type(error).__name__}: {error}") from error
        if result is not None:
            if inspect.iscoroutine(result):
                result.close()  # never awaited: no warning
            raise TypeError(f"a validator returns None or raises, not {result!r}")


def _log_step(step: str, tenant: str, resource: str) -> None:
    """One step of creating or dropping a tenant's resources, as data an operator can query."""
    log.info(step, extra={"step": step, "tenant": tenant, "resource": resource})
