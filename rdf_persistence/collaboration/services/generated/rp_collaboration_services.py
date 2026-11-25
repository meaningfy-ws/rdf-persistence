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


class Referrer(ConfiguredBaseModel):
    "One aggregate that points at another: its IRI, its schema class and the slot that holds the reference."
    referrer: str = _Field(default=..., title="Referrer", description="The IRI of the aggregate that holds the reference.")
    referrer_class: str = _Field(default=..., title="Referrer class", description="The name of the schema class of the aggregate that holds the reference; its IRI when the schema does not know the class.")
    referrer_slot: str = _Field(default=..., title="Referrer slot", description="The name of the slot that holds the reference; its IRI when the schema does not know the slot.")
    referrer_rp_path: _Optional[str] = _Field(default=None, title="Referrer path", description="The path the service serves the referrer\u0027s class at, with ``referrer_id`` the address of the referrer; set together with ``referrer_id``, and absent when the class is not served or the IRI is not an aggregate IRI the policy mints.")
    referrer_id: _Optional[str] = _Field(default=None, title="Referrer id", description="The id of the referrer in its path, set together with ``referrer_rp_path`` and absent when that is.")


class ReferrerList(ConfiguredBaseModel):
    "The aggregates that point at one resource and that the caller may read, and the number of referrers left out because the caller may not read them."
    referrers: _Optional[list[Referrer]] = _Field(default=None, title="Referrers", description="The aggregates that point at the resource, ordered by IRI and slot.")
    hidden_count: int = _Field(default=..., title="Hidden count", description="The number of referrers or members the caller may not read, so are not listed.", ge=0)


class MemberList(ConfiguredBaseModel):
    "The members of a collection that the caller may read, and the number of members left out because the caller may not read them."
    member_iris: _Optional[list[str]] = _Field(default=None, title="Member IRIs", description="The IRIs of the members of a collection.")
    hidden_count: int = _Field(default=..., title="Hidden count", description="The number of referrers or members the caller may not read, so are not listed.", ge=0)


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
Referrer.model_rebuild()
ReferrerList.model_rebuild()
MemberList.model_rebuild()
