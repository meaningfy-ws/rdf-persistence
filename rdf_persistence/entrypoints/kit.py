"""What the routes share: the ports, the settings, and the pieces built from the application's schema (PD-13)."""

from collections.abc import AsyncIterator, Sequence
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from datetime import timedelta
from pathlib import Path
from types import ModuleType
from typing import BinaryIO, cast

from rdf_persistence.domain.generated import rp_access, rp_core, rp_tenancy
from rdf_persistence.domain.generated.rp_access import Action
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.generated.rp_tenancy import TenantAccess, TenantSweepReport
from rdf_persistence.domain.generated.service.rp_service import (
    Authorised,
    ServiceSettings,
    TenantDump,
    TenantSummary,
    VerifiedCaller,
)
from rdf_persistence.domain.iris import IdSource, Iris, draw_id, system_database_name
from rdf_persistence.entrypoints.auth import Gate
from rdf_persistence.services import file_removal, tenant_dump, tenant_sweep
from rdf_persistence.services.access import AccessRules
from rdf_persistence.services.aggregates import Aggregates
from rdf_persistence.services.artifacts import CONTEXT_FILE
from rdf_persistence.services.collaboration import Collaboration
from rdf_persistence.services.documents import Documents
from rdf_persistence.services.files import FileStore
from rdf_persistence.services.identity import Identity
from rdf_persistence.services.listing import Listings
from rdf_persistence.services.mapper import Mapper, generated_models_of
from rdf_persistence.services.schema import load_schema
from rdf_persistence.services.schema_structure import iri_types, tenant_access_class
from rdf_persistence.services.session import Session
from rdf_persistence.services.store import Store, ToolkitStore
from rdf_persistence.services.tenancy import GrantValidator, RootValidator, Tenancy
from rdf_persistence.services.tokens import TokenVerifier


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
        prefix: str = "",
        id_source: IdSource = draw_id,
        grant_validators: Sequence[GrantValidator] = (),
        root_validators: Sequence[RootValidator] = (),
    ) -> None:
        """Build the kit; ``prefix``, ``id_source`` and the validators are ``install_service``'s arguments of those names."""
        view = load_schema(schema)
        self.view = view
        self.listings = Listings(view)
        self.store = ToolkitStore(store)
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
        self.documents = Documents(view, self.generated_folder, self.iris)
        self.documents.require_frames()
        models = generated_models_of(generated, rp_access, rp_core, rp_tenancy)
        access_class = cast(type[TenantAccess], models.named(tenant_access_class(view).name))
        self.tenancy = Tenancy(
            self.store,
            files,
            settings,
            mapper=Mapper(view, models),
            root_class=models.named(self.documents.tenant_root.name),
            access_class=access_class,
            iris=self.iris,
            listings=self.listings,
            grant_validators=grant_validators,
            root_validators=root_validators,
        )
        self.aggregates = Aggregates(self.documents, self.tenancy, self.iris)

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
        return Authorised(
            principal=caller.principal,
            caller_access=access,
            checked_target=access.tenant,
            global_roles=caller.global_roles,
        )

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
        in ``rp:fileKey``. See ``rdf_persistence.services.tenant_sweep.sweep_tenant``.

        Raises:
            NotFound: The tenant has no access record.
            Conflict: The tenant is being deleted.
        """
        return await tenant_sweep.sweep_tenant(
            self.tenancy,
            self.store,
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
        ``rdf_persistence.services.tenant_dump.dump``.

        Raises:
            NotFound: The tenant has no access record.
            Conflict: The tenant is being deleted; nothing is written.
        """
        return await tenant_dump.dump(
            self.tenancy, self.store, self.files, self.iris, self.view, tenant, out
        )

    async def restore_tenant(self, src: BinaryIO, creator: str) -> TenantSummary:
        """Create a new tenant, with a new IRI, from the archive ``dump_tenant`` wrote, which ``src`` holds; ``creator``
        (a principal IRI) is granted the creator role in it and no one else is.

        The archive must come from a service with the same schema and IRI policy, and may hold at most
        ``settings.max_restore_bytes`` once decompressed. Restore only an archive your own deployment wrote, or one
        from a party you trust as much as a tenant creator: the restore checks the archive's structure (its graph
        names, its root, its blob keys), not each object against its shapes. Nothing is created if it is refused,
        and nothing is left if the restore fails. There is no tenant yet, so ``require`` cannot guard it: verify the
        caller with ``gate.caller``, apply the consumer's own rule on who may create a tenant, and pass
        ``caller.principal`` as ``creator``. Reading ``src`` blocks (a synchronous file or buffer): run the call off
        the request loop. See ``rdf_persistence.services.tenant_dump.restore``.

        Raises:
            InvalidBody: The archive is not a dump this service can restore, or is larger than
                ``max_restore_bytes`` decompressed.
            Conflict: The new tenant's id was taken at the same moment; retry the call.
            PersistenceError: The store or the object store failed, or a start-up sweep dropped the new
                database or bucket meanwhile; nothing is left, except that a failed write of the access record
                leaves an unnamed database and bucket for the start-up sweep.
        """
        return await tenant_dump.restore(
            self.tenancy,
            self.iris,
            self.view,
            src,
            Principal(id=creator),
            max_bytes=self.max_restore_bytes,
        )

    async def remove_with_files(
        self, tenant: str, principal: str, iri: str, if_version: str
    ) -> None:
        """Remove the aggregate ``iri`` at ``if_version`` and delete the blobs only it names in
        ``rp:fileKey``. A blob that cannot be deleted is logged; the sweep removes it later.

        Raises:
            NotFound: The tenant or the aggregate does not exist.
            Conflict: The aggregate is not at ``if_version``; nothing changed.
        """
        await file_removal.remove_with_files(
            self.tenancy, self.files, tenant, Principal(id=principal), iri, if_version
        )

    @asynccontextmanager
    async def collaboration(self, authorised: Authorised) -> AsyncIterator[Collaboration]:
        """A collaboration on the tenant of ``authorised``, acting as its principal with its global roles.

        ``authorised`` is the answer of ``require`` or ``require_aggregate``.
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
                caller=caller,
                access=access,
            )

    def session(self, tenant: str, principal: str) -> AbstractAsyncContextManager[Session]:
        """A session on the tenant's database for ``principal``."""
        return self.tenancy.tenant_session(tenant, Principal(id=principal))
