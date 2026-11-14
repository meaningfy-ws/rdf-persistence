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

from .rp_core import (
    AggregateRoot,
    Principal
)
from .rp_provenance import Activity


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


class Workflow(ConfiguredBaseModel):
    "The definition of a workflow, read from a file when the service starts and never stored: its name, its states, the state an aggregate starts in and the transitions between states. Its identifier is the IRI of the scheme whose concepts are the states, and it must stay stable once aggregates have states."
    id: str = Field(default=..., title="Identifier", description="The IRI that identifies the object.")
    workflow_name: str = Field(default=..., title="Workflow name", description="The name the workflow goes by, which the workflow annotation of a class refers to.")
    workflow_states: list[str] = Field(default=..., title="Workflow states", description="The names of the states, lower case, starting with a letter, with digits, hyphens and underscores. The IRI of a state is the workflow\u0027s identifier, a slash and its name.")
    initial_state: str = Field(default=..., title="Initial state", description="The name of the state a new aggregate starts in, one of the states.")
    workflow_transitions: Optional[list[WorkflowTransition]] = Field(default=None, title="Workflow transitions", description="The transitions of the workflow; they are part of its definition.")

    @field_validator("workflow_name")
    def pattern_workflow_name(cls, v):
        pattern=re.compile("^[a-z][a-z0-9-]*$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.fullmatch(element):
                    err_msg = "Invalid workflow_name format: " + str(element)
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.fullmatch(v):
            err_msg = "Invalid workflow_name format: " + str(v)
            raise ValueError(err_msg)
        return v

    @field_validator("workflow_states")
    def pattern_workflow_states(cls, v):
        pattern=re.compile("^[a-z][a-z0-9_-]*$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.fullmatch(element):
                    err_msg = "Invalid workflow_states format: " + str(element)
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.fullmatch(v):
            err_msg = "Invalid workflow_states format: " + str(v)
            raise ValueError(err_msg)
        return v


class WorkflowTransition(ConfiguredBaseModel):
    "One transition of a workflow, from one state to another, with the roles that may make it. The states are named, not given as IRIs."
    from_state: str = Field(default=..., title="From state", description="The name of the state a transition leaves. A stored record gives an IRI in from_state_iri.")
    to_state: str = Field(default=..., title="To state", description="The name of the state a transition enters. A stored record gives an IRI in to_state_iri.")
    transition_roles: list[str] = Field(default=..., title="Transition roles", description="The names of the roles of which one is needed to make the transition.")
    comment_required: Optional[bool] = Field(default=False, title="Comment required", description="Whether the transition needs a comment; no by default.")


class UnderWorkflow(ConfiguredBaseModel):
    "A mixin for an aggregate root that follows a workflow, which its class names with the workflow annotation. It gives the root its current state; only a transition changes it."
    workflow_status: Optional[str] = Field(default=None, title="Workflow status", description="The current state of the aggregate, the IRI of a state of its workflow.")


class TransitionRecord(AggregateRoot, Activity):
    "The record of one transition of an aggregate: which aggregate, from which state to which, when, by whom and with which comment. The toolkit writes it in the update that changes the state and deletes it with the aggregate. It is a prov:Activity in the generated vocabulary, and typed with its own class when stored."
    used_resource: str = Field(default=..., title="Used resource", description="The IRI of the aggregate the transition moved.")
    from_state_iri: str = Field(default=..., title="From state IRI", description="The IRI of the state an aggregate left, on the comment a transition posted and on the transition\u0027s record. Defined here, so that the workflow module, which imports this one, uses it too. A state name in a workflow file is another thing: it has no IRI.")
    to_state_iri: str = Field(default=..., title="To state IRI", description="The IRI of the state an aggregate entered, on the comment a transition posted and on the transition\u0027s record. Defined here beside from_state_iri.")
    started_at_time: datetime  = Field(default=..., title="Started at time", description="The time the transition was made.")
    transition_comment: Optional[str] = Field(default=None, title="Transition comment", description="The IRI of the comment the transition posted, when it had one.")
    id: str = Field(default=..., title="Identifier", description="The IRI that identifies the object.")
    was_associated_with: Optional[list[str]] = Field(default=None, title="Was associated with", description="A principal that carried out the activity.")


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
Workflow.model_rebuild()
WorkflowTransition.model_rebuild()
UnderWorkflow.model_rebuild()
TransitionRecord.model_rebuild()
