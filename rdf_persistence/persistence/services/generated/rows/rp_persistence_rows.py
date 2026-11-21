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


class ReferrerRow(ConfiguredBaseModel):
    "One link to a resource, as the store holds it: the referrer, its class, the class of the subject when it is a part, and the predicate, all IRIs; the schema names are the caller\u0027s to find."
    referrer: str = Field(default=..., title="Referrer", description="The IRI of the aggregate root that holds the link.")
    referrer_class: str = Field(default=..., title="Referrer class", description="The IRI of a class of the referrer; a root of several classes gives one row per class.")
    subject_class: Optional[str] = Field(default=None, title="Subject class", description="The IRI of the class of the statement\u0027s subject when that is a part of the referrer; absent when the subject is the referrer itself.")
    predicate: str = Field(default=..., title="Predicate", description="The IRI of the predicate that links to the resource.")


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
ReferrerRow.model_rebuild()
