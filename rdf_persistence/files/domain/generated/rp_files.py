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
from rdf_persistence.core.domain.generated.rp_core import Principal
from rdf_persistence.provenance.domain.generated.rp_provenance import (
    Generation,
    Invalidation,
    Remove
)


metamodel_version = "1.12.0"
version = "None"


from rdf_persistence.core.domain.base import RpModel as ConfiguredBaseModel

linkml_meta = None

class RdfFormat(str, _Enum):
    "The serialisations a file of RDF can be loaded from."
    TURTLE = "turtle"
    "The Turtle serialisation."
    RDFXML = "rdfxml"
    "The RDF/XML serialisation."
    NTRIPLES = "ntriples"
    "The N-Triples serialisation."
    JSONLD = "jsonld"
    "The JSON-LD serialisation."



class DeleteFile(Remove):
    "The activity of removing a stored file, with the file aggregate it used and an invalidation of it."
    used_resource: _Optional[str] = _Field(default=None, title="Used resource", description="The IRI of the aggregate the activity used.")
    id: str = _Field(default=..., title="Identifier", description="The IRI that identifies the object.")
    was_associated_with: _Optional[list[str]] = _Field(default=None, title="Was associated with", description="A principal that carried out the activity.")
    started_at_time: _Optional[datetime ] = _Field(default=None, title="Started at time", description="The time the activity started.")
    ended_at_time: _Optional[datetime ] = _Field(default=None, title="Ended at time", description="The time the activity ended.")
    generations: _Optional[list[Generation]] = _Field(default=None, title="Generations", description="The versions of entities the activity generated.")
    invalidations: _Optional[list[Invalidation]] = _Field(default=None, title="Invalidations", description="The versions of entities the activity invalidated.")


class StoredFile(ConfiguredBaseModel):
    "A mixin for the current content of a kept file; the bytes live in the tenant\u0027s bucket under the file key."
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


class BlobEntry(ConfiguredBaseModel):
    "One object in a tenant\u0027s bucket, as a listing of the bucket reports it."
    file_key: str = _Field(default=..., title="File key", description="The random key of the file in the tenant\u0027s bucket.", json_schema_extra = { "rp_internal": True })
    modified: datetime  = _Field(default=..., title="Modified", description="The time the object was last written to the bucket.")


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
DeleteFile.model_rebuild()
StoredFile.model_rebuild()
BlobEntry.model_rebuild()
