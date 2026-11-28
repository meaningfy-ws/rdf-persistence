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
    AggregateRoot,
    Described,
    Principal,
    Tracked
)


metamodel_version = "1.12.0"
version = "None"


from rdf_persistence import RpModel as ConfiguredBaseModel

linkml_meta = None


class Audit(Tracked, Described, AggregateRoot):
    "An audit of the library; an aggregate root, the whole that its results depend on."
    cites_finding: _Optional[str] = _Field(default=None, title="Cites finding", description="A finding the audit cites, another aggregate outside its own parts, stored as its IRI.")
    id: str = _Field(default=..., title="Identifier", description="The IRI that identifies the object.")
    label: str = _Field(default=..., title="Label", description="The preferred label of the object.")
    description: _Optional[str] = _Field(default=None, title="Description", description="A free-text description of the object.")
    created: _Optional[datetime ] = _Field(default=None, title="Created", description="The time the graph was first committed.")
    modified: _Optional[datetime ] = _Field(default=None, title="Modified", description="The time the graph was last committed.")
    creator: _Optional[str] = _Field(default=None, title="Creator", description="The principal that first committed the graph.")
    contributor: _Optional[list[str]] = _Field(default=None, title="Contributor", description="A principal that committed a later version of the graph.")


class AuditResult(Tracked, Described, AggregateRoot):
    "The result of an audit; an aggregate root stored apart from its audit, which cannot exist without it."
    of_audit: str = _Field(default=..., title="Of audit", description="The audit a result belongs to, another aggregate, stored as its IRI.")
    id: str = _Field(default=..., title="Identifier", description="The IRI that identifies the object.")
    label: str = _Field(default=..., title="Label", description="The preferred label of the object.")
    description: _Optional[str] = _Field(default=None, title="Description", description="A free-text description of the object.")
    created: _Optional[datetime ] = _Field(default=None, title="Created", description="The time the graph was first committed.")
    modified: _Optional[datetime ] = _Field(default=None, title="Modified", description="The time the graph was last committed.")
    creator: _Optional[str] = _Field(default=None, title="Creator", description="The principal that first committed the graph.")
    contributor: _Optional[list[str]] = _Field(default=None, title="Contributor", description="A principal that committed a later version of the graph.")


class AuditFinding(Tracked, Described, AggregateRoot):
    "A finding of an audit result; an aggregate root that depends on its result, and that cannot be deleted while another aggregate still cites it."
    of_result: str = _Field(default=..., title="Of result", description="The audit result a finding belongs to, another aggregate, stored as its IRI.")
    id: str = _Field(default=..., title="Identifier", description="The IRI that identifies the object.")
    label: str = _Field(default=..., title="Label", description="The preferred label of the object.")
    description: _Optional[str] = _Field(default=None, title="Description", description="A free-text description of the object.")
    created: _Optional[datetime ] = _Field(default=None, title="Created", description="The time the graph was first committed.")
    modified: _Optional[datetime ] = _Field(default=None, title="Modified", description="The time the graph was last committed.")
    creator: _Optional[str] = _Field(default=None, title="Creator", description="The principal that first committed the graph.")
    contributor: _Optional[list[str]] = _Field(default=None, title="Contributor", description="A principal that committed a later version of the graph.")


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
Audit.model_rebuild()
AuditResult.model_rebuild()
AuditFinding.model_rebuild()
