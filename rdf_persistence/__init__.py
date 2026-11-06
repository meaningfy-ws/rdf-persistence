"""RDF Persistence.

The domain and the generated classes are imported at once. The adapters and the services are loaded
on first use (``__getattr__``), so importing ``rdf_persistence.domain``, as every consumer's
generated module does, loads no HTTP client or service (PD-8c).
"""

from importlib import import_module
from typing import TYPE_CHECKING, Any

from rdf_persistence.domain.base import RpModel
from rdf_persistence.domain.exceptions import (
    BadQuery,
    Conflict,
    DatabaseGone,
    Forbidden,
    IdentityUnavailable,
    InvalidGraph,
    InvalidRoleDefinition,
    InvalidToken,
    NotFound,
    PersistenceError,
    StoreUnavailable,
    TenantGone,
    UnknownRole,
)
from rdf_persistence.domain.generated.rp_access import (
    Action,
    Grant,
    Policy,
    Prohibition,
    RoleDefinition,
    RoleLevel,
    Rule,
)
from rdf_persistence.domain.generated.rp_annotations import (
    Described,
    Tracked,
)
from rdf_persistence.domain.generated.rp_core import (
    AggregateRoot,
    DatabaseKind,
    GraphKind,
    ModuleKind,
    Principal,
    RegistryEntry,
    RegistryKind,
    RpAnnotation,
)
from rdf_persistence.domain.generated.rp_files import (
    RdfFormat,
    StoredFile,
)
from rdf_persistence.domain.generated.rp_provenance import (
    Activity,
    Provenanced,
)
from rdf_persistence.domain.generated.rp_tenancy import (
    TenantAccess,
    TenantLabelled,
    TenantState,
)
from rdf_persistence.domain.generated.service.rp_service import (
    AccountSummary,
    CallerAccess,
    GrantSet,
    LabelUpdate,
    Page,
    Problem,
    ServiceSettings,
    TenantCreate,
    TenantSummary,
    VerifiedCaller,
)

if TYPE_CHECKING:  # what the lazy names are, for type checkers and editors
    from rdf_persistence.adapters.fuseki import FusekiStore
    from rdf_persistence.adapters.jwks import JwksTokenVerifier
    from rdf_persistence.adapters.s3 import S3FileStore
    from rdf_persistence.adapters.zitadel import ZitadelIdentity, zitadel_roles_claim
    from rdf_persistence.services.access import (
        AccessRules,
        load_caller_access,
        load_role_definitions,
        validate_grants,
    )
    from rdf_persistence.services.files import FileStore
    from rdf_persistence.services.identity import Identity
    from rdf_persistence.services.mapper import Mapper, UnitOfWork, generated_models, new_part
    from rdf_persistence.services.session import Session, open_session
    from rdf_persistence.services.store import Store
    from rdf_persistence.services.sweep import sweep
    from rdf_persistence.services.tenancy import Tenancy
    from rdf_persistence.services.tokens import TokenVerifier

__version__ = "0.1.0"

_ADAPTERS, _SERVICES = "rdf_persistence.adapters", "rdf_persistence.services"
_LAZY_MODULES = {
    "FusekiStore": f"{_ADAPTERS}.fuseki",
    "JwksTokenVerifier": f"{_ADAPTERS}.jwks",
    "S3FileStore": f"{_ADAPTERS}.s3",
    "ZitadelIdentity": f"{_ADAPTERS}.zitadel",
    "zitadel_roles_claim": f"{_ADAPTERS}.zitadel",
    "Identity": f"{_SERVICES}.identity",
    "AccessRules": f"{_SERVICES}.access",
    "load_caller_access": f"{_SERVICES}.access",
    "load_role_definitions": f"{_SERVICES}.access",
    "validate_grants": f"{_SERVICES}.access",
    "TokenVerifier": f"{_SERVICES}.tokens",
    "FileStore": f"{_SERVICES}.files",
    "Mapper": f"{_SERVICES}.mapper",
    "UnitOfWork": f"{_SERVICES}.mapper",
    "generated_models": f"{_SERVICES}.mapper",
    "new_part": f"{_SERVICES}.mapper",
    "Session": f"{_SERVICES}.session",
    "open_session": f"{_SERVICES}.session",
    "Store": f"{_SERVICES}.store",
    "sweep": f"{_SERVICES}.sweep",
    "Tenancy": f"{_SERVICES}.tenancy",
}


def __getattr__(name: str) -> Any:
    """Load an adapter or service name on first use, then keep it."""
    if name not in _LAZY_MODULES:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(_LAZY_MODULES[name]), name)
    globals()[name] = value
    return value


__all__ = [
    "AccessRules",
    "AccountSummary",
    "Action",
    "Activity",
    "AggregateRoot",
    "BadQuery",
    "CallerAccess",
    "Conflict",
    "DatabaseGone",
    "DatabaseKind",
    "Described",
    "FileStore",
    "Forbidden",
    "FusekiStore",
    "Grant",
    "GrantSet",
    "GraphKind",
    "Identity",
    "IdentityUnavailable",
    "InvalidGraph",
    "InvalidRoleDefinition",
    "InvalidToken",
    "JwksTokenVerifier",
    "LabelUpdate",
    "Mapper",
    "ModuleKind",
    "NotFound",
    "Page",
    "PersistenceError",
    "Policy",
    "Principal",
    "Problem",
    "Prohibition",
    "Provenanced",
    "RdfFormat",
    "RegistryEntry",
    "RegistryKind",
    "RoleDefinition",
    "RoleLevel",
    "RpAnnotation",
    "RpModel",
    "Rule",
    "S3FileStore",
    "ServiceSettings",
    "Session",
    "Store",
    "StoreUnavailable",
    "StoredFile",
    "Tenancy",
    "TenantAccess",
    "TenantCreate",
    "TenantGone",
    "TenantLabelled",
    "TenantState",
    "TenantSummary",
    "TokenVerifier",
    "Tracked",
    "UnitOfWork",
    "UnknownRole",
    "VerifiedCaller",
    "ZitadelIdentity",
    "generated_models",
    "load_caller_access",
    "load_role_definitions",
    "new_part",
    "open_session",
    "sweep",
    "validate_grants",
    "zitadel_roles_claim",
]
