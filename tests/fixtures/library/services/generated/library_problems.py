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
from rdf_persistence import Problem


metamodel_version = "1.12.0"
version = "None"


from rdf_persistence import RpModel as ConfiguredBaseModel

linkml_meta = None


class HeldKeyProblem(Problem):
    "A problem detail that names the aggregate holding a key the request asked for."
    holder: str = _Field(default=..., title="Holder", description="The IRI of the aggregate that holds the key.")
    type: str = _Field(default=..., title="Problem type", description="The IRI that identifies the kind of problem.")
    title: str = _Field(default=..., title="Problem title", description="A short, fixed summary of the kind of problem.")
    status: int = _Field(default=..., title="Problem status", description="The HTTP status code of the answer.")
    detail: _Optional[str] = _Field(default=None, title="Problem detail", description="An explanation of this occurrence of the problem.")
    instance: _Optional[str] = _Field(default=None, title="Problem instance", description="The IRI that identifies this occurrence of the problem.")


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
HeldKeyProblem.model_rebuild()
