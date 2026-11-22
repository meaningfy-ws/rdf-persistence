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
    Action,
    Activity,
    Add,
    AggregateKey,
    AggregateRoot,
    BlobEntry,
    Comment,
    CommitMarker,
    DatabaseKind,
    DeleteFile,
    Described,
    Generation,
    Grant,
    GraphKind,
    Invalidation,
    KeyDuplicate,
    MembershipRule,
    ModuleKind,
    Motivation,
    OnReferencedDelete,
    PendingLoad,
    Policy,
    PostComment,
    PostReply,
    Principal,
    Prohibition,
    Provenanced,
    RdfFormat,
    ReferenceCollection,
    RegistryEntry,
    RegistryKind,
    Remove,
    Replace,
    RoleDefinition,
    RoleLevel,
    RpAnnotation,
    Rule,
    SlotEquality,
    StoredFile,
    TenantAccess,
    TenantLabelled,
    TenantState,
    TenantSweepReport,
    Tracked,
    Transition,
    UnderWorkflow,
    UniqueScope,
    Workflow,
    WorkflowTransition,
    WritesKind
)

from .books import (
    Author,
    Book,
    Chapter,
    Genre,
    Note,
    Shelf
)
from .books_activities import (
    ApproveBook,
    Review,
    ShelveBooks
)
from .library_access import LibraryAccess
from .library_tenant import (
    Charter,
    Library
)
from .scans import Scan
from .templates import Template


metamodel_version = "1.12.0"
version = "1"


from rdf_persistence import RpModel as ConfiguredBaseModel

linkml_meta = None


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
