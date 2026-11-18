"""RDF Persistence.

The domain and the generated classes are imported at once. The adapters and the services are loaded
on first use (``__getattr__``), so importing ``rdf_persistence.core.domain``, as every consumer's
generated module does, loads no HTTP client or service (PD-8c).
"""

from importlib import import_module
from importlib.metadata import version
from typing import TYPE_CHECKING, Any

from rdf_persistence.core.domain.base import RpModel
from rdf_persistence.core.domain.exceptions import (
    BadQuery,
    CommitTooLarge,
    Conflict,
    DatabaseGone,
    Forbidden,
    IdentityUnavailable,
    InvalidBody,
    InvalidGrant,
    InvalidGraph,
    InvalidIri,
    InvalidMigration,
    InvalidRoleDefinition,
    InvalidToken,
    InvalidWorkflow,
    KeyConflict,
    MessageLimitExceeded,
    MigrationFailed,
    NotAcceptable,
    NotFound,
    PayloadTooLarge,
    PersistenceError,
    PreconditionRequired,
    StoredDataInvalid,
    StoreNotWired,
    StoreUnavailable,
    TenantBehind,
    TenantGone,
    UnknownRole,
    UnsupportedMediaType,
)
from rdf_persistence.core.domain.generated.rp_access import (
    Action,
    Grant,
    Policy,
    Prohibition,
    RoleDefinition,
    RoleLevel,
    Rule,
)
from rdf_persistence.core.domain.generated.rp_annotations import (
    Described,
    Tracked,
)
from rdf_persistence.core.domain.generated.rp_collections import (
    MembershipRule,
    ReferenceCollection,
    SlotEquality,
)
from rdf_persistence.core.domain.generated.rp_core import (
    AggregateKey,
    AggregateRoot,
    CommitMarker,
    DatabaseKind,
    GraphKind,
    KeyDuplicate,
    ModuleKind,
    PendingLoad,
    Principal,
    RegistryEntry,
    RegistryKind,
    RpAnnotation,
    UniqueScope,
    WritesKind,
)
from rdf_persistence.core.domain.generated.rp_discussion import (
    Comment,
    Motivation,
    PostComment,
    PostReply,
)
from rdf_persistence.core.domain.generated.rp_files import (
    BlobEntry,
    DeleteFile,
    RdfFormat,
    StoredFile,
)
from rdf_persistence.core.domain.generated.rp_provenance import (
    Activity,
    Add,
    Generation,
    Invalidation,
    Provenanced,
    Remove,
    Replace,
)
from rdf_persistence.core.domain.generated.rp_tenancy import (
    TenantAccess,
    TenantLabelled,
    TenantState,
    TenantSweepReport,
)
from rdf_persistence.core.domain.generated.rp_workflow import (
    Transition,
    UnderWorkflow,
    Workflow,
    WorkflowTransition,
)

if TYPE_CHECKING:  # what the lazy names are, for type checkers and editors
    from rdf_persistence.adapters.fuseki import FusekiStore
    from rdf_persistence.adapters.jwks import JwksTokenVerifier
    from rdf_persistence.adapters.s3 import S3FileStore
    from rdf_persistence.adapters.zitadel import ZitadelIdentity, zitadel_roles_claim
    from rdf_persistence.core.services.generated.rp_core_services import HttpSettings
    from rdf_persistence.entrypoints.environment import settings_from_env
    from rdf_persistence.entrypoints.kit import ServiceKit
    from rdf_persistence.entrypoints.router import limited_body
    from rdf_persistence.entrypoints.service import install_service
    from rdf_persistence.iris.services.generated.rp_iris_services import (
        IdKind,
        IdSpec,
        IriPolicy,
        ServiceSettings,
    )
    from rdf_persistence.iris.services.iris import DEFAULT_IRIS, IdSource, Iris, mint_aggregate_iri
    from rdf_persistence.services.access import (
        AccessRules,
        load_caller_access,
        load_role_definitions,
    )
    from rdf_persistence.services.collaboration import Collaboration
    from rdf_persistence.services.events import EventBus, Receive, context_link
    from rdf_persistence.services.file_removal import remove_with_files
    from rdf_persistence.services.files import FileStore
    from rdf_persistence.services.generated.service.rp_service import (
        AccountSummary,
        Authorised,
        CallerAccess,
        EventEnvelope,
        GrantSet,
        LabelUpdate,
        MemberList,
        Page,
        Problem,
        ProblemKind,
        Referrer,
        ReferrerList,
        TenantCreate,
        TenantDump,
        TenantSummary,
        VerifiedCaller,
    )
    from rdf_persistence.services.generated.settings.rp_settings import (
        DirectorySettings,
        EventSettings,
        JwksSettings,
        LimitSettings,
        SseSettings,
        ToolkitSettings,
    )
    from rdf_persistence.services.identity import Identity
    from rdf_persistence.services.listing import Listings
    from rdf_persistence.services.mapper import Mapper, UnitOfWork, generated_models, new_part
    from rdf_persistence.services.messagebus import MessageBus, Work, bootstrap, command
    from rdf_persistence.services.schema import load_schema
    from rdf_persistence.services.session import Session, open_session
    from rdf_persistence.services.store import Store
    from rdf_persistence.services.sweep import sweep
    from rdf_persistence.services.tenancy import GrantValidator, RootValidator, Tenancy
    from rdf_persistence.services.tenant_sweep import sweep_tenant
    from rdf_persistence.services.tokens import TokenVerifier
    from rdf_persistence.services.workflows import Workflows

__version__ = version("rdf-persistence")

_ADAPTERS, _SERVICES = "rdf_persistence.adapters", "rdf_persistence.services"
_ENTRYPOINTS = "rdf_persistence.entrypoints"
_IRIS_MODELS = "rdf_persistence.iris.services.generated.rp_iris_services"
_IRIS = "rdf_persistence.iris.services.iris"
_SERVICE_MODELS = f"{_SERVICES}.generated.service.rp_service"
_SETTINGS_MODELS = f"{_SERVICES}.generated.settings.rp_settings"
_LAZY_MODULES = {
    "HttpSettings": "rdf_persistence.core.services.generated.rp_core_services",
    **dict.fromkeys(
        (
            "DirectorySettings",
            "EventSettings",
            "JwksSettings",
            "LimitSettings",
            "SseSettings",
            "ToolkitSettings",
        ),
        _SETTINGS_MODELS,
    ),
    "settings_from_env": f"{_ENTRYPOINTS}.environment",
    **dict.fromkeys(
        (
            "AccountSummary",
            "Authorised",
            "CallerAccess",
            "EventEnvelope",
            "GrantSet",
            "LabelUpdate",
            "MemberList",
            "Page",
            "Problem",
            "ProblemKind",
            "Referrer",
            "ReferrerList",
            "TenantCreate",
            "TenantDump",
            "TenantSummary",
            "VerifiedCaller",
        ),
        _SERVICE_MODELS,
    ),
    **dict.fromkeys(("IdKind", "IdSpec", "IriPolicy", "ServiceSettings"), _IRIS_MODELS),
    "FusekiStore": f"{_ADAPTERS}.fuseki",
    "JwksTokenVerifier": f"{_ADAPTERS}.jwks",
    "S3FileStore": f"{_ADAPTERS}.s3",
    "ZitadelIdentity": f"{_ADAPTERS}.zitadel",
    "zitadel_roles_claim": f"{_ADAPTERS}.zitadel",
    "install_service": f"{_ENTRYPOINTS}.service",
    "ServiceKit": f"{_ENTRYPOINTS}.kit",
    "limited_body": f"{_ENTRYPOINTS}.router",
    "Identity": f"{_SERVICES}.identity",
    **dict.fromkeys(("DEFAULT_IRIS", "IdSource", "Iris", "mint_aggregate_iri"), _IRIS),
    "EventBus": f"{_SERVICES}.events",
    "Receive": f"{_SERVICES}.events",
    "context_link": f"{_SERVICES}.events",
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
    "sweep_tenant": f"{_SERVICES}.tenant_sweep",
    "remove_with_files": f"{_SERVICES}.file_removal",
    "Tenancy": f"{_SERVICES}.tenancy",
    "GrantValidator": f"{_SERVICES}.tenancy",
    "RootValidator": f"{_SERVICES}.tenancy",
    "Collaboration": f"{_SERVICES}.collaboration",
    "Workflows": f"{_SERVICES}.workflows",
    "MessageBus": f"{_SERVICES}.messagebus",
    "Work": f"{_SERVICES}.messagebus",
    "command": f"{_SERVICES}.messagebus",
    "bootstrap": f"{_SERVICES}.messagebus",
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
    "Add",
    "AggregateKey",
    "AggregateRoot",
    "Authorised",
    "BadQuery",
    "BlobEntry",
    "CallerAccess",
    "Collaboration",
    "Comment",
    "CommitMarker",
    "CommitTooLarge",
    "Conflict",
    "KeyConflict",
    "DatabaseGone",
    "DEFAULT_IRIS",
    "DatabaseKind",
    "DeleteFile",
    "Described",
    "DirectorySettings",
    "EventSettings",
    "EventEnvelope",
    "EventBus",
    "FileStore",
    "Forbidden",
    "FusekiStore",
    "Generation",
    "Grant",
    "GrantSet",
    "GrantValidator",
    "GraphKind",
    "HttpSettings",
    "IdKind",
    "IdSource",
    "IdSpec",
    "Identity",
    "IdentityUnavailable",
    "InvalidBody",
    "InvalidGraph",
    "InvalidIri",
    "InvalidGrant",
    "InvalidMigration",
    "InvalidRoleDefinition",
    "InvalidToken",
    "InvalidWorkflow",
    "Invalidation",
    "IriPolicy",
    "Iris",
    "JwksSettings",
    "JwksTokenVerifier",
    "KeyDuplicate",
    "LabelUpdate",
    "LimitSettings",
    "Listings",
    "Mapper",
    "MemberList",
    "MembershipRule",
    "MessageBus",
    "MessageLimitExceeded",
    "MigrationFailed",
    "ModuleKind",
    "Motivation",
    "NotAcceptable",
    "NotFound",
    "Page",
    "Receive",
    "PayloadTooLarge",
    "PendingLoad",
    "PersistenceError",
    "PostComment",
    "PostReply",
    "PreconditionRequired",
    "Policy",
    "Principal",
    "Problem",
    "ProblemKind",
    "Prohibition",
    "Provenanced",
    "RdfFormat",
    "ReferenceCollection",
    "Referrer",
    "ReferrerList",
    "RegistryEntry",
    "RegistryKind",
    "Remove",
    "Replace",
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
    "SlotEquality",
    "SseSettings",
    "Store",
    "StoreUnavailable",
    "StoredDataInvalid",
    "StoredFile",
    "Tenancy",
    "TenantAccess",
    "StoreNotWired",
    "TenantBehind",
    "TenantCreate",
    "TenantDump",
    "TenantGone",
    "TenantLabelled",
    "TenantState",
    "TenantSweepReport",
    "TenantSummary",
    "TokenVerifier",
    "ToolkitSettings",
    "Tracked",
    "Transition",
    "UnderWorkflow",
    "UniqueScope",
    "UnitOfWork",
    "UnknownRole",
    "UnsupportedMediaType",
    "VerifiedCaller",
    "Workflow",
    "WorkflowTransition",
    "Work",
    "Workflows",
    "WritesKind",
    "ZitadelIdentity",
    "command",
    "context_link",
    "bootstrap",
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
    "sweep_tenant",
    "remove_with_files",
    "settings_from_env",
    "zitadel_roles_claim",
]
