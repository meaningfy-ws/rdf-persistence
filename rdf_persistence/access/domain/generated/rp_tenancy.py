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
from rdf_persistence.core.domain.generated.rp_annotations import Described
from rdf_persistence.core.domain.generated.rp_core import AggregateRoot

from .rp_access import (
    Grant,
    Policy,
    Prohibition
)


metamodel_version = "1.12.0"
version = "None"


from rdf_persistence.core.domain.base import RpModel as ConfiguredBaseModel

linkml_meta = None

class TenantState(str, _Enum):
    "The states of a tenant."
    ACTIVE = "active"
    "The tenant is in use."
    DELETING = "deleting"
    "The tenant is being deleted and answers as if it did not exist."



class TenantLabelled(ConfiguredBaseModel):
    "A mixin for what carries a tenant\u0027s label, one line of 1 to 200 characters that neither starts nor ends in a space; the access record and the service\u0027s request bodies share it, so the label is checked the same everywhere."
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


class TenantAccess(Policy, TenantLabelled, Described, AggregateRoot):
    "The access record of a tenant: its label, state and database name, with the grants and prohibitions that say who may do what in it."
    state: TenantState = _Field(default=..., title="State", description="Where the tenant is in its life.")
    database_name: str = _Field(default=..., title="Database name", description="The name of the tenant\u0027s database, the prefix, \"-t-\" and the tenant id (hyphens left out); the prefix is lower case, at most 20 characters, the tenant id 4 to 32 lower case letters and digits.", json_schema_extra = { "rp_internal": True })
    store_name: _Optional[str] = _Field(default=None, title="Store name", description="The name of the wired store that holds the tenant\u0027s database; absent means the store named \"default\". It is lower case, starts with a letter and is at most 32 characters long.", json_schema_extra = { "rp_internal": True })
    grants: _Optional[list[Grant]] = _Field(default=None, title="Grants", description="The permissions given in the tenant, by role or as direct actions; they live in the access record\u0027s graph.")
    prohibitions: _Optional[list[Prohibition]] = _Field(default=None, title="Prohibitions", description="The actions forbidden in the tenant; they live in the access record\u0027s graph.")
    id: str = _Field(default=..., title="Identifier", description="The IRI that identifies the object.")
    label: str = _Field(default=..., title="Label", description="The preferred label of the object.")
    description: _Optional[str] = _Field(default=None, title="Description", description="A free-text description of the object.")

    @field_validator("database_name")
    def pattern_database_name(cls, v):
        pattern=re.compile("^[a-z][a-z0-9]{0,19}-t-[a-z0-9]{4,32}$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.fullmatch(element):
                    err_msg = "Invalid database_name format: " + str(element)
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.fullmatch(v):
            err_msg = "Invalid database_name format: " + str(v)
            raise ValueError(err_msg)
        return v

    @field_validator("store_name")
    def pattern_store_name(cls, v):
        pattern=re.compile("^[a-z][a-z0-9-]{0,31}$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.fullmatch(element):
                    err_msg = "Invalid store_name format: " + str(element)
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.fullmatch(v):
            err_msg = "Invalid store_name format: " + str(v)
            raise ValueError(err_msg)
        return v

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

    @model_validator(mode="after")
    def unique_keys_grants_grant_key(self) -> "TenantAccess":
        seen: set[str] = set()
        repeated: list[tuple] = []
        value = self.grants
        for item in value.values() if isinstance(value, dict) else value if isinstance(value, list) else ([] if value is None else [value]):
            key = (item.assignee, item.target, item.role, item.action,)
            if repr(key) in seen:
                repeated.append(key)
            seen.add(repr(key))
        if repeated:
            raise ValueError(
                "TenantAccess.grants: unique_keys grant_key (assignee, target, role, action) repeated by "
                + str(repeated)
            )
        return self


class TenantSweepReport(ConfiguredBaseModel):
    "The outcome of a sweep of one live tenant: the loaded graphs and bucket objects found orphaned past the grace period, and whether each list was removed."
    tenant: str = _Field(default=..., title="Tenant", description="The IRI of the tenant.")
    older_than_seconds: int = _Field(default=..., title="Older than seconds", description="The grace period in seconds; only what is older is reported.")
    loaded_graphs: list[str] = _Field(default=..., title="Loaded graphs", description="The IRIs of the orphaned loaded graphs found, sorted.")
    blobs: list[str] = _Field(default=..., title="Blobs", description="The keys of the orphaned bucket objects found, sorted.")
    removed_loaded_graphs: bool = _Field(default=..., title="Removed loaded graphs", description="Whether the orphaned loaded graphs were removed.")
    removed_blobs: bool = _Field(default=..., title="Removed blobs", description="Whether the orphaned bucket objects were removed.")
    skipped_blobs: list[str] = _Field(default=..., title="Skipped blobs", description="The keys of orphaned objects the object store would not delete.")


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
TenantLabelled.model_rebuild()
TenantAccess.model_rebuild()
TenantSweepReport.model_rebuild()
