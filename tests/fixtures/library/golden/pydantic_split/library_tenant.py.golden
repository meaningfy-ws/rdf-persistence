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
from rdf_persistence import (
    Described,
    Principal,
    Tracked
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


class Library(Tracked, Described):
    "A library; the tenant root. Its IRI is the tenant IRI and it lives in the tenant\u0027s meta graph."
    city: Optional[str] = Field(default=None, title="City", description="The city where the library is located.")
    id: str = Field(default=..., title="Identifier", description="The IRI that identifies the object.")
    label: str = Field(default=..., title="Label", description="The preferred label of the object.")
    description: Optional[str] = Field(default=None, title="Description", description="A free-text description of the object.")
    created: Optional[datetime ] = Field(default=None, title="Created", description="The time the graph was first committed.")
    modified: Optional[datetime ] = Field(default=None, title="Modified", description="The time the graph was last committed.")
    creator: Optional[str] = Field(default=None, title="Creator", description="The principal that first committed the graph.")
    contributor: Optional[list[str]] = Field(default=None, title="Contributor", description="A principal that committed a later version of the graph.")


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
Library.model_rebuild()
