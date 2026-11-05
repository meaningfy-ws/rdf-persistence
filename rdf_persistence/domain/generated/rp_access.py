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

from .rp_core import Principal


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

class Action(str, Enum):
    """
    The actions a rule can name.
    """
    READ = "read"
    """
    Read an object.
    """
    MODIFY = "modify"
    """
    Change an object; at tenant scope, also create one.
    """
    DELETE = "delete"
    """
    Delete an object.
    """
    ADMINISTER = "administer"
    """
    Change the grants of a tenant.
    """


class RoleLevel(str, Enum):
    """
    The levels at which a role applies.
    """
    SYSTEM = "system"
    """
    The whole system; only for global roles from the token.
    """
    TENANT = "tenant"
    """
    One tenant.
    """
    AGGREGATE = "aggregate"
    """
    One aggregate.
    """



class Policy(ConfiguredBaseModel):
    """
    A set of permissions and prohibitions.
    """
    pass


class Rule(ConfiguredBaseModel):
    """
    An ODRL rule that gives an assignee a ruling on an action over a target.
    """
    assignee: str = Field(default=..., title="Assignee", description="""The principal the rule applies to.""")
    target: str = Field(default=..., title="Target", description="""The IRI of the tenant, or of an aggregate's graph, the rule applies to.""")
    action: Optional[Action] = Field(default=None, title="Action", description="""The action a direct permission allows, or a prohibition forbids.""")


class Grant(Rule):
    """
    A permission given to a principal on a tenant or on one aggregate, either by role or as a direct action; exactly one of role and action is given.
    """
    role: Optional[str] = Field(default=None, title="Role", description="""The name of a role, matched against the application's role definitions. An application may narrow it to an enum.""")
    assignee: str = Field(default=..., title="Assignee", description="""The principal the rule applies to.""")
    target: str = Field(default=..., title="Target", description="""The IRI of the tenant, or of an aggregate's graph, the rule applies to.""")
    action: Optional[Action] = Field(default=None, title="Action", description="""The action a direct permission allows, or a prohibition forbids.""")


class Prohibition(Rule):
    """
    The ODRL prohibition that forbids an assignee an action on a target; it wins over any permission.
    """
    assignee: str = Field(default=..., title="Assignee", description="""The principal the rule applies to.""")
    target: str = Field(default=..., title="Target", description="""The IRI of the tenant, or of an aggregate's graph, the rule applies to.""")
    action: Action = Field(default=..., title="Action", description="""The action a direct permission allows, or a prohibition forbids.""")


class RoleDefinition(ConfiguredBaseModel):
    """
    What a role may do and where it applies. An application supplies its role definitions as data; they are not stored.
    """
    role: str = Field(default=..., title="Role", description="""The name of a role, matched against the application's role definitions. An application may narrow it to an enum.""")
    level: RoleLevel = Field(default=..., title="Level", description="""Where the role applies.""")
    actions: list[Action] = Field(default=..., title="Actions", description="""The actions the role permits.""")


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
Policy.model_rebuild()
Rule.model_rebuild()
Grant.model_rebuild()
Prohibition.model_rebuild()
RoleDefinition.model_rebuild()
