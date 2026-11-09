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
    InvalidBody,
    InvalidGrant,
    InvalidGraph,
    InvalidIri,
    InvalidRoleDefinition,
    InvalidToken,
    NotAcceptable,
    NotFound,
    PayloadTooLarge,
    PersistenceError,
    PreconditionRequired,
    StoredDataInvalid,
    StoreUnavailable,
    TenantGone,
    UnknownRole,
    UnsupportedMediaType,
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
    WritesKind,
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
    Authorised,
    CallerAccess,
    GrantSet,
    IdKind,
    IdSpec,
    IriPolicy,
    LabelUpdate,
    Page,
    Problem,
    ProblemKind,
    ServiceSettings,
    TenantCreate,
    TenantSummary,
    VerifiedCaller,
)
from rdf_persistence.domain.iris import DEFAULT_IRIS, IdSource, Iris, mint_aggregate_iri

if TYPE_CHECKING:  # what the lazy names are, for type checkers and editors
    from rdf_persistence.adapters.fuseki import FusekiStore
    from rdf_persistence.adapters.jwks import JwksTokenVerifier
    from rdf_persistence.adapters.s3 import S3FileStore
    from rdf_persistence.adapters.zitadel import ZitadelIdentity, zitadel_roles_claim
    from rdf_persistence.entrypoints.kit import ServiceKit
    from rdf_persistence.entrypoints.router import limited_body
    from rdf_persistence.entrypoints.service import install_service
    from rdf_persistence.services.access import (
        AccessRules,
        load_caller_access,
        load_role_definitions,
    )
    from rdf_persistence.services.files import FileStore
    from rdf_persistence.services.identity import Identity
    from rdf_persistence.services.listing import Listings
    from rdf_persistence.services.mapper import Mapper, UnitOfWork, generated_models, new_part
    from rdf_persistence.services.schema import load_schema
    from rdf_persistence.services.session import Session, open_session
    from rdf_persistence.services.store import Store
    from rdf_persistence.services.sweep import sweep
    from rdf_persistence.services.tenancy import GrantValidator, RootValidator, Tenancy
    from rdf_persistence.services.tokens import TokenVerifier

__version__ = "0.1.0"

_ADAPTERS, _SERVICES = "rdf_persistence.adapters", "rdf_persistence.services"
_ENTRYPOINTS = "rdf_persistence.entrypoints"
_LAZY_MODULES = {
    "FusekiStore": f"{_ADAPTERS}.fuseki",
    "JwksTokenVerifier": f"{_ADAPTERS}.jwks",
    "S3FileStore": f"{_ADAPTERS}.s3",
    "ZitadelIdentity": f"{_ADAPTERS}.zitadel",
    "zitadel_roles_claim": f"{_ADAPTERS}.zitadel",
    "install_service": f"{_ENTRYPOINTS}.service",
    "ServiceKit": f"{_ENTRYPOINTS}.kit",
    "limited_body": f"{_ENTRYPOINTS}.router",
    "Identity": f"{_SERVICES}.identity",
    "AccessRules": f"{_SERVICES}.access",
    "load_caller_access": f"{_SERVICES}.access",
    "load_role_definitions": f"{_SERVICES}.access",
    "TokenVerifier": f"{_SERVICES}.tokens",
    "FileStore": f"{_SERVICES}.files",
    "Mapper": f"{_SERVICES}.mapper",
    "UnitOfWork": f"{_SERVICES}.mapper",
    "generated_models": f"{_SERVICES}.mapper",
    "new_part": f"{_SERVICES}.mapper",
    "Listings": f"{_SERVICES}.listing",
    "load_schema": f"{_SERVICES}.schema",
    "Session": f"{_SERVICES}.session",
    "open_session": f"{_SERVICES}.session",
    "Store": f"{_SERVICES}.store",
    "sweep": f"{_SERVICES}.sweep",
    "Tenancy": f"{_SERVICES}.tenancy",
    "GrantValidator": f"{_SERVICES}.tenancy",
    "RootValidator": f"{_SERVICES}.tenancy",
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
    "Authorised",
    "BadQuery",
    "CallerAccess",
    "Conflict",
    "DatabaseGone",
    "DEFAULT_IRIS",
    "DatabaseKind",
    "Described",
    "FileStore",
    "Forbidden",
    "FusekiStore",
    "Grant",
    "GrantSet",
    "GrantValidator",
    "GraphKind",
    "IdKind",
    "IdSource",
    "IdSpec",
    "Identity",
    "IdentityUnavailable",
    "InvalidBody",
    "InvalidGraph",
    "InvalidIri",
    "InvalidGrant",
    "InvalidRoleDefinition",
    "InvalidToken",
    "IriPolicy",
    "Iris",
    "JwksTokenVerifier",
    "LabelUpdate",
    "Listings",
    "Mapper",
    "ModuleKind",
    "NotAcceptable",
    "NotFound",
    "Page",
    "PayloadTooLarge",
    "PersistenceError",
    "PreconditionRequired",
    "Policy",
    "Principal",
    "Problem",
    "ProblemKind",
    "Prohibition",
    "Provenanced",
    "RdfFormat",
    "RegistryEntry",
    "RegistryKind",
    "RoleDefinition",
    "RoleLevel",
    "RootValidator",
    "RpAnnotation",
    "RpModel",
    "Rule",
    "S3FileStore",
    "ServiceKit",
    "ServiceSettings",
    "Session",
    "Store",
    "StoreUnavailable",
    "StoredDataInvalid",
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
    "UnsupportedMediaType",
    "VerifiedCaller",
    "WritesKind",
    "ZitadelIdentity",
    "generated_models",
    "install_service",
    "limited_body",
    "load_caller_access",
    "load_role_definitions",
    "load_schema",
    "mint_aggregate_iri",
    "new_part",
    "open_session",
    "sweep",
    "zitadel_roles_claim",
]
