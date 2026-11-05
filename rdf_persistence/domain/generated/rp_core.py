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


class RpAnnotation(str, Enum):
    "The annotations the toolkit reads from a schema, one entry per tag; any other tag is left alone. Each description says which element carries the tag and which values it accepts."
    OWNED = "owned"
    "Slot annotation, `true` when the slot\u0027s values are part of the aggregate and live in its graph; any other slot ranging over a class refers to another aggregate root, by IRI."
    INTERNAL = "internal"
    "Slot annotation, `true` when the slot never appears in the API contract; the toolkit writes it."
    GRAPH = "graph"
    "Class annotation, `meta` (see GraphKind) for the tenant root object, which lives in the tenant\u0027s meta graph instead of a graph of its own."
    DATABASE = "database"
    "Class annotation, `tenant` (the default) or `system` (see DatabaseKind): the database an aggregate lives in."
    MODULE_KIND = "module_kind"
    "Schema annotation, `domain`, `technical` or `access` (see ModuleKind): the kind of the module; a domain module may not import a technical or an access one."
    RP_PATH = "rp_path"
    "Class annotation, required on every aggregate root: its path segment in the API and in its IRIs. It follows the pattern of the url_segment slot."
    RP_UNLABELLED = "rp_unlabelled"
    "Class annotation, `true` on an owned value class whose instances need no label of their own."
    BOOKKEEPING = "bookkeeping"
    "Slot annotation, `true` when the session writes the slot about a graph (its version, who created or contributed to it, when); closed shapes ignore the statement."


class ModuleKind(str, Enum):
    "The kinds of schema module, the values of the module_kind annotation."
    DOMAIN = "domain"
    "A module of the application\u0027s domain; it imports no technical or access module."
    TECHNICAL = "technical"
    "A module of technical concerns, such as files or provenance."
    ACCESS = "access"
    "A module of access control, such as grants and tenancy."


class DatabaseKind(str, Enum):
    "The databases an aggregate can live in, the values of the database annotation."
    TENANT = "tenant"
    "The tenant\u0027s own database, the default."
    SYSTEM = "system"
    "The system database, shared by all tenants."


class GraphKind(str, Enum):
    "The special graphs a class can live in, the values of the graph annotation."
    META = "meta"
    "The tenant\u0027s meta graph, which holds the tenant root object."



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
