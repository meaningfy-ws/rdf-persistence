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
    Activity,
    AggregateRoot,
    Described,
    Generation,
    Invalidation,
    Principal,
    Tracked,
    Transition
)


metamodel_version = "1.12.0"
version = "None"


from rdf_persistence import RpModel as ConfiguredBaseModel

linkml_meta = None


class ApproveBook(Transition):
    "The command to approve a book, a workflow transition the toolkit\u0027s own handler carries out."
    used_resource: str = _Field(default=..., title="Used resource", description="The IRI of the aggregate the activity used.")
    from_state_iri: _Optional[str] = _Field(default=None, title="From state IRI", description="The IRI of the state an aggregate left, on the comment a transition posted and on the transition\u0027s record. Defined here, so that the workflow module, which imports this one, uses it too. A state name in a workflow file is another thing: it has no IRI.")
    to_state_iri: _Optional[str] = _Field(default=None, title="To state IRI", description="The IRI of the state an aggregate entered, on the comment a transition posted and on the transition\u0027s record. Defined here beside from_state_iri.")
    transition_comment: _Optional[str] = _Field(default=None, title="Transition comment", description="The IRI of the comment the transition posted, when it had one.")
    to_state: _Optional[str] = _Field(default=None, title="To state", description="The name of the state a transition enters. A stored record gives an IRI in to_state_iri.")
    expected_version: _Optional[str] = _Field(default=None, title="Expected version", description="The version of the aggregate the caller read; the move is made only if it still holds.")
    body_value: _Optional[str] = _Field(default=None, title="Body value", description="The text of the comment.")
    id: str = _Field(default=..., title="Identifier", description="The IRI that identifies the object.")
    was_associated_with: _Optional[list[str]] = _Field(default=None, title="Was associated with", description="A principal that carried out the activity.")
    started_at_time: _Optional[datetime ] = _Field(default=None, title="Started at time", description="The time the activity started.")
    ended_at_time: _Optional[datetime ] = _Field(default=None, title="Ended at time", description="The time the activity ended.")
    generations: _Optional[list[Generation]] = _Field(default=None, title="Generations", description="The versions of entities the activity generated.")
    invalidations: _Optional[list[Invalidation]] = _Field(default=None, title="Invalidations", description="The versions of entities the activity invalidated.")


class ShelveBooks(Activity):
    "The command to shelve a book, with a note on the shelf."
    used_resource: _Optional[str] = _Field(default=None, title="Used resource", description="The IRI of the aggregate the activity used.")
    shelf_note: _Optional[str] = _Field(default=None, title="Shelf note", description="A note the librarian leaves with the shelving.")
    id: str = _Field(default=..., title="Identifier", description="The IRI that identifies the object.")
    was_associated_with: _Optional[list[str]] = _Field(default=None, title="Was associated with", description="A principal that carried out the activity.")
    started_at_time: _Optional[datetime ] = _Field(default=None, title="Started at time", description="The time the activity started.")
    ended_at_time: _Optional[datetime ] = _Field(default=None, title="Ended at time", description="The time the activity ended.")
    generations: _Optional[list[Generation]] = _Field(default=None, title="Generations", description="The versions of entities the activity generated.")
    invalidations: _Optional[list[Invalidation]] = _Field(default=None, title="Invalidations", description="The versions of entities the activity invalidated.")


class Review(Activity, Tracked, Described, AggregateRoot):
    "A review of a book, kept as a root that is also an activity (the guard of DEC-4)."
    id: str = _Field(default=..., title="Identifier", description="The IRI that identifies the object.")
    label: str = _Field(default=..., title="Label", description="The preferred label of the object.")
    description: _Optional[str] = _Field(default=None, title="Description", description="A free-text description of the object.")
    created: _Optional[datetime ] = _Field(default=None, title="Created", description="The time the graph was first committed.")
    modified: _Optional[datetime ] = _Field(default=None, title="Modified", description="The time the graph was last committed.")
    creator: _Optional[str] = _Field(default=None, title="Creator", description="The principal that first committed the graph.")
    contributor: _Optional[list[str]] = _Field(default=None, title="Contributor", description="A principal that committed a later version of the graph.")
    was_associated_with: _Optional[list[str]] = _Field(default=None, title="Was associated with", description="A principal that carried out the activity.")
    started_at_time: _Optional[datetime ] = _Field(default=None, title="Started at time", description="The time the activity started.")
    ended_at_time: _Optional[datetime ] = _Field(default=None, title="Ended at time", description="The time the activity ended.")
    generations: _Optional[list[Generation]] = _Field(default=None, title="Generations", description="The versions of entities the activity generated.")
    invalidations: _Optional[list[Invalidation]] = _Field(default=None, title="Invalidations", description="The versions of entities the activity invalidated.")


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
ApproveBook.model_rebuild()
ShelveBooks.model_rebuild()
Review.model_rebuild()
