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


class GenerationAnnotation(str, Enum):
    "The annotations this module\u0027s schema carries for the toolchain itself."
    CLI_FLAG = "cli_flag"
    "On a GenerationTarget slot, the command-line flag that overrides it."
    SECRET = "secret"
    "On a slot, `true` when its value must stay out of the repr of the generated class."



class GenerationTarget(ConfiguredBaseModel):
    "One entry of the `[tool.rp-generate]` table of a `pyproject.toml`: a schema and the folders its generated artefacts are written to. Paths are relative to the folder of the `pyproject.toml`."
    schema_file: str = Field(default=..., title="Schema file", description="The root LinkML schema file; the TOML key and the flag are `schema`, which the field name avoids because it would shadow a pydantic method.")
    package: str = Field(default=..., title="Package", description="The Python import path of the generated package, a dotted identifier.")
    python: Optional[str] = Field(default=None, title="Python folder", description="The folder that receives the classes, shapes, context, frames and the schema copy; the folder of `package` when absent.")
    typescript: Optional[str] = Field(default=None, title="TypeScript folder", description="The folder that receives the TypeScript types; none are written when absent.")
    diagrams: Optional[str] = Field(default=None, title="Diagrams folder", description="The folder that receives one Mermaid file per module; none are written when absent.")

    @field_validator("schema_file")
    def pattern_schema_file(cls, v):
        pattern=re.compile("^(?:[^/:\\\\.\\x00-\\x1f\\x7f][^/:\\\\\\x00-\\x1f\\x7f]*|\\.[^/:\\\\.\\x00-\\x1f\\x7f][^/:\\\\\\x00-\\x1f\\x7f]*|\\.\\.[^/:\\\\\\x00-\\x1f\\x7f]+)(?:/(?:[^/:\\\\.\\x00-\\x1f\\x7f][^/:\\\\\\x00-\\x1f\\x7f]*|\\.[^/:\\\\.\\x00-\\x1f\\x7f][^/:\\\\\\x00-\\x1f\\x7f]*|\\.\\.[^/:\\\\\\x00-\\x1f\\x7f]+))*$")
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
        pattern=re.compile("^(?:[^/:\\\\.\\x00-\\x1f\\x7f][^/:\\\\\\x00-\\x1f\\x7f]*|\\.[^/:\\\\.\\x00-\\x1f\\x7f][^/:\\\\\\x00-\\x1f\\x7f]*|\\.\\.[^/:\\\\\\x00-\\x1f\\x7f]+)(?:/(?:[^/:\\\\.\\x00-\\x1f\\x7f][^/:\\\\\\x00-\\x1f\\x7f]*|\\.[^/:\\\\.\\x00-\\x1f\\x7f][^/:\\\\\\x00-\\x1f\\x7f]*|\\.\\.[^/:\\\\\\x00-\\x1f\\x7f]+))*$")
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
        pattern=re.compile("^(?:[^/:\\\\.\\x00-\\x1f\\x7f][^/:\\\\\\x00-\\x1f\\x7f]*|\\.[^/:\\\\.\\x00-\\x1f\\x7f][^/:\\\\\\x00-\\x1f\\x7f]*|\\.\\.[^/:\\\\\\x00-\\x1f\\x7f]+)(?:/(?:[^/:\\\\.\\x00-\\x1f\\x7f][^/:\\\\\\x00-\\x1f\\x7f]*|\\.[^/:\\\\.\\x00-\\x1f\\x7f][^/:\\\\\\x00-\\x1f\\x7f]*|\\.\\.[^/:\\\\\\x00-\\x1f\\x7f]+))*$")
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
        pattern=re.compile("^(?:[^/:\\\\.\\x00-\\x1f\\x7f][^/:\\\\\\x00-\\x1f\\x7f]*|\\.[^/:\\\\.\\x00-\\x1f\\x7f][^/:\\\\\\x00-\\x1f\\x7f]*|\\.\\.[^/:\\\\\\x00-\\x1f\\x7f]+)(?:/(?:[^/:\\\\.\\x00-\\x1f\\x7f][^/:\\\\\\x00-\\x1f\\x7f]*|\\.[^/:\\\\.\\x00-\\x1f\\x7f][^/:\\\\\\x00-\\x1f\\x7f]*|\\.\\.[^/:\\\\\\x00-\\x1f\\x7f]+))*$")
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
        pattern=re.compile("^(?:[^/:\\\\.\\x00-\\x1f\\x7f][^/:\\\\\\x00-\\x1f\\x7f]*|\\.[^/:\\\\.\\x00-\\x1f\\x7f][^/:\\\\\\x00-\\x1f\\x7f]*|\\.\\.[^/:\\\\\\x00-\\x1f\\x7f]+)(?:/(?:[^/:\\\\.\\x00-\\x1f\\x7f][^/:\\\\\\x00-\\x1f\\x7f]*|\\.[^/:\\\\.\\x00-\\x1f\\x7f][^/:\\\\\\x00-\\x1f\\x7f]*|\\.\\.[^/:\\\\\\x00-\\x1f\\x7f]+))*$")
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
    name: str = Field(default=..., title="Name", description="The name of the thing a record describes (a slot, a file, a class, a rule).")
    required: bool = Field(default=..., title="Required", description="Whether a value is required.")
    multivalued: bool = Field(default=..., title="Multivalued", description="Whether the slot takes several values.")
    range: str = Field(default=..., title="Range", description="The name of the type, enum or class the slot\u0027s values belong to.")
    alias: Optional[str] = Field(default=None, title="Alias", description="The name the slot\u0027s field carries in code and JSON when it differs from the slot\u0027s name; absent otherwise.")


class ClassShape(ConfiguredBaseModel):
    "The reviewed shape of one class, its name and the shape of each of its slots."
    class_name: str = Field(default=..., title="Class name", description="The name of a class of the schema.")
    slots: Optional[list[SlotShape]] = Field(default=None, title="Slots", description="The shapes of a class\u0027s slots, in schema order.")


class CliFlag(ConfiguredBaseModel):
    "A command-line flag of `rp-generate` and the GenerationTarget field it overrides."
    option: str = Field(default=..., title="Option", description="The command-line option, with its leading dashes.")
    field: str = Field(default=..., title="Field", description="The name of the GenerationTarget field the option overrides.")


class GeneratedFile(ConfiguredBaseModel):
    "One file a generator renders, its name inside the target folder and its text."
    name: str = Field(default=..., title="Name", description="The name of the thing a record describes (a slot, a file, a class, a rule).")
    text: str = Field(default=..., title="Text", description="The text of a file.")


class CheckProblem(ConfiguredBaseModel):
    "One problem a check, a pipeline step or the freshness comparison found, with where and by which rule. Only the command line formats it for the developer."
    rule: Optional[str] = Field(default=None, title="Rule", description="The id of the rule a problem breaks, a `HardRule` or `BoundaryRule` value or a lint rule name.")
    element: Optional[str] = Field(default=None, title="Element", description="The element of the schema, or the file, a problem is about.")
    message: str = Field(default=..., title="Message", description="What is wrong, in a line.")
    schema_file: Optional[str] = Field(default=None, title="Schema file", description="The root LinkML schema file; the TOML key and the flag are `schema`, which the field name avoids because it would shadow a pydantic method.")
    step: Optional[str] = Field(default=None, title="Step", description="The name of the pipeline step that found a problem.")

    @field_validator("schema_file")
    def pattern_schema_file(cls, v):
        pattern=re.compile("^(?:[^/:\\\\.\\x00-\\x1f\\x7f][^/:\\\\\\x00-\\x1f\\x7f]*|\\.[^/:\\\\.\\x00-\\x1f\\x7f][^/:\\\\\\x00-\\x1f\\x7f]*|\\.\\.[^/:\\\\\\x00-\\x1f\\x7f]+)(?:/(?:[^/:\\\\.\\x00-\\x1f\\x7f][^/:\\\\\\x00-\\x1f\\x7f]*|\\.[^/:\\\\.\\x00-\\x1f\\x7f][^/:\\\\\\x00-\\x1f\\x7f]*|\\.\\.[^/:\\\\\\x00-\\x1f\\x7f]+))*$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.fullmatch(element):
                    err_msg = "Invalid schema_file format: " + str(element)
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.fullmatch(v):
            err_msg = "Invalid schema_file format: " + str(v)
            raise ValueError(err_msg)
        return v


class PresenceRule(ConfiguredBaseModel):
    "A class-level rule over alternatives, and when its validator refuses."
    name: str = Field(default=..., title="Name", description="The name of the thing a record describes (a slot, a file, a class, a rule).")
    need: str = Field(default=..., title="Need", description="What a rule needs of its alternatives, in words.")
    refused: str = Field(default=..., title="Refused", description="The Python condition under which a rule\u0027s validator refuses.")


class RuleAlternative(ConfiguredBaseModel):
    "One alternative of a rule, its readable label and the Python expression that tells it holds."
    label: str = Field(default=..., title="Label", description="A readable label.")
    holds: str = Field(default=..., title="Holds", description="The Python expression that tells an alternative holds.")


class UniqueKeyOn(ConfiguredBaseModel):
    "A unique key that a class\u0027s multivalued slot is subject to, with the IRIs the constraint query needs."
    name: str = Field(default=..., title="Name", description="The name of the thing a record describes (a slot, a file, a class, a rule).")
    slot_iri: str = Field(default=..., title="Slot IRI", description="The expanded IRI of a slot.")
    key_name: str = Field(default=..., title="Key name", description="The name of a unique key.")
    description: Optional[str] = Field(default=None, title="Description", description="A description in words.")
    key_iris: list[str] = Field(default=..., title="Key IRIs", description="The expanded IRIs of the slots that make up a unique key.")


class Frame(ConfiguredBaseModel):
    "A JSON-LD frame, the types it selects, its references and the frames of its owned parts."
    type_terms: list[str] = Field(default=..., title="Type terms", description="The context terms of the types a frame selects.")
    references: list[str] = Field(default=..., title="References", description="The slots of a frame that hold references, left as IRIs.")
    parts: list[FramePart] = Field(default=..., title="Parts", description="The frames of the owned parts nested in a frame, one per owned slot.")


class FramePart(ConfiguredBaseModel):
    "The frame of the parts nested in one owned slot of a frame."
    name: str = Field(default=..., title="Name", description="The name of the thing a record describes (a slot, a file, a class, a rule).")
    frame: Frame = Field(default=..., title="Frame", description="The frame of the parts held by a slot.")


class TsField(ConfiguredBaseModel):
    "A field of a TypeScript interface."
    name: str = Field(default=..., title="Name", description="The name of the thing a record describes (a slot, a file, a class, a rule).")
    type: str = Field(default=..., title="Type", description="The type of a value, as the target language names it.")
    optional: bool = Field(default=..., title="Optional", description="Whether a field may be left out.")
    doc: str = Field(default=..., title="Doc", description="A one-line doc comment, empty when there is none.")


class TsInterface(ConfiguredBaseModel):
    "A TypeScript interface and its fields."
    name: str = Field(default=..., title="Name", description="The name of the thing a record describes (a slot, a file, a class, a rule).")
    doc: str = Field(default=..., title="Doc", description="A one-line doc comment, empty when there is none.")
    fields: list[TsField] = Field(default=..., title="Fields", description="The fields of an interface.")


class TsEnumValue(ConfiguredBaseModel):
    "A string literal of a TypeScript union type."
    literal: str = Field(default=..., title="Literal", description="A string literal, quoted.")
    doc: str = Field(default=..., title="Doc", description="A one-line doc comment, empty when there is none.")


class TsEnum(ConfiguredBaseModel):
    "A union of string literals that stands for an enum of the schema."
    name: str = Field(default=..., title="Name", description="The name of the thing a record describes (a slot, a file, a class, a rule).")
    doc: str = Field(default=..., title="Doc", description="A one-line doc comment, empty when there is none.")
    values: list[TsEnumValue] = Field(default=..., title="Values", description="The values of a union type.")


class TsImport(ConfiguredBaseModel):
    "The names a TypeScript module imports from another module."
    module: str = Field(default=..., title="Module", description="The name of a schema module.")
    names: list[str] = Field(default=..., title="Names", description="The names imported from a module.")


class TsModule(ConfiguredBaseModel):
    "One TypeScript file, for one module of the schema."
    name: str = Field(default=..., title="Name", description="The name of the thing a record describes (a slot, a file, a class, a rule).")
    enums: list[TsEnum] = Field(default=..., title="Enums", description="The enums a TypeScript module declares.")
    interfaces: list[TsInterface] = Field(default=..., title="Interfaces", description="The interfaces a TypeScript module declares.")
    imports: list[TsImport] = Field(default=..., title="Imports", description="The imports of a TypeScript module.")


class MmdAttribute(ConfiguredBaseModel):
    "An attribute line of a Mermaid class box."
    type: str = Field(default=..., title="Type", description="The type of a value, as the target language names it.")
    name: str = Field(default=..., title="Name", description="The name of the thing a record describes (a slot, a file, a class, a rule).")


class MmdClass(ConfiguredBaseModel):
    "One class box of a Mermaid diagram."
    name: str = Field(default=..., title="Name", description="The name of the thing a record describes (a slot, a file, a class, a rule).")
    stereotype: Optional[str] = Field(default=None, title="Stereotype", description="The stereotype of a class box, `root` or `owned`, absent for a plain class.")
    attributes: list[MmdAttribute] = Field(default=..., title="Attributes", description="The attribute lines of a class box.")


class MmdModule(ConfiguredBaseModel):
    "One Mermaid class diagram, for one module of the schema."
    classes: list[MmdClass] = Field(default=..., title="Classes", description="The class boxes of a diagram.")
    links: list[str] = Field(default=..., title="Links", description="The relationship lines of a diagram.")
    externals: list[str] = Field(default=..., title="Externals", description="The names of the classes a diagram draws as a name only.")


class Violation(ConfiguredBaseModel):
    "A hand-written model or a generated artefact that a guard found out of place."
    where: str = Field(default=..., title="Where", description="The place of a violation, a file and a line or a path.")
    what: str = Field(default=..., title="What", description="What is wrong at that place.")


class ContainerMarker(ConfiguredBaseModel):
    "A pytest marker of the container tests, the container it starts and its help text."
    marker: str = Field(default=..., title="Marker", description="The name of a pytest marker.")
    container: str = Field(default=..., title="Container", description="The name of a container the testkit starts.")
    help: str = Field(default=..., title="Help", description="A line of help text.")


class ExecResult(ConfiguredBaseModel):
    "What a command run inside a container printed, and how it ended."
    stdout: str = Field(default=..., title="Standard output", description="What the command wrote to its standard output.")
    stderr: str = Field(default=..., title="Standard error", description="What the command wrote to its standard error.")
    exit_code: int = Field(default=..., title="Exit code", description="The exit code the command ended with.")


class FusekiServer(ConfiguredBaseModel):
    "Where the test Fuseki answers, and the one user it admits."
    url: str = Field(default=..., title="URL", description="The base URL a server answers on.")
    user: str = Field(default=..., title="User", description="The user name the server admits.")
    password: str = Field(default=..., title="Password", description="The password of the user.", repr=False)


class GarageServer(ConfiguredBaseModel):
    "The S3 endpoint of the test Garage and the key bootstrapped on it."
    endpoint: str = Field(default=..., title="Endpoint", description="The URL of the S3 endpoint.")
    key_id: str = Field(default=..., title="Key id", description="The id of the access key.")
    secret: str = Field(default=..., title="Secret", description="The secret of the access key.", repr=False)
    region: str = Field(default=..., title="Region", description="The region name the S3 client signs for.")


class ZitadelServer(ConfiguredBaseModel):
    "Where the test Zitadel answers, and the admin machine user\u0027s personal access token, which authenticates the management API for provisioning a project, an application and machine users."
    url: str = Field(default=..., title="URL", description="The base URL a server answers on.")
    admin_pat: str = Field(default=..., title="Admin PAT", description="The personal access token of the admin machine user.", repr=False)


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
GenerationTarget.model_rebuild()
ManifestEntry.model_rebuild()
GenerationManifest.model_rebuild()
ConstraintCase.model_rebuild()
SlotShape.model_rebuild()
ClassShape.model_rebuild()
CliFlag.model_rebuild()
GeneratedFile.model_rebuild()
CheckProblem.model_rebuild()
PresenceRule.model_rebuild()
RuleAlternative.model_rebuild()
UniqueKeyOn.model_rebuild()
Frame.model_rebuild()
FramePart.model_rebuild()
TsField.model_rebuild()
TsInterface.model_rebuild()
TsEnumValue.model_rebuild()
TsEnum.model_rebuild()
TsImport.model_rebuild()
TsModule.model_rebuild()
MmdAttribute.model_rebuild()
MmdClass.model_rebuild()
MmdModule.model_rebuild()
Violation.model_rebuild()
ContainerMarker.model_rebuild()
ExecResult.model_rebuild()
FusekiServer.model_rebuild()
GarageServer.model_rebuild()
ZitadelServer.model_rebuild()
