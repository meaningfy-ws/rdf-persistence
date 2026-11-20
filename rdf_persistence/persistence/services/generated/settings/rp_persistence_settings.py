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


class LimitSettings(ConfiguredBaseModel):
    "The most the toolkit takes in one message bus run, one commit, one body and one restore manifest."
    max_messages: int = Field(default=100, title="Maximum messages", description="The most messages one run of the message bus handles.", ge=1)
    max_roots: int = Field(default=500, title="Maximum roots", description="The most aggregate roots one commit transaction holds.", ge=1)
    max_named_referrers: int = Field(default=20, title="Maximum named referrers", description="The most referrers a refused delete names in its answer; 0 names none and counts all of them.", ge=0)
    max_document_nodes: int = Field(default=10000, title="Maximum document nodes", description="The most objects and list values one JSON or JSON-LD body may hold.", ge=1)
    max_manifest_bytes: int = Field(default=65536, title="Maximum manifest size", description="The most bytes the manifest of a tenant dump may hold.", ge=1)


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
LimitSettings.model_rebuild()
