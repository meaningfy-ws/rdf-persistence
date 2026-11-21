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


class IriTemplateVariables(ConfiguredBaseModel):
    "The settings\u0027 values that every IRI template writes in as plain text: the base, the deployment (empty when there is none) and the tenant segment. A mapping of them goes to `str.format` and to the pattern compiler, which take a mapping (technical-models PD-5)."
    base: str = _Field(default=..., title="Base", description="The base IRI of the service, as the settings give it.")
    deployment: str = _Field(default=..., title="Deployment", description="The deployment segment of the IRIs; empty when the settings give none.")
    tenant_segment: str = _Field(default=..., title="Tenant segment", description="The path segment that holds the tenants, as the settings give it.")


class IriParts(ConfiguredBaseModel):
    "The named groups of an IRI template\u0027s match. A group the model does not name is refused: it would be a pattern that the toolkit builds and no reader reads."
    tenant: _Optional[str] = _Field(default=None, title="Tenant", description="The tenant IRI a pattern matched.")
    tenant_id: _Optional[str] = _Field(default=None, title="Tenant id", description="The id of the tenant a pattern matched.")
    id: _Optional[str] = _Field(default=None, title="Object id", description="The id of the aggregate or part a pattern matched.")
    type: _Optional[str] = _Field(default=None, title="Type", description="The class type a pattern matched.")
    rp_path: _Optional[str] = _Field(default=None, title="Path segment", description="The path segment of the aggregate\u0027s class a pattern matched.")
    root: _Optional[str] = _Field(default=None, title="Root", description="The root IRI a pattern matched.")


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
IriTemplateVariables.model_rebuild()
IriParts.model_rebuild()
