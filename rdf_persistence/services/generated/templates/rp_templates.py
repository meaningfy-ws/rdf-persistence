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
from rdf_persistence.domain.sparql import SparqlTerm


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


class RegistryTerms(ConfiguredBaseModel):
    "The registry graph and the two predicates of its entries, shared by the templates that read it."
    registry: SparqlTerm = Field(default=..., title="Registry graph", description="The registry graph of the tenant.")
    p_kind: SparqlTerm = Field(default=..., title="Kind predicate", description="The predicate that gives a registry entry its kind.")
    p_owned_by: SparqlTerm = Field(default=..., title="Owned-by predicate", description="The predicate that names the root that owns a registry entry.")


class KeyHeldTerms(RegistryTerms):
    "The terms of the pattern that holds while another aggregate has the claimed values of a key."
    values: SparqlTerm = Field(default=..., title="Key values", description="The patterns that match the values a key claims, over the variable of the root.")
    aggregate: SparqlTerm = Field(default=..., title="Aggregate kind", description="The registry kind of an aggregate graph.")
    excluded: SparqlTerm = Field(default=..., title="Excluded roots", description="The list of roots the key check leaves out.")
    registry: SparqlTerm = Field(default=..., title="Registry graph", description="The registry graph of the tenant.")
    p_kind: SparqlTerm = Field(default=..., title="Kind predicate", description="The predicate that gives a registry entry its kind.")
    p_owned_by: SparqlTerm = Field(default=..., title="Owned-by predicate", description="The predicate that names the root that owns a registry entry.")


class KeyBranchTerms(KeyHeldTerms):
    "The terms of one branch of the diagnosis, which are the key held terms and the claim\u0027s index."
    index: SparqlTerm = Field(default=..., title="Claim index", description="The position of the claim a branch of the diagnosis stands for.")
    values: SparqlTerm = Field(default=..., title="Key values", description="The patterns that match the values a key claims, over the variable of the root.")
    aggregate: SparqlTerm = Field(default=..., title="Aggregate kind", description="The registry kind of an aggregate graph.")
    excluded: SparqlTerm = Field(default=..., title="Excluded roots", description="The list of roots the key check leaves out.")
    registry: SparqlTerm = Field(default=..., title="Registry graph", description="The registry graph of the tenant.")
    p_kind: SparqlTerm = Field(default=..., title="Kind predicate", description="The predicate that gives a registry entry its kind.")
    p_owned_by: SparqlTerm = Field(default=..., title="Owned-by predicate", description="The predicate that names the root that owns a registry entry.")


class OwnerTerms(ConfiguredBaseModel):
    "The terms of the operations that drop what a root owns. It has no registry of its own, so it is not a `RegistryTerms`."
    root: SparqlTerm = Field(default=..., title="Root", description="The aggregate root a write operates on.")
    p_owned_by: SparqlTerm = Field(default=..., title="Owned-by predicate", description="The predicate that names the root that owns a registry entry.")
    p_kind: SparqlTerm = Field(default=..., title="Kind predicate", description="The predicate that gives a registry entry its kind.")
    loaded: SparqlTerm = Field(default=..., title="Loaded-graph kind", description="The registry kind of a loaded graph.")


class ListingTerms(RegistryTerms):
    "The terms of the listing query over a tenant\u0027s registry."
    aggregate: SparqlTerm = Field(default=..., title="Aggregate kind", description="The registry kind of an aggregate graph.")
    target: SparqlTerm = Field(default=..., title="Listed class", description="The class of the aggregates a listing lists.")
    patterns: SparqlTerm = Field(default=..., title="Condition patterns", description="The patterns the conditions of a listing add over the variable of the root.")
    hidden: SparqlTerm = Field(default=..., title="Hidden graphs", description="The list of graphs a listing leaves out.")
    p_listed_in: SparqlTerm = Field(default=..., title="Listed-in predicate", description="The predicate that states the graph a listed subject was found in.")
    p_total: SparqlTerm = Field(default=..., title="Total predicate", description="The predicate that states the size of the whole listing.")
    p_sort: Optional[SparqlTerm] = Field(default=None, title="Sort predicate", description="The predicate a listing is ordered by; absent, the listing is ordered by IRI.")
    order: SparqlTerm = Field(default=..., title="Order", description="The ordering clause of a listing.")
    limit: SparqlTerm = Field(default=..., title="Limit", description="The most aggregates the page can hold.")
    offset: SparqlTerm = Field(default=..., title="Offset", description="The position of the page\u0027s first aggregate in the whole listing.")
    registry: SparqlTerm = Field(default=..., title="Registry graph", description="The registry graph of the tenant.")
    p_kind: SparqlTerm = Field(default=..., title="Kind predicate", description="The predicate that gives a registry entry its kind.")
    p_owned_by: SparqlTerm = Field(default=..., title="Owned-by predicate", description="The predicate that names the root that owns a registry entry.")


class StampGuardTerms(ConfiguredBaseModel):
    "The terms that make a migration operation match only the stamp of the version it starts from."
    stamps: SparqlTerm = Field(default=..., title="Stamps graph", description="The graph that holds the schema stamps.")
    schema_id: SparqlTerm = Field(default=..., title="Schema id", description="The schema whose stamp a migration moves. Not `schema`, which pydantic\u0027s `BaseModel` has as a method.")
    p_stamp: SparqlTerm = Field(default=..., title="Stamp predicate", description="The predicate of a schema\u0027s data version in the stamps graph.")
    from_version: SparqlTerm = Field(default=..., title="From version", description="The version of the schema that the data follows before the migration.")


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
RegistryTerms.model_rebuild()
KeyHeldTerms.model_rebuild()
KeyBranchTerms.model_rebuild()
OwnerTerms.model_rebuild()
ListingTerms.model_rebuild()
StampGuardTerms.model_rebuild()
