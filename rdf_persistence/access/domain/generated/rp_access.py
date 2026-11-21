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
    model_serializer,
    model_validator
)
from rdf_persistence.core.domain.generated.rp_core import Principal


metamodel_version = "1.12.0"
version = "None"


from rdf_persistence.core.domain.base import RpModel as ConfiguredBaseModel

linkml_meta = None

class Action(str, _Enum):
    "The actions a rule can name."
    READ = "read"
    "Read an object."
    MODIFY = "modify"
    "Change an object; at tenant scope, also create one."
    DELETE = "delete"
    "Delete an object."
    ADMINISTER = "administer"
    "Change the grants of a tenant."
    ANNOTATE = "annotate"
    "Add a comment to an object without changing it."


class RoleLevel(str, _Enum):
    "The levels at which a role applies."
    SYSTEM = "system"
    "The whole system; only for global roles from the token."
    TENANT = "tenant"
    "One tenant."
    AGGREGATE = "aggregate"
    "One aggregate."



class Policy(ConfiguredBaseModel):
    "A set of permissions and prohibitions."
    pass


class Rule(ConfiguredBaseModel):
    "An ODRL rule that gives an assignee a ruling on an action over a target."
    assignee: str = _Field(default=..., title="Assignee", description="The principal the rule applies to.")
    target: str = _Field(default=..., title="Target", description="The IRI of the tenant, or of an aggregate\u0027s graph, the rule applies to.")
    action: _Optional[Action] = _Field(default=None, title="Action", description="The action a direct permission allows, or a prohibition forbids.")


class Grant(Rule):
    "A permission given to a principal on a tenant or on one aggregate, either by role or as a direct action; exactly one of role and action is given."
    role: _Optional[str] = _Field(default=None, title="Role", description="The name of a role, matched against the application\u0027s role definitions.")
    assignee: str = _Field(default=..., title="Assignee", description="The principal the rule applies to.")
    target: str = _Field(default=..., title="Target", description="The IRI of the tenant, or of an aggregate\u0027s graph, the rule applies to.")
    action: _Optional[Action] = _Field(default=None, title="Action", description="The action a direct permission allows, or a prohibition forbids.")

    @model_validator(mode="after")
    def exactly_one_of_Grant(self) -> "Grant":
        held = [
            label
            for label, present in (
                ("role present", self.role not in (None, [])),
                ("action present", self.action not in (None, [])),
            )
            if present
        ]
        if len(held) != 1:
            raise ValueError(
                "Grant: exactly_one_of needs exactly one of [role present, action present], but "
                + str(held or "none")
                + " hold"
            )
        return self


class Prohibition(Rule):
    "The ODRL prohibition that forbids an assignee an action on a target; it wins over any permission."
    assignee: str = _Field(default=..., title="Assignee", description="The principal the rule applies to.")
    target: str = _Field(default=..., title="Target", description="The IRI of the tenant, or of an aggregate\u0027s graph, the rule applies to.")
    action: Action = _Field(default=..., title="Action", description="The action a direct permission allows, or a prohibition forbids.")


class RoleDefinition(ConfiguredBaseModel):
    "What a role may do and where it applies. An application supplies its role definitions as data; they are not stored."
    role: str = _Field(default=..., title="Role", description="The name of a role, matched against the application\u0027s role definitions.")
    level: RoleLevel = _Field(default=..., title="Level", description="Where the role applies.")
    actions: list[Action] = _Field(default=..., title="Actions", description="The actions the role permits.")


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
Policy.model_rebuild()
Rule.model_rebuild()
Grant.model_rebuild()
Prohibition.model_rebuild()
RoleDefinition.model_rebuild()
