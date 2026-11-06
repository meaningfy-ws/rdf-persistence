"""Step 5: the JSON-LD context and one frame per aggregate type (PD-12, PD-25).

``gen-jsonld-context`` has no ``@type`` alias, keeps ``internal`` slots, tags integers and booleans
with a datatype (so a native JSON number comes back as a string after framing), reads a ``uri`` as a
typed literal where the shapes expect an IRI, maps an enum to SKOS notation terms where the shapes list
the meaning IRIs, and has no frames per aggregate. This module closes those gaps in a subclass and a
frame builder; the stock output is not edited.
"""

import json
from pathlib import Path

from linkml.generators.jsonldcontextgen import ContextGenerator
from linkml_runtime.linkml_model.meta import ClassDefinition, EnumDefinition, SlotDefinition
from linkml_runtime.utils.formatutils import camelcase, underscore
from linkml_runtime.utils.schemaview import SchemaView

from rdf_persistence.generation.exceptions import SchemaGenerationError
from rdf_persistence.generation.generated.rp_generation import Frame, FramePart, GeneratedFile
from rdf_persistence.services.artifacts import CONTEXT_FILE, FRAME_SUFFIX
from rdf_persistence.services.schema import load_schema
from rdf_persistence.services.schema_structure import is_internal, is_owned, root_classes

# JSON carries these natively: a datatype tag would turn them into strings when framed back.
NATIVE_JSON_DATATYPES = ("xsd:integer", "xsd:boolean")
JSON_LD_VERSION = 1.1  # property-scoped contexts are a JSON-LD 1.1 feature
ALWAYS = "@always"
NEVER = "@never"


class ToolkitContextGenerator(ContextGenerator):
    """``gen-jsonld-context`` with ``id``/``type`` aliases, no ``internal`` slots, native JSON scalars,
    ``uri`` values as IRIs and enum values as their meaning IRIs (PD-10)."""

    def visit_slot(self, aliased_slot_name: str, slot: SlotDefinition) -> None:
        if is_internal(slot):
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


def frame_json(frame: Frame) -> dict:
    """The JSON-LD of a frame: its types and references, and its parts nested."""
    body: dict = {"@embed": ALWAYS, "@omitDefault": True}
    if frame.type_terms:
        body["@type"] = frame.type_terms[0] if len(frame.type_terms) == 1 else frame.type_terms
    body.update({slot: {"@embed": NEVER, "@omitDefault": True} for slot in frame.references})
    body.update({part.name: frame_json(part.frame) for part in frame.parts})
    return body


def _term(view: SchemaView, name: str) -> list[str]:
    """The context terms of a class and its subclasses."""
    return [camelcase(c) for c in view.class_descendants(name)]


def build_frame(view: SchemaView, cls: str, seen: tuple[str, ...] = ()) -> Frame:
    """The frame of ``cls``: its owned parts nested, recursively; its references left as IRIs."""
    frame = Frame(type_terms=_term(view, cls), references=[], parts=[])
    for slot in view.class_induced_slots(cls):
        if is_internal(slot) or slot.range not in view.all_classes():
            continue
        if not is_owned(slot):
            frame.references.append(slot.name)
        elif slot.range in seen or slot.range == cls:  # a cycle of ownership: stop nesting
            nested = Frame(type_terms=_term(view, slot.range), references=[], parts=[])
            frame.parts.append(FramePart(name=slot.name, frame=nested))
        else:
            nested = build_frame(view, slot.range, (*seen, cls))
            frame.parts.append(FramePart(name=slot.name, frame=nested))
    return frame


def render_frame(view: SchemaView, cls: ClassDefinition) -> str:
    body = {"@context": CONTEXT_FILE, "@omitGraph": True, **frame_json(build_frame(view, cls.name))}
    return json.dumps(body, indent=2, ensure_ascii=False) + "\n"


def render(schema_path: Path) -> list[GeneratedFile]:
    """``context.jsonld`` and ``<Class>.frame.jsonld`` for every aggregate type."""
    view = load_schema(schema_path)
    return [
        GeneratedFile(name=CONTEXT_FILE, text=render_context(schema_path)),
        *(
            GeneratedFile(name=f"{cls.name}{FRAME_SUFFIX}", text=render_frame(view, cls))
            for cls in root_classes(view, schema_path.parent)
        ),
    ]
