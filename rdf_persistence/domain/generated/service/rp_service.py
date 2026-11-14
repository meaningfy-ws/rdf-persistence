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
    CommitMarker,
    DatabaseKind,
    GraphKind,
    ModuleKind,
    PendingLoad,
    Principal,
    RegistryEntry,
    RegistryKind,
    RpAnnotation,
    WritesKind
)
from rdf_persistence.domain.generated.rp_tenancy import (
    TenantAccess,
    TenantLabelled,
    TenantState,
    TenantSweepReport
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

class IdKind(str, Enum):
    "The ways an id is drawn."
    UUID4 = "uuid4"
    "A random UUID, in its canonical form."
    RANDOM = "random"
    "Characters drawn at random from an alphabet."


class ProblemSlug(str, Enum):
    "The kinds of problem the toolkit answers with, by the last segment of their problem type IRI, with the underscores written as hyphens."
    INVALID_TOKEN = "invalid_token"
    "No bearer token, or one the service refuses."
    FORBIDDEN = "forbidden"
    "The caller may see the thing but is not allowed the action."
    NOT_FOUND = "not_found"
    "There is no such thing, or the caller cannot see it."
    CONFLICT = "conflict"
    "The write lost a race, or the thing to create already exists."
    PRECONDITION_REQUIRED = "precondition_required"
    "An update or a delete came without the version it expects."
    INVALID_BODY = "invalid_body"
    "The body is not a valid representation for its route."
    NOT_ACCEPTABLE = "not_acceptable"
    "The service produces nothing the client accepts."
    UNSUPPORTED_MEDIA_TYPE = "unsupported_media_type"
    "The route does not take the media type of the body."
    BAD_QUERY = "bad_query"
    "The query string is not one the route takes."
    UNAVAILABLE = "unavailable"
    "A store, the identity provider or the role definitions are not usable."
    PAYLOAD_TOO_LARGE = "payload_too_large"
    "The body is larger than the service takes."
    METHOD_NOT_ALLOWED = "method_not_allowed"
    "The route has no such method."
    INTERNAL_ERROR = "internal_error"
    "The service failed; the answer says no more."



class ServiceSettings(ConfiguredBaseModel):
    "The settings of `install_service`: where the service is mounted, how it names tenants and which role its callers get on a tenant they create."
    base: str = Field(default=..., title="Base", description="The IRI under which the service mints identifiers and problem types, ending in a slash.")
    prefix: str = Field(default=..., title="Prefix", description="The prefix of the database names of the service\u0027s tenants; lower case, at most 20 characters.")
    tenant_segment: str = Field(default=..., title="Tenant segment", description="The path segment that names the tenant collection in the service\u0027s routes.")
    creator_role: str = Field(default=..., title="Creator role", description="The role a caller is given on the tenant it creates.")
    roles_claim: str = Field(default=..., title="Roles claim", description="The claim of the token that holds the caller\u0027s global roles, an object keyed by role name; for Zitadel, urn:zitadel:iam:org:project:{project_id}:roles of the consumer\u0027s project.")
    max_body_bytes: Optional[int] = Field(default=1048576, title="Maximum body size", description="The most bytes a request body may hold; a larger one is refused with 413 before it is read whole.", ge=1)
    max_restore_bytes: Optional[int] = Field(default=1073741824, title="Maximum restore size", description="The most bytes a restore archive may hold once decompressed, counting each member\u0027s size and its tar block; a larger archive is refused with `InvalidBody` as it is read, so a small hostile upload cannot fill the memory or the object store.", ge=1)
    deployment: Optional[str] = Field(default=None, title="Deployment", description="A slug that names this deployment, for templates that use `{deployment}`; lower case letters and digits, at most 32.")
    iri_policy: Optional[IriPolicy] = Field(default=None, title="IRI policy", description="The IRI policy of the service; absent, the default policy applies.")

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

    @field_validator("roles_claim")
    def pattern_roles_claim(cls, v):
        pattern=re.compile("^.+$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.fullmatch(element):
                    err_msg = "Invalid roles_claim format: " + str(element)
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.fullmatch(v):
            err_msg = "Invalid roles_claim format: " + str(v)
            raise ValueError(err_msg)
        return v

    @field_validator("deployment")
    def pattern_deployment(cls, v):
        pattern=re.compile("^[a-z0-9]{1,32}$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.fullmatch(element):
                    err_msg = "Invalid deployment format: " + str(element)
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.fullmatch(v):
            err_msg = "Invalid deployment format: " + str(v)
            raise ValueError(err_msg)
        return v


class IdSpec(ConfiguredBaseModel):
    "How the toolkit draws an id: a UUIDv4, or `length` characters drawn from `alphabet`. The length is required for `random` ids."
    kind: IdKind = Field(default=..., title="Id kind", description="Whether ids are UUIDv4 or random characters of an alphabet.")
    length: Optional[int] = Field(default=None, title="Id length", description="The number of characters of a random id, 4 to 32.", ge=4, le=32)
    alphabet: Optional[str] = Field(default="0123456789abcdefghijklmnopqrstuvwxyz", title="Id alphabet", description="The characters a random id is drawn from, each a lower case letter or a digit.")

    @field_validator("alphabet")
    def pattern_alphabet(cls, v):
        pattern=re.compile("^[a-z0-9]+$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.fullmatch(element):
                    err_msg = "Invalid alphabet format: " + str(element)
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.fullmatch(v):
            err_msg = "Invalid alphabet format: " + str(v)
            raise ValueError(err_msg)
        return v


class IriPolicy(ConfiguredBaseModel):
    "The templates the toolkit mints and accepts IRIs by, one per kind of IRI, and the id specifications of tenant and object ids. Every slot defaults to today\u0027s shape, so an empty policy is the default one. A template fills the variables allowed for its kind; the tenant, aggregate, part, loaded graph and principal templates end in their id variable, the access, meta and registry templates contain the tenant, and the aggregate, part and loaded graph templates name their tenant or, for the last two, their root."
    tenant_template: Optional[str] = Field(default="{base}{tenant_segment}/{tenant_id}", title="Tenant template", description="The template of a tenant IRI; ends in `{tenant_id}`.")
    access_template: Optional[str] = Field(default="{tenant}/access", title="Access template", description="The template of the IRI of a tenant\u0027s access record; contains `{tenant}` or `{tenant_id}`.")
    meta_template: Optional[str] = Field(default="{tenant}/meta", title="Meta template", description="The template of the IRI of a tenant\u0027s meta graph; contains `{tenant}` or `{tenant_id}`.")
    registry_template: Optional[str] = Field(default="{tenant}/registry", title="Registry template", description="The template of the IRI of a tenant\u0027s registry graph; contains `{tenant}` or `{tenant_id}`.")
    aggregate_template: Optional[str] = Field(default="{tenant}/{rp_path}/{id}", title="Aggregate template", description="The template of an aggregate root IRI; contains `{tenant}` or `{tenant_id}` and ends in `{id}`.")
    part_template: Optional[str] = Field(default="{root}/parts/{id}", title="Part template", description="The template of the IRI of an owned part; contains `{tenant}`, `{tenant_id}` or `{root}` and ends in `{id}`.")
    loaded_graph_template: Optional[str] = Field(default="{root}/content/{id}", title="Loaded graph template", description="The template of the IRI of a loaded graph; contains `{tenant}`, `{tenant_id}` or `{root}` and ends in `{id}`.")
    principal_template: Optional[str] = Field(default="{issuer}/users/{sub}", title="Principal template", description="The template of the IRI of a principal; ends in `{sub}`.")
    tenant_id: Optional[IdSpec] = Field(default=None, title="Tenant id", description="How the id of a new tenant is drawn; absent, a UUIDv4.")
    object_id: Optional[IdSpec] = Field(default=None, title="Object id", description="How the id of a new aggregate root, part or loaded graph is drawn; absent, a UUIDv4.")

    @field_validator("tenant_template")
    def pattern_tenant_template(cls, v):
        pattern=re.compile("^(?:[a-z0-9/:.-]|\\{(?:base|deployment|tenant_segment|tenant_id)\\})*\\{tenant_id\\}$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.fullmatch(element):
                    err_msg = "Invalid tenant_template format: " + str(element)
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.fullmatch(v):
            err_msg = "Invalid tenant_template format: " + str(v)
            raise ValueError(err_msg)
        return v

    @field_validator("access_template")
    def pattern_access_template(cls, v):
        pattern=re.compile("^(?:[a-z0-9/:.-]|\\{(?:base|deployment|tenant|tenant_id)\\})*\\{tenant(?:_id)?\\}(?:[a-z0-9/:.-]|\\{(?:base|deployment|tenant|tenant_id)\\})*$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.fullmatch(element):
                    err_msg = "Invalid access_template format: " + str(element)
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.fullmatch(v):
            err_msg = "Invalid access_template format: " + str(v)
            raise ValueError(err_msg)
        return v

    @field_validator("meta_template")
    def pattern_meta_template(cls, v):
        pattern=re.compile("^(?:[a-z0-9/:.-]|\\{(?:base|deployment|tenant|tenant_id)\\})*\\{tenant(?:_id)?\\}(?:[a-z0-9/:.-]|\\{(?:base|deployment|tenant|tenant_id)\\})*$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.fullmatch(element):
                    err_msg = "Invalid meta_template format: " + str(element)
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.fullmatch(v):
            err_msg = "Invalid meta_template format: " + str(v)
            raise ValueError(err_msg)
        return v

    @field_validator("registry_template")
    def pattern_registry_template(cls, v):
        pattern=re.compile("^(?:[a-z0-9/:.-]|\\{(?:base|deployment|tenant|tenant_id)\\})*\\{tenant(?:_id)?\\}(?:[a-z0-9/:.-]|\\{(?:base|deployment|tenant|tenant_id)\\})*$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.fullmatch(element):
                    err_msg = "Invalid registry_template format: " + str(element)
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.fullmatch(v):
            err_msg = "Invalid registry_template format: " + str(v)
            raise ValueError(err_msg)
        return v

    @field_validator("aggregate_template")
    def pattern_aggregate_template(cls, v):
        pattern=re.compile("^(?:[a-z0-9/:.-]|\\{(?:base|deployment|tenant|tenant_id|type|rp_path|id)\\})*\\{tenant(?:_id)?\\}(?:[a-z0-9/:.-]|\\{(?:base|deployment|tenant|tenant_id|type|rp_path|id)\\})*\\{id\\}$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.fullmatch(element):
                    err_msg = "Invalid aggregate_template format: " + str(element)
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.fullmatch(v):
            err_msg = "Invalid aggregate_template format: " + str(v)
            raise ValueError(err_msg)
        return v

    @field_validator("part_template")
    def pattern_part_template(cls, v):
        pattern=re.compile("^(?:[a-z0-9/:.-]|\\{(?:base|deployment|tenant|tenant_id|root|type|id)\\})*\\{(?:tenant|tenant_id|root)\\}(?:[a-z0-9/:.-]|\\{(?:base|deployment|tenant|tenant_id|root|type|id)\\})*\\{id\\}$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.fullmatch(element):
                    err_msg = "Invalid part_template format: " + str(element)
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.fullmatch(v):
            err_msg = "Invalid part_template format: " + str(v)
            raise ValueError(err_msg)
        return v

    @field_validator("loaded_graph_template")
    def pattern_loaded_graph_template(cls, v):
        pattern=re.compile("^(?:[a-z0-9/:.-]|\\{(?:base|deployment|tenant|tenant_id|root|type|id)\\})*\\{(?:tenant|tenant_id|root)\\}(?:[a-z0-9/:.-]|\\{(?:base|deployment|tenant|tenant_id|root|type|id)\\})*\\{id\\}$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.fullmatch(element):
                    err_msg = "Invalid loaded_graph_template format: " + str(element)
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.fullmatch(v):
            err_msg = "Invalid loaded_graph_template format: " + str(v)
            raise ValueError(err_msg)
        return v

    @field_validator("principal_template")
    def pattern_principal_template(cls, v):
        pattern=re.compile("^(?:[a-z0-9/:.-]|\\{(?:base|deployment|issuer|sub)\\})*\\{sub\\}$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.fullmatch(element):
                    err_msg = "Invalid principal_template format: " + str(element)
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.fullmatch(v):
            err_msg = "Invalid principal_template format: " + str(v)
            raise ValueError(err_msg)
        return v


class TenantDump(ConfiguredBaseModel):
    "The manifest of a tenant dump archive, written by `dump_tenant` and read by `restore_tenant`: where and when the dump was taken, which schema and toolkit it came from, the tenant it holds and the IRI policy that minted its IRIs, so a restore can check that the dump was made under the same schema and policy."
    format_version: int = Field(default=..., title="Format version", description="The version of the dump archive layout; a restore refuses a version it does not know.")
    created_at: datetime  = Field(default=..., title="Dump created at", description="When the dump was taken, so a person choosing among dumps can tell them apart.")
    toolkit_version: str = Field(default=..., title="Toolkit version", description="The version of the toolkit that wrote the dump.")
    schema_id: str = Field(default=..., title="Schema id", description="The id of the LinkML schema whose data the dump holds; a restore checks it against its own.")
    schema_version: Optional[str] = Field(default=None, title="Schema version", description="The version of that schema, when it declares one.")
    source_tenant: str = Field(default=..., title="Source tenant", description="The IRI of the tenant the dump was taken from.")
    source_tenant_id: str = Field(default=..., title="Source tenant id", description="The id part of the source tenant\u0027s IRI, which a restore replaces by the new tenant\u0027s id.")
    label: str = Field(default=..., title="Label", description="The preferred label of the object.")
    iri_policy: IriPolicy = Field(default=..., title="IRI policy", description="The IRI policy of the service; absent, the default policy applies.")


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
    allowed_actions: Optional[list[Action]] = Field(default=None, title="Allowed actions", description="The actions the caller who asked may take on the tenant, in the order read, modify, delete, administer. Only a listing fills it.")


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


class Authorised(ConfiguredBaseModel):
    "What a route\u0027s access check settled: the caller\u0027s principal, its access to the tenant, and the IRI of the tenant or aggregate it was checked on, which the route then acts on, and the global roles the token granted the caller."
    principal: str = Field(default=..., title="Principal", description="The user account the token identifies.")
    caller_access: CallerAccess = Field(default=..., title="Caller access", description="The caller\u0027s access to the tenant, as the access check loaded it.")
    checked_target: str = Field(default=..., title="Checked target", description="The IRI of the tenant or aggregate the access check was made on, which the route acts on.")
    global_roles: Optional[list[str]] = Field(default=None, title="Global roles", description="The system-level roles the token grants the principal.")


class Page(ConfiguredBaseModel):
    "One page of a listing, with the position of the page in the whole listing."
    items: list[Any] = Field(default=..., title="Items", description="The objects of the page; framed aggregates, or tenant summaries.")
    total: int = Field(default=..., title="Total", description="The number of objects in the whole listing.", ge=0)
    limit: int = Field(default=..., title="Limit", description="The most objects the page can hold.", ge=1, le=200)
    offset: int = Field(default=..., title="Offset", description="The position of the page\u0027s first object in the whole listing.", ge=0)


class Filter(ConfiguredBaseModel):
    "One equality filter of a listing, the name of a slot of the listed type and the value it must have, as the text the caller sent."
    slot: str = Field(default=..., title="Filter slot", description="The name of the slot the filter is on.")
    value: str = Field(default=..., title="Filter value", description="The value the slot must have, as text.")


class ListRequest(ConfiguredBaseModel):
    "The query of a listing, as the caller sent it: the equality filters, the position and size of the page and the key to sort by."
    limit: Optional[int] = Field(default=50, title="Limit", description="The most objects the page can hold.", ge=1, le=200)
    offset: Optional[int] = Field(default=0, title="Offset", description="The position of the page\u0027s first object in the whole listing.", ge=0)
    sort: Optional[str] = Field(default=None, title="Sort", description="The slot a listing is ordered by, ascending, or descending when its name starts with a minus sign; absent, the listing is ordered by IRI.")
    filters: Optional[list[Filter]] = Field(default=None, title="Filters", description="The equality filters of a listing; all of them must hold.")


class Condition(ConfiguredBaseModel):
    "An equality filter of a listing resolved against the slots of the listed type: the aggregate has this statement. The value is an IRI when it is a reference, else a literal of the datatype."
    predicate: str = Field(default=..., title="Condition predicate", description="The IRI of the predicate the aggregate must have a statement with.")
    value: str = Field(default=..., title="Condition value", description="The value of the statement, an IRI or the lexical form of a literal.")
    datatype: Optional[str] = Field(default=None, title="Condition datatype", description="The IRI of the datatype of a literal value; absent for a plain string.")
    reference: Optional[bool] = Field(default=False, title="Condition reference", description="Whether the value is an IRI rather than a literal.")


class ListPlan(ConfiguredBaseModel):
    "A listing resolved against the slots of the listed type: the class, the typed conditions, the predicate to order by (none orders by IRI), the page, and the graphs of the aggregates the caller may not read."
    target: str = Field(default=..., title="Plan class", description="The IRI of the class of the aggregates listed.")
    conditions: Optional[list[Condition]] = Field(default=None, title="Conditions", description="The equality conditions of a listing; all of them must hold.")
    sort_by: Optional[str] = Field(default=None, title="Plan sort", description="The IRI of the predicate a listing is ordered by; absent, it is ordered by IRI.")
    descending: Optional[bool] = Field(default=False, title="Descending", description="Whether the order is reversed.")
    limit: int = Field(default=..., title="Limit", description="The most objects the page can hold.", ge=1, le=200)
    offset: int = Field(default=..., title="Offset", description="The position of the page\u0027s first object in the whole listing.", ge=0)
    hidden_graphs: Optional[list[str]] = Field(default=None, title="Hidden graphs", description="The IRIs of the graphs of the aggregates a listing leaves out.")


class Problem(ConfiguredBaseModel):
    "An RFC 9457 problem detail, the body of every error answer of the service."
    type: str = Field(default=..., title="Problem type", description="The IRI that identifies the kind of problem.")
    title: str = Field(default=..., title="Problem title", description="A short, fixed summary of the kind of problem.")
    status: int = Field(default=..., title="Problem status", description="The HTTP status code of the answer.")
    detail: Optional[str] = Field(default=None, title="Problem detail", description="An explanation of this occurrence of the problem.")
    instance: Optional[str] = Field(default=None, title="Problem instance", description="The IRI that identifies this occurrence of the problem.")


class ProblemKind(ConfiguredBaseModel):
    "A kind of problem the service answers with: the slug that ends its problem type IRI, its fixed title and the HTTP status it comes with."
    slug: str = Field(default=..., title="Problem slug", description="The last segment of the problem type IRI, lower case words joined by hyphens.")
    title: str = Field(default=..., title="Problem title", description="A short, fixed summary of the kind of problem.")
    status: int = Field(default=..., title="Problem status", description="The HTTP status code of the answer.")

    @field_validator("slug")
    def pattern_slug(cls, v):
        pattern=re.compile("^[a-z]+(?:-[a-z]+)*$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.fullmatch(element):
                    err_msg = "Invalid slug format: " + str(element)
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.fullmatch(v):
            err_msg = "Invalid slug format: " + str(v)
            raise ValueError(err_msg)
        return v


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


class AggregateHead(ConfiguredBaseModel):
    "The IRI, the types and the version token of one stored aggregate, without its content."
    head_iri: Optional[str] = Field(default=None, title="Head IRI", description="The IRI of the stored aggregate.")
    head_types: Optional[list[str]] = Field(default=None, title="Head types", description="The class IRIs the stored aggregate is typed with.")
    head_version: Optional[str] = Field(default=None, title="Head version", description="The version token of the stored aggregate\u0027s graph.")


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
ServiceSettings.model_rebuild()
IdSpec.model_rebuild()
IriPolicy.model_rebuild()
TenantDump.model_rebuild()
VerifiedCaller.model_rebuild()
TenantCreate.model_rebuild()
TenantSummary.model_rebuild()
LabelUpdate.model_rebuild()
GrantSet.model_rebuild()
CallerAccess.model_rebuild()
Authorised.model_rebuild()
Page.model_rebuild()
Filter.model_rebuild()
ListRequest.model_rebuild()
Condition.model_rebuild()
ListPlan.model_rebuild()
Problem.model_rebuild()
ProblemKind.model_rebuild()
AccountSummary.model_rebuild()
Referrer.model_rebuild()
ReferrerList.model_rebuild()
MemberList.model_rebuild()
AggregateHead.model_rebuild()
