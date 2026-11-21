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


class ReferrerRow(ConfiguredBaseModel):
    "One link to a resource, as the store holds it: the referrer, its class, the class of the subject when it is a part, and the predicate, all IRIs; the schema names are the caller\u0027s to find."
    referrer: str = _Field(default=..., title="Referrer", description="The IRI of the aggregate root that holds the link.")
    referrer_class: str = _Field(default=..., title="Referrer class", description="The IRI of a class of the referrer; a root of several classes gives one row per class.")
    subject_class: _Optional[str] = _Field(default=None, title="Subject class", description="The IRI of the class of the statement\u0027s subject when that is a part of the referrer; absent when the subject is the referrer itself.")
    predicate: str = _Field(default=..., title="Predicate", description="The IRI of the predicate that links to the resource.")


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
ReferrerRow.model_rebuild()
