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
    StoredFile,
    Tracked
)

from .books import Book


metamodel_version = "1.12.0"
version = "None"


from rdf_persistence import RpModel as ConfiguredBaseModel

linkml_meta = None


class Scan(StoredFile, Tracked, Described, AggregateRoot):
    "A scanned copy of a book; an aggregate root whose current content is a stored file."
    scan_of: _Optional[str] = _Field(default=None, title="Scan of", description="The book this is a scan of, another aggregate, stored as its IRI.")
    id: str = _Field(default=..., title="Identifier", description="The IRI that identifies the object.")
    label: str = _Field(default=..., title="Label", description="The preferred label of the object.")
    description: _Optional[str] = _Field(default=None, title="Description", description="A free-text description of the object.")
    created: _Optional[datetime ] = _Field(default=None, title="Created", description="The time the graph was first committed.")
    modified: _Optional[datetime ] = _Field(default=None, title="Modified", description="The time the graph was last committed.")
    creator: _Optional[str] = _Field(default=None, title="Creator", description="The principal that first committed the graph.")
    contributor: _Optional[list[str]] = _Field(default=None, title="Contributor", description="A principal that committed a later version of the graph.")
    file_name: _Optional[str] = _Field(default=None, title="File name", description="The name of the file as uploaded.")
    media_type: _Optional[str] = _Field(default=None, title="Media type", description="The media type of the file.")
    byte_size: _Optional[int] = _Field(default=None, title="Byte size", description="The size of the file in bytes.")
    sha256: _Optional[str] = _Field(default=None, title="SHA-256", description="The SHA-256 digest of the file, in lowercase hexadecimal.")
    uploaded: _Optional[datetime ] = _Field(default=None, title="Uploaded", description="The time the file was uploaded.")
    uploaded_by: _Optional[str] = _Field(default=None, title="Uploaded by", description="The principal that uploaded the file.")
    file_key: _Optional[str] = _Field(default=None, title="File key", description="The random key of the file in the tenant\u0027s bucket.", json_schema_extra = { "rp_internal": True })

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
Scan.model_rebuild()
