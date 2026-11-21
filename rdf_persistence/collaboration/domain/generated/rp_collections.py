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


metamodel_version = "1.12.0"
version = "None"


from rdf_persistence.core.domain.base import RpModel as ConfiguredBaseModel

linkml_meta = None


class ReferenceCollection(ConfiguredBaseModel):
    "A mixin for an aggregate that collects other aggregates of one class: the members it names, and a rule that says which aggregates of that class belong. A collection of collections has the collection class as its member class."
    member_class: str = _Field(default=..., title="Member class", description="The schema name of the class of the aggregates the collection collects.")
    has_part: _Optional[list[str]] = _Field(default=None, title="Has part", description="The IRIs of the aggregates the collection names as its members.")
    membership_rule: _Optional[MembershipRule] = _Field(default=None, title="Membership rule", description="The rule that says which aggregates of the member class belong to the collection.")
    nests: _Optional[bool] = _Field(default=None, title="Nests", description="Whether the collection may hold collections of its own class and member class as members, to any depth. Absent means false.")


class MembershipRule(ConfiguredBaseModel):
    "The rule of a collection, a part of its graph with no identifier of its own. An aggregate belongs when it equals every equality; a rule with no equality means every aggregate of the member class."
    rule_equalities: _Optional[list[SlotEquality]] = _Field(default=None, title="Rule equalities", description="The conditions of the rule, all of which an aggregate must meet.")


class SlotEquality(ConfiguredBaseModel):
    "One condition of a membership rule, a slot of the member class and the value it must equal."
    equals_slot: str = _Field(default=..., title="Equals slot", description="The name of the slot of the member class the condition looks at.")
    equals_value: str = _Field(default=..., title="Equals value", description="The value the slot must equal, in the lexical form a listing filter would send.")


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
ReferenceCollection.model_rebuild()
MembershipRule.model_rebuild()
SlotEquality.model_rebuild()
