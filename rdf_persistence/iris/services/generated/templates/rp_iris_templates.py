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


class IriTemplateVariables(ConfiguredBaseModel):
    "The settings\u0027 values that every IRI template writes in as plain text: the base, the deployment (empty when there is none) and the tenant segment. A mapping of them goes to `str.format` and to the pattern compiler, which take a mapping (technical-models PD-5)."
    base: str = Field(default=..., title="Base", description="The base IRI of the service, as the settings give it.")
    deployment: str = Field(default=..., title="Deployment", description="The deployment segment of the IRIs; empty when the settings give none.")
    tenant_segment: str = Field(default=..., title="Tenant segment", description="The path segment that holds the tenants, as the settings give it.")


class IriParts(ConfiguredBaseModel):
    "The named groups of an IRI template\u0027s match. A group the model does not name is refused: it would be a pattern that the toolkit builds and no reader reads."
    tenant: Optional[str] = Field(default=None, title="Tenant", description="The tenant IRI a pattern matched.")
    tenant_id: Optional[str] = Field(default=None, title="Tenant id", description="The id of the tenant a pattern matched.")
    id: Optional[str] = Field(default=None, title="Object id", description="The id of the aggregate or part a pattern matched.")
    type: Optional[str] = Field(default=None, title="Type", description="The class type a pattern matched.")
    rp_path: Optional[str] = Field(default=None, title="Path segment", description="The path segment of the aggregate\u0027s class a pattern matched.")
    root: Optional[str] = Field(default=None, title="Root", description="The root IRI a pattern matched.")


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
IriTemplateVariables.model_rebuild()
IriParts.model_rebuild()
