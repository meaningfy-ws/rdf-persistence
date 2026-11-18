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
from rdf_persistence.core.domain.generated.rp_annotations import (
    Described,
    Tracked
)
from rdf_persistence.core.domain.generated.rp_core import (
    AggregateKey,
    AggregateRoot,
    CommitMarker,
    DatabaseKind,
    GraphKind,
    KeyDuplicate,
    ModuleKind,
    PendingLoad,
    Principal,
    RegistryEntry,
    RegistryKind,
    RpAnnotation,
    UniqueScope,
    WritesKind
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


class MigrationStep(ConfiguredBaseModel):
    "One step of a migration: three group graph patterns, as text, that the toolkit wraps into one update request over the graphs of a database. A step with `unresolved` is a draft and does not load."
    title: str = Field(default=..., title="Title", description="A short name for what a record describes.")
    where_pattern: Optional[str] = Field(default=None, title="Where pattern", description="The group graph pattern, as text, that selects what a migration step changes.")
    delete_pattern: Optional[str] = Field(default=None, title="Delete pattern", description="The group graph pattern, as text, of the triples a migration step removes.")
    insert_pattern: Optional[str] = Field(default=None, title="Insert pattern", description="The group graph pattern, as text, of the triples a migration step adds.")
    unresolved: Optional[str] = Field(default=None, title="Unresolved", description="Text saying what a draft step still needs from the developer; a step that has it does not load.")


class Migration(ConfiguredBaseModel):
    "The reviewed file that moves the data of a database from one version of a schema to the next: the schema\u0027s id, the two versions and the steps, in order."
    schema_id: str = Field(default=..., title="Schema id", description="The id of the schema whose data the migration moves.")
    from_version: str = Field(default=..., title="From version", description="The version of the schema that the data follows before the migration.")
    to_version: str = Field(default=..., title="To version", description="The version of the schema that the data follows after the migration.")
    description: Optional[str] = Field(default=None, title="Description", description="A free-text description of the object.")
    steps: Optional[list[MigrationStep]] = Field(default=None, title="Steps", description="The steps of a migration, in the order they run.")


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
MigrationStep.model_rebuild()
Migration.model_rebuild()
