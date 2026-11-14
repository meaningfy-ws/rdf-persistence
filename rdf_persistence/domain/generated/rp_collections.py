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


class ReferenceCollection(ConfiguredBaseModel):
    "A mixin for an aggregate that collects other aggregates of one class: the members it names, and a rule that says which aggregates of that class belong. A collection of collections has the collection class as its member class."
    member_class: str = Field(default=..., title="Member class", description="The schema name of the class of the aggregates the collection collects.")
    had_member: Optional[list[str]] = Field(default=None, title="Had member", description="The IRIs of the aggregates the collection names as its members.")
    membership_rule: Optional[MembershipRule] = Field(default=None, title="Membership rule", description="The rule that says which aggregates of the member class belong to the collection.")


class MembershipRule(ConfiguredBaseModel):
    "The rule of a collection, a part of its graph with no identifier of its own. An aggregate belongs when it equals every equality; a rule with no equality means every aggregate of the member class."
    rule_equalities: Optional[list[SlotEquality]] = Field(default=None, title="Rule equalities", description="The conditions of the rule, all of which an aggregate must meet.")


class SlotEquality(ConfiguredBaseModel):
    "One condition of a membership rule, a slot of the member class and the value it must equal."
    equals_slot: str = Field(default=..., title="Equals slot", description="The name of the slot of the member class the condition looks at.")
    equals_value: str = Field(default=..., title="Equals value", description="The value the slot must equal, in the lexical form a listing filter would send.")


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
ReferenceCollection.model_rebuild()
MembershipRule.model_rebuild()
SlotEquality.model_rebuild()
