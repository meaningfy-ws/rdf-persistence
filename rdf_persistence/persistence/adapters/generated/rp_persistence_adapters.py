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


from rdf_persistence.core.domain.base import RpModel as ConfiguredBaseModel

linkml_meta = None


class FusekiDatasetList(ConfiguredBaseModel):
    "The answer of the Fuseki administration endpoint that lists datasets."
    model_config = _ConfigDict(extra="allow")

    datasets: list[FusekiDataset] = _Field(default=..., title="Fuseki datasets", description="The datasets Fuseki serves.")


class FusekiDataset(ConfiguredBaseModel):
    "One dataset of the Fuseki dataset list."
    model_config = _ConfigDict(extra="allow")

    fuseki_dataset_name: str = _Field(default=..., alias="ds.name", title="Fuseki dataset name", description="The name of the dataset, with a leading slash.")


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
FusekiDatasetList.model_rebuild()
FusekiDataset.model_rebuild()
