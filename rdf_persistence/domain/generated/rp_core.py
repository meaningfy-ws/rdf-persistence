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

class RegistryKind(str, Enum):
    "The kinds of graph a registry entry can name."
    AGGREGATE = "aggregate"
    "The graph of an aggregate root."
    LOADED_GRAPH = "loaded_graph"
    "A graph loaded for an aggregate, whose lifecycle belongs to it."



class AggregateRoot(ConfiguredBaseModel):
    "A mixin for classes whose instances are aggregate roots. Each instance is one named graph, whose IRI is derived from the root\u0027s IRI; it is versioned, loaded and saved as a whole."
    pass


class Principal(ConfiguredBaseModel):
    "A reference to a user account in the identity provider, by IRI only."
    id: str = Field(default=..., title="Identifier", description="The IRI that identifies the object.")


class RegistryEntry(ConfiguredBaseModel):
    "An entry of a tenant\u0027s registry graph, naming a graph that belongs to an aggregate. It is written by the session, never by the application."
    graph: str = Field(default=..., title="Graph", description="The IRI of a named graph.")
    kind: RegistryKind = Field(default=..., title="Kind", description="The kind of graph a registry entry names.")
    owned_by: str = Field(default=..., title="Owned by", description="The IRI of the aggregate root that owns the graph.")


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
AggregateRoot.model_rebuild()
Principal.model_rebuild()
RegistryEntry.model_rebuild()
