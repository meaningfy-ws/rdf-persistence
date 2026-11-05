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
    "The rules of the hard check; a problem line starts with its rule."
    IRI = "iri"
    "An element needs an IRI, explicit or from a declared default prefix."
    TITLE = "title"
    "An element needs a title."
    DESCRIPTION = "description"
    "An element needs a description."
    MEANING = "meaning"
    "A permissible value needs a meaning, an IRI."
    RP_PATH = "rp_path"
    "An aggregate root needs the rp_path annotation."
    DESCRIBED = "described"
    "A root or an owned class includes Described."
    ANNOTATION = "annotation"
    "An annotation value is one of its allowed values; the `rp_path` value is a URL segment."
    UNIQUE_KEY = "unique_key"
    "A unique key is named by an identifier, since generated code carries the name."


class BoundaryRule(str, Enum):
    "The rules of the boundary check; a problem line starts with its rule."
    OWNERSHIP = "ownership"
    "A class is an aggregate root or is owned by a root."
    REFERENCE = "reference"
    "A slot that is not owned points to a root or to a reference class."
    MODULE_KIND = "module_kind"
    "A domain module does not import a technical or an access module."


class ConstraintKind(str, Enum):
    "The constraint kinds of v1 that the generated classes and shapes must agree on."
    REQUIRED = "required"
    "A required slot refuses a missing value."
    CARDINALITY = "cardinality"
    "A slot\u0027s minimum and maximum cardinality bound the number of values."
    RANGE_TYPE = "range_type"
    "A slot\u0027s range type refuses a value of another type."
    RANGE_ENUM = "range_enum"
    "An enum range refuses a value outside its permissible values."
    PATTERN = "pattern"
    "A pattern refuses a value that does not match."
    VALUE_BOUNDS = "value_bounds"
    "A minimum or maximum value refuses a value outside the bounds."
    IDENTIFIER = "identifier"
    "An identifier slot takes one IRI that names the instance."
    CLOSED = "closed"
    "A class refuses an unknown field or predicate."
    EXACTLY_ONE_OF = "exactly_one_of"
    "Exactly one of several alternatives is present."
    ANY_OF = "any_of"
    "At least one of several alternatives is present."
    UNIQUE_KEYS = "unique_keys"
    "No two items of a multivalued slot have equal key values."



class GenerationTarget(ConfiguredBaseModel):
    "One entry of the `[tool.rp-generate]` table of a `pyproject.toml`: a schema and the folders its generated artefacts are written to. Paths are relative to the folder of the `pyproject.toml`."
    schema_file: str = Field(default=..., title="Schema file", description="The root LinkML schema file; the TOML key and the flag are `schema`, which the field name avoids because it would shadow a pydantic method.")
    package: str = Field(default=..., title="Package", description="The Python import path of the generated package, a dotted identifier.")
    python: Optional[str] = Field(default=None, title="Python folder", description="The folder that receives the classes, shapes, context, frames and the schema copy; the folder of `package` when absent.")
    typescript: Optional[str] = Field(default=None, title="TypeScript folder", description="The folder that receives the TypeScript types; none are written when absent.")
    diagrams: Optional[str] = Field(default=None, title="Diagrams folder", description="The folder that receives one Mermaid file per module; none are written when absent.")

    @field_validator("schema_file")
    def pattern_schema_file(cls, v):
        pattern=re.compile("^(?:[^/:\\\\.][^/:\\\\]*|\\.[^/:\\\\.][^/:\\\\]*|\\.\\.[^/:\\\\]+)(?:/(?:[^/:\\\\.][^/:\\\\]*|\\.[^/:\\\\.][^/:\\\\]*|\\.\\.[^/:\\\\]+))*$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.fullmatch(element):
                    err_msg = "Invalid schema_file format: " + str(element)
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.fullmatch(v):
            err_msg = "Invalid schema_file format: " + str(v)
            raise ValueError(err_msg)
        return v

    @field_validator("package")
    def pattern_package(cls, v):
        pattern=re.compile("^[A-Za-z_][A-Za-z0-9_]*(?:\\.[A-Za-z_][A-Za-z0-9_]*)*$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.fullmatch(element):
                    err_msg = "Invalid package format: " + str(element)
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.fullmatch(v):
            err_msg = "Invalid package format: " + str(v)
            raise ValueError(err_msg)
        return v

    @field_validator("python")
    def pattern_python(cls, v):
        pattern=re.compile("^(?:[^/:\\\\.][^/:\\\\]*|\\.[^/:\\\\.][^/:\\\\]*|\\.\\.[^/:\\\\]+)(?:/(?:[^/:\\\\.][^/:\\\\]*|\\.[^/:\\\\.][^/:\\\\]*|\\.\\.[^/:\\\\]+))*$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.fullmatch(element):
                    err_msg = "Invalid python format: " + str(element)
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.fullmatch(v):
            err_msg = "Invalid python format: " + str(v)
            raise ValueError(err_msg)
        return v

    @field_validator("typescript")
    def pattern_typescript(cls, v):
        pattern=re.compile("^(?:[^/:\\\\.][^/:\\\\]*|\\.[^/:\\\\.][^/:\\\\]*|\\.\\.[^/:\\\\]+)(?:/(?:[^/:\\\\.][^/:\\\\]*|\\.[^/:\\\\.][^/:\\\\]*|\\.\\.[^/:\\\\]+))*$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.fullmatch(element):
                    err_msg = "Invalid typescript format: " + str(element)
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.fullmatch(v):
            err_msg = "Invalid typescript format: " + str(v)
            raise ValueError(err_msg)
        return v

    @field_validator("diagrams")
    def pattern_diagrams(cls, v):
        pattern=re.compile("^(?:[^/:\\\\.][^/:\\\\]*|\\.[^/:\\\\.][^/:\\\\]*|\\.\\.[^/:\\\\]+)(?:/(?:[^/:\\\\.][^/:\\\\]*|\\.[^/:\\\\.][^/:\\\\]*|\\.\\.[^/:\\\\]+))*$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.fullmatch(element):
                    err_msg = "Invalid diagrams format: " + str(element)
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.fullmatch(v):
            err_msg = "Invalid diagrams format: " + str(v)
            raise ValueError(err_msg)
        return v


class ManifestEntry(ConfiguredBaseModel):
    "A file and the SHA-256 of its bytes, as recorded by a generation run."
    path: str = Field(default=..., title="Path", description="A file path, POSIX, relative to the folder of the `pyproject.toml`.")
    sha256: str = Field(default=..., title="SHA-256", description="The SHA-256 of a file\u0027s bytes, in lowercase hexadecimal.")

    @field_validator("path")
    def pattern_path(cls, v):
        pattern=re.compile("^(?:[^/:\\\\.][^/:\\\\]*|\\.[^/:\\\\.][^/:\\\\]*|\\.\\.[^/:\\\\]+)(?:/(?:[^/:\\\\.][^/:\\\\]*|\\.[^/:\\\\.][^/:\\\\]*|\\.\\.[^/:\\\\]+))*$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.fullmatch(element):
                    err_msg = "Invalid path format: " + str(element)
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.fullmatch(v):
            err_msg = "Invalid path format: " + str(v)
            raise ValueError(err_msg)
        return v

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


class GenerationManifest(ConfiguredBaseModel):
    "What one generation run read and wrote: the installed `linkml` version, the files it read and the files it wrote. Written as `rp-manifest.json` in the target\u0027s Python folder."
    linkml: str = Field(default=..., title="LinkML version", description="The version of the `linkml` package that ran the generation.")
    inputs: Optional[list[ManifestEntry]] = Field(default=None, title="Inputs", description="The files a generation run read, sorted by path.")
    outputs: Optional[list[ManifestEntry]] = Field(default=None, title="Outputs", description="The files a generation run wrote, sorted by path; not the manifest itself.")


class ConstraintCase(ConfiguredBaseModel):
    "One row of the conformance table: a constraint kind, a class that declares it, and the instance files the generated class and shape must accept and refuse."
    kind: ConstraintKind = Field(default=..., title="Constraint kind", description="The kind of constraint a case exercises.")
    class_name: str = Field(default=..., title="Class name", description="The name of a class of the schema.")
    valid: Optional[list[str]] = Field(default=None, title="Valid instances", description="Paths of instance files, beside the cases file, that the class and the shape must accept.")
    invalid: Optional[list[str]] = Field(default=None, title="Invalid instances", description="Paths of instance files, beside the cases file, that the class and the shape must refuse.")


class SlotShape(ConfiguredBaseModel):
    "The shape of one slot of a class, as the schema induces it."
    name: str = Field(default=..., title="Name", description="The name of a slot.")
    required: bool = Field(default=..., title="Required", description="Whether a value is required.")
    multivalued: bool = Field(default=..., title="Multivalued", description="Whether the slot takes several values.")
    range: str = Field(default=..., title="Range", description="The name of the type, enum or class the slot\u0027s values belong to.")


class ClassShape(ConfiguredBaseModel):
    "The reviewed shape of one class, its name and the shape of each of its slots."
    class_name: str = Field(default=..., title="Class name", description="The name of a class of the schema.")
    slots: Optional[list[SlotShape]] = Field(default=None, title="Slots", description="The shapes of a class\u0027s slots, in schema order.")


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
GenerationTarget.model_rebuild()
ManifestEntry.model_rebuild()
GenerationManifest.model_rebuild()
ConstraintCase.model_rebuild()
SlotShape.model_rebuild()
ClassShape.model_rebuild()
