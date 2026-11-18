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


class Page(ConfiguredBaseModel):
    "One page of a listing, with the position of the page in the whole listing."
    items: list[Any] = Field(default=..., title="Items", description="The objects of the page; framed aggregates, or tenant summaries.")
    total: int = Field(default=..., title="Total", description="The number of objects in the whole listing.", ge=0)
    limit: int = Field(default=..., title="Limit", description="The most objects the page can hold.", ge=1, le=200)
    offset: int = Field(default=..., title="Offset", description="The position of the page\u0027s first object in the whole listing.", ge=0)


class Filter(ConfiguredBaseModel):
    "One equality filter of a listing, the name of a slot of the listed type and the value it must have, as the text the caller sent."
    slot: str = Field(default=..., title="Filter slot", description="The name of the slot the filter is on.")
    value: str = Field(default=..., title="Filter value", description="The value the slot must have, as text.")


class ListRequest(ConfiguredBaseModel):
    "The query of a listing, as the caller sent it: the equality filters, the position and size of the page and the key to sort by."
    limit: Optional[int] = Field(default=50, title="Limit", description="The most objects the page can hold.", ge=1, le=200)
    offset: Optional[int] = Field(default=0, title="Offset", description="The position of the page\u0027s first object in the whole listing.", ge=0)
    sort: Optional[str] = Field(default=None, title="Sort", description="The slot a listing is ordered by, ascending, or descending when its name starts with a minus sign; absent, the listing is ordered by IRI.")
    filters: Optional[list[Filter]] = Field(default=None, title="Filters", description="The equality filters of a listing; all of them must hold.")


class Condition(ConfiguredBaseModel):
    "An equality filter of a listing resolved against the slots of the listed type: the aggregate has this statement. The value is an IRI when it is a reference, else a literal of the datatype."
    predicate: str = Field(default=..., title="Condition predicate", description="The IRI of the predicate the aggregate must have a statement with.")
    value: str = Field(default=..., title="Condition value", description="The value of the statement, an IRI or the lexical form of a literal.")
    datatype: Optional[str] = Field(default=None, title="Condition datatype", description="The IRI of the datatype of a literal value; absent for a plain string.")
    reference: Optional[bool] = Field(default=False, title="Condition reference", description="Whether the value is an IRI rather than a literal.")


class ListPlan(ConfiguredBaseModel):
    "A listing resolved against the slots of the listed type: the class, the typed conditions, the predicate to order by (none orders by IRI), the page, and the graphs of the aggregates the caller may not read."
    target: str = Field(default=..., title="Plan class", description="The IRI of the class of the aggregates listed.")
    conditions: Optional[list[Condition]] = Field(default=None, title="Conditions", description="The equality conditions of a listing; all of them must hold.")
    sort_by: Optional[str] = Field(default=None, title="Plan sort", description="The IRI of the predicate a listing is ordered by; absent, it is ordered by IRI.")
    descending: Optional[bool] = Field(default=False, title="Descending", description="Whether the order is reversed.")
    limit: int = Field(default=..., title="Limit", description="The most objects the page can hold.", ge=1, le=200)
    offset: int = Field(default=..., title="Offset", description="The position of the page\u0027s first object in the whole listing.", ge=0)
    hidden_graphs: Optional[list[str]] = Field(default=None, title="Hidden graphs", description="The IRIs of the graphs of the aggregates a listing leaves out.")


class AggregateHead(ConfiguredBaseModel):
    "The IRI, the types and the version token of one stored aggregate, without its content."
    head_iri: Optional[str] = Field(default=None, title="Head IRI", description="The IRI of the stored aggregate.")
    head_types: Optional[list[str]] = Field(default=None, title="Head types", description="The class IRIs the stored aggregate is typed with.")
    head_version: Optional[str] = Field(default=None, title="Head version", description="The version token of the stored aggregate\u0027s graph.")


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
Page.model_rebuild()
Filter.model_rebuild()
ListRequest.model_rebuild()
Condition.model_rebuild()
ListPlan.model_rebuild()
AggregateHead.model_rebuild()
