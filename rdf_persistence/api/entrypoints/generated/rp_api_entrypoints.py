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
from rdf_persistence.access.services.generated.rp_access_services import (
    AccountSummary,
    CallerAccess,
    GrantSet,
    VerifiedCaller
)
from rdf_persistence.collaboration.services.generated.rp_collaboration_services import (
    MemberList,
    Referrer,
    ReferrerList
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
    OnReferencedDelete,
    PendingLoad,
    Principal,
    RegistryEntry,
    RegistryKind,
    RpAnnotation,
    UniqueScope,
    WritesKind
)
from rdf_persistence.persistence.services.generated.rp_persistence_services import (
    AggregateHead,
    Condition,
    Contains,
    Filter,
    ListPlan,
    ListRequest,
    Page
)


metamodel_version = "1.12.0"
version = "None"


from rdf_persistence.core.domain.base import RpModel as ConfiguredBaseModel

linkml_meta = None

class ProblemSlug(str, _Enum):
    "The kinds of problem the toolkit answers with, by the last segment of their problem type IRI, with the underscores written as hyphens."
    INVALID_TOKEN = "invalid_token"
    "No bearer token, or one the service refuses."
    FORBIDDEN = "forbidden"
    "The caller may see the thing but is not allowed the action."
    NOT_FOUND = "not_found"
    "There is no such thing, or the caller cannot see it."
    CONFLICT = "conflict"
    "The write lost a race, or the thing to create already exists."
    KEY_CONFLICT = "key_conflict"
    "The write would give an aggregate a key value that another aggregate of its class holds."
    IN_USE = "in_use"
    "The delete would leave other aggregates pointing at a class that refuses it; the answer names them."
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
    TENANT_BEHIND = "tenant_behind"
    "The tenant\u0027s data follows an older schema version than the service runs; it is not served until migrated."
    PAYLOAD_TOO_LARGE = "payload_too_large"
    "The body is larger than the service takes."
    METHOD_NOT_ALLOWED = "method_not_allowed"
    "The route has no such method."
    INTERNAL_ERROR = "internal_error"
    "The service failed; the answer says no more."



class TenantCreate(TenantLabelled):
    "The body that creates a tenant, its label and the slots of the tenant\u0027s root object."
    root: _Any = _Field(default=..., title="Root", description="The slots of the tenant\u0027s root object, as the application\u0027s schema defines them.")
    label: str = _Field(default=..., title="Label", description="The preferred label of the object.")

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


class LabelUpdate(TenantLabelled):
    "The body that replaces the label of a tenant."
    label: str = _Field(default=..., title="Label", description="The preferred label of the object.")

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


class Authorised(ConfiguredBaseModel):
    "What a route\u0027s access check settled: the caller\u0027s principal, its access to the tenant, and the IRI of the tenant or aggregate it was checked on, which the route then acts on, and the global roles the token granted the caller."
    principal: str = _Field(default=..., title="Principal", description="The user account the token identifies.")
    caller_access: CallerAccess = _Field(default=..., title="Caller access", description="The caller\u0027s access to the tenant, as the access check loaded it.")
    checked_target: str = _Field(default=..., title="Checked target", description="The IRI of the tenant or aggregate the access check was made on, which the route acts on.")
    global_roles: _Optional[list[str]] = _Field(default=None, title="Global roles", description="The system-level roles the token grants the principal.")


class Problem(ConfiguredBaseModel):
    "An RFC 9457 problem detail, the body of every error answer of the service."
    type: str = _Field(default=..., title="Problem type", description="The IRI that identifies the kind of problem.")
    title: str = _Field(default=..., title="Problem title", description="A short, fixed summary of the kind of problem.")
    status: int = _Field(default=..., title="Problem status", description="The HTTP status code of the answer.")
    detail: _Optional[str] = _Field(default=None, title="Problem detail", description="An explanation of this occurrence of the problem.")
    instance: _Optional[str] = _Field(default=None, title="Problem instance", description="The IRI that identifies this occurrence of the problem.")


class InUseProblem(Problem):
    "The problem detail of a delete refused because other aggregates still point at the resource: it names up to the configured number of referrers the caller may read, and counts the rest."
    referrers: _Optional[list[Referrer]] = _Field(default=None, title="Referrers", description="The aggregates that point at the resource, ordered by IRI and slot.")
    hidden_count: _Optional[int] = _Field(default=None, title="Hidden count", description="The number of referrers or members the caller may not read, so are not listed.", ge=0)
    more_count: _Optional[int] = _Field(default=None, title="More count", description="The number of referrers the caller may read but the answer does not name, past the limit.", ge=0)
    type: str = _Field(default=..., title="Problem type", description="The IRI that identifies the kind of problem.")
    title: str = _Field(default=..., title="Problem title", description="A short, fixed summary of the kind of problem.")
    status: int = _Field(default=..., title="Problem status", description="The HTTP status code of the answer.")
    detail: _Optional[str] = _Field(default=None, title="Problem detail", description="An explanation of this occurrence of the problem.")
    instance: _Optional[str] = _Field(default=None, title="Problem instance", description="The IRI that identifies this occurrence of the problem.")


class ProblemKind(ConfiguredBaseModel):
    "A kind of problem the service answers with: the slug that ends its problem type IRI, its fixed title and the HTTP status it comes with."
    slug: str = _Field(default=..., title="Problem slug", description="The last segment of the problem type IRI, lower case words joined by hyphens.")
    title: str = _Field(default=..., title="Problem title", description="A short, fixed summary of the kind of problem.")
    status: int = _Field(default=..., title="Problem status", description="The HTTP status code of the answer.")

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


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
TenantCreate.model_rebuild()
LabelUpdate.model_rebuild()
Authorised.model_rebuild()
Problem.model_rebuild()
InUseProblem.model_rebuild()
ProblemKind.model_rebuild()
