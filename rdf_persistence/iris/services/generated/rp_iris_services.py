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

class IdKind(str, _Enum):
    "The ways an id is drawn."
    UUID4 = "uuid4"
    "A random UUID, in its canonical form."
    RANDOM = "random"
    "Characters drawn at random from an alphabet."



class ServiceSettings(ConfiguredBaseModel):
    "The settings of `install_service`: where the service is mounted, how it names tenants and which role its callers get on a tenant they create."
    base: str = _Field(default=..., title="Base", description="The IRI under which the service mints identifiers and problem types, ending in a slash.")
    prefix: str = _Field(default=..., title="Prefix", description="The prefix of the database names of the service\u0027s tenants; lower case, at most 20 characters.")
    tenant_segment: str = _Field(default=..., title="Tenant segment", description="The path segment that names the tenant collection in the service\u0027s routes.")
    creator_role: str = _Field(default=..., title="Creator role", description="The role a caller is given on the tenant it creates.")
    roles_claim: str = _Field(default=..., title="Roles claim", description="The claim of the token that holds the caller\u0027s global roles, an object keyed by role name; for Zitadel, urn:zitadel:iam:org:project:{project_id}:roles of the consumer\u0027s project.")
    max_body_bytes: _Optional[int] = _Field(default=1048576, title="Maximum body size", description="The most bytes a request body may hold; a larger one is refused with 413 before it is read whole.", ge=1)
    max_restore_bytes: _Optional[int] = _Field(default=1073741824, title="Maximum restore size", description="The most bytes a restore archive may hold once decompressed, counting each member\u0027s size and its tar block; a larger archive is refused with `InvalidBody` as it is read, so a small hostile upload cannot fill the memory or the object store.", ge=1)
    deployment: _Optional[str] = _Field(default=None, title="Deployment", description="A slug that names this deployment, for templates that use `{deployment}`; lower case letters and digits, at most 32.")
    public_url: _Optional[str] = _Field(default=None, title="Public URL", description="The address this deployment is reachable at from outside, without a trailing slash; the event envelope\u0027s context link is absolute under it. Absent, the link is relative.")
    iri_policy: _Optional[IriPolicy] = _Field(default=None, title="IRI policy", description="The IRI policy of the service; absent, the default policy applies.")

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

    @field_validator("public_url")
    def pattern_public_url(cls, v):
        pattern=re.compile("^https?://.+[^/]$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.fullmatch(element):
                    err_msg = "Invalid public_url format: " + str(element)
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.fullmatch(v):
            err_msg = "Invalid public_url format: " + str(v)
            raise ValueError(err_msg)
        return v


class IdSpec(ConfiguredBaseModel):
    "How the toolkit draws an id: a UUIDv4, or `length` characters drawn from `alphabet`. The length is required for `random` ids."
    kind: IdKind = _Field(default=..., title="Id kind", description="Whether ids are UUIDv4 or random characters of an alphabet.")
    length: _Optional[int] = _Field(default=None, title="Id length", description="The number of characters of a random id, 4 to 32.", ge=4, le=32)
    alphabet: _Optional[str] = _Field(default="0123456789abcdefghijklmnopqrstuvwxyz", title="Id alphabet", description="The characters a random id is drawn from, each a lower case letter or a digit.")

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
    "The templates the toolkit mints and accepts IRIs by, one per kind of IRI, and the id specifications of tenant and object ids. Every slot defaults to today\u0027s shape, so an empty policy is the default one. A template fills the variables allowed for its kind; the tenant, aggregate, part, loaded graph and principal templates end in their id variable, the access, meta, registry and provenance templates contain the tenant, and the aggregate, part and loaded graph templates name their tenant or, for the last two, their root."
    tenant_template: _Optional[str] = _Field(default="{base}{tenant_segment}/{tenant_id}", title="Tenant template", description="The template of a tenant IRI; ends in `{tenant_id}`.")
    application_template: _Optional[str] = _Field(default="{base}app", title="Application template", description="The template of the application IRI, the root of the application database\u0027s IRIs.")
    access_template: _Optional[str] = _Field(default="{tenant}/access", title="Access template", description="The template of the IRI of a tenant\u0027s access record; contains `{tenant}` or `{tenant_id}`.")
    meta_template: _Optional[str] = _Field(default="{tenant}/meta", title="Meta template", description="The template of the IRI of a tenant\u0027s meta graph; contains `{tenant}` or `{tenant_id}`.")
    registry_template: _Optional[str] = _Field(default="{tenant}/registry", title="Registry template", description="The template of the IRI of a tenant\u0027s registry graph; contains `{tenant}` or `{tenant_id}`.")
    provenance_template: _Optional[str] = _Field(default="{tenant}/provenance", title="Provenance template", description="The template of the IRI of a tenant\u0027s provenance graph; contains `{tenant}` or `{tenant_id}`.")
    aggregate_template: _Optional[str] = _Field(default="{tenant}/{rp_path}/{id}", title="Aggregate template", description="The template of an aggregate root IRI; contains `{tenant}` or `{tenant_id}` and ends in `{id}`.")
    part_template: _Optional[str] = _Field(default="{root}/parts/{id}", title="Part template", description="The template of the IRI of an owned part; contains `{tenant}`, `{tenant_id}` or `{root}` and ends in `{id}`.")
    loaded_graph_template: _Optional[str] = _Field(default="{root}/content/{id}", title="Loaded graph template", description="The template of the IRI of a loaded graph; contains `{tenant}`, `{tenant_id}` or `{root}` and ends in `{id}`.")
    principal_template: _Optional[str] = _Field(default="{issuer}/users/{sub}", title="Principal template", description="The template of the IRI of a principal; ends in `{sub}`.")
    tenant_id: _Optional[IdSpec] = _Field(default=None, title="Tenant id", description="How the id of a new tenant is drawn; absent, a UUIDv4.")
    object_id: _Optional[IdSpec] = _Field(default=None, title="Object id", description="How the id of a new aggregate root, part or loaded graph is drawn; absent, a UUIDv4.")

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

    @field_validator("application_template")
    def pattern_application_template(cls, v):
        pattern=re.compile("^(?:[a-z0-9/:.-]|\\{(?:base|deployment|tenant_segment)\\})+$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.fullmatch(element):
                    err_msg = "Invalid application_template format: " + str(element)
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.fullmatch(v):
            err_msg = "Invalid application_template format: " + str(v)
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

    @field_validator("provenance_template")
    def pattern_provenance_template(cls, v):
        pattern=re.compile("^(?:[a-z0-9/:.-]|\\{(?:base|deployment|tenant|tenant_id)\\})*\\{tenant(?:_id)?\\}(?:[a-z0-9/:.-]|\\{(?:base|deployment|tenant|tenant_id)\\})*$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.fullmatch(element):
                    err_msg = "Invalid provenance_template format: " + str(element)
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.fullmatch(v):
            err_msg = "Invalid provenance_template format: " + str(v)
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


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
ServiceSettings.model_rebuild()
IdSpec.model_rebuild()
IriPolicy.model_rebuild()
