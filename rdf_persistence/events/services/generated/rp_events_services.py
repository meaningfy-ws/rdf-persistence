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


metamodel_version = "1.12.0"
version = "None"


from rdf_persistence.core.domain.base import RpModel as ConfiguredBaseModel

linkml_meta = None


class EventEnvelope(ConfiguredBaseModel):
    "What travels beside an activity on the event bus: the tenant it happened in, the deployment that published it, the class of its body and where to find the JSON-LD context that reads it."
    tenant: str = _Field(default=..., title="Tenant", description="The IRI of the tenant, or of the application, the activity happened in.")
    origin: str = _Field(default=..., title="Origin", description="The deployment that published the message, as its `deployment` setting names it.")
    activity_class: str = _Field(default=..., title="Activity class", description="The IRI of the class of the activity the message carries.")
    context: str = _Field(default=..., title="Context", description="A link to the JSON-LD context that reads the message body.")


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
EventEnvelope.model_rebuild()
