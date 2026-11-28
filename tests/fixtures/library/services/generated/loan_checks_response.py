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
    AccountSummary,
    Action,
    AggregateKey,
    AggregateRoot,
    Authorised,
    CallerAccess,
    CommitMarker,
    Contains,
    DatabaseKind,
    DependenceLink,
    Described,
    Grant,
    GrantSet,
    GraphKind,
    KeyDuplicate,
    LabelUpdate,
    MemberList,
    ModuleKind,
    OnReferencedDelete,
    Page,
    PendingLoad,
    Policy,
    Principal,
    Problem,
    ProblemKind,
    Prohibition,
    Referrer,
    ReferrerList,
    RegistryEntry,
    RegistryKind,
    RoleDefinition,
    RoleLevel,
    RpAnnotation,
    Rule,
    TenantAccess,
    TenantCreate,
    TenantLabelled,
    TenantState,
    TenantSweepReport,
    Tracked,
    UniqueScope,
    VerifiedCaller,
    WritesKind
)
from tests.fixtures.library.domain.generated.values.loan_checks import (
    LoanCheck,
    LoanFinding,
    LoanStatus
)

from .library_problems import HeldKeyProblem


metamodel_version = "1.12.0"
version = "None"


from rdf_persistence import RpModel as ConfiguredBaseModel

linkml_meta = None


class LoanChecksResponse(ConfiguredBaseModel):
    "The answer of a loan check, the outcomes of every check run."
    checks: _Optional[list[LoanCheck]] = _Field(default=None, title="Checks", description="The outcomes of the checks.")
    registry_kind: _Optional[RegistryKind] = _Field(default=None, title="Registry kind", description="The kind of graph the answer was read from, when it names one.")


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
LoanChecksResponse.model_rebuild()
