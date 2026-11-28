from __future__ import annotations

import re
import sys
from datetime import (
    date,
    datetime,
    time
)
from decimal import Decimal as _Decimal
from enum import Enum as _Enum
from typing import (
    Any as _Any,
    ClassVar as _ClassVar,
    Literal as _Literal,
    Optional as _Optional,
    Union as _Union
)

from pydantic import (
    BaseModel as _BaseModel,
    ConfigDict as _ConfigDict,
    Field as _Field,
    RootModel as _RootModel,
    SerializationInfo as _SerializationInfo,
    SerializerFunctionWrapHandler as _SerializerFunctionWrapHandler,
    field_validator,
    model_serializer
)
from rdf_persistence.access.domain.generated.rp_access import (
    Action,
    Grant,
    Policy,
    Prohibition,
    RoleDefinition,
    RoleLevel,
    Rule
)
from rdf_persistence.access.domain.generated.rp_tenancy import (
    TenantAccess,
    TenantLabelled,
    TenantState,
    TenantSweepReport
)
from rdf_persistence.core.domain.generated.rp_annotations import (
    Described,
    Tracked
)
from rdf_persistence.core.domain.generated.rp_core import (
    AggregateKey,
    AggregateRoot,
    CommitMarker,
    DatabaseKind,
    DependenceLink,
    GraphKind,
    KeyDuplicate,
    ModuleKind,
    OnReferencedDelete,
    PendingLoad,
    Principal,
    RegistryEntry,
    RegistryKind,
    RpAnnotation,
    UniqueScope,
    WritesKind
)
from rdf_persistence.iris.services.generated.rp_iris_services import (
    IdKind,
    IdSpec,
    IriPolicy,
    ServiceSettings
)
from rdf_persistence.migrations.services.generated.rp_migrations_services import (
    GrantRoles,
    Migration,
    MigrationStep,
    RoleRename
)


metamodel_version = "1.12.0"
version = "None"


from rdf_persistence.core.domain.base import RpModel as ConfiguredBaseModel

linkml_meta = None


class TenantDump(ConfiguredBaseModel):
    "The manifest of a tenant dump archive, written by `dump_tenant` and read by `restore_tenant`: where and when the dump was taken, which schema and toolkit it came from, the tenant it holds and the IRI policy that minted its IRIs, so a restore can check that the dump was made under the same schema and policy."
    format_version: int = _Field(default=..., title="Format version", description="The version of the dump archive layout; a restore refuses a version it does not know.")
    created_at: datetime  = _Field(default=..., title="Dump created at", description="When the dump was taken, so a person choosing among dumps can tell them apart.")
    toolkit_version: str = _Field(default=..., title="Toolkit version", description="The version of the toolkit that wrote the dump.")
    schema_id: str = _Field(default=..., title="Schema id", description="The id of the LinkML schema whose data the dump holds; a restore checks it against its own.")
    schema_version: _Optional[str] = _Field(default=None, title="Schema version", description="The version of that schema, when it declares one.")
    source_tenant: str = _Field(default=..., title="Source tenant", description="The IRI of the tenant the dump was taken from.")
    source_tenant_id: str = _Field(default=..., title="Source tenant id", description="The id part of the source tenant\u0027s IRI, which a restore replaces by the new tenant\u0027s id.")
    label: str = _Field(default=..., title="Label", description="The preferred label of the object.")
    iri_policy: IriPolicy = _Field(default=..., title="IRI policy", description="The IRI policy of the service; absent, the default policy applies.")


class TenantSummary(ConfiguredBaseModel):
    "What the service answers about one tenant, in a listing or after creating it."
    id: str = _Field(default=..., title="Identifier", description="The IRI that identifies the object.")
    label: str = _Field(default=..., title="Label", description="The preferred label of the object.")
    state: TenantState = _Field(default=..., title="State", description="Where the tenant is in its life.")
    allowed_actions: _Optional[list[Action]] = _Field(default=None, title="Allowed actions", description="The actions the caller who asked may take on the tenant, in the order read, modify, delete, administer. Only a listing fills it.")


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
TenantDump.model_rebuild()
TenantSummary.model_rebuild()
