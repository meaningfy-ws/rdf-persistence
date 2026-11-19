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
from rdf_persistence import (
    Activity,
    Generation,
    Invalidation,
    Principal,
    Transition
)


metamodel_version = "1.12.0"
version = "None"


from rdf_persistence import RpModel as ConfiguredBaseModel



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


class ApproveBook(Transition):
    "The command to approve a book, a workflow transition the toolkit\u0027s own handler carries out."
    used_resource: str = Field(default=..., title="Used resource", description="The IRI of the aggregate the activity used.")
    from_state_iri: Optional[str] = Field(default=None, title="From state IRI", description="The IRI of the state an aggregate left, on the comment a transition posted and on the transition\u0027s record. Defined here, so that the workflow module, which imports this one, uses it too. A state name in a workflow file is another thing: it has no IRI.")
    to_state_iri: Optional[str] = Field(default=None, title="To state IRI", description="The IRI of the state an aggregate entered, on the comment a transition posted and on the transition\u0027s record. Defined here beside from_state_iri.")
    transition_comment: Optional[str] = Field(default=None, title="Transition comment", description="The IRI of the comment the transition posted, when it had one.")
    to_state: Optional[str] = Field(default=None, title="To state", description="The name of the state a transition enters. A stored record gives an IRI in to_state_iri.")
    expected_version: Optional[str] = Field(default=None, title="Expected version", description="The version of the aggregate the caller read; the move is made only if it still holds.")
    body_value: Optional[str] = Field(default=None, title="Body value", description="The text of the comment.")
    id: str = Field(default=..., title="Identifier", description="The IRI that identifies the object.")
    was_associated_with: Optional[list[str]] = Field(default=None, title="Was associated with", description="A principal that carried out the activity.")
    started_at_time: Optional[datetime ] = Field(default=None, title="Started at time", description="The time the activity started.")
    ended_at_time: Optional[datetime ] = Field(default=None, title="Ended at time", description="The time the activity ended.")
    generations: Optional[list[Generation]] = Field(default=None, title="Generations", description="The versions of entities the activity generated.")
    invalidations: Optional[list[Invalidation]] = Field(default=None, title="Invalidations", description="The versions of entities the activity invalidated.")


class ShelveBooks(Activity):
    "The command to shelve a book, with a note on the shelf."
    used_resource: Optional[str] = Field(default=None, title="Used resource", description="The IRI of the aggregate the activity used.")
    shelf_note: Optional[str] = Field(default=None, title="Shelf note", description="A note the librarian leaves with the shelving.")
    id: str = Field(default=..., title="Identifier", description="The IRI that identifies the object.")
    was_associated_with: Optional[list[str]] = Field(default=None, title="Was associated with", description="A principal that carried out the activity.")
    started_at_time: Optional[datetime ] = Field(default=None, title="Started at time", description="The time the activity started.")
    ended_at_time: Optional[datetime ] = Field(default=None, title="Ended at time", description="The time the activity ended.")
    generations: Optional[list[Generation]] = Field(default=None, title="Generations", description="The versions of entities the activity generated.")
    invalidations: Optional[list[Invalidation]] = Field(default=None, title="Invalidations", description="The versions of entities the activity invalidated.")


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
ApproveBook.model_rebuild()
ShelveBooks.model_rebuild()
