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


class Referrer(ConfiguredBaseModel):
    "One aggregate that points at another: its IRI, its schema class and the slot that holds the reference."
    referrer: str = Field(default=..., title="Referrer", description="The IRI of the aggregate that holds the reference.")
    referrer_class: str = Field(default=..., title="Referrer class", description="The name of the schema class of the aggregate that holds the reference; its IRI when the schema does not know the class.")
    referrer_slot: str = Field(default=..., title="Referrer slot", description="The name of the slot that holds the reference; its IRI when the schema does not know the slot.")


class ReferrerList(ConfiguredBaseModel):
    "The aggregates that point at one resource and that the caller may read, and the number of referrers left out because the caller may not read them."
    referrers: Optional[list[Referrer]] = Field(default=None, title="Referrers", description="The aggregates that point at the resource, ordered by IRI and slot.")
    hidden_count: int = Field(default=..., title="Hidden count", description="The number of referrers or members the caller may not read, so are not listed.", ge=0)


class MemberList(ConfiguredBaseModel):
    "The members of a collection that the caller may read, and the number of members left out because the caller may not read them."
    member_iris: Optional[list[str]] = Field(default=None, title="Member IRIs", description="The IRIs of the members of a collection.")
    hidden_count: int = Field(default=..., title="Hidden count", description="The number of referrers or members the caller may not read, so are not listed.", ge=0)


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
Referrer.model_rebuild()
ReferrerList.model_rebuild()
MemberList.model_rebuild()
