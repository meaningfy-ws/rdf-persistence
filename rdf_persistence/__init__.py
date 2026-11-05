"""RDF Persistence."""

from rdf_persistence.domain.base import RpModel
from rdf_persistence.domain.generated.rp import (
    Action,
    Activity,
    AggregateRoot,
    Described,
    Grant,
    Policy,
    Principal,
    Prohibition,
    Provenanced,
    RegistryEntry,
    RegistryKind,
    RoleDefinition,
    RoleLevel,
    Rule,
    StoredFile,
    TenantAccess,
    TenantState,
    Tracked,
)

__version__ = "0.1.0"

__all__ = [
    "Action",
    "Activity",
    "AggregateRoot",
    "Described",
    "Grant",
    "Policy",
    "Principal",
    "Prohibition",
    "Provenanced",
    "RegistryEntry",
    "RegistryKind",
    "RoleDefinition",
    "RoleLevel",
    "Rule",
    "RpModel",
    "StoredFile",
    "TenantAccess",
    "TenantState",
    "Tracked",
]
