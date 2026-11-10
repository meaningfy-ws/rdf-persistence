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

from .rp_access import (
    Grant,
    Policy,
    Prohibition
)
from .rp_annotations import Described
from .rp_core import AggregateRoot


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

class TenantState(str, Enum):
    "The states of a tenant."
    ACTIVE = "active"
    "The tenant is in use."
    DELETING = "deleting"
    "The tenant is being deleted and answers as if it did not exist."



class TenantLabelled(ConfiguredBaseModel):
    "A mixin for what carries a tenant\u0027s label, one line of 1 to 200 characters that neither starts nor ends in a space; the access record and the service\u0027s request bodies share it, so the label is checked the same everywhere."
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


class TenantAccess(TenantLabelled, Described, AggregateRoot, Policy):
    "The access record of a tenant: its label, state and database name, with the grants and prohibitions that say who may do what in it."
    state: TenantState = Field(default=..., title="State", description="Where the tenant is in its life.")
    database_name: str = Field(default=..., title="Database name", description="The name of the tenant\u0027s database, the prefix, \"-t-\" and the tenant id (hyphens left out); the prefix is lower case, at most 20 characters, the tenant id 4 to 32 lower case letters and digits.", json_schema_extra = { "rp_internal": True })
    grants: Optional[list[Grant]] = Field(default=None, title="Grants", description="The permissions given in the tenant, by role or as direct actions; they live in the access record\u0027s graph.")
    prohibitions: Optional[list[Prohibition]] = Field(default=None, title="Prohibitions", description="The actions forbidden in the tenant; they live in the access record\u0027s graph.")
    id: str = Field(default=..., title="Identifier", description="The IRI that identifies the object.")
    label: str = Field(default=..., title="Label", description="The preferred label of the object.")
    description: Optional[str] = Field(default=None, title="Description", description="A free-text description of the object.")

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
        for item in self.grants or []:
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
    tenant: str = Field(default=..., title="Tenant", description="The IRI of the tenant.")
    older_than_seconds: int = Field(default=..., title="Older than seconds", description="The grace period in seconds; only what is older is reported.")
    loaded_graphs: list[str] = Field(default=..., title="Loaded graphs", description="The IRIs of the orphaned loaded graphs found, sorted.")
    blobs: list[str] = Field(default=..., title="Blobs", description="The keys of the orphaned bucket objects found, sorted.")
    removed_loaded_graphs: bool = Field(default=..., title="Removed loaded graphs", description="Whether the orphaned loaded graphs were removed.")
    removed_blobs: bool = Field(default=..., title="Removed blobs", description="Whether the orphaned bucket objects were removed.")
    skipped_blobs: list[str] = Field(default=..., title="Skipped blobs", description="The keys of orphaned objects the object store would not delete.")


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
TenantLabelled.model_rebuild()
TenantAccess.model_rebuild()
TenantSweepReport.model_rebuild()
