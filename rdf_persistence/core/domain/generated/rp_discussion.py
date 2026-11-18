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

from .rp_annotations import Tracked
from .rp_core import (
    AggregateRoot,
    Principal
)
from .rp_provenance import (
    Activity,
    Generation,
    Invalidation
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

class Motivation(str, Enum):
    "Why a comment was made."
    COMMENTING = "commenting"
    "A remark on the aggregate."
    REPLYING = "replying"
    "An answer to another comment."



class PostComment(Activity):
    "The activity of posting a comment on an aggregate: the aggregate it used, and a generation of the comment. The text, the audience and the references belong to the command only; the comment holds them, and the stored record has none of them."
    used_resource: str = Field(default=..., title="Used resource", description="The IRI of the aggregate the activity used.")
    body_value: Optional[str] = Field(default=None, title="Body value", description="The text of the comment.")
    comment_audience: Optional[list[str]] = Field(default=None, title="Comment audience", description="The names of the roles that may see the comment; none means everyone who may read the aggregate.")
    comment_references: Optional[list[str]] = Field(default=None, title="Comment references", description="The IRIs of other aggregates the comment points to.")
    id: str = Field(default=..., title="Identifier", description="The IRI that identifies the object.")
    was_associated_with: Optional[list[str]] = Field(default=None, title="Was associated with", description="A principal that carried out the activity.")
    started_at_time: Optional[datetime ] = Field(default=None, title="Started at time", description="The time the activity started.")
    ended_at_time: Optional[datetime ] = Field(default=None, title="Ended at time", description="The time the activity ended.")
    generations: Optional[list[Generation]] = Field(default=None, title="Generations", description="The versions of entities the activity generated.")
    invalidations: Optional[list[Invalidation]] = Field(default=None, title="Invalidations", description="The versions of entities the activity invalidated.")


class PostReply(PostComment):
    "The activity of posting a reply to a comment: a post of a comment that also names the comment it answers."
    replies_to: str = Field(default=..., title="Replies to", description="The IRI of the comment this one answers.")
    used_resource: str = Field(default=..., title="Used resource", description="The IRI of the aggregate the activity used.")
    body_value: Optional[str] = Field(default=None, title="Body value", description="The text of the comment.")
    comment_audience: Optional[list[str]] = Field(default=None, title="Comment audience", description="The names of the roles that may see the comment; none means everyone who may read the aggregate.")
    comment_references: Optional[list[str]] = Field(default=None, title="Comment references", description="The IRIs of other aggregates the comment points to.")
    id: str = Field(default=..., title="Identifier", description="The IRI that identifies the object.")
    was_associated_with: Optional[list[str]] = Field(default=None, title="Was associated with", description="A principal that carried out the activity.")
    started_at_time: Optional[datetime ] = Field(default=None, title="Started at time", description="The time the activity started.")
    ended_at_time: Optional[datetime ] = Field(default=None, title="Ended at time", description="The time the activity ended.")
    generations: Optional[list[Generation]] = Field(default=None, title="Generations", description="The versions of entities the activity generated.")
    invalidations: Optional[list[Invalidation]] = Field(default=None, title="Invalidations", description="The versions of entities the activity invalidated.")


class Comment(Tracked, AggregateRoot):
    "A remark on an aggregate, or a reply to another remark. Each comment is an aggregate root of its own, whose target is always the aggregate it is about; a reply also names the comment it answers. The toolkit writes and reads it, since its audience limits who may see it. The session writes its author and time as the tracking of its graph."
    id: str = Field(default=..., title="Identifier", description="The IRI that identifies the object.")
    has_target: str = Field(default=..., title="Has target", description="The IRI of the aggregate the comment is about.")
    body_value: str = Field(default=..., title="Body value", description="The text of the comment.")
    motivated_by: Motivation = Field(default=..., title="Motivated by", description="Why the comment was made, a remark or a reply.")
    comment_audience: Optional[list[str]] = Field(default=None, title="Comment audience", description="The names of the roles that may see the comment; none means everyone who may read the aggregate.")
    comment_references: Optional[list[str]] = Field(default=None, title="Comment references", description="The IRIs of other aggregates the comment points to.")
    replies_to: Optional[str] = Field(default=None, title="Replies to", description="The IRI of the comment this one answers.")
    from_state_iri: Optional[str] = Field(default=None, title="From state IRI", description="The IRI of the state an aggregate left, on the comment a transition posted and on the transition\u0027s record. Defined here, so that the workflow module, which imports this one, uses it too. A state name in a workflow file is another thing: it has no IRI.")
    to_state_iri: Optional[str] = Field(default=None, title="To state IRI", description="The IRI of the state an aggregate entered, on the comment a transition posted and on the transition\u0027s record. Defined here beside from_state_iri.")
    created: Optional[datetime ] = Field(default=None, title="Created", description="The time the graph was first committed.")
    modified: Optional[datetime ] = Field(default=None, title="Modified", description="The time the graph was last committed.")
    creator: Optional[str] = Field(default=None, title="Creator", description="The principal that first committed the graph.")
    contributor: Optional[list[str]] = Field(default=None, title="Contributor", description="A principal that committed a later version of the graph.")


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
PostComment.model_rebuild()
PostReply.model_rebuild()
Comment.model_rebuild()
