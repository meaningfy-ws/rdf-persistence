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


class Page(ConfiguredBaseModel):
    "One page of a listing, with the position of the page in the whole listing."
    items: list[_Any] = _Field(default=..., title="Items", description="The objects of the page; framed aggregates, or tenant summaries.")
    total: int = _Field(default=..., title="Total", description="The number of objects in the whole listing.", ge=0)
    limit: int = _Field(default=..., title="Limit", description="The most objects the page can hold.", ge=1, le=200)
    offset: int = _Field(default=..., title="Offset", description="The position of the page\u0027s first object in the whole listing.", ge=0, le=9007199254740991)


class Filter(ConfiguredBaseModel):
    "One filter of a listing, the name of a slot of the listed type and the value it must have, or whose text it must contain, as the text the caller sent."
    slot: str = _Field(default=..., title="Filter slot", description="The name of the slot the filter is on.")
    value: str = _Field(default=..., title="Filter value", description="The value the slot must have, as text.")
    contains: _Optional[bool] = _Field(default=False, title="Filter contains", description="Whether the filter matches a substring of the slot\u0027s text, ignoring case, rather than the value.")
    absent: _Optional[bool] = _Field(default=False, title="Filter absent", description="Whether the filter matches the aggregates that hold no value for the slot, rather than a value; the filter\u0027s value is then empty and unread.")


class Contains(ConfiguredBaseModel):
    "A value of `Session.find` that asks for a case-insensitive substring of a string slot rather than its value."
    text: str = _Field(default=..., title="Contains text", description="The text a string slot must hold, in any case.")


class ListRequest(ConfiguredBaseModel):
    "The query of a listing, as the caller sent it: the filters, the position and size of the page and the key to sort by."
    limit: _Optional[int] = _Field(default=50, title="Limit", description="The most objects the page can hold.", ge=1, le=200)
    offset: _Optional[int] = _Field(default=0, title="Offset", description="The position of the page\u0027s first object in the whole listing.", ge=0, le=9007199254740991)
    sort: _Optional[str] = _Field(default=None, title="Sort", description="The slot a listing is ordered by, ascending, or descending when its name starts with a minus sign; absent, the listing is ordered by IRI.")
    filters: _Optional[list[Filter]] = _Field(default=None, title="Filters", description="The filters of a listing; all of them must hold.")


class Condition(ConfiguredBaseModel):
    "A filter of a listing resolved against the slots of the listed type: the aggregate has this statement, or a statement whose text contains the value. The value is an IRI when it is a reference, else a literal of the datatype."
    predicate: str = _Field(default=..., title="Condition predicate", description="The IRI of the predicate the aggregate must have a statement with.")
    value: str = _Field(default=..., title="Condition value", description="The value of the statement, an IRI or the lexical form of a literal.")
    datatype: _Optional[str] = _Field(default=None, title="Condition datatype", description="The IRI of the datatype of a literal value; absent for a plain string.")
    reference: _Optional[bool] = _Field(default=False, title="Condition reference", description="Whether the value is an IRI rather than a literal.")
    via: _Optional[list[str]] = _Field(default=None, title="Condition via", description="The IRIs of the predicates of the references the condition crosses, in order, from the listed aggregate to the one whose statement is tested; empty when the condition is on the listed aggregate itself. The predicate and value are those of the last aggregate.")
    contains: _Optional[bool] = _Field(default=False, title="Filter contains", description="Whether the filter matches a substring of the slot\u0027s text, ignoring case, rather than the value.")
    absent: _Optional[bool] = _Field(default=False, title="Filter absent", description="Whether the filter matches the aggregates that hold no value for the slot, rather than a value; the filter\u0027s value is then empty and unread.")


class ListPlan(ConfiguredBaseModel):
    "A listing resolved against the slots of the listed type: the class, the typed conditions, the predicate to order by (none orders by IRI), the page, and the graphs of the aggregates the caller may not read."
    target: str = _Field(default=..., title="Plan class", description="The IRI of the class of the aggregates listed.")
    conditions: _Optional[list[Condition]] = _Field(default=None, title="Conditions", description="The conditions of a listing; all of them must hold.")
    sort_by: _Optional[str] = _Field(default=None, title="Plan sort", description="The IRI of the predicate a listing is ordered by; absent, it is ordered by IRI.")
    descending: _Optional[bool] = _Field(default=False, title="Descending", description="Whether the order is reversed.")
    limit: int = _Field(default=..., title="Limit", description="The most objects the page can hold.", ge=1, le=200)
    offset: int = _Field(default=..., title="Offset", description="The position of the page\u0027s first object in the whole listing.", ge=0, le=9007199254740991)
    hidden_graphs: _Optional[list[str]] = _Field(default=None, title="Hidden graphs", description="The IRIs of the graphs of the aggregates a listing leaves out.")


class AggregateHead(ConfiguredBaseModel):
    "The IRI, the types and the version token of one stored aggregate, without its content."
    head_iri: _Optional[str] = _Field(default=None, title="Head IRI", description="The IRI of the stored aggregate.")
    head_types: _Optional[list[str]] = _Field(default=None, title="Head types", description="The class IRIs the stored aggregate is typed with.")
    head_version: _Optional[str] = _Field(default=None, title="Head version", description="The version token of the stored aggregate\u0027s graph.")


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
Page.model_rebuild()
Filter.model_rebuild()
Contains.model_rebuild()
ListRequest.model_rebuild()
Condition.model_rebuild()
ListPlan.model_rebuild()
AggregateHead.model_rebuild()
