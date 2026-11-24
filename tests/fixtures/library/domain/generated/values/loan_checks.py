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


from rdf_persistence import RpModel as ConfiguredBaseModel

linkml_meta = None

class LoanStatus(str, _Enum):
    "Whether a loan passed its checks."
    OK = "ok"
    "Every check passed."
    OVERDUE = "overdue"
    "The book is past its due date."



class LoanFinding(ConfiguredBaseModel):
    "One thing a check found about a loan."
    finding_code: str = _Field(default=..., title="Finding code", description="The code of the finding.")
    finding_message: _Optional[str] = _Field(default=None, title="Finding message", description="What the finding says.")


class LoanCheck(ConfiguredBaseModel):
    "The outcome of checking a loan, its status and what was found."
    check_status: LoanStatus = _Field(default=..., title="Check status", description="Whether the loan passed.")
    check_findings: _Optional[list[LoanFinding]] = _Field(default=None, title="Check findings", description="What the check found.")


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
LoanFinding.model_rebuild()
LoanCheck.model_rebuild()
