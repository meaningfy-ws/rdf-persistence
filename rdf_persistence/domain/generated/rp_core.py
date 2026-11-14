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
    "Class annotation, `tenant` (the default), `system` or `application` (see DatabaseKind): the database an aggregate lives in."
    MODULE_KIND = "module_kind"
    "Schema annotation, `domain`, `technical` or `access` (see ModuleKind): the kind of the module; a domain module may not import a technical or an access one."
    RP_PATH = "rp_path"
    "Class annotation, required on every aggregate root: its path segment in the API. It follows the pattern of the url_segment slot."
    RP_IRI_TYPE = "rp_iri_type"
    "Class annotation, the `{type}` segment of the IRIs of the class\u0027s instances; default, the class name in kebab case. It follows the pattern of the url_segment slot and is unique in a schema."
    RP_UNLABELLED = "rp_unlabelled"
    "Class annotation, `true` on an owned value class whose instances need no label of their own."
    RP_WRITES = "rp_writes"
    "Class annotation (see WritesKind). `service` marks an aggregate root whose generic create, replace and delete are not served; the consumer writes it through a session. A root that mixes in StoredFile is service-written without it. `toolkit` marks a root the toolkit writes and reads itself, which no route serves."
    WORKFLOW = "workflow"
    "Class annotation on an aggregate root: the name of the workflow its instances follow, which follows the pattern of the url_segment slot; the root includes UnderWorkflow. A subclass inherits it."
    BOOKKEEPING = "bookkeeping"
    "Slot annotation, `true` when the session writes the slot about a graph (its version, who created or contributed to it, when); closed shapes ignore the statement."
    RP_UNIQUE_SCOPE = "rp_unique_scope"
    "Annotation of a `unique_keys` entry on an aggregate root (or an ancestor of roots), `tenant` (see UniqueScope): the key holds across the aggregates of a tenant, not inside one aggregate. A key without it keeps its in-aggregate meaning."


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
    APPLICATION = "application"
    "The application database, one per deployment, outside every tenant."


class WritesKind(str, Enum):
    "How an aggregate root is written, the values of the rp_writes annotation."
    SERVICE = "service"
    "The consumer writes the root through a session; the API serves no generic create, replace or delete."
    TOOLKIT = "toolkit"
    "The toolkit writes and reads the root itself; no route serves it, and the consumer does not write it."


class GraphKind(str, Enum):
    "The special graphs a class can live in, the values of the graph annotation."
    META = "meta"
    "The tenant\u0027s meta graph, which holds the tenant root object."


class UniqueScope(str, Enum):
    "The scopes of a key across aggregates, the values of the rp_unique_scope annotation."
    TENANT = "tenant"
    "The key holds across all the aggregate roots of one class in a tenant\u0027s database."



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


class PendingLoad(ConfiguredBaseModel):
    "The registry marker of a load not yet committed: one triple saying when the graph was put. It names no registry entry, so deleting it never deletes an entry."
    id: str = Field(default=..., title="Identifier", description="The IRI of the graph the load put; the marker\u0027s subject, so no rp:graph triple.")
    loaded_at: datetime  = Field(default=..., title="Loaded at", description="The time a graph was put to the store by a load.")


class CommitMarker(ConfiguredBaseModel):
    "The registry marker of one transaction\u0027s commit: a fresh IRI per transaction, written first in the single request, so the writes that follow apply only if it was written."
    id: str = Field(default=..., title="Identifier", description="A fresh urn:uuid IRI, never shared by two transactions.")
    started_at: datetime  = Field(default=..., title="Started at", description="The time a transaction started.")


class AggregateKey(ConfiguredBaseModel):
    "A key across aggregates, as the runtime reads it from the schema: no two aggregate roots of one class in a tenant\u0027s database hold the same values for its predicates."
    key_name: str = Field(default=..., title="Key name", description="The name of a key across aggregates, as declared in `unique_keys`.")
    root_class: str = Field(default=..., title="Root class", description="The IRI of the class of the aggregate roots the key governs; a root of a subclass is its own scope.")
    key_predicates: list[str] = Field(default=..., title="Key predicates", description="The predicates of the key\u0027s slots, in the order of the key.")


class KeyDuplicate(ConfiguredBaseModel):
    "A set of aggregate roots of one class that hold the same values for a key across aggregates, found in a tenant\u0027s database by the duplicates report."
    key_name: str = Field(default=..., title="Key name", description="The name of a key across aggregates, as declared in `unique_keys`.")
    root_class: str = Field(default=..., title="Root class", description="The IRI of the class of the roots.")
    key_values: list[str] = Field(default=..., title="Key values", description="The lexical forms of the shared values, in the order of the key.")
    key_roots: list[str] = Field(default=..., title="Key roots", description="The IRIs of the roots that hold the values, sorted.")


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
AggregateRoot.model_rebuild()
Principal.model_rebuild()
RegistryEntry.model_rebuild()
PendingLoad.model_rebuild()
CommitMarker.model_rebuild()
AggregateKey.model_rebuild()
KeyDuplicate.model_rebuild()
