"""RDF Persistence."""

from rdf_persistence.domain.base import RpModel
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
    Principal,
    RegistryEntry,
    RegistryKind,
)
from rdf_persistence.domain.generated.rp_files import (
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
    GrantSet,
    LabelUpdate,
    Page,
    Problem,
    ServiceSettings,
    TenantCreate,
    TenantSummary,
    VerifiedCaller,
)

__version__ = "0.1.0"

__all__ = [
    "Action",
    "Activity",
    "AggregateRoot",
    "Described",
    "Grant",
    "GrantSet",
    "LabelUpdate",
    "Page",
    "Policy",
    "Principal",
    "Problem",
    "Prohibition",
    "Provenanced",
    "RegistryEntry",
    "RegistryKind",
    "RoleDefinition",
    "RoleLevel",
    "Rule",
    "RpModel",
    "ServiceSettings",
    "StoredFile",
    "TenantAccess",
    "TenantCreate",
    "TenantLabelled",
    "TenantState",
    "TenantSummary",
    "Tracked",
    "VerifiedCaller",
]
