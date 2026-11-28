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

class HardRule(str, _Enum):
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
    IRI_TYPE = "iri_type"
    "The `rp_iri_type` of a root or an owned class, or its kebab-case name when it has none, is unique among them and is not a reserved word of the IRI layout."
    RESERVED_SEGMENT = "reserved_segment"
    "The `rp_path` and `rp_iri_type` of an application class do not start with `rp-`, the prefix of the toolkit\u0027s own roots."
    WORKFLOW = "workflow"
    "The `workflow` annotation is on an aggregate root that is not the tenant root and includes `UnderWorkflow`, and every concrete root that includes `UnderWorkflow` has the annotation, its own or inherited."
    MIGRATIONS_FOLDER = "migrations_folder"
    "A target whose own modules define a root class that the toolkit stores sets `migrations`, the folder of the schema lock and of its migration files, in its `[tool.rp-generate]` entry."
    QUOTED_VERSION = "quoted_version"
    "The root schema of a target that sets `migrations` has a `version`, written as a quoted string in the YAML source, since an unquoted `1.10` is read as the number 1.1."
    TOOLKIT_FILLED = "toolkit_filled"
    "A class of the application does not give `slot_usage`, `ifabsent` or an attribute of its own to a slot annotated `toolkit_filled`, gives no slot of its own the `slot_uri` of one, and has no slot that is both `payload` and required."
    TOOLKIT_SLOT_NAME = "toolkit_slot_name"
    "A slot of the application does not take the name of a toolkit slot that a toolkit class carries under another `slot_uri`: LinkML keeps one slot per name, so one of the two would be lost. A toolkit slot that no toolkit class carries gives way to the application\u0027s."
    SLOT_IRI = "slot_iri"
    "Two slots of different names do not resolve to one IRI, whether by the same `slot_uri` or by one slot\u0027s default IRI equal to another\u0027s `slot_uri`: the triples of the two would merge. A slot or attribute marked `identifier` is exempt. Reported by the target that declares one of the slots."
    DEFAULT_INSTANCE = "default_instance"
    "A slot annotated `default_instance` ranges over a class, and every required slot of that class has an `ifabsent`, so the class can be built with no argument."
    PYTHON_PACKAGE = "python_package"
    "A schema module of the toolkit\u0027s own targets carries the `python_package` annotation."
    PYTHON_PACKAGE_MISMATCH = "python_package_mismatch"
    "The `python_package` of a schema module of the toolkit\u0027s own targets equals the `package` of the `[[tool.rp-generate]]` entry that generates it."


class LockRule(str, _Enum):
    "How a change between two locks is treated."
    SAFE = "safe"
    "Nothing stored is lost or left invalid; the lock is rewritten."
    DESTRUCTIVE = "destructive"
    "Stored data would be deleted; needs a new version and a drop step."
    NEEDS_STEP = "needs_step"
    "Stored data may no longer fit; needs a new version and a step the developer writes."
    NOT_MIGRATABLE = "not_migratable"
    "An IRI would change or data would move between graphs; no step can do it."


class BoundaryRule(str, _Enum):
    "The rules of the boundary check; a problem line starts with its rule."
    OWNERSHIP = "ownership"
    "A class is an aggregate root or is owned by a root."
    REFERENCE = "reference"
    "A slot that is not owned points to a root or to a reference class."
    MODULE_KIND = "module_kind"
    "A domain module does not import a technical or an access module."
    ACTIVITY_DIRECTION = "activity_direction"
    "A slot of a class that is not an activity does not range over an application activity class that is not an aggregate root: the stored model never refers to a use case."
    TARGET_KIND = "target_kind"
    "A target\u0027s modules are of one kind, derived from them, and its package sits in a folder that kind allows."


class TargetKind(str, _Enum):
    "The kind of a generation target, derived from the modules it generates."
    DOMAIN = "domain"
    "Not every module the target generates is `module_kind: technical`."
    TECHNICAL = "technical"
    "Every module the target generates is `module_kind: technical`."


class ConstraintKind(str, _Enum):
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


class GenerationAnnotation(str, _Enum):
    "The annotations this module\u0027s schema carries for the toolchain itself."
    CLI_FLAG = "cli_flag"
    "On a GenerationTarget slot, the command-line flag that overrides it."
    SECRET = "secret"
    "On a slot, `true` when its value must stay out of the repr of the generated class."
    ALLOWS_EXTRA = "allows_extra"
    "On a class, `true` when it accepts fields it does not declare and keeps them in `model_extra`, as the answer of a foreign API needs. Every other class refuses them."
    STRICT = "strict"
    "On a slot, `true` when its value must already be of its type: a string is not read as a number, and a boolean is not read as one either."
    PYTHON_IMPORT = "python_import"
    "On a type, the Python module its `repr` class is imported from: the generated module then reads `from \u003cmodule\u003e import \u003crepr\u003e`."
    DEFAULT_INSTANCE = "default_instance"
    "On a slot whose range is a class, `true` when the slot\u0027s default is a new instance of that class (`Field(default_factory=\u003cRange\u003e)`), so it is never absent. The hard check refuses it on a slot whose range is not a class, or whose range class has a required slot with no `ifabsent`."
    FIELD_NAME = "field_name"
    "On a slot with an `alias`, `slot` when the generated field is named after the slot and keeps the alias as its pydantic alias. Without it the field is named after the alias when that is a Python identifier (the stock behaviour, which the wire and service schemas rely on)."
    PYTHON_PACKAGE = "python_package"
    "On a schema module of the toolkit, the Python package its classes are generated into: a toolkit run imports them from `\u003cpython_package\u003e.\u003cmodule name\u003e`. It equals the `package` of the `[[tool.rp-generate]]` entry that generates the module, which the hard check compares."
    PUBLIC_PACKAGE = "public_package"
    "On the root schema of the metamodel (`rp.yaml`), the package an application\u0027s generated code imports the metamodel\u0027s classes from, which re-exports them."


class UmlLinkKind(str, _Enum):
    "The kinds of connector the UML reader keeps."
    ASSOCIATION = "association"
    "A connector between two classes, with roles and cardinalities."
    DEPENDENCY = "dependency"
    "A connector from a class to the enumeration it is typed by."
    GENERALISATION = "generalisation"
    "A connector from a class to its parent."


class UmlStateNodeKind(str, _Enum):
    "The kinds of state node the UML reader recognises."
    STATE = "state"
    "A state of a state machine."
    INITIAL = "initial"
    "The initial node of a state machine."


class ReportKind(str, _Enum):
    "The kinds of line the conversion report holds; the report prints them with `-` where the schema has `_`."
    NOT_GENERATED = "not_generated"
    "A class left out because its stereotype is listed as not generated."
    EXCLUDED_LINK = "excluded_link"
    "A link left out because it reaches an excluded package."
    OUTSIDE_LINK = "outside_link"
    "A link that reaches a class that is not generated, kept as a reference by IRI."
    NO_NOTE = "no_note"
    "A class or an attribute with no note, so no description to carry."
    IMPLICIT_MEANING = "implicit_meaning"
    "A value of an enumeration written without a prefix, so with no `meaning`."
    TOOLKIT_FILLED = "toolkit_filled"
    "An element the converter took from the toolkit\u0027s classes, not from the drawing."
    TOOLKIT_SLOT_KEPT = "toolkit_slot_kept"
    "An attribute that stood for a toolkit slot and was replaced by it."
    IGNORED_TAG = "ignored_tag"
    "A tagged value no rule uses."
    IGNORED_STEREOTYPE = "ignored_stereotype"
    "A stereotype no rule uses."
    STALE_FILE = "stale_file"
    "A file of an earlier run left in the output folder, which this run did not write."
    EXTERNAL_LIST = "external_list"
    "An enumeration with no literals, a list kept outside the model, so its slots range over a URI."
    UNSPECIFIED_MULTIPLICITY = "unspecified_multiplicity"
    "A connector end with no multiplicity, read as zero or more."
    ROLE = "role"
    "A role definition drawn as an object, with its role, level and actions."
    WORKFLOW = "workflow"
    "A Statechart diagram read as a workflow, with its state and transition counts, or a workflow no class names."
    DERIVED_IRI = "derived_iri"
    "A workflow whose diagram name has no prefix, so its IRI is made from the schema base."
    ROOT = "root"
    "An aggregate root the converter derived, with the parts of its aggregate."
    DEPRECATED_ROOT = "deprecated_root"
    "A \u00abroot\u00bb stereotype the model still draws that agrees with the derived roots; informational."
    BOUNDARY_DISAGREES = "boundary_disagrees"
    "A boundary in a converted package whose name is not the name of a derived root or the tenant root."
    COMPOSITION_NAMED = "composition_named"
    "A composition that carries a note, or a role where a single candidate makes it unneeded."
    AGGREGATES_DIAGRAM = "aggregates_diagram"
    "An aggregates diagram that shows what it should not, or whose name does not start with its package\u0027s name."
    COMPOSITION_DIAGRAM = "composition_diagram"
    "A class diagram that is not an aggregates diagram and shows a composition."
    UNPREFIXED_NAME = "unprefixed_name"
    "A class or an attribute written without a prefix."
    UNUSED_ENUMERATION = "unused_enumeration"
    "An enumeration no slot ranges over."
    DRAWN_TOOLKIT_PARENT = "drawn_toolkit_parent"
    "A class that draws a generalisation to a class of the toolkit instead of taking its mixin."
    TENANT_REQUIRED_POINTER = "tenant_required_pointer"
    "A required pointer to the tenant root, which the toolkit fills."


class LeftOutReason(str, _Enum):
    "Why the converter leaves a class of the drawing out of the generated schemas; a link to it is then reported by this reason."
    NOT_GENERATED = "not_generated"
    "The class carries a stereotype listed as not generated, or is an enumeration of the toolkit."
    EXCLUDED = "excluded"
    "The class sits in an excluded package."
    OUTSIDE = "outside"
    "The class sits in a package outside the converted subtree."


class UmlRule(str, _Enum):
    "The rules of the UML conversion, one value for each rule of the design\u0027s rule table that is in force; a problem names the one it breaks. `no_rule` stands for an element no rule maps."
    NO_RULE = "no_rule"
    "An element of the model that no rule maps; the run fails."
    PACKAGE_MODULE = "package_module"
    "R-1, a package becomes a module of the root schema."
    CLASS_IRI = "class_iri"
    "R-2, a class `pfx:Name` becomes a class `Name` with that IRI."
    ABSTRACT_CLASS = "abstract_class"
    "R-3, an abstract class becomes an abstract class."
    GENERALISATION = "generalisation"
    "R-4, a generalisation becomes `is_a` for the first parent and mixins for the others."
    ATTRIBUTE_SLOT = "attribute_slot"
    "R-5, an attribute becomes a slot with its IRI, range, required and multivalued."
    ASSOCIATION_SLOT = "association_slot"
    "R-6, an association becomes a slot on its source whose range is its destination."
    ENUMERATION = "enumeration"
    "R-7, an enumeration becomes an enum, its literals permissible values."
    DEPENDENCY_ENUM_SLOT = "dependency_enum_slot"
    "R-8, a dependency on an enumeration becomes a slot ranged by that enum."
    NOTES_DESCRIPTION = "notes_description"
    "R-9, the notes of a class, an attribute or a connector become descriptions."
    ROOT_CLASS = "root_class"
    "R-10, a root class gets the aggregate-root mixin and a path."
    BOUNDARY_OWNED = "boundary_owned"
    "R-11, the classes of a boundary or a composite association are owned by the root."
    NOT_GENERATED = "not_generated"
    "R-12, a stereotype listed as not generated makes no class and is reported."
    SHARED_SLOT = "shared_slot"
    "R-13, one slot name and IRI on several classes make one shared slot."
    TOOLKIT_SLOT = "toolkit_slot"
    "R-15 and R-22, an attribute whose IRI a toolkit slot has is that slot; a `dct:identifier` is the new identifier slot."
    TENANT_ROOT = "tenant_root"
    "R-18, a tenant root is stored in the meta graph and is no aggregate root."
    TITLE = "title"
    "R-19, a class or a slot with no title gets its name split into words."
    CLASS_ANNOTATION = "class_annotation"
    "R-20, a tagged value named like a toolkit class annotation becomes that annotation."
    UNIQUE_KEY = "unique_key"
    "R-21, a `unique_key` tagged value becomes a unique key of the class."
    ABSTRACT_ROOT = "abstract_root"
    "R-23, an abstract class of roots that is a slot\u0027s range is an aggregate root with no path."
    SHARED_SLOT_ACROSS_PACKAGES = "shared_slot_across_packages"
    "R-24, a slot on classes of several packages is defined once in the module the others import."
    TOOLKIT_MIXINS = "toolkit_mixins"
    "R-25 to R-28, the default mixins, `rp_mixins`, `workflow` and a drawn toolkit parent."
    LEFT_OUT_LINK = "left_out_link"
    "R-29, a link to a class that is not generated, or to an excluded package, is left out and reported."
    CARDINALITY_UNBOUNDED = "cardinality_unbounded"
    "R-31, an unbounded role under an `is_a` ancestor whose role of the same name is bounded; a subclass cannot redraw a bounded role as unbounded."
    ACTIVITY_ROOT = "activity_root"
    "A root class that is an activity, which the toolkit\u0027s rules do not allow."
    ROLE_RUN_STATE = "role_run_state"
    "PD-3, the run state of a role object holds the variables `role`, `level` and `actions`, each once, with the operator `=` and nothing else."
    ROLE_DEFINITION = "role_definition"
    "PD-3, the values of a role object are a role definition of the toolkit, with at least one action and none twice."
    ROLE_DUPLICATE = "role_duplicate"
    "PD-3, two role objects with one role and level."
    WORKFLOW_NODE = "workflow_node"
    "PD-5, a state of the converted packages is placed on exactly one Statechart diagram."
    WORKFLOW_INITIAL = "workflow_initial"
    "PD-5, a Statechart diagram has one Initial node with one untagged flow to a state of the diagram."
    WORKFLOW_TRANSITION = "workflow_transition"
    "PD-5, a transition carries the tags `roles` (drawn roles only) and `comment_required`, runs between states of one diagram and is the only one between them."
    WORKFLOW_DEFINITION = "workflow_definition"
    "PD-5, the name, states and transitions of a diagram are a workflow definition of the toolkit, its states named once."
    WORKFLOW_DUPLICATE = "workflow_duplicate"
    "PD-5, two Statechart diagrams with one workflow name or one workflow IRI."
    WORKFLOW_CLASS = "workflow_class"
    "PD-5, a class tagged `workflow` names a workflow a converted diagram draws, when one is converted."



class GenerationTarget(ConfiguredBaseModel):
    "One entry of the `[tool.rp-generate]` table of a `pyproject.toml`: a schema and the folders its generated artefacts are written to. Paths are relative to the folder of the `pyproject.toml`."
    schema_file: str = _Field(default=..., alias="schema", title="Schema file", description="The root LinkML schema file; the TOML key and the flag are `schema`, its alias: the field keeps the slot\u0027s name, which does not shadow a pydantic method.")
    package: str = _Field(default=..., title="Package", description="The Python import path of the generated package, a dotted identifier.")
    python: _Optional[str] = _Field(default=None, title="Python folder", description="The folder that receives the classes, shapes, context, frames and the schema copy; the folder of `package` when absent.")
    typescript: _Optional[str] = _Field(default=None, title="TypeScript folder", description="The folder that receives the TypeScript types; none are written when absent.")
    toolkit_typescript: _Optional[bool] = _Field(default=False, alias="toolkit-typescript", title="Toolkit TypeScript owner", description="Whether this entry\u0027s TypeScript folder holds the toolkit\u0027s shared TypeScript modules, which the project\u0027s other TypeScript entries import (TOML key `toolkit-typescript`). Required on exactly one entry when two or more set `typescript`; changes nothing when one does.")
    diagrams: _Optional[str] = _Field(default=None, title="Diagrams folder", description="The folder that receives one Mermaid file per module; none are written when absent.")
    openapi: _Optional[bool] = _Field(default=True, title="OpenAPI components", description="Whether the OpenAPI component schemas of the classes (`openapi-components.json`) are written next to the context. Only a schema whose classes a service serves needs them; on unless set to false.")
    regenerate_command: _Optional[str] = _Field(default=None, alias="regenerate-command", title="Regenerate command", description="The command that regenerates this entry, named in the hint of a failed freshness check (TOML key `regenerate-command`); `rp-generate` when absent.")
    migrations: _Optional[str] = _Field(default=None, title="Migrations folder", description="The folder of the target\u0027s migration files and schema lock, relative to the folder of the `pyproject.toml`; absent for a target that stores nothing of its own.")

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

    @field_validator("regenerate_command")
    def pattern_regenerate_command(cls, v):
        pattern=re.compile("^[^`\\r\\n]*[^`\\s][^`\\r\\n]*$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.fullmatch(element):
                    err_msg = "Invalid regenerate_command format: " + str(element)
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.fullmatch(v):
            err_msg = "Invalid regenerate_command format: " + str(v)
            raise ValueError(err_msg)
        return v

    @field_validator("migrations")
    def pattern_migrations(cls, v):
        pattern=re.compile("^(?:[^/:\\\\.\\x00-\\x1f\\x7f][^/:\\\\\\x00-\\x1f\\x7f]*|\\.[^/:\\\\.\\x00-\\x1f\\x7f][^/:\\\\\\x00-\\x1f\\x7f]*|\\.\\.[^/:\\\\\\x00-\\x1f\\x7f]+)(?:/(?:[^/:\\\\.\\x00-\\x1f\\x7f][^/:\\\\\\x00-\\x1f\\x7f]*|\\.[^/:\\\\.\\x00-\\x1f\\x7f][^/:\\\\\\x00-\\x1f\\x7f]*|\\.\\.[^/:\\\\\\x00-\\x1f\\x7f]+))*$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.fullmatch(element):
                    err_msg = "Invalid migrations format: " + str(element)
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.fullmatch(v):
            err_msg = "Invalid migrations format: " + str(v)
            raise ValueError(err_msg)
        return v


class SchemaLock(ConfiguredBaseModel):
    "The RDF-facing summary of what a target stores, at one schema version: its stored classes and the enums they use. Committed as `schema.lock.json` in the target\u0027s migrations folder, so a change to what is stored is compared with it."
    schema_id: str = _Field(default=..., title="Schema id", description="The id of the schema a lock describes.")
    schema_version: str = _Field(default=..., title="Schema version", description="The `version` of the schema when the lock was written.")
    locked_classes: _Optional[list[LockedClass]] = _Field(default=None, title="Locked classes", description="The stored classes of a lock, sorted by class IRI.")
    locked_enums: _Optional[list[LockedEnum]] = _Field(default=None, title="Locked enums", description="The enums a lock records, sorted by name.")


class LockedClass(ConfiguredBaseModel):
    "A stored class as the lock records it, with its IRI, the type and path of a root, and its slots."
    class_uri: str = _Field(default=..., title="Class IRI", description="The IRI of a stored class.")
    iri_type: _Optional[str] = _Field(default=None, title="IRI type", description="The `rp_iri_type` of a root class, the type segment of its aggregates\u0027 IRIs.")
    root_path: _Optional[str] = _Field(default=None, title="Root path", description="The `rp_path` of a root class, the route segment of its aggregates.")
    root_database: _Optional[str] = _Field(default=None, title="Root database", description="The database of a root class (`tenant`, `application` or `system`), where its aggregates are read from.")
    locked_slots: _Optional[list[LockedSlot]] = _Field(default=None, title="Locked slots", description="The slots of a locked class, sorted by slot IRI.")


class LockedSlot(ConfiguredBaseModel):
    "A slot of a stored class as the lock records it, by its IRI."
    slot_uri: str = _Field(default=..., title="Slot IRI", description="The IRI of a slot.")
    range: str = _Field(default=..., title="Range", description="The IRI of the slot\u0027s range; the name of the enum when the range is an enum.")
    required: _Optional[bool] = _Field(default=None, title="Required", description="Whether a value is required.")
    multivalued: _Optional[bool] = _Field(default=None, title="Multivalued", description="Whether the slot takes several values.")
    inlined: _Optional[bool] = _Field(default=None, title="Inlined", description="Whether the slot\u0027s values are stored inside the aggregate\u0027s graph.")


class LockedEnum(ConfiguredBaseModel):
    "An enum used as a range, with the `meaning` IRI of each value (its text when it has none)."
    name: str = _Field(default=..., title="Name", description="The name of the thing a record describes (a slot, a file, a class, a rule).")
    enum_values: _Optional[list[str]] = _Field(default=None, title="Enum values", description="The `meaning` IRI of each value of an enum, or its text when it has none; sorted.")


class LockChange(ConfiguredBaseModel):
    "One difference between two locks: the rule that treats it, a sentence, and what it is about (a class and a slot, or an enum and a value)."
    rule: LockRule = _Field(default=..., title="Rule", description="How the change is treated, by the table of the schema lock.")
    what: str = _Field(default=..., title="What", description="What changed, as a sentence.")
    class_uri: _Optional[str] = _Field(default=None, title="Class IRI", description="The IRI of a stored class.")
    slot_uri: _Optional[str] = _Field(default=None, title="Slot IRI", description="The IRI of a slot.")
    enum_name: _Optional[str] = _Field(default=None, title="Enum name", description="The name of the enum a lock change is about.")
    enum_value: _Optional[str] = _Field(default=None, title="Enum value", description="The `meaning` IRI, or the text, of the enum value a lock change is about.")


class ManifestEntry(ConfiguredBaseModel):
    "A file and the SHA-256 of its bytes, as recorded by a generation run."
    path: str = _Field(default=..., title="Path", description="A file path, POSIX, relative to the folder of the `pyproject.toml`.")
    sha256: str = _Field(default=..., title="SHA-256", description="The SHA-256 of a file\u0027s bytes, in lowercase hexadecimal.")

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
    linkml: str = _Field(default=..., title="LinkML version", description="The version of the `linkml` package that ran the generation.")
    inputs: _Optional[list[ManifestEntry]] = _Field(default=None, title="Inputs", description="The files a generation run read, sorted by path.")
    outputs: _Optional[list[ManifestEntry]] = _Field(default=None, title="Outputs", description="The files a generation run wrote, sorted by path; not the manifest itself.")


class ConstraintCase(ConfiguredBaseModel):
    "One row of the conformance table: a constraint kind, a class that declares it, and the instance files the generated class and shape must accept and refuse."
    kind: ConstraintKind = _Field(default=..., title="Constraint kind", description="The kind of constraint a case exercises.")
    class_name: str = _Field(default=..., title="Class name", description="The name of a class of the schema.")
    valid: _Optional[list[str]] = _Field(default=None, title="Valid instances", description="Paths of instance files, beside the cases file, that the class and the shape must accept.")
    invalid: _Optional[list[str]] = _Field(default=None, title="Invalid instances", description="Paths of instance files, beside the cases file, that the class and the shape must refuse.")


class CliFlag(ConfiguredBaseModel):
    "A command-line flag of `rp-generate` and the GenerationTarget field it overrides."
    option: str = _Field(default=..., title="Option", description="The command-line option, with its leading dashes.")
    field: str = _Field(default=..., title="Field", description="The name of the GenerationTarget field the option overrides.")


class GeneratedFile(ConfiguredBaseModel):
    "One file a generator renders, its name inside the target folder and its text."
    name: str = _Field(default=..., title="Name", description="The name of the thing a record describes (a slot, a file, a class, a rule).")
    text: str = _Field(default=..., title="Text", description="The text of a file.")


class CheckProblem(ConfiguredBaseModel):
    "One problem a check, a pipeline step or the freshness comparison found, with where and by which rule. Only the command line formats it for the developer."
    rule: _Optional[str] = _Field(default=None, title="Rule", description="The id of the rule a problem breaks, a `HardRule` or `BoundaryRule` value or a lint rule name.")
    element: _Optional[str] = _Field(default=None, title="Element", description="The element of the schema, or the file, a problem is about.")
    message: str = _Field(default=..., title="Message", description="What is wrong, in a line.")
    schema_file: _Optional[str] = _Field(default=None, alias="schema", title="Schema file", description="The root LinkML schema file; the TOML key and the flag are `schema`, its alias: the field keeps the slot\u0027s name, which does not shadow a pydantic method.")
    step: _Optional[str] = _Field(default=None, title="Step", description="The name of the pipeline step that found a problem.")

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


class UmlModel(ConfiguredBaseModel):
    "What the UML reader takes from a model file: the packages, the classes and enumerations with their attributes, the connectors, the tagged values and the boundaries. The converter reads nothing else."
    uml_packages: _Optional[list[UmlPackage]] = _Field(default=None, title="UML packages", description="The packages of a UML model.")
    uml_outside_packages: _Optional[list[UmlPackage]] = _Field(default=None, title="UML outside packages", description="The packages an outside class sits in, and their ancestors, that are not converted. With `uml_packages` they give the package path of an outside class.")
    uml_classes: _Optional[list[UmlClass]] = _Field(default=None, title="UML classes", description="The classes and enumerations of a UML model.")
    uml_outside_classes: _Optional[list[UmlClass]] = _Field(default=None, title="UML outside classes", description="The classes and enumerations at the far end of a link whose near end is a converted class, and that are not converted themselves (outside the subtree, or in an excluded package), without their attributes.")
    uml_links: _Optional[list[UmlLink]] = _Field(default=None, title="UML links", description="The connectors of a UML model.")
    uml_tagged_values: _Optional[list[UmlTaggedValue]] = _Field(default=None, title="UML tagged values", description="The tagged values of the classes of a UML model.")
    uml_boundaries: _Optional[list[UmlBoundary]] = _Field(default=None, title="UML boundaries", description="The boundaries of a UML model.")
    uml_compositions: _Optional[list[UmlComposition]] = _Field(default=None, title="UML compositions", description="The compositions of a UML model, the whole and the part of each read once.")
    uml_diagrams: _Optional[list[UmlDiagram]] = _Field(default=None, title="UML diagrams", description="The class diagrams of the converted packages of a UML model, by membership.")
    uml_objects: _Optional[list[UmlObject]] = _Field(default=None, title="UML objects", description="The objects of a UML model, the instances of its drawn classes.")
    uml_state_nodes: _Optional[list[UmlStateNode]] = _Field(default=None, title="UML state nodes", description="The states and state nodes of the converted packages of a UML model.")
    uml_state_flows: _Optional[list[UmlStateFlow]] = _Field(default=None, title="UML state flows", description="The transitions between the state nodes of the converted packages of a UML model.")
    uml_statecharts: _Optional[list[UmlStatechart]] = _Field(default=None, title="UML statecharts", description="The Statechart diagrams of the converted packages of a UML model.")


class UmlPackage(ConfiguredBaseModel):
    "A package of the UML model, with its parent, so the package tree can be rebuilt, and the object that draws it, which owns its tagged values."
    package_id: int = _Field(default=..., title="Package id", description="The id a UML model gives a package.")
    name: str = _Field(default=..., title="Name", description="The name of the thing a record describes (a slot, a file, a class, a rule).")
    parent_id: _Optional[int] = _Field(default=None, title="Parent id", description="The id of the package that holds a package, absent for a top one.")
    note: _Optional[str] = _Field(default=None, title="Note", description="The note of a UML element.")
    object_id: _Optional[int] = _Field(default=None, title="Object id", description="The id a UML model gives a class, an enumeration, a boundary or the object of a package.")


class UmlClass(ConfiguredBaseModel):
    "A class or an enumeration of the UML model. For an enumeration the attributes are its literals."
    object_id: int = _Field(default=..., title="Object id", description="The id a UML model gives a class, an enumeration, a boundary or the object of a package.")
    name: str = _Field(default=..., title="Name", description="The name of the thing a record describes (a slot, a file, a class, a rule).")
    object_type: str = _Field(default=..., title="Object type", description="The kind of element a UML object is, as the model file names it (`Class`, `Enumeration`).")
    uml_alias: _Optional[str] = _Field(default=None, title="Alias", description="The alias of a UML element, the title the author gave it.")
    note: _Optional[str] = _Field(default=None, title="Note", description="The note of a UML element.")
    package_id: int = _Field(default=..., title="Package id", description="The id a UML model gives a package.")
    uml_stereotype: _Optional[str] = _Field(default=None, title="UML stereotype", description="The stereotype of a UML element, absent when it has none.")
    multiple_stereotypes: _Optional[bool] = _Field(default=None, title="Multiple stereotypes", description="Whether the model gives the element a second stereotype besides the first.")
    is_abstract: _Optional[bool] = _Field(default=None, title="Is abstract", description="Whether a UML class is abstract.")
    ea_guid: _Optional[str] = _Field(default=None, title="GUID", description="The globally unique id the modelling tool gives an object.")
    uml_attributes: _Optional[list[UmlAttribute]] = _Field(default=None, title="UML attributes", description="The attributes of a class, or the literals of an enumeration, in the order the model gives them.")


class UmlAttribute(ConfiguredBaseModel):
    "An attribute of a UML class, or a literal of a UML enumeration."
    attribute_id: int = _Field(default=..., title="Attribute id", description="The id a UML model gives an attribute.")
    owner_id: int = _Field(default=..., title="Owner id", description="The id of the class or enumeration an attribute or a tagged value belongs to.")
    name: str = _Field(default=..., title="Name", description="The name of the thing a record describes (a slot, a file, a class, a rule).")
    note: _Optional[str] = _Field(default=None, title="Note", description="The note of a UML element.")
    declared_type: _Optional[str] = _Field(default=None, title="Declared type", description="The type of an attribute as the model writes it, a datatype or the name of a class.")
    classifier_id: _Optional[int] = _Field(default=None, title="Classifier id", description="The id of the class an attribute or an object is typed by, absent for a plain type.")
    lower_bound: _Optional[str] = _Field(default=None, title="Lower bound", description="The lower bound of an attribute\u0027s multiplicity, as the model writes it.")
    upper_bound: _Optional[str] = _Field(default=None, title="Upper bound", description="The upper bound of an attribute\u0027s multiplicity, as the model writes it (`*` for no bound).")
    position: _Optional[int] = _Field(default=None, title="Position", description="The place of an attribute among those of its class.")
    uml_stereotype: _Optional[str] = _Field(default=None, title="UML stereotype", description="The stereotype of a UML element, absent when it has none.")


class UmlLink(ConfiguredBaseModel):
    "A connector of the UML model: an association, a dependency or a generalisation, from its source class to its target class. Roles and cardinalities are those of each end; an end is the whole of an aggregation when its aggregate flag is set."
    connector_id: int = _Field(default=..., title="Connector id", description="The id a UML model gives a connector.")
    link_kind: UmlLinkKind = _Field(default=..., title="Link kind", description="Whether a connector is an association, a dependency or a generalisation.")
    sub_type: _Optional[str] = _Field(default=None, title="Sub type", description="The sub type of a connector, as the model writes it.")
    uml_stereotype: _Optional[str] = _Field(default=None, title="UML stereotype", description="The stereotype of a UML element, absent when it has none.")
    note: _Optional[str] = _Field(default=None, title="Note", description="The note of a UML element.")
    source_id: int = _Field(default=..., title="Source id", description="The id of the class a connector starts at.")
    target_id: int = _Field(default=..., title="Target id", description="The id of the class a connector ends at.")
    source_role: _Optional[str] = _Field(default=None, title="Source role", description="The role name at the source end of a connector.")
    source_card: _Optional[str] = _Field(default=None, title="Source cardinality", description="The cardinality at the source end of a connector, as the model writes it.")
    source_aggregate: _Optional[int] = _Field(default=None, title="Source aggregate", description="The aggregation flag of the source end of a connector, 0 for none, 1 for shared, 2 for composite.")
    target_role: _Optional[str] = _Field(default=None, title="Target role", description="The role name at the target end of a connector.")
    target_card: _Optional[str] = _Field(default=None, title="Target cardinality", description="The cardinality at the target end of a connector, as the model writes it.")
    target_aggregate: _Optional[int] = _Field(default=None, title="Target aggregate", description="The aggregation flag of the target end of a connector, 0 for none, 1 for shared, 2 for composite.")
    association_class: _Optional[str] = _Field(default=None, title="Association class", description="The id or name the model gives to the class an association is drawn as, absent for a plain one.")
    direction: _Optional[str] = _Field(default=None, title="Direction", description="The direction of a connector as the model writes it (`Source -\u003e Destination`, `Bi-Directional`), absent when the model gives none.")


class UmlTaggedValue(ConfiguredBaseModel):
    "A named value attached to a class of the UML model, its text resolved from the memo when it is one."
    owner_id: int = _Field(default=..., title="Owner id", description="The id of the class or enumeration an attribute or a tagged value belongs to.")
    name: str = _Field(default=..., title="Name", description="The name of the thing a record describes (a slot, a file, a class, a rule).")
    tag_value: _Optional[str] = _Field(default=None, title="Tag value", description="The text of a tagged value.")


class UmlBoundary(ConfiguredBaseModel):
    "A boundary drawn on a diagram, with the classes and enumerations whose rectangles lie wholly inside it."
    object_id: int = _Field(default=..., title="Object id", description="The id a UML model gives a class, an enumeration, a boundary or the object of a package.")
    name: str = _Field(default=..., title="Name", description="The name of the thing a record describes (a slot, a file, a class, a rule).")
    diagram_id: int = _Field(default=..., title="Diagram id", description="The id of the diagram a boundary is drawn on.")
    member_ids: _Optional[list[int]] = _Field(default=None, title="Member ids", description="The ids of the classes and enumerations that lie inside a boundary.")


class UmlComposition(ConfiguredBaseModel):
    "A composition of the UML model, read once from the end columns of an Aggregation connector (PD-1): the class that is the whole and the class that is the part, whatever way it was drawn, with the stereotype and the role written on it."
    composition_id: int = _Field(default=..., title="Composition id", description="The id of the connector a composition was read from.")
    whole_id: int = _Field(default=..., title="Whole id", description="The id of the class that is the whole of a composition.")
    part_id: int = _Field(default=..., title="Part id", description="The id of the class that is the part of a composition.")
    own_graph: _Optional[bool] = _Field(default=False, title="Own graph", description="Whether a composition is drawn with the \u00abown graph\u00bb stereotype.")
    uml_stereotype: _Optional[str] = _Field(default=None, title="UML stereotype", description="The stereotype of a UML element, absent when it has none.")
    role: _Optional[str] = _Field(default=None, title="Role", description="The role written on a composition, naming the association beside it that it marks.")


class UmlDiagram(ConfiguredBaseModel):
    "A class diagram of the UML model, read by membership only (PD-12): the package it sits in, the elements it shows and the connectors it hides. No geometry."
    diagram_id: int = _Field(default=..., title="Diagram id", description="The id of the diagram a boundary is drawn on.")
    name: str = _Field(default=..., title="Name", description="The name of the thing a record describes (a slot, a file, a class, a rule).")
    package_id: _Optional[int] = _Field(default=None, title="Package id", description="The id a UML model gives a package.")
    diagram_type: _Optional[str] = _Field(default=None, title="Diagram type", description="The type of a diagram as the model file writes it.")
    element_ids: _Optional[list[int]] = _Field(default=None, title="Element ids", description="The ids of the elements a diagram shows.")
    hidden_connector_ids: _Optional[list[int]] = _Field(default=None, title="Hidden connector ids", description="The ids of the connectors a diagram hides although both their ends are on it.")


class UmlPartOf(ConfiguredBaseModel):
    "One row of the aggregate tree (PD-19): a class that is a part, the class that is its whole, the composition that says so and whether that composition is an own graph. A part with two wholes has two rows."
    part_id: int = _Field(default=..., title="Part id", description="The id of the class that is the part of a composition.")
    whole_id: int = _Field(default=..., title="Whole id", description="The id of the class that is the whole of a composition.")
    own_graph: _Optional[bool] = _Field(default=False, title="Own graph", description="Whether a composition is drawn with the \u00abown graph\u00bb stereotype.")
    composition_id: int = _Field(default=..., title="Composition id", description="The id of the connector a composition was read from.")


class UmlReach(ConfiguredBaseModel):
    "The tops of the aggregates that reach one part class (PD-4): a part class may be reached from several tops."
    part_id: int = _Field(default=..., title="Part id", description="The id of the class that is the part of a composition.")
    top_ids: _Optional[list[int]] = _Field(default=None, title="Top ids", description="The ids of the tops (roots, the tenant root, abstract tops) of aggregates.")


class UmlOwnedEnd(ConfiguredBaseModel):
    "A connector end that gives an owned slot (PD-5): the connector and the class that holds the slot."
    link_id: int = _Field(default=..., title="Link id", description="The id of the connector an owned end belongs to.")
    holder_id: int = _Field(default=..., title="Holder id", description="The id of the class that holds the slot an end of a connector gives.")


class UmlAggregates(ConfiguredBaseModel):
    "What the aggregate pass returns (PD-19): the derived roots, the tenant root, the tree as rows of parts and wholes, the tops that reach each part, the owned ends, the classes left inside an own graph, and the findings, which the converter merges into its own."
    root_ids: _Optional[list[int]] = _Field(default=None, title="Root ids", description="The ids of the classes derived as aggregate roots.")
    tenant_root_id: _Optional[int] = _Field(default=None, title="Tenant root id", description="The id of the tenant root, absent when the model has none.")
    part_of: _Optional[list[UmlPartOf]] = _Field(default=None, title="Part of", description="The tree as rows, one for each part and whole it belongs to.")
    reached_from: _Optional[list[UmlReach]] = _Field(default=None, title="Reached from", description="For each part class, the tops of the aggregates that reach it.")
    owned_ends: _Optional[list[UmlOwnedEnd]] = _Field(default=None, title="Owned ends", description="The connector ends whose slots are owned by their holder.")
    left_inside_ids: _Optional[list[int]] = _Field(default=None, title="Left-inside ids", description="The ids of the classes left inside the own graph of another class, so not generated.")
    problems: _Optional[list[CheckProblem]] = _Field(default=None, title="Problems", description="The problems a pass found.")
    report_lines: _Optional[list[ReportLine]] = _Field(default=None, title="Report lines", description="The report lines a pass wrote.")


class UmlObject(ConfiguredBaseModel):
    "An object of the UML model, an instance of a drawn class, with the class that types it, the package it sits in and the values its run state sets, as the model file writes them."
    object_id: int = _Field(default=..., title="Object id", description="The id a UML model gives a class, an enumeration, a boundary or the object of a package.")
    uml_name: str = _Field(default=..., title="UML name", description="The name of a UML element, as drawn.")
    classifier_id: _Optional[int] = _Field(default=None, title="Classifier id", description="The id of the class an attribute or an object is typed by, absent for a plain type.")
    realised_ids: _Optional[list[int]] = _Field(default=None, title="Realised ids", description="The ids of the classes an object realises, read from its Realisation connectors.")
    package_path: _Optional[str] = _Field(default=None, title="Package path", description="The path of the package a UML element sits in, the package names joined by `/`.")
    run_values: _Optional[list[UmlRunValue]] = _Field(default=None, title="Run values", description="The variables a UML object\u0027s run state sets, in the order the model file writes them.")
    run_state_rest: _Optional[str] = _Field(default=None, title="Run state rest", description="The text of a UML object\u0027s run state outside its variable blocks, stripped; absent when blank.")


class UmlStateNode(ConfiguredBaseModel):
    "A state or a state node of the UML model, with the kind the reader recognises (a state, or the initial node) and the type the file gives a state node, so the workflow rule can refuse any other."
    object_id: int = _Field(default=..., title="Object id", description="The id a UML model gives a class, an enumeration, a boundary or the object of a package.")
    uml_name: str = _Field(default=..., title="UML name", description="The name of a UML element, as drawn.")
    node_kind: _Optional[UmlStateNodeKind] = _Field(default=None, title="Node kind", description="Whether a state node is a state or the initial node; absent for any other kind of node.")
    node_type: _Optional[int] = _Field(default=None, title="Node type", description="The type code the model file gives a state node (`3` for the initial node), as written.")
    note: _Optional[str] = _Field(default=None, title="Note", description="The note of a UML element.")


class UmlStateFlow(ConfiguredBaseModel):
    "A transition of the UML model between two state nodes of the converted packages, with its tags as the model file writes them."
    connector_id: int = _Field(default=..., title="Connector id", description="The id a UML model gives a connector.")
    source_id: int = _Field(default=..., title="Source id", description="The id of the class a connector starts at.")
    target_id: int = _Field(default=..., title="Target id", description="The id of the class a connector ends at.")
    uml_tagged_values: _Optional[list[UmlTaggedValue]] = _Field(default=None, title="UML tagged values", description="The tagged values of the classes of a UML model.")


class UmlStatechart(ConfiguredBaseModel):
    "A Statechart diagram of the UML model, with the package it sits in and the state nodes placed on it."
    diagram_id: int = _Field(default=..., title="Diagram id", description="The id of the diagram a boundary is drawn on.")
    uml_name: str = _Field(default=..., title="UML name", description="The name of a UML element, as drawn.")
    package_path: _Optional[str] = _Field(default=None, title="Package path", description="The path of the package a UML element sits in, the package names joined by `/`.")
    node_ids: _Optional[list[int]] = _Field(default=None, title="Node ids", description="The ids of the state nodes placed on a diagram.")


class UmlRunValue(ConfiguredBaseModel):
    "One variable a UML object\u0027s run state sets: its name, its value and its operator, as written."
    variable: _Optional[str] = _Field(default=None, title="Variable", description="The name of a variable a run state sets.")
    value: _Optional[str] = _Field(default=None, title="Value", description="The text a run state gives a variable, as written.")
    operator: _Optional[str] = _Field(default=None, title="Operator", description="The operator a run state applies between a variable and its value, as written.")


class UmlPrefix(ConfiguredBaseModel):
    "One prefix of the prefixes file and the namespace it stands for."
    prefix_name: str = _Field(default=..., title="Prefix name", description="The name of a prefix, the part of a CURIE before the colon.")
    namespace: str = _Field(default=..., title="Namespace", description="The IRI a prefix stands for.")


class UmlName(ConfiguredBaseModel):
    "A written name resolved (PD-6): its local name and, when it was prefixed, the IRI it expands to and the CURIE written to the output."
    name: str = _Field(default=..., title="Name", description="The name of the thing a record describes (a slot, a file, a class, a rule).")
    iri: _Optional[str] = _Field(default=None, title="IRI", description="The full IRI a prefixed name expands to; absent for an unprefixed name.")
    curie: _Optional[str] = _Field(default=None, title="CURIE", description="The prefixed name written to the output, in the metamodel\u0027s prefix name when it names the namespace.")


class UmlSettings(ConfiguredBaseModel):
    "What one run of the UML converter is told: the keys of the prefixes file and the command line values the conversion depends on."
    schema_base: str = _Field(default=..., title="Schema base", description="The IRI a module\u0027s id is made from, followed by the module name.")
    default_prefix: str = _Field(default=..., title="Default prefix", description="The name of the prefix the converted modules use for unprefixed names.")
    schema_version: str = _Field(default=..., title="Schema version", description="The `version` of the schema when the lock was written.")
    prefixes: _Optional[list[UmlPrefix]] = _Field(default=None, title="Prefixes", description="The prefixes of the prefixes file.")
    subtree_package: str = _Field(default=..., title="Subtree package", description="The name or path of the package whose subtree is converted.")
    root_name: str = _Field(default=..., title="Root name", description="The name of the root schema, and the prefix of the module names.")
    exclude_packages: _Optional[list[str]] = _Field(default=None, title="Excluded packages", description="The paths of the packages left out of the conversion with their subtrees.")
    default_mixins: _Optional[list[str]] = _Field(default=None, title="Default mixins", description="The mixins a root class and its labelled parts get by default.")
    not_generated_stereotypes: _Optional[list[str]] = _Field(default=None, title="Not-generated stereotypes", description="The stereotypes whose classes are not generated, only listed in the report.")


class UmlElement(ConfiguredBaseModel):
    "A class or an enumeration the conversion generates: the UML class it was read from, its resolved name, where its package sits and what the conversion has classified it as (PD-17, R-18, R-23)."
    uml_class: UmlClass = _Field(default=..., title="UML class", description="The class or enumeration of the UML model that an element was read from.")
    resolved_name: UmlName = _Field(default=..., title="Resolved name", description="The name an element was written with, resolved against the prefixes file.")
    label: str = _Field(default=..., title="Label", description="A readable label.")
    module_path: _Optional[list[str]] = _Field(default=None, title="Module path", description="The names of the packages below the subtree package that an element sits in, outermost first.")
    is_enum: _Optional[bool] = _Field(default=False, title="Is enumeration", description="Whether an element is an enumeration.")
    is_drawn_root: _Optional[bool] = _Field(default=False, title="Is drawn root", description="Whether the model draws an element with the \u00abroot\u00bb stereotype, whatever the derivation says.")
    is_root: _Optional[bool] = _Field(default=False, title="Is root", description="Whether an element is the root of an application aggregate.")
    is_abstract: _Optional[bool] = _Field(default=False, title="Is abstract", description="Whether a UML class is abstract.")
    is_tenant_root: _Optional[bool] = _Field(default=False, title="Is tenant root", description="Whether an element is the root of the tenant, a root of its own kind (R-18).")
    is_abstract_root: _Optional[bool] = _Field(default=False, title="Is abstract root", description="Whether an element is an abstract root, set by the abstract-roots pass (R-23).")


class UmlPackagePath(ConfiguredBaseModel):
    "Where a package sits: its names below the subtree package, whether an exclusion covers it, and its note."
    below: _Optional[list[str]] = _Field(default=None, title="Below the subtree package", description="The names of the packages between the subtree package, which is left out, and a package, which is last.")
    is_excluded: _Optional[bool] = _Field(default=False, title="Is excluded", description="Whether an `--exclude-package` covers a package.")
    note: _Optional[str] = _Field(default=None, title="Note", description="The note of a UML element.")


class UmlLinkEnd(ConfiguredBaseModel):
    "One end of a connector that may become a slot: the class that holds it, the one it points at, and the role and cardinality written at that end."
    holder_id: int = _Field(default=..., title="Holder id", description="The id of the class that holds the slot an end of a connector gives.")
    other_id: int = _Field(default=..., title="Other id", description="The id of the class that the slot an end of a connector gives points at.")
    end_role: _Optional[str] = _Field(default=None, title="End role", description="The role written at the end of a connector that names the slot.")
    end_card: _Optional[str] = _Field(default=None, title="End cardinality", description="The cardinality written at the end of a connector that names the slot, as the model writes it.")
    owned_by_composite: _Optional[bool] = _Field(default=False, title="Owned by composite", description="Whether the destination of the slot is owned because the connector is a composite association.")


class ReportLine(ConfiguredBaseModel):
    "One line of the report a conversion writes beside its output, saying what was left out or changed."
    report_kind: ReportKind = _Field(default=..., title="Report kind", description="What a report line says was left out or changed.")
    element: str = _Field(default=..., title="Element", description="The element of the schema, or the file, a problem is about.")
    message: str = _Field(default=..., title="Message", description="What is wrong, in a line.")


class ModuleCycle(ConfiguredBaseModel):
    "A group of two or more generated modules that import each other."
    modules: list[str] = _Field(default=..., title="Modules", description="The names of schema modules.")


class ModuleDeferral(ConfiguredBaseModel):
    "The names a module of a cycle imports from another module of its cycle without needing them while it loads, so the import can wait for the type checker."
    module: str = _Field(default=..., title="Module", description="The name of a schema module.")
    source_module: str = _Field(default=..., title="Source module", description="The name of the schema module a name is imported from.")
    names: list[str] = _Field(default=..., title="Names", description="The names imported from a module.")


class CycleAnalysis(ConfiguredBaseModel):
    "What the modules of a target need in order to load: the groups that import each other, and per module of a group the names it defers."
    cycles: _Optional[list[ModuleCycle]] = _Field(default=None, title="Cycles", description="The groups of modules that import each other, each sorted, the groups sorted.")
    deferrals: _Optional[list[ModuleDeferral]] = _Field(default=None, title="Deferrals", description="The names each module of a cycle imports from another module of its cycle without needing them at load.")


class PresenceRule(ConfiguredBaseModel):
    "A class-level rule over alternatives, and when its validator refuses."
    name: str = _Field(default=..., title="Name", description="The name of the thing a record describes (a slot, a file, a class, a rule).")
    need: str = _Field(default=..., title="Need", description="What a rule needs of its alternatives, in words.")
    refused: str = _Field(default=..., title="Refused", description="The Python condition under which a rule\u0027s validator refuses.")


class RuleAlternative(ConfiguredBaseModel):
    "One alternative of a rule, its readable label and the Python expression that tells it holds."
    label: str = _Field(default=..., title="Label", description="A readable label.")
    holds: str = _Field(default=..., title="Holds", description="The Python expression that tells an alternative holds.")


class UniqueKeyOn(ConfiguredBaseModel):
    "A unique key that a class\u0027s multivalued slot is subject to, with the IRIs the constraint query needs."
    name: str = _Field(default=..., title="Name", description="The name of the thing a record describes (a slot, a file, a class, a rule).")
    slot_iri: str = _Field(default=..., title="Slot IRI", description="The expanded IRI of a slot.")
    key_name: str = _Field(default=..., title="Key name", description="The name of a unique key.")
    description: _Optional[str] = _Field(default=None, title="Description", description="A description in words.")
    key_iris: list[str] = _Field(default=..., title="Key IRIs", description="The expanded IRIs of the slots that make up a unique key.")


class Frame(ConfiguredBaseModel):
    "A JSON-LD frame, the types it selects, its references and the frames of its owned parts."
    type_terms: list[str] = _Field(default=..., title="Type terms", description="The context terms of the types a frame selects.")
    references: list[str] = _Field(default=..., title="References", description="The slots of a frame that hold references, left as IRIs.")
    parts: list[FramePart] = _Field(default=..., title="Parts", description="The frames of the owned parts nested in a frame, one per owned slot.")


class FramePart(ConfiguredBaseModel):
    "The frame of the parts nested in one owned slot of a frame."
    name: str = _Field(default=..., title="Name", description="The name of the thing a record describes (a slot, a file, a class, a rule).")
    frame: Frame = _Field(default=..., title="Frame", description="The frame of the parts held by a slot.")


class TsField(ConfiguredBaseModel):
    "A field of a TypeScript interface."
    name: str = _Field(default=..., title="Name", description="The name of the thing a record describes (a slot, a file, a class, a rule).")
    type: str = _Field(default=..., title="Type", description="The type of a value, as the target language names it.")
    optional: bool = _Field(default=..., title="Optional", description="Whether a field may be left out.")
    doc: str = _Field(default=..., title="Doc", description="A one-line doc comment, empty when there is none.")


class TsInterface(ConfiguredBaseModel):
    "A TypeScript interface and its fields."
    name: str = _Field(default=..., title="Name", description="The name of the thing a record describes (a slot, a file, a class, a rule).")
    doc: str = _Field(default=..., title="Doc", description="A one-line doc comment, empty when there is none.")
    fields: list[TsField] = _Field(default=..., title="Fields", description="The fields of an interface.")


class TsEnumValue(ConfiguredBaseModel):
    "A string literal of a TypeScript union type."
    literal: str = _Field(default=..., title="Literal", description="A string literal, quoted.")
    doc: str = _Field(default=..., title="Doc", description="A one-line doc comment, empty when there is none.")


class TsEnum(ConfiguredBaseModel):
    "A union of string literals that stands for an enum of the schema."
    name: str = _Field(default=..., title="Name", description="The name of the thing a record describes (a slot, a file, a class, a rule).")
    doc: str = _Field(default=..., title="Doc", description="A one-line doc comment, empty when there is none.")
    values: list[TsEnumValue] = _Field(default=..., title="Values", description="The values of a union type.")


class TsImport(ConfiguredBaseModel):
    "The names a TypeScript module imports from another module."
    module: str = _Field(default=..., title="Module", description="The name of the module to import, or, for a module another target writes as TypeScript, its path relative to the importing file\u0027s folder (it starts with a dot).")
    names: list[str] = _Field(default=..., title="Names", description="The names imported from a module.")


class TsModule(ConfiguredBaseModel):
    "One TypeScript file, for one module of the schema."
    name: str = _Field(default=..., title="Name", description="The name of the thing a record describes (a slot, a file, a class, a rule).")
    enums: list[TsEnum] = _Field(default=..., title="Enums", description="The enums a TypeScript module declares.")
    interfaces: list[TsInterface] = _Field(default=..., title="Interfaces", description="The interfaces a TypeScript module declares.")
    imports: list[TsImport] = _Field(default=..., title="Imports", description="The imports of a TypeScript module.")


class MmdAttribute(ConfiguredBaseModel):
    "An attribute line of a Mermaid class box."
    type: str = _Field(default=..., title="Type", description="The type of a value, as the target language names it.")
    name: str = _Field(default=..., title="Name", description="The name of the thing a record describes (a slot, a file, a class, a rule).")


class MmdClass(ConfiguredBaseModel):
    "One class box of a Mermaid diagram."
    name: str = _Field(default=..., title="Name", description="The name of the thing a record describes (a slot, a file, a class, a rule).")
    stereotype: _Optional[str] = _Field(default=None, title="Stereotype", description="The stereotype of a class box, `root` or `owned`, absent for a plain class.")
    attributes: list[MmdAttribute] = _Field(default=..., title="Attributes", description="The attribute lines of a class box.")


class MmdModule(ConfiguredBaseModel):
    "One Mermaid class diagram, for one module of the schema."
    classes: list[MmdClass] = _Field(default=..., title="Classes", description="The class boxes of a diagram.")
    links: list[str] = _Field(default=..., title="Links", description="The relationship lines of a diagram.")
    externals: list[str] = _Field(default=..., title="Externals", description="The names of the classes a diagram draws as a name only.")


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
GenerationTarget.model_rebuild()
SchemaLock.model_rebuild()
LockedClass.model_rebuild()
LockedSlot.model_rebuild()
LockedEnum.model_rebuild()
LockChange.model_rebuild()
ManifestEntry.model_rebuild()
GenerationManifest.model_rebuild()
ConstraintCase.model_rebuild()
CliFlag.model_rebuild()
GeneratedFile.model_rebuild()
CheckProblem.model_rebuild()
UmlModel.model_rebuild()
UmlPackage.model_rebuild()
UmlClass.model_rebuild()
UmlAttribute.model_rebuild()
UmlLink.model_rebuild()
UmlTaggedValue.model_rebuild()
UmlBoundary.model_rebuild()
UmlComposition.model_rebuild()
UmlDiagram.model_rebuild()
UmlPartOf.model_rebuild()
UmlReach.model_rebuild()
UmlOwnedEnd.model_rebuild()
UmlAggregates.model_rebuild()
UmlObject.model_rebuild()
UmlStateNode.model_rebuild()
UmlStateFlow.model_rebuild()
UmlStatechart.model_rebuild()
UmlRunValue.model_rebuild()
UmlPrefix.model_rebuild()
UmlName.model_rebuild()
UmlSettings.model_rebuild()
UmlElement.model_rebuild()
UmlPackagePath.model_rebuild()
UmlLinkEnd.model_rebuild()
ReportLine.model_rebuild()
ModuleCycle.model_rebuild()
ModuleDeferral.model_rebuild()
CycleAnalysis.model_rebuild()
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
