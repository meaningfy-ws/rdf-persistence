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

class HardRule(str, Enum):
    """
    The rules of the hard check; a problem line starts with its rule.
    """
    Iri = "iri"
    """
    An element needs an IRI, explicit or from a declared default prefix.
    """
    Title = "title"
    """
    An element needs a title.
    """
    Description = "description"
    """
    An element needs a description.
    """
    Meaning = "meaning"
    """
    A permissible value needs a meaning, an IRI.
    """
    Rp_path = "rp_path"
    """
    An aggregate root needs the rp_path annotation.
    """
    Described = "described"
    """
    A root or an owned class includes Described.
    """
    Annotation = "annotation"
    """
    An annotation value is one of its allowed values.
    """


class BoundaryRule(str, Enum):
    """
    The rules of the boundary check; a problem line starts with its rule.
    """
    Ownership = "ownership"
    """
    A class is an aggregate root or is owned by a root.
    """
    Reference = "reference"
    """
    A slot that is not owned points to a root or to a reference class.
    """
    Module_kind = "module_kind"
    """
    A domain module does not import a technical or an access module.
    """



class GenerationTarget(ConfiguredBaseModel):
    """
    One entry of the `[tool.rp-generate]` table of a `pyproject.toml`: a schema and the folders its generated artefacts are written to. Paths are relative to the folder of the `pyproject.toml`.
    """
    schema_file: str = Field(default=..., title="Schema file", description="""The root LinkML schema file; the TOML key and the flag are `schema`, which the field name avoids because it would shadow a pydantic method.""")
    package: str = Field(default=..., title="Package", description="""The Python import path of the generated package.""")
    python: Optional[str] = Field(default=None, title="Python folder", description="""The folder that receives the classes, shapes, context, frames and the schema copy; the folder of `package` when absent.""")
    typescript: Optional[str] = Field(default=None, title="TypeScript folder", description="""The folder that receives the TypeScript types; none are written when absent.""")
    diagrams: Optional[str] = Field(default=None, title="Diagrams folder", description="""The folder that receives one Mermaid file per module; none are written when absent.""")


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
GenerationTarget.model_rebuild()
