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
from rdf_persistence.domain.generated.rp_access import (
    Action,
    Grant,
    Policy,
    Prohibition,
    RoleDefinition,
    RoleLevel,
    Rule
)
from rdf_persistence.domain.generated.rp_annotations import (
    Described,
    Tracked
)
from rdf_persistence.domain.generated.rp_core import (
    AggregateRoot,
    DatabaseKind,
    GraphKind,
    ModuleKind,
    Principal,
    RegistryEntry,
    RegistryKind,
    RpAnnotation
)
from rdf_persistence.domain.generated.rp_tenancy import (
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


class ServiceSettings(ConfiguredBaseModel):
    "The settings of `install_service`: where the service is mounted, how it names tenants and which role its callers get on a tenant they create."
    base: str = Field(default=..., title="Base", description="The IRI under which the service mints identifiers and problem types, ending in a slash.")
    prefix: str = Field(default=..., title="Prefix", description="The prefix of the database names of the service\u0027s tenants; lower case, at most 20 characters.")
    tenant_segment: str = Field(default=..., title="Tenant segment", description="The path segment that names the tenant collection in the service\u0027s routes.")
    creator_role: str = Field(default=..., title="Creator role", description="The role a caller is given on the tenant it creates.")
    roles_claim: str = Field(default=..., title="Roles claim", description="The claim of the token that holds the caller\u0027s global roles, an object keyed by role name; for Zitadel, urn:zitadel:iam:org:project:{project_id}:roles of the consumer\u0027s project.")

    @field_validator("base")
    def pattern_base(cls, v):
        pattern=re.compile("^https?://.+/$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.fullmatch(element):
                    err_msg = "Invalid base format: " + str(element)
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.fullmatch(v):
            err_msg = "Invalid base format: " + str(v)
            raise ValueError(err_msg)
        return v

    @field_validator("prefix")
    def pattern_prefix(cls, v):
        pattern=re.compile("^[a-z][a-z0-9]{0,19}$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.fullmatch(element):
                    err_msg = "Invalid prefix format: " + str(element)
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.fullmatch(v):
            err_msg = "Invalid prefix format: " + str(v)
            raise ValueError(err_msg)
        return v

    @field_validator("tenant_segment")
    def pattern_tenant_segment(cls, v):
        pattern=re.compile("^[a-z][a-z0-9-]*$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.fullmatch(element):
                    err_msg = "Invalid tenant_segment format: " + str(element)
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.fullmatch(v):
            err_msg = "Invalid tenant_segment format: " + str(v)
            raise ValueError(err_msg)
        return v

    @field_validator("creator_role")
    def pattern_creator_role(cls, v):
        pattern=re.compile("^.+$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.fullmatch(element):
                    err_msg = "Invalid creator_role format: " + str(element)
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.fullmatch(v):
            err_msg = "Invalid creator_role format: " + str(v)
            raise ValueError(err_msg)
        return v


class VerifiedCaller(ConfiguredBaseModel):
    "What a token verifier returns for a valid token, the principal and its global roles."
    principal: str = Field(default=..., title="Principal", description="The user account the token identifies.")
    global_roles: Optional[list[str]] = Field(default=None, title="Global roles", description="The system-level roles the token grants the principal.")


class TenantCreate(TenantLabelled):
    "The body that creates a tenant, its label and the slots of the tenant\u0027s root object."
    root: Any = Field(default=..., title="Root", description="The slots of the tenant\u0027s root object, as the application\u0027s schema defines them.")
    label: str = Field(default=..., title="Label", description="The preferred label of the object.")

    @field_validator("label")
    def pattern_label(cls, v):
        pattern=re.compile("^\\S(?:.{0,198}\\S)?$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.fullmatch(element):
                    err_msg = "Invalid label format: " + str(element)
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.fullmatch(v):
            err_msg = "Invalid label format: " + str(v)
            raise ValueError(err_msg)
        return v


class TenantSummary(ConfiguredBaseModel):
    "What the service answers about one tenant, in a listing or after creating it."
    id: str = Field(default=..., title="Identifier", description="The IRI that identifies the object.")
    label: str = Field(default=..., title="Label", description="The preferred label of the object.")
    state: TenantState = Field(default=..., title="State", description="Where the tenant is in its life.")


class LabelUpdate(TenantLabelled):
    "The body that replaces the label of a tenant."
    label: str = Field(default=..., title="Label", description="The preferred label of the object.")

    @field_validator("label")
    def pattern_label(cls, v):
        pattern=re.compile("^\\S(?:.{0,198}\\S)?$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.fullmatch(element):
                    err_msg = "Invalid label format: " + str(element)
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.fullmatch(v):
            err_msg = "Invalid label format: " + str(v)
            raise ValueError(err_msg)
        return v


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


class Page(ConfiguredBaseModel):
    "One page of a listing, with the position of the page in the whole listing."
    items: list[Any] = Field(default=..., title="Items", description="The objects of the page; framed aggregates, or tenant summaries.")
    total: int = Field(default=..., title="Total", description="The number of objects in the whole listing.", ge=0)
    limit: int = Field(default=..., title="Limit", description="The most objects the page can hold.", ge=1)
    offset: int = Field(default=..., title="Offset", description="The position of the page\u0027s first object in the whole listing.", ge=0)


class Problem(ConfiguredBaseModel):
    "An RFC 9457 problem detail, the body of every error answer of the service."
    type: str = Field(default=..., title="Problem type", description="The IRI that identifies the kind of problem.")
    title: str = Field(default=..., title="Problem title", description="A short, fixed summary of the kind of problem.")
    status: int = Field(default=..., title="Problem status", description="The HTTP status code of the answer.")
    detail: Optional[str] = Field(default=None, title="Problem detail", description="An explanation of this occurrence of the problem.")
    instance: Optional[str] = Field(default=None, title="Problem instance", description="The IRI that identifies this occurrence of the problem.")


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
ServiceSettings.model_rebuild()
VerifiedCaller.model_rebuild()
TenantCreate.model_rebuild()
TenantSummary.model_rebuild()
LabelUpdate.model_rebuild()
GrantSet.model_rebuild()
Page.model_rebuild()
Problem.model_rebuild()
AccountSummary.model_rebuild()
