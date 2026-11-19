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
    model_serializer,
    model_validator
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


class VerifiedCaller(ConfiguredBaseModel):
    "What a token verifier returns for a valid token, the principal and its global roles."
    principal: str = Field(default=..., title="Principal", description="The user account the token identifies.")
    global_roles: Optional[list[str]] = Field(default=None, title="Global roles", description="The system-level roles the token grants the principal.")


class GrantSet(ConfiguredBaseModel):
    "The body that replaces the grants and prohibitions of a tenant; two grants with the same assignee, target and role or action are refused."
    grants: Optional[list[Grant]] = Field(default=None, title="Grants", description="The permissions given in the tenant, by role or as direct actions; they live in the access record\u0027s graph.")
    prohibitions: Optional[list[Prohibition]] = Field(default=None, title="Prohibitions", description="The actions forbidden in the tenant; they live in the access record\u0027s graph.")

    @model_validator(mode="after")
    def unique_keys_grants_grant_key(self) -> "GrantSet":
        seen: set[str] = set()
        repeated: list[tuple] = []
        for item in self.grants or []:
            key = (item.assignee, item.target, item.role, item.action,)
            if repr(key) in seen:
                repeated.append(key)
            seen.add(repr(key))
        if repeated:
            raise ValueError(
                "GrantSet.grants: unique_keys grant_key (assignee, target, role, action) repeated by "
                + str(repeated)
            )
        return self


class CallerAccess(ConfiguredBaseModel):
    "What the access check needs to know about one caller in one tenant: the tenant\u0027s state, and the grants and prohibitions of the access record that name the caller."
    tenant: str = Field(default=..., title="Tenant", description="The IRI of the tenant.")
    state: TenantState = Field(default=..., title="State", description="Where the tenant is in its life.")
    grants: Optional[list[Grant]] = Field(default=None, title="Grants", description="The permissions given in the tenant, by role or as direct actions; they live in the access record\u0027s graph.")
    prohibitions: Optional[list[Prohibition]] = Field(default=None, title="Prohibitions", description="The actions forbidden in the tenant; they live in the access record\u0027s graph.")

    @model_validator(mode="after")
    def unique_keys_grants_grant_key(self) -> "CallerAccess":
        seen: set[str] = set()
        repeated: list[tuple] = []
        for item in self.grants or []:
            key = (item.assignee, item.target, item.role, item.action,)
            if repr(key) in seen:
                repeated.append(key)
            seen.add(repr(key))
        if repeated:
            raise ValueError(
                "CallerAccess.grants: unique_keys grant_key (assignee, target, role, action) repeated by "
                + str(repeated)
            )
        return self


class AccountSummary(ConfiguredBaseModel):
    "What the identity port reports about one account of the identity provider: its id, its login name, its email (a service account has none), whether it may sign in, and its global roles."
    account_id: str = Field(default=..., title="Account id", description="The identity provider\u0027s id of the account.")
    user_name: str = Field(default=..., title="User name", description="The name the account signs in with.")
    email: Optional[str] = Field(default=None, title="Email", description="The email address of a person\u0027s account.")
    active: bool = Field(default=..., title="Active", description="Whether the account may sign in; a disabled account is refused new tokens.")
    global_roles: Optional[list[str]] = Field(default=None, title="Global roles", description="The system-level roles the token grants the principal.")

    @field_validator("account_id")
    def pattern_account_id(cls, v):
        pattern=re.compile("^.+$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.fullmatch(element):
                    err_msg = "Invalid account_id format: " + str(element)
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.fullmatch(v):
            err_msg = "Invalid account_id format: " + str(v)
            raise ValueError(err_msg)
        return v


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
VerifiedCaller.model_rebuild()
GrantSet.model_rebuild()
CallerAccess.model_rebuild()
AccountSummary.model_rebuild()
