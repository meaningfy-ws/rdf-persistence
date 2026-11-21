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
from rdf_persistence.core.domain.generated.rp_annotations import Tracked
from rdf_persistence.core.domain.generated.rp_core import (
    AggregateRoot,
    Principal
)
from rdf_persistence.provenance.domain.generated.rp_provenance import (
    Activity,
    Generation,
    Invalidation
)


metamodel_version = "1.12.0"
version = "None"


from rdf_persistence.core.domain.base import RpModel as ConfiguredBaseModel

linkml_meta = None

class Motivation(str, _Enum):
    "Why a comment was made."
    COMMENTING = "commenting"
    "A remark on the aggregate."
    REPLYING = "replying"
    "An answer to another comment."



class PostComment(Activity):
    "The activity of posting a comment on an aggregate: the aggregate it used, and a generation of the comment. The text, the audience and the references belong to the command only; the comment holds them, and the stored record has none of them."
    used_resource: str = _Field(default=..., title="Used resource", description="The IRI of the aggregate the activity used.")
    body_value: _Optional[str] = _Field(default=None, title="Body value", description="The text of the comment.")
    comment_audience: _Optional[list[str]] = _Field(default=None, title="Comment audience", description="The names of the roles that may see the comment; none means everyone who may read the aggregate.")
    comment_references: _Optional[list[str]] = _Field(default=None, title="Comment references", description="The IRIs of other aggregates the comment points to.")
    id: str = _Field(default=..., title="Identifier", description="The IRI that identifies the object.")
    was_associated_with: _Optional[list[str]] = _Field(default=None, title="Was associated with", description="A principal that carried out the activity.")
    started_at_time: _Optional[datetime ] = _Field(default=None, title="Started at time", description="The time the activity started.")
    ended_at_time: _Optional[datetime ] = _Field(default=None, title="Ended at time", description="The time the activity ended.")
    generations: _Optional[list[Generation]] = _Field(default=None, title="Generations", description="The versions of entities the activity generated.")
    invalidations: _Optional[list[Invalidation]] = _Field(default=None, title="Invalidations", description="The versions of entities the activity invalidated.")


class PostReply(PostComment):
    "The activity of posting a reply to a comment: a post of a comment that also names the comment it answers."
    replies_to: str = _Field(default=..., title="Replies to", description="The IRI of the comment this one answers.")
    used_resource: str = _Field(default=..., title="Used resource", description="The IRI of the aggregate the activity used.")
    body_value: _Optional[str] = _Field(default=None, title="Body value", description="The text of the comment.")
    comment_audience: _Optional[list[str]] = _Field(default=None, title="Comment audience", description="The names of the roles that may see the comment; none means everyone who may read the aggregate.")
    comment_references: _Optional[list[str]] = _Field(default=None, title="Comment references", description="The IRIs of other aggregates the comment points to.")
    id: str = _Field(default=..., title="Identifier", description="The IRI that identifies the object.")
    was_associated_with: _Optional[list[str]] = _Field(default=None, title="Was associated with", description="A principal that carried out the activity.")
    started_at_time: _Optional[datetime ] = _Field(default=None, title="Started at time", description="The time the activity started.")
    ended_at_time: _Optional[datetime ] = _Field(default=None, title="Ended at time", description="The time the activity ended.")
    generations: _Optional[list[Generation]] = _Field(default=None, title="Generations", description="The versions of entities the activity generated.")
    invalidations: _Optional[list[Invalidation]] = _Field(default=None, title="Invalidations", description="The versions of entities the activity invalidated.")


class Comment(Tracked, AggregateRoot):
    "A remark on an aggregate, or a reply to another remark. Each comment is an aggregate root of its own, whose target is always the aggregate it is about; a reply also names the comment it answers. The toolkit writes and reads it, since its audience limits who may see it. The session writes its author and time as the tracking of its graph."
    id: str = _Field(default=..., title="Identifier", description="The IRI that identifies the object.")
    has_target: str = _Field(default=..., title="Has target", description="The IRI of the aggregate the comment is about.")
    body_value: str = _Field(default=..., title="Body value", description="The text of the comment.")
    motivated_by: Motivation = _Field(default=..., title="Motivated by", description="Why the comment was made, a remark or a reply.")
    comment_audience: _Optional[list[str]] = _Field(default=None, title="Comment audience", description="The names of the roles that may see the comment; none means everyone who may read the aggregate.")
    comment_references: _Optional[list[str]] = _Field(default=None, title="Comment references", description="The IRIs of other aggregates the comment points to.")
    replies_to: _Optional[str] = _Field(default=None, title="Replies to", description="The IRI of the comment this one answers.")
    from_state_iri: _Optional[str] = _Field(default=None, title="From state IRI", description="The IRI of the state an aggregate left, on the comment a transition posted and on the transition\u0027s record. Defined here, so that the workflow module, which imports this one, uses it too. A state name in a workflow file is another thing: it has no IRI.")
    to_state_iri: _Optional[str] = _Field(default=None, title="To state IRI", description="The IRI of the state an aggregate entered, on the comment a transition posted and on the transition\u0027s record. Defined here beside from_state_iri.")
    created: _Optional[datetime ] = _Field(default=None, title="Created", description="The time the graph was first committed.")
    modified: _Optional[datetime ] = _Field(default=None, title="Modified", description="The time the graph was last committed.")
    creator: _Optional[str] = _Field(default=None, title="Creator", description="The principal that first committed the graph.")
    contributor: _Optional[list[str]] = _Field(default=None, title="Contributor", description="A principal that committed a later version of the graph.")


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
PostComment.model_rebuild()
PostReply.model_rebuild()
Comment.model_rebuild()
