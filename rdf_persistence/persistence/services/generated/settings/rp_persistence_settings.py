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


class LimitSettings(ConfiguredBaseModel):
    "The most the toolkit takes in one message bus run, one commit, one body and one restore manifest."
    max_messages: int = _Field(default=100, title="Maximum messages", description="The most messages one run of the message bus handles.", ge=1)
    max_roots: int = _Field(default=500, title="Maximum roots", description="The most aggregate roots one commit transaction holds.", ge=1)
    max_named_referrers: int = _Field(default=20, title="Maximum named referrers", description="The most referrers a refused delete names in its answer; 0 names none and counts all of them.", ge=0)
    max_document_nodes: int = _Field(default=10000, title="Maximum document nodes", description="The most objects and list values one JSON or JSON-LD body may hold.", ge=1)
    max_manifest_bytes: int = _Field(default=65536, title="Maximum manifest size", description="The most bytes the manifest of a tenant dump may hold.", ge=1)


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
LimitSettings.model_rebuild()
