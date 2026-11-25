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
    OnReferencedDelete,
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

linkml_meta = None


class MigrationStep(ConfiguredBaseModel):
    "One step of a migration: three group graph patterns, as text, that the toolkit wraps into one update request over the graphs of a database. A step with `unresolved` is a draft and does not load."
    title: str = _Field(default=..., title="Title", description="A short name for what a record describes.")
    where_pattern: _Optional[str] = _Field(default=None, title="Where pattern", description="The group graph pattern, as text, that selects what a migration step changes.")
    delete_pattern: _Optional[str] = _Field(default=None, title="Delete pattern", description="The group graph pattern, as text, of the triples a migration step removes.")
    insert_pattern: _Optional[str] = _Field(default=None, title="Insert pattern", description="The group graph pattern, as text, of the triples a migration step adds.")
    unresolved: _Optional[str] = _Field(default=None, title="Unresolved", description="Text saying what a draft step still needs from the developer; a step that has it does not load.")


class RoleRename(ConfiguredBaseModel):
    "One role name a migration changes to another in the stored grants."
    from_role: str = _Field(default=..., title="From role", description="The role name a grant names before the migration.")
    to_role: str = _Field(default=..., title="To role", description="The role name a grant names after the migration.")

    @field_validator("to_role")
    def pattern_to_role(cls, v):
        pattern=re.compile("^[^,]*$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.fullmatch(element):
                    err_msg = "Invalid to_role format: " + str(element)
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.fullmatch(v):
            err_msg = "Invalid to_role format: " + str(v)
            raise ValueError(err_msg)
        return v


class GrantRoles(ConfiguredBaseModel):
    "What a migration does to the role names in the stored grants of the system database: the renames, in the order they apply, then the names whose grants are deleted. In the file, `rename` is a map from the old name to the new one; loading turns it into the list."
    rename: _Optional[list[RoleRename]] = _Field(default=None, title="Rename", description="The role renames of a migration, in the order they apply.")
    drop: _Optional[list[str]] = _Field(default=None, title="Drop", description="The role names whose grants a migration deletes, after the renames.")


class Migration(ConfiguredBaseModel):
    "The reviewed file that moves the data of a database from one version of a schema to the next: the schema\u0027s id, the two versions and the steps, in order; and, optionally, the renames and drops of the role names in the stored grants."
    schema_id: str = _Field(default=..., title="Schema id", description="The id of the schema whose data the migration moves.")
    from_version: str = _Field(default=..., title="From version", description="The version of the schema that the data follows before the migration.")
    to_version: str = _Field(default=..., title="To version", description="The version of the schema that the data follows after the migration.")
    description: _Optional[str] = _Field(default=None, title="Description", description="A free-text description of the object.")
    steps: _Optional[list[MigrationStep]] = _Field(default=None, title="Steps", description="The steps of a migration, in the order they run.")
    grant_roles: _Optional[GrantRoles] = _Field(default=None, title="Grant roles", description="The renames and drops of role names in the stored grants of the system database.")


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
MigrationStep.model_rebuild()
RoleRename.model_rebuild()
GrantRoles.model_rebuild()
Migration.model_rebuild()
