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
from rdf_persistence import (
    AggregateRoot,
    Described,
    Principal,
    Tracked
)


metamodel_version = "1.12.0"
version = "None"


from rdf_persistence import RpModel as ConfiguredBaseModel

linkml_meta = None


class Template(Tracked, Described, AggregateRoot):
    "A report template shared by every library."
    identifier: _Optional[str] = _Field(default=None, title="Identifier", description="A business code of the template, a literal; not its IRI, though the toolkit\u0027s id slot has the same slot_uri.")
    version: _Optional[str] = _Field(default=None, title="Version", description="The edition of the template; a slot of this module, though the toolkit has an internal slot of the same name.")
    id: str = _Field(default=..., title="Identifier", description="The IRI that identifies the object.")
    label: str = _Field(default=..., title="Label", description="The preferred label of the object.")
    description: _Optional[str] = _Field(default=None, title="Description", description="A free-text description of the object.")
    created: _Optional[datetime ] = _Field(default=None, title="Created", description="The time the graph was first committed.")
    modified: _Optional[datetime ] = _Field(default=None, title="Modified", description="The time the graph was last committed.")
    creator: _Optional[str] = _Field(default=None, title="Creator", description="The principal that first committed the graph.")
    contributor: _Optional[list[str]] = _Field(default=None, title="Contributor", description="A principal that committed a later version of the graph.")


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
Template.model_rebuild()
