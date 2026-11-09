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


class Scan(StoredFile, Tracked, Described, AggregateRoot):
    "A scanned copy of a book; an aggregate root whose current content is a stored file."
    scan_of: Optional[str] = Field(default=None, title="Scan of", description="The book this is a scan of, another aggregate, stored as its IRI.")
    id: str = Field(default=..., title="Identifier", description="The IRI that identifies the object.")
    label: str = Field(default=..., title="Label", description="The preferred label of the object.")
    description: Optional[str] = Field(default=None, title="Description", description="A free-text description of the object.")
    created: Optional[datetime ] = Field(default=None, title="Created", description="The time the graph was first committed.")
    modified: Optional[datetime ] = Field(default=None, title="Modified", description="The time the graph was last committed.")
    creator: Optional[str] = Field(default=None, title="Creator", description="The principal that first committed the graph.")
    contributor: Optional[list[str]] = Field(default=None, title="Contributor", description="A principal that committed a later version of the graph.")
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
Scan.model_rebuild()
