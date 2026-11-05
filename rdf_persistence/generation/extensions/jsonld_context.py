"""Step 5: the JSON-LD context and one frame per aggregate type (PD-12, PD-25).

``gen-jsonld-context`` has no ``@type`` alias, keeps ``internal`` slots, tags integers and booleans
with a datatype (so a native JSON number comes back as a string after framing), reads a ``uri`` as a
typed literal where the shapes expect an IRI, maps an enum to SKOS notation terms where the shapes list
the meaning IRIs, and has no frames per aggregate. This module closes those gaps in a subclass and a
frame builder; the stock output is not edited.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from linkml.generators.jsonldcontextgen import ContextGenerator
from linkml_runtime.linkml_model.meta import ClassDefinition, EnumDefinition, SlotDefinition
from linkml_runtime.utils.formatutils import camelcase, underscore
from linkml_runtime.utils.schemaview import SchemaView

from rdf_persistence.generation.aggregates import root_classes
from rdf_persistence.generation.checks.scope import TRUE, annotation
from rdf_persistence.generation.exceptions import SchemaGenerationError
from rdf_persistence.generation.outputs import GeneratedFile, stage
from rdf_persistence.generation.pipeline import Run, Step, schema_faults
from rdf_persistence.services.schema import load_schema

CONTEXT_FILE = "context.jsonld"
FRAME_SUFFIX = ".frame.jsonld"
# JSON carries these natively: a datatype tag would turn them into strings when framed back.
NATIVE_JSON_DATATYPES = ("xsd:integer", "xsd:boolean")
JSON_LD_VERSION = 1.1  # property-scoped contexts are a JSON-LD 1.1 feature
ALWAYS = "@always"
NEVER = "@never"


class ToolkitContextGenerator(ContextGenerator):
    """``gen-jsonld-context`` with ``id``/``type`` aliases, no ``internal`` slots, native JSON scalars,
    ``uri`` values as IRIs and enum values as their meaning IRIs (PD-10)."""

    def visit_slot(self, aliased_slot_name: str, slot: SlotDefinition) -> None:
        if annotation(slot, "internal") == TRUE:
            return
        super().visit_slot(aliased_slot_name, slot)
        definition = self.context_body.get(underscore(aliased_slot_name))
        if not isinstance(definition, dict):
            return
        if definition.get("@type") in NATIVE_JSON_DATATYPES:
            del definition["@type"]
        if slot.range in self.schema.enums:
            self._map_enum_to_meanings(definition, self.schema.enums[slot.range])

    def _map_enum_to_meanings(self, definition: dict, enum: EnumDefinition) -> None:
        """Replace the stock SKOS terms by one term per value, its meaning IRI; the shapes list those IRIs."""
        definition.pop("@context", None)
        definition.pop("@type", None)
        meanings = {text: value.meaning for text, value in enum.permissible_values.items()}
        if not any(meanings.values()):
            return  # no meanings: the shapes list the plain values
        if not all(meanings.values()):
            raise SchemaGenerationError(f"enum {enum.name}: give every value a meaning, or none")
        definition["@type"] = "@vocab"
        definition["@context"] = {
            str(text): str(self.namespaces.uri_for(str(meaning)))
            for text, meaning in meanings.items()
        }

    def end_schema(self, *args, **kwargs) -> str:
        self.context_body["@version"] = JSON_LD_VERSION
        self.context_body["type"] = "@type"
        return str(super().end_schema(*args, **kwargs))


def render_context(schema_path: Path) -> str:
    """The context of the schema at ``schema_path`` with its imports merged, as JSON text."""
    # shortcut: the stock generator reads imports without the metamodel import map (PD-22), so it is
    # given the merged schema; upgrade when gen-jsonld-context takes a SchemaView.
    view = load_schema(schema_path)
    view.merge_imports()
    generator = ToolkitContextGenerator(
        view.schema, fix_multivalue_containers=True, metadata=False, xsd_anyuri_as_iri=True
    )
    return str(generator.serialize())


@dataclass
class Frame:
    """A JSON-LD frame: the type it selects and, per owned slot, the frame of the parts nested in it."""

    type_terms: list[str]
    references: list[str] = field(default_factory=list)
    parts: dict[str, "Frame"] = field(default_factory=dict)

    def to_json(self) -> dict:
        body: dict = {"@embed": ALWAYS, "@omitDefault": True}
        if self.type_terms:
            body["@type"] = self.type_terms[0] if len(self.type_terms) == 1 else self.type_terms
        body.update({slot: {"@embed": NEVER, "@omitDefault": True} for slot in self.references})
        body.update({slot: part.to_json() for slot, part in self.parts.items()})
        return body


def _term(view: SchemaView, name: str) -> list[str]:
    """The context terms of a class and its subclasses."""
    return [camelcase(c) for c in view.class_descendants(name)]


def build_frame(view: SchemaView, cls: str, seen: tuple[str, ...] = ()) -> Frame:
    """The frame of ``cls``: its owned parts nested, recursively; its references left as IRIs."""
    frame = Frame(_term(view, cls))
    for slot in view.class_induced_slots(cls):
        if annotation(slot, "internal") == TRUE or slot.range not in view.all_classes():
            continue
        if annotation(slot, "owned") != TRUE:
            frame.references.append(slot.name)
        elif slot.range in seen or slot.range == cls:  # a cycle of ownership: stop nesting
            frame.parts[slot.name] = Frame(_term(view, slot.range))
        else:
            frame.parts[slot.name] = build_frame(view, slot.range, (*seen, cls))
    return frame


def render_frame(view: SchemaView, cls: ClassDefinition) -> str:
    body = {"@context": CONTEXT_FILE, "@omitGraph": True, **build_frame(view, cls.name).to_json()}
    return json.dumps(body, indent=2, ensure_ascii=False) + "\n"


def context_files(view: SchemaView, schema_path: Path) -> list[GeneratedFile]:
    """``context.jsonld`` and ``<Class>.frame.jsonld`` for every aggregate type."""
    return [
        GeneratedFile(CONTEXT_FILE, render_context(schema_path)),
        *(
            GeneratedFile(f"{cls.name}{FRAME_SUFFIX}", render_frame(view, cls))
            for cls in root_classes(view, schema_path.parent)
        ),
    ]


def write_context(run: Run) -> None:
    """Write the context and the frames into the Python output folder."""
    with schema_faults():
        files = context_files(run.view, run.schema_path)
    stage(run, run.python_dir, files)


CONTEXT_STEP = Step("context", write_context, writes=True)
