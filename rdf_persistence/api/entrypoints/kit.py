"""What the routes share: the ports, the settings, and the pieces built from the application's schema (PD-13)."""

import logging
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import AbstractAsyncContextManager, AsyncExitStack, asynccontextmanager
from datetime import timedelta
from pathlib import Path
from types import ModuleType
from typing import BinaryIO, cast

from pydantic import BaseModel, ValidationError

from rdf_persistence.access.domain.generated import rp_access, rp_tenancy
from rdf_persistence.access.domain.generated.rp_access import Action
from rdf_persistence.access.domain.generated.rp_tenancy import (
    TenantAccess,
    TenantState,
    TenantSweepReport,
)
from rdf_persistence.access.services.access import AccessRules
from rdf_persistence.access.services.generated.rp_access_services import (
    CallerAccess,
    VerifiedCaller,
)
from rdf_persistence.access.services.identity import Identity
from rdf_persistence.access.services.tokens import TokenVerifier
from rdf_persistence.api.entrypoints.auth import Gate
from rdf_persistence.api.entrypoints.generated.rp_api_entrypoints import Authorised
from rdf_persistence.api.entrypoints.generated.settings.rp_api_settings import ToolkitSettings
from rdf_persistence.api.services import file_removal
from rdf_persistence.api.services.aggregates import Aggregates
from rdf_persistence.api.services.documents import Documents
from rdf_persistence.collaboration.domain.generated import (
    rp_collections,
    rp_discussion,
    rp_workflow,
)
from rdf_persistence.collaboration.services.collaboration import Collaboration
from rdf_persistence.collaboration.services.discussion import dependents as discussion_dependents
from rdf_persistence.collaboration.services.referenced_removals import ReferencedRemovals
from rdf_persistence.collaboration.services.workflows import Workflows
from rdf_persistence.collaboration.services.write_guards import WriteGuards
from rdf_persistence.core.domain.exceptions import (
    DatabaseGone,
    MessageLimitExceeded,
    NotFound,
    StoreNotWired,
)
from rdf_persistence.core.domain.generated import rp_core
from rdf_persistence.core.domain.generated.rp_core import Principal
from rdf_persistence.core.services.artifacts import CONTEXT_FILE
from rdf_persistence.core.services.generated.rp_core_services import LogContext
from rdf_persistence.core.services.telemetry import error_type, log_extra
from rdf_persistence.events.services.event_hub import EventHub
from rdf_persistence.events.services.events import EventBus, context_link
from rdf_persistence.events.services.generated.rp_events_services import EventEnvelope
from rdf_persistence.events.services.relay import Relay
from rdf_persistence.files.domain.generated import rp_files
from rdf_persistence.files.services.files import FileStore
from rdf_persistence.iris.domain.layout import system_database_name
from rdf_persistence.iris.services.generated.rp_iris_services import ServiceSettings
from rdf_persistence.iris.services.iris import IdSource, Iris, draw_id
from rdf_persistence.messaging.services.messagebus import MessageBus
from rdf_persistence.migrations.services.migrations import chain_of, current_version
from rdf_persistence.persistence.services.decoding import error_text
from rdf_persistence.persistence.services.listing import Listings
from rdf_persistence.persistence.services.mapper import Mapper, generated_models_of
from rdf_persistence.persistence.services.session import Readable, Session
from rdf_persistence.persistence.services.store import (
    Store,
    ToolkitStore,
    TracedStore,
    system_name_of,
)
from rdf_persistence.provenance.domain.generated import rp_provenance
from rdf_persistence.provenance.domain.generated.rp_provenance import Activity
from rdf_persistence.provenance.services.provenance import activity_class_named
from rdf_persistence.schema.services.schema import load_schema
from rdf_persistence.schema.services.schema_structure import (
    iri_types,
    tenant_access_class,
)
from rdf_persistence.schema.services.vocabulary import TOOLKIT_MIGRATIONS, metamodel
from rdf_persistence.tenancy.services import tenant_dump, tenant_sweep
from rdf_persistence.tenancy.services.generated.rp_tenancy_services import (
    TenantDump,
    TenantSummary,
)
from rdf_persistence.tenancy.services.tenancy import (
    DEFAULT_STORE,
    GrantValidator,
    RootValidator,
    Tenancy,
)

log = logging.getLogger(__name__)


def toolkit_store(raw: Store) -> ToolkitStore:
    """The store the kit's services use: ``raw`` traced under its system name, then guarded (DEC-6)."""
    return ToolkitStore(TracedStore(raw, system_name_of(raw)))


class ServiceKit:
    """The collaborators of the routes. The consumer's composition root wires the ports in.

    A consumer's own route uses ``require`` and ``require_aggregate`` to get the same token check and
    access check the toolkit's routes have.
    """

    def __init__(
        self,
        *,
        schema: Path,
        generated: ModuleType,
        store: Store,
        files: FileStore,
        identity: Identity,
        verifier: TokenVerifier,
        rules: AccessRules,
        settings: ServiceSettings,
        migrations: Path,
        prefix: str = "",
        id_source: IdSource = draw_id,
        grant_validators: Sequence[GrantValidator] = (),
        root_validators: Sequence[RootValidator] = (),
        workflows: Sequence[Path] = (),
        stores: Mapping[str, Store] = {},
        event_bus: EventBus | None = None,
        toolkit: ToolkitSettings | None = None,
    ) -> None:
        """Build the kit; ``migrations``, ``prefix``, ``id_source``, the validators, ``workflows``, ``stores``, ``event_bus`` and ``toolkit`` are ``install_service``'s arguments of those names.

        ``toolkit`` (a fresh ``ToolkitSettings`` unless given) is kept as ``kit.toolkit``; the kit hands its
        ``limits`` to the documents, the mapper and the restore, its ``events`` to the hub and the relay, and
        the router its ``sse`` to the events route.

        ``store`` stays the default store as ``kit.store``; each of ``stores`` is wrapped in a ``ToolkitStore``
        for the tenancy (tenant-stores PD-3).

        The relay is built here, with ``event_bus`` (a constructor argument: the relay holds it).

        ``chains`` holds the toolkit's chain of migrations and then the consumer's, each with its
        schema id, as the migration runner takes them.

        Raises:
            InvalidWorkflow: A workflow file is not valid, or a class names a workflow no file defines.
            InvalidMigration: A chain of migration files, the toolkit's or the consumer's, is not valid.
            ValueError: A name in ``stores`` is ``default``, or one raw store is wired under two names
                (the default store included); ``Tenancy`` raises it and the message names the key.
        """
        view = load_schema(schema)
        self.view = view
        self.toolkit = toolkit or ToolkitSettings()
        # None at first, assignable: a handler's dependencies are often parts of this kit, so the bus
        # is built after it (message-bus PD-17)
        self.bus: MessageBus | None = None
        self.chains = (
            chain_of(metamodel(), TOOLKIT_MIGRATIONS),
            chain_of(view, migrations),
        )
        self.listings = Listings(view)
        self.store = toolkit_store(store)
        # one wrapper per raw store, so Tenancy's identity check sees a store wired twice (PD-16)
        wrapped = {id(store): self.store}
        for other in stores.values():
            wrapped.setdefault(id(other), toolkit_store(other))
        self.files = files
        self.identity = identity
        self.verifier = verifier
        self.iris = Iris(settings, *iri_types(view), id_source=id_source)
        self.rules = rules.with_iris(self.iris)
        self.settings = settings
        mounted = prefix.strip("/")
        # from the service's own base, never from a request: a Host header is the caller's to forge
        self.context_url = f"{settings.base}{mounted + '/' if mounted else ''}{CONTEXT_FILE}"
        assert settings.max_body_bytes is not None, "ServiceSettings defaults it"
        self.max_body_bytes: int = settings.max_body_bytes
        assert settings.max_restore_bytes is not None, "ServiceSettings defaults it"
        self.max_restore_bytes: int = settings.max_restore_bytes
        self.gate = Gate(self)
        self.system_database = system_database_name(settings.prefix)
        self.generated_folder = Path(next(iter(generated.__path__)))
        self.documents = Documents(
            view, self.generated_folder, self.iris, limits=self.toolkit.limits
        )
        self.documents.require_frames()
        models = generated_models_of(
            generated,
            rp_access,
            rp_core,
            rp_tenancy,
            rp_collections,
            rp_discussion,
            rp_files,
            rp_provenance,
            rp_workflow,
        )
        mapper = Mapper(view, models, limits=self.toolkit.limits)
        self.mapper, self.models = mapper, models
        self.workflows = Workflows.from_files(workflows, view, self.rules)
        access_class = cast(type[TenantAccess], models.named(tenant_access_class(view).name))
        self.tenancy = Tenancy(
            self.store,
            files,
            settings,
            mapper=mapper,
            root_class=models.named(self.documents.tenant_root.name),
            access_class=access_class,
            iris=self.iris,
            listings=self.listings,
            guards=WriteGuards(mapper, models, self.listings, self.workflows),
            removals=ReferencedRemovals(view, self.toolkit.limits),
            grant_validators=grant_validators,
            root_validators=root_validators,
            dependents=discussion_dependents(view),
            stamps=[(schema_id, current_version(chain)) for schema_id, chain in self.chains],
            on_commit=self._publish,
            stores={name: wrapped[id(other)] for name, other in stores.items()},
        )
        self.aggregates = Aggregates(self.documents, self.tenancy, self.iris)
        self.event_bus = event_bus
        self.hub = EventHub(events=self.toolkit.events)
        self.relay = Relay(
            self.tenancy,
            view,
            models,
            mapper,
            event_bus,
            self.hub,
            deployment=settings.deployment or "",
            context=context_link(settings.public_url, prefix),
            events=self.toolkit.events,
        )

    async def _publish(self, activity: Activity, session: Session) -> None:
        """The sessions' ``on_commit``: hand the activity to the bus, if one is set by now (PD-17), then wake the relay."""
        if self.bus is not None:
            await self.bus.publish(activity, session)
        self.relay.wake()

    async def receive(self, envelope: EventEnvelope, body: bytes) -> None:
        """What the event bus delivers to this deployment: hand another deployment's activity to the bus (PD-10).

        Returning acks the message; what is raised is not acked and comes again at the next start.
        Skipped, logged and acked: a message of this deployment's own origin, one received with no
        bus, one of an unknown class (or of a class that is not an activity) or whose body does not
        validate, one for a tenant this deployment lacks or whose id is no IRI, and one over the
        bus's message limit.

        Raises:
            TenantBehind: The tenant's migration failed at start-up.
            StoreUnavailable: The store does not answer.
        """
        if envelope.origin == self.settings.deployment:
            log.debug(
                "skipped an event this deployment published",
                extra=log_extra(
                    LogContext(step="receive-own-event", activity_class_iri=envelope.activity_class)
                ),
            )
        elif self.bus is None:
            log.debug(
                "skipped an event: the kit has no message bus",
                extra=log_extra(
                    LogContext(step="receive-no-bus", activity_class_iri=envelope.activity_class)
                ),
            )
        elif (activity := self._incoming(envelope, body)) is not None:
            await self._hand_over(envelope.tenant, activity, self.bus)

    def _incoming(self, envelope: EventEnvelope, body: bytes) -> Activity | None:
        """The activity the message carries; None, logged, if its class is unknown here or its body invalid."""
        try:
            cls = activity_class_named(self.view, self.models, envelope.activity_class)
            return cls.model_validate_json(body)
        except (LookupError, ValidationError) as error:
            # no exc_info: a validation error's traceback would print the body's values (PD-8)
            log.warning(
                "skipped an event whose class is unknown or whose body is invalid",
                extra=log_extra(
                    LogContext(
                        step="receive-invalid-event",
                        activity_class_iri=envelope.activity_class,
                        event_origin=envelope.origin,
                        error_type=error_type(error),
                        error_detail=error_text(error),
                    )
                ),
            )
            return None

    async def _hand_over(self, tenant: str, activity: Activity, bus: MessageBus) -> None:
        """Publish ``activity`` to ``bus`` in a session of the toolkit on ``tenant``, once the store answers."""
        toolkit = self.tenancy.toolkit.id
        try:
            # only a schema with no application class is a skip (D-6); a LookupError later is a failure
            opening = (
                self.application_session(toolkit)
                if tenant == self.tenancy.application
                else self.session(tenant, toolkit)
            )
        except (LookupError, ValueError) as error:
            log.warning(
                "skipped an event whose tenant has no session here",
                exc_info=error,
                extra=log_extra(
                    LogContext(
                        step="receive-no-session",
                        activity_id=activity.id,
                        tenant_id=tenant,
                        error_type=error_type(error),
                    )
                ),
            )
            return
        try:
            async with AsyncExitStack() as stack:
                try:
                    session = await stack.enter_async_context(opening)
                    # the probe: the database is there, the store answers
                    await session.is_recorded(activity.id)
                except ValueError as error:  # a tenant that is no IRI (D-19); never the observers'
                    log.warning(
                        "skipped an event whose tenant is no IRI",
                        exc_info=error,
                        extra=log_extra(
                            LogContext(
                                step="receive-invalid-tenant",
                                activity_id=activity.id,
                                tenant_id=tenant,
                                error_type=error_type(error),
                            )
                        ),
                    )
                    return
                await bus.publish(activity, session)
        except (DatabaseGone, NotFound) as error:
            log.warning(
                "skipped an event of a tenant this deployment lacks",
                exc_info=error,
                extra=log_extra(
                    LogContext(
                        step="receive-unknown-tenant",
                        activity_id=activity.id,
                        tenant_id=tenant,
                        error_type=error_type(error),
                    )
                ),
            )
        except MessageLimitExceeded as error:
            log.error(
                "an incoming event exceeded the message limit",
                exc_info=error,
                extra=log_extra(
                    LogContext(
                        step="receive-message-limit",
                        activity_id=activity.id,
                        message_limit=error.limit,
                        error_type=error_type(error),
                    )
                ),
            )

    def tenant_iri(self, tenant_id: str) -> str:
        """The IRI of the tenant whose id is ``tenant_id`` in a path.

        Raises:
            NotFound: ``tenant_id`` is not an id the IRI policy mints, so no tenant has it.
        """
        return str(self.iris.tenant(tenant_id))

    async def require(
        self, authorization: str | None, tenant_id: str, action: Action
    ) -> Authorised:
        """The caller's principal and access to the tenant, once its token is verified and it may take
        ``action`` there; ``checked_target`` is the tenant IRI.

        ``authorization`` is the ``Authorization`` header of the request; ``tenant_id`` is the tenant's
        id in the path.

        Raises:
            InvalidToken: No bearer token, or one the verifier refuses.
            NotFound: The tenant is not a tenant, or not visible to the caller.
            Forbidden: The caller may see the tenant but not take ``action`` in it.
        """
        caller = await self.gate.caller(authorization)
        access = await self.gate.tenant_access(caller, tenant_id, action)
        return self.gate.authorised(caller, access, access.tenant)

    async def require_aggregate(
        self,
        authorization: str | None,
        tenant_id: str,
        rp_path: str,
        aggregate_id: str,
        action: Action,
    ) -> Authorised:
        """Like ``require``, for ``action`` on one aggregate, whose rules (a Prohibition on it) apply too.

        The answer holds the IRI of the aggregate that was checked, to act on.

        Raises:
            InvalidToken: No bearer token, or one the verifier refuses.
            NotFound: The tenant or the aggregate id is not one, or not visible to the caller.
            Forbidden: The caller may see the aggregate but not take ``action`` on it.
        """
        caller = await self.gate.caller(authorization)
        return await self.gate.aggregate_access(caller, tenant_id, rp_path, aggregate_id, action)

    async def bucket_of(self, tenant: str) -> str:
        """The tenant's file bucket: the database name its access record stores (PD-6a).

        Raises:
            NotFound: The tenant has no access record.
        """
        record, _ = await self.tenancy.get(tenant)
        return record.database_name

    async def store_of(self, tenant: str) -> Store:
        """The store that holds the database of ``tenant``: its default store or a wired one (tenant-stores PD-9).

        Raises:
            NotFound: The tenant has no access record.
            StoreNotWired: The record names a store this service does not wire.
        """
        return await self.tenancy.store_of(tenant)

    async def sweep_tenant(
        self,
        tenant: str,
        *,
        remove: bool = False,
        remove_blobs: bool = False,
        older_than: timedelta = timedelta(hours=1),
    ) -> TenantSweepReport:
        """Find the loaded graphs no commit owns and the blobs no graph names in the active tenant,
        older than ``older_than``; delete the graphs if ``remove`` and the blobs if ``remove_blobs``.

        A dry run by default. Pass ``remove_blobs`` only when every blob key of the tenant is stored
        in ``rp:fileKey``. See ``rdf_persistence.tenancy.services.tenant_sweep.sweep_tenant``.

        Raises:
            NotFound: The tenant has no access record.
            Conflict: The tenant is being deleted.
        """
        return await tenant_sweep.sweep_tenant(
            self.tenancy,
            await self.store_of(tenant),
            self.files,
            self.iris,
            tenant,
            remove=remove,
            remove_blobs=remove_blobs,
            older_than=older_than,
        )

    async def dump_tenant(self, tenant: str, out: BinaryIO) -> TenantDump:
        """Write the active tenant, its graphs and its blobs, to ``out`` as one gzipped tar archive; answers the
        manifest, the archive's first member.

        Stop writes to the tenant for an exact copy: a blob deleted between the listing and its read is left out.
        Writing to ``out`` blocks (a synchronous file or buffer): run the call off the request loop, or give it a
        buffer and send that. Route it behind ``require(..., Action.ADMINISTER)``. See
        ``rdf_persistence.tenancy.services.tenant_dump.dump``.

        Raises:
            NotFound: The tenant has no access record.
            Conflict: The tenant is being deleted; nothing is written.
        """
        return await tenant_dump.dump(
            self.tenancy, await self.store_of(tenant), self.files, self.iris, self.view, tenant, out
        )

    async def restore_tenant(
        self, src: BinaryIO, creator: str, *, store: str = DEFAULT_STORE
    ) -> TenantSummary:
        """Create a new tenant, with a new IRI, from the archive ``dump_tenant`` wrote, which ``src`` holds; ``creator``
        (a principal IRI) is granted the creator role in it and no one else is. The new tenant's database is on the
        wired store named ``store``, ``default`` unless given.

        The archive must come from a service with the same schema, at any version of its migration chain (an
        older one is migrated to the running version before anything is created), and the same IRI policy, and may hold at most
        ``settings.max_restore_bytes`` once decompressed. Restore only an archive your own deployment wrote, or one
        from a party you trust as much as a tenant creator: the restore checks the archive's structure (its graph
        names, its root, its blob keys), not each object against its shapes, and not the workflow rule: the states
        of the aggregates and their transition records are restored as they were dumped. Nothing is created if it is refused,
        and nothing is left if the restore fails. There is no tenant yet, so ``require`` cannot guard it: verify the
        caller with ``gate.caller``, apply the consumer's own rule on who may create a tenant, and pass
        ``caller.principal`` as ``creator``. Reading ``src`` blocks (a synchronous file or buffer): run the call off
        the request loop. See ``rdf_persistence.tenancy.services.tenant_dump.restore``.

        Raises:
            InvalidBody: The archive is not a dump this service can restore, or is larger than
                ``max_restore_bytes`` decompressed.
            Conflict: The new tenant's id was taken at the same moment; retry the call.
            PersistenceError: The store or the object store failed, or a start-up sweep dropped the new
                database or bucket meanwhile, or ``store`` is not wired (``StoreNotWired``); nothing is left, except that a failed write of the access record
                leaves an unnamed database and bucket for the start-up sweep.
        """
        if store not in self.tenancy.stores():  # before anything reads ``src``
            raise StoreNotWired(
                f"the store {store!r} is not wired: {sorted(self.tenancy.stores())}"
            )
        return await tenant_dump.restore(
            self.tenancy,
            self.iris,
            self.view,
            src,
            Principal(id=creator),
            max_bytes=self.max_restore_bytes,
            chains=self.chains,
            store=store,
            limits=self.toolkit.limits,
        )

    async def remove_with_files(
        self,
        tenant: str,
        principal: str,
        iri: str,
        if_version: str,
        *,
        readable: Readable | None = None,
    ) -> None:
        """Remove the aggregate ``iri`` at ``if_version`` and delete the blobs only it names in
        ``rp:fileKey``. A blob that cannot be deleted is logged; the sweep removes it later.

        A consumer route should pass its collaboration's ``readable_referrers`` as ``readable``, to
        have the referrers the caller may read named when the removal is refused as in use; without
        it the refusal names nobody over HTTP (it counts every referrer as hidden).

        It removes whatever aggregate ``iri`` names and checks no class: with an IRI policy whose
        aggregate template names neither the type nor the path, check the type of what is stored
        there before calling it with an id from a request.

        Raises:
            NotFound: The tenant or the aggregate does not exist.
            Conflict: The aggregate is not at ``if_version``; nothing changed.
        """
        await file_removal.remove_with_files(
            self.tenancy,
            self.files,
            tenant,
            Principal(id=principal),
            iri,
            if_version,
            self.mapper,
            readable=readable,
        )

    @asynccontextmanager
    async def collaboration(self, authorised: Authorised) -> AsyncIterator[Collaboration]:
        """A collaboration on the tenant of ``authorised``, acting as its principal with its global roles.

        ``authorised`` must be the answer of ``require`` or ``require_aggregate``, never one built by
        hand: the collaboration trusts its principal and global roles, and checks access itself on
        every call.
        """
        caller = VerifiedCaller(
            principal=authorised.principal, global_roles=authorised.global_roles
        )
        access = authorised.caller_access
        async with self.session(access.tenant, authorised.principal) as session:
            yield Collaboration(
                session,
                view=self.view,
                rules=self.rules,
                iris=self.iris,
                mapper=self.mapper,
                models=self.models,
                listings=self.listings,
                caller=caller,
                access=access,
                workflows=self.workflows,
            )

    def session(self, tenant: str, principal: str) -> AbstractAsyncContextManager[Session]:
        """A session on the tenant's database for ``principal``."""
        return self.tenancy.tenant_session(tenant, Principal(id=principal))

    async def require_application(self, authorization: str | None, action: Action) -> Authorised:
        """The caller's principal, once its token is verified and its global roles permit ``action`` on
        application data; ``checked_target`` is the application IRI.

        The application is no tenant: no grant is read and the store is not called. A role defined at
        level ``system`` permits its actions here as it does in every tenant (PD-9). The answer is for
        ``application_session`` only: it is not an authorisation on any tenant.

        Raises:
            InvalidToken: No bearer token, or one the verifier refuses.
            Forbidden: The caller's global roles do not permit ``action``.
        """
        caller = await self.gate.caller(authorization)
        self.rules.require_application(caller, action)
        application = str(self.iris.application)
        access = CallerAccess(tenant=application, state=TenantState.ACTIVE)
        return self.gate.authorised(caller, access, application)

    def application_session(self, principal: str) -> AbstractAsyncContextManager[Session]:
        """A session on the application database for ``principal``; it takes application classes only.

        The session checks no right: call ``require_application`` first and pass it the principal it
        answers.

        Raises:
            LookupError: The schema declares no application class.
        """
        return self.tenancy.application_session(Principal(id=principal))

    def application_iri(self, cls: type[BaseModel]) -> str:
        """A new aggregate IRI of the application for the application class ``cls``.

        Raises:
            InvalidIri: ``cls`` is not an application class, a class served from the application database.
        """
        return self.tenancy.application_iri(cls)
