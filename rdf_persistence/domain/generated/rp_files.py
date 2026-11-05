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

from .rp_core import Principal


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


class StoredFile(ConfiguredBaseModel):
    "A mixin for the current content of a kept file; the bytes live in the tenant\u0027s bucket under the file key."
    file_name: Optional[str] = Field(default=None, title="File name", description="The name of the file as uploaded.")
    media_type: Optional[str] = Field(default=None, title="Media type", description="The media type of the file.")
    byte_size: Optional[int] = Field(default=None, title="Byte size", description="The size of the file in bytes.")
    sha256: Optional[str] = Field(default=None, title="SHA-256", description="The SHA-256 digest of the file, in lowercase hexadecimal.")
    uploaded: Optional[datetime ] = Field(default=None, title="Uploaded", description="The time the file was uploaded.")
    uploaded_by: Optional[str] = Field(default=None, title="Uploaded by", description="The principal that uploaded the file.")
    file_key: Optional[str] = Field(default=None, title="File key", description="The random key of the file in the tenant\u0027s bucket.", json_schema_extra = { "rp_internal": True })

    @field_validator("sha256")
    def pattern_sha256(cls, v):
        pattern=re.compile("^[0-9a-f]{64}$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.fullmatch(element):
                    err_msg = "Invalid sha256 format: " + str(element)
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.fullmatch(v):
            err_msg = "Invalid sha256 format: " + str(v)
            raise ValueError(err_msg)
        return v


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
StoredFile.model_rebuild()
