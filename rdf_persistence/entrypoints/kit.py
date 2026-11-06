"""What the routes share: the ports, the settings, and the pieces built from the application's schema (PD-13)."""

import importlib
import pkgutil
from contextlib import AbstractAsyncContextManager
from pathlib import Path
from types import ModuleType
from typing import cast
from uuid import UUID

from rdf_persistence.domain.exceptions import NotFound
from rdf_persistence.domain.generated import rp_access, rp_core, rp_tenancy
from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.generated.rp_tenancy import TenantAccess
from rdf_persistence.domain.generated.service.rp_service import ServiceSettings
from rdf_persistence.domain.iris import system_database_name, tenant_resource_name
from rdf_persistence.services.access import AccessRules
from rdf_persistence.services.documents import Documents
from rdf_persistence.services.files import FileStore
from rdf_persistence.services.identity import Identity
from rdf_persistence.services.mapper import Mapper, generated_models
from rdf_persistence.services.schema import load_schema
from rdf_persistence.services.schema_structure import tenant_access_class
from rdf_persistence.services.session import Session, open_session
from rdf_persistence.services.store import Store
from rdf_persistence.services.tenancy import Tenancy
from rdf_persistence.services.tokens import TokenVerifier


class ServiceKit:
    """The collaborators of the routes. The consumer's composition root wires the ports in."""

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
    ) -> None:
        view = load_schema(schema)
        self.store = store
        self.files = files
        self.identity = identity
        self.verifier = verifier
        self.rules = rules
        self.settings = settings
        self.system_database = system_database_name(settings.prefix)
        self.documents = Documents(view, Path(next(iter(generated.__path__))))
        models = generated_models(*_modules_of(generated), rp_access, rp_core, rp_tenancy)
        self.tenant_root_model = models.named(self.documents.tenant_root.name)
        access_class = cast(type[TenantAccess], models.named(tenant_access_class(view).name))
        self.tenancy = Tenancy(
            store, files, settings, mapper=Mapper(view, models), access_class=access_class
        )

    def tenant_iri(self, tenant_id: str) -> str:
        """The IRI of the tenant whose id is ``tenant_id`` in a path.

        Raises:
            NotFound: ``tenant_id`` is not a canonical UUID, so no tenant has it.
        """
        try:
            canonical = str(UUID(tenant_id)) == tenant_id
        except ValueError:
            canonical = False
        if not canonical:
            raise NotFound(f"no tenant {tenant_id!r}")
        return f"{self.settings.base}{self.settings.tenant_segment}/{tenant_id}"

    def session(self, tenant: str, principal: str) -> AbstractAsyncContextManager[Session]:
        """A session on the tenant's database for ``principal``."""
        return open_session(
            self.store,
            database=tenant_resource_name(self.settings.prefix, tenant),
            tenant_iri=tenant,
            principal=Principal(id=principal),
        )


def _modules_of(package: ModuleType) -> list[ModuleType]:
    """The generated modules of a package: one per module of the application's schema."""
    return [
        importlib.import_module(f"{package.__name__}.{info.name}")
        for info in pkgutil.iter_modules(package.__path__)
    ]
