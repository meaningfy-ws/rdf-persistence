from __future__ import annotations

import re
import sys
from datetime import (
    date,
    datetime,
    time
)
from decimal import Decimal
from enum import Enum
from typing import (
    Any,
    ClassVar,
    Literal,
    Optional,
    Union
)

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    SerializationInfo,
    SerializerFunctionWrapHandler,
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
    GraphKind,
    KeyDuplicate,
    ModuleKind,
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
    Migration,
    MigrationStep
)


metamodel_version = "1.12.0"
version = "None"


from rdf_persistence.core.domain.base import RpModel as ConfiguredBaseModel



class LinkMLMeta(RootModel):
    root: dict[str, Any] = {}
    model_config = ConfigDict(frozen=True)

    def __getattr__(self, key:str):
        return getattr(self.root, key)

    def __getitem__(self, key:str):
        return self.root[key]

    def __setitem__(self, key:str, value):
        self.root[key] = value

    def __contains__(self, key:str) -> bool:
        return key in self.root


linkml_meta = None


class TenantDump(ConfiguredBaseModel):
    "The manifest of a tenant dump archive, written by `dump_tenant` and read by `restore_tenant`: where and when the dump was taken, which schema and toolkit it came from, the tenant it holds and the IRI policy that minted its IRIs, so a restore can check that the dump was made under the same schema and policy."
    format_version: int = Field(default=..., title="Format version", description="The version of the dump archive layout; a restore refuses a version it does not know.")
    created_at: datetime  = Field(default=..., title="Dump created at", description="When the dump was taken, so a person choosing among dumps can tell them apart.")
    toolkit_version: str = Field(default=..., title="Toolkit version", description="The version of the toolkit that wrote the dump.")
    schema_id: str = Field(default=..., title="Schema id", description="The id of the LinkML schema whose data the dump holds; a restore checks it against its own.")
    schema_version: Optional[str] = Field(default=None, title="Schema version", description="The version of that schema, when it declares one.")
    source_tenant: str = Field(default=..., title="Source tenant", description="The IRI of the tenant the dump was taken from.")
    source_tenant_id: str = Field(default=..., title="Source tenant id", description="The id part of the source tenant\u0027s IRI, which a restore replaces by the new tenant\u0027s id.")
    label: str = Field(default=..., title="Label", description="The preferred label of the object.")
    iri_policy: IriPolicy = Field(default=..., title="IRI policy", description="The IRI policy of the service; absent, the default policy applies.")


class TenantSummary(ConfiguredBaseModel):
    "What the service answers about one tenant, in a listing or after creating it."
    id: str = Field(default=..., title="Identifier", description="The IRI that identifies the object.")
    label: str = Field(default=..., title="Label", description="The preferred label of the object.")
    state: TenantState = Field(default=..., title="State", description="Where the tenant is in its life.")
    allowed_actions: Optional[list[Action]] = Field(default=None, title="Allowed actions", description="The actions the caller who asked may take on the tenant, in the order read, modify, delete, administer. Only a listing fills it.")


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
TenantDump.model_rebuild()
TenantSummary.model_rebuild()
