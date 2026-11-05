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

from .rp_access import (
    Action,
    Grant,
    Policy,
    Prohibition,
    RoleDefinition,
    RoleLevel,
    Rule
)
from .rp_annotations import (
    Described,
    Tracked
)
from .rp_core import (
    AggregateRoot,
    DatabaseKind,
    GraphKind,
    ModuleKind,
    Principal,
    RegistryEntry,
    RegistryKind,
    RpAnnotation
)
from .rp_files import (
    RdfFormat,
    StoredFile
)
from .rp_provenance import (
    Activity,
    Provenanced
)
from .rp_tenancy import (
    TenantAccess,
    TenantLabelled,
    TenantState
)


metamodel_version = "1.12.0"
version = "None"


from rdf_persistence.domain.base import RpModel as ConfiguredBaseModel



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


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
