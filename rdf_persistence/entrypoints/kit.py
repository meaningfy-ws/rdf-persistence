"""What the routes share: the ports, the settings, and the pieces built from the application's schema (PD-13)."""

from contextlib import AbstractAsyncContextManager
from pathlib import Path
from types import ModuleType
from typing import cast

from rdf_persistence.domain.generated import rp_access, rp_core, rp_tenancy
from rdf_persistence.domain.generated.rp_access import Action
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.generated.rp_tenancy import TenantAccess
from rdf_persistence.domain.generated.service.rp_service import (
    Authorised,
    CallerAccess,
    ServiceSettings,
)
from rdf_persistence.domain.iris import system_database_name, tenant_iri
from rdf_persistence.entrypoints.auth import Gate
from rdf_persistence.services.access import AccessRules
from rdf_persistence.services.aggregates import Aggregates
from rdf_persistence.services.artifacts import CONTEXT_FILE
from rdf_persistence.services.documents import Documents
from rdf_persistence.services.files import FileStore
from rdf_persistence.services.identity import Identity
from rdf_persistence.services.listing import Listings
from rdf_persistence.services.mapper import Mapper, generated_models_of
from rdf_persistence.services.schema import load_schema
from rdf_persistence.services.schema_structure import tenant_access_class
from rdf_persistence.services.session import Session
from rdf_persistence.services.store import Store, ToolkitStore
from rdf_persistence.services.tenancy import Tenancy
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
    ) -> None:
        """Build the kit; ``prefix`` is the path the routes are mounted under (``install_service``'s)."""
        view = load_schema(schema)
        self.view = view
        self.listings = Listings(view)
        self.store = ToolkitStore(store)
        self.files = files
        self.identity = identity
        self.verifier = verifier
        self.rules = rules
        self.settings = settings
        mounted = prefix.strip("/")
        # from the service's own base, never from a request: a Host header is the caller's to forge
        self.context_url = f"{settings.base}{mounted + '/' if mounted else ''}{CONTEXT_FILE}"
        assert settings.max_body_bytes is not None, "ServiceSettings defaults it"
        self.max_body_bytes: int = settings.max_body_bytes
        self.gate = Gate(self)
        self.system_database = system_database_name(settings.prefix)
        self.generated_folder = Path(next(iter(generated.__path__)))
        self.documents = Documents(view, self.generated_folder)
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
        )
        self.aggregates = Aggregates(self.documents, self.tenancy)

    def tenant_iri(self, tenant_id: str) -> str:
        """The IRI of the tenant whose id is ``tenant_id`` in a path.

        Raises:
            NotFound: ``tenant_id`` is not a canonical UUID, so no tenant has it.
        """
        return str(tenant_iri(self.settings.base, self.settings.tenant_segment, tenant_id))

    async def require(
        self, authorization: str | None, tenant_id: str, action: Action
    ) -> CallerAccess:
        """The caller's access to the tenant, once its token is verified and it may take ``action`` there.

        ``authorization`` is the ``Authorization`` header of the request; ``tenant_id`` is the tenant's
        id in the path.

        Raises:
            InvalidToken: No bearer token, or one the verifier refuses.
            NotFound: The tenant is not a tenant, or not visible to the caller.
            Forbidden: The caller may see the tenant but not take ``action`` in it.
        """
        caller = await self.gate.caller(authorization)
        return await self.gate.tenant_access(caller, tenant_id, action)

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

    def session(self, tenant: str, principal: str) -> AbstractAsyncContextManager[Session]:
        """A session on the tenant's database for ``principal``."""
        return self.tenancy.tenant_session(tenant, Principal(id=principal))
