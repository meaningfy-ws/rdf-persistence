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
    from rdf_persistence.access.adapters.jwks import JwksTokenVerifier
    from rdf_persistence.access.adapters.zitadel import ZitadelIdentity, zitadel_roles_claim
    from rdf_persistence.access.services.access import (
        AccessRules,
        load_caller_access,
        load_role_definitions,
    )
    from rdf_persistence.access.services.generated.rp_access_services import (
        AccountSummary,
        CallerAccess,
        GrantSet,
        VerifiedCaller,
    )
    from rdf_persistence.access.services.generated.settings.rp_access_settings import (
        DirectorySettings,
        JwksSettings,
    )
    from rdf_persistence.access.services.identity import Identity
    from rdf_persistence.access.services.tokens import TokenVerifier
    from rdf_persistence.collaboration.services.collaboration import Collaboration
    from rdf_persistence.collaboration.services.generated.rp_collaboration_services import (
        MemberList,
        Referrer,
        ReferrerList,
    )
    from rdf_persistence.collaboration.services.workflows import Workflows
    from rdf_persistence.core.services.generated.rp_core_services import HttpSettings
    from rdf_persistence.entrypoints.environment import settings_from_env
    from rdf_persistence.entrypoints.kit import ServiceKit
    from rdf_persistence.entrypoints.router import limited_body
    from rdf_persistence.entrypoints.service import install_service
    from rdf_persistence.events.services.events import EventBus, Receive, context_link
    from rdf_persistence.events.services.generated.rp_events_services import EventEnvelope
    from rdf_persistence.events.services.generated.settings.rp_events_settings import (
        EventSettings,
    )
    from rdf_persistence.files.adapters.s3 import S3FileStore
    from rdf_persistence.files.services.files import FileStore
    from rdf_persistence.iris.services.generated.rp_iris_services import (
        IdKind,
        IdSpec,
        IriPolicy,
        ServiceSettings,
    )
    from rdf_persistence.iris.services.iris import DEFAULT_IRIS, IdSource, Iris, mint_aggregate_iri
    from rdf_persistence.messaging.services.messagebus import MessageBus, Work, bootstrap, command
    from rdf_persistence.persistence.adapters.fuseki import FusekiStore
    from rdf_persistence.persistence.services.generated.rp_persistence_services import Page
    from rdf_persistence.persistence.services.generated.settings.rp_persistence_settings import (
        LimitSettings,
    )
    from rdf_persistence.persistence.services.listing import Listings
    from rdf_persistence.persistence.services.mapper import (
        Mapper,
        UnitOfWork,
        generated_models,
        new_part,
    )
    from rdf_persistence.persistence.services.session import Session, open_session
    from rdf_persistence.persistence.services.store import Store
    from rdf_persistence.schema.services.schema import load_schema
    from rdf_persistence.services.file_removal import remove_with_files
    from rdf_persistence.services.generated.service.rp_service import (
        Authorised,
        LabelUpdate,
        Problem,
        ProblemKind,
        TenantCreate,
    )
    from rdf_persistence.services.generated.settings.rp_settings import (
        SseSettings,
        ToolkitSettings,
    )
    from rdf_persistence.tenancy.services.generated.rp_tenancy_services import (
        TenantDump,
        TenantSummary,
    )
    from rdf_persistence.tenancy.services.sweep import sweep
    from rdf_persistence.tenancy.services.tenancy import GrantValidator, RootValidator, Tenancy
    from rdf_persistence.tenancy.services.tenant_sweep import sweep_tenant

__version__ = version("rdf-persistence")

_SERVICES = "rdf_persistence.services"
_EVENTS = "rdf_persistence.events.services"
_EVENTS_MODELS = f"{_EVENTS}.generated.rp_events_services"
_EVENTS_SETTINGS_MODELS = f"{_EVENTS}.generated.settings.rp_events_settings"
_COLLABORATION = "rdf_persistence.collaboration.services"
_COLLABORATION_MODELS = f"{_COLLABORATION}.generated.rp_collaboration_services"
_MESSAGING = "rdf_persistence.messaging.services"
_ENTRYPOINTS = "rdf_persistence.entrypoints"
_ACCESS = "rdf_persistence.access.services"
_ACCESS_ADAPTERS = "rdf_persistence.access.adapters"
_ACCESS_MODELS = f"{_ACCESS}.generated.rp_access_services"
_ACCESS_SETTINGS_MODELS = f"{_ACCESS}.generated.settings.rp_access_settings"
_TENANCY = "rdf_persistence.tenancy.services"
_TENANCY_MODELS = f"{_TENANCY}.generated.rp_tenancy_services"
_IRIS_MODELS = "rdf_persistence.iris.services.generated.rp_iris_services"
_IRIS = "rdf_persistence.iris.services.iris"
_FILES = "rdf_persistence.files.services.files"
_S3 = "rdf_persistence.files.adapters.s3"
_SCHEMA = "rdf_persistence.schema.services.schema"
_SERVICE_MODELS = f"{_SERVICES}.generated.service.rp_service"
_SETTINGS_MODELS = f"{_SERVICES}.generated.settings.rp_settings"
_PERSISTENCE = "rdf_persistence.persistence.services"
_PERSISTENCE_MODELS = f"{_PERSISTENCE}.generated.rp_persistence_services"
_LIMIT_MODELS = f"{_PERSISTENCE}.generated.settings.rp_persistence_settings"
_LAZY_MODULES = {
    "HttpSettings": "rdf_persistence.core.services.generated.rp_core_services",
    "LimitSettings": _LIMIT_MODELS,
    **dict.fromkeys(("DirectorySettings", "JwksSettings"), _ACCESS_SETTINGS_MODELS),
    "EventSettings": _EVENTS_SETTINGS_MODELS,
    **dict.fromkeys(("SseSettings", "ToolkitSettings"), _SETTINGS_MODELS),
    "settings_from_env": f"{_ENTRYPOINTS}.environment",
    **dict.fromkeys(
        ("AccountSummary", "CallerAccess", "GrantSet", "VerifiedCaller"), _ACCESS_MODELS
    ),
    **dict.fromkeys(("TenantDump", "TenantSummary"), _TENANCY_MODELS),
    **dict.fromkeys(
        (
            "Authorised",
            "LabelUpdate",
            "Problem",
            "ProblemKind",
            "TenantCreate",
        ),
        _SERVICE_MODELS,
    ),
    "EventEnvelope": _EVENTS_MODELS,
    **dict.fromkeys(("MemberList", "Referrer", "ReferrerList"), _COLLABORATION_MODELS),
    **dict.fromkeys(("IdKind", "IdSpec", "IriPolicy", "ServiceSettings"), _IRIS_MODELS),
    "Page": _PERSISTENCE_MODELS,
    "FusekiStore": "rdf_persistence.persistence.adapters.fuseki",
    "JwksTokenVerifier": f"{_ACCESS_ADAPTERS}.jwks",
    "S3FileStore": _S3,
    "ZitadelIdentity": f"{_ACCESS_ADAPTERS}.zitadel",
    "zitadel_roles_claim": f"{_ACCESS_ADAPTERS}.zitadel",
    "install_service": f"{_ENTRYPOINTS}.service",
    "ServiceKit": f"{_ENTRYPOINTS}.kit",
    "limited_body": f"{_ENTRYPOINTS}.router",
    "Identity": f"{_ACCESS}.identity",
    **dict.fromkeys(("DEFAULT_IRIS", "IdSource", "Iris", "mint_aggregate_iri"), _IRIS),
    "EventBus": f"{_EVENTS}.events",
    "Receive": f"{_EVENTS}.events",
    "context_link": f"{_EVENTS}.events",
    "AccessRules": f"{_ACCESS}.access",
    "load_caller_access": f"{_ACCESS}.access",
    "load_role_definitions": f"{_ACCESS}.access",
    "TokenVerifier": f"{_ACCESS}.tokens",
    "FileStore": _FILES,
    "Mapper": f"{_PERSISTENCE}.mapper",
    "UnitOfWork": f"{_PERSISTENCE}.mapper",
    "generated_models": f"{_PERSISTENCE}.mapper",
    "new_part": f"{_PERSISTENCE}.mapper",
    "Listings": f"{_PERSISTENCE}.listing",
    "load_schema": _SCHEMA,
    "Session": f"{_PERSISTENCE}.session",
    "open_session": f"{_PERSISTENCE}.session",
    "Store": f"{_PERSISTENCE}.store",
    "sweep": f"{_TENANCY}.sweep",
    "sweep_tenant": f"{_TENANCY}.tenant_sweep",
    "remove_with_files": f"{_SERVICES}.file_removal",
    "Tenancy": f"{_TENANCY}.tenancy",
    "GrantValidator": f"{_TENANCY}.tenancy",
    "RootValidator": f"{_TENANCY}.tenancy",
    "Collaboration": f"{_COLLABORATION}.collaboration",
    "Workflows": f"{_COLLABORATION}.workflows",
    "MessageBus": f"{_MESSAGING}.messagebus",
    "Work": f"{_MESSAGING}.messagebus",
    "command": f"{_MESSAGING}.messagebus",
    "bootstrap": f"{_MESSAGING}.messagebus",
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
