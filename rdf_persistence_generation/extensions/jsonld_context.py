"""Step 5: the JSON-LD context and one frame per aggregate type (PD-12, PD-25).

``gen-jsonld-context`` has no ``@type`` alias, keeps ``internal`` slots, tags integers and booleans
with a datatype (so a native JSON number comes back as a string after framing), reads a ``uri`` as a
typed literal where the shapes expect an IRI, maps an enum to SKOS notation terms where the shapes list
the meaning IRIs, and has no frames per aggregate. This module closes those gaps in a subclass and a
frame builder; the stock output is not edited.
"""

import json
from functools import cached_property
from pathlib import Path

from linkml.generators.jsonldcontextgen import ContextGenerator
from linkml_runtime.linkml_model.meta import ClassDefinition, EnumDefinition, SlotDefinition
from linkml_runtime.utils.formatutils import camelcase, underscore
from linkml_runtime.utils.schemaview import SchemaView

from rdf_persistence.core.services.artifacts import (
    CONTEXT_FILE,
    CONTEXT_KEY,
    FRAME_SUFFIX,
    TYPE_KEY,
)
from rdf_persistence.schema.services.schema import load_schema
from rdf_persistence.schema.services.schema_structure import (
    ACTIVITY,
    FIELD_NAME_SLOT,
    annotation_text,
    is_internal,
    is_owned,
    root_classes,
)
from rdf_persistence_generation.exceptions import SchemaGenerationError
from rdf_persistence_generation.generated.rp_generation import (
    Frame,
    FramePart,
    GeneratedFile,
    GenerationAnnotation,
)

# JSON carries these natively: a datatype tag would turn them into strings when framed back.
NATIVE_JSON_DATATYPES = ("xsd:integer", "xsd:boolean")
JSON_LD_VERSION = 1.1  # property-scoped contexts are a JSON-LD 1.1 feature
CONTAINER_KEY = "@container"
SET_CONTAINER = "@set"
ALWAYS = "@always"
NEVER = "@never"


def _term_of(aliased_slot_name: str, slot: SlotDefinition) -> str:
    """The context term of a slot: its alias, except a slot annotated ``field_name: slot``, which keeps its name (D-55).

    The alias of such a slot is the wire name of a service or settings key and may shadow a prefix
    (``schema``) or another slot's term (``kind``).
    """
    opted_in = annotation_text(slot, GenerationAnnotation.FIELD_NAME) == FIELD_NAME_SLOT
    return str(slot.name) if opted_in else aliased_slot_name


class ToolkitContextGenerator(ContextGenerator):
    """``gen-jsonld-context`` with ``id``/``type`` aliases, no ``internal`` slots, native JSON scalars,
    ``uri`` values as IRIs and enum values as their meaning IRIs (PD-10)."""

    def visit_slot(self, aliased_slot_name: str, slot: SlotDefinition) -> None:
        if is_internal(slot):
            return
        term = _term_of(aliased_slot_name, slot)
        super().visit_slot(term, slot)
        definition = self.context_body.get(str(underscore(term)))
        if not isinstance(definition, dict):
            return
        if definition.get(TYPE_KEY) in NATIVE_JSON_DATATYPES:
            del definition[TYPE_KEY]
        if slot.range in self.schema.enums:
            self._map_enum_to_meanings(definition, self.schema.enums[slot.range])

    def _map_enum_to_meanings(self, definition: dict, enum: EnumDefinition) -> None:
        """Replace the stock SKOS terms by one term per value, its meaning IRI; the shapes list those IRIs."""
        definition.pop(CONTEXT_KEY, None)
        definition.pop(TYPE_KEY, None)
        meanings = {text: value.meaning for text, value in enum.permissible_values.items()}
        if not any(meanings.values()):
            return  # no meanings: the shapes list the plain values
        if not all(meanings.values()):
            raise SchemaGenerationError(f"enum {enum.name}: give every value a meaning, or none")
        definition[TYPE_KEY] = "@vocab"
        definition[CONTEXT_KEY] = {
            str(text): str(self.namespaces.uri_for(str(meaning)))
            for text, meaning in meanings.items()
        }

    def end_schema(self, *args, **kwargs) -> str:
        self.context_body["@version"] = JSON_LD_VERSION
        self.context_body["type"] = TYPE_KEY
        self._scope_multivalued_usages()
        return str(super().end_schema(*args, **kwargs))

    def _scope_multivalued_usages(self) -> None:
        """A class whose ``slot_usage`` makes a single-valued slot multivalued gets a type-scoped
        term with ``@container: @set`` for it, so its framed values stay a list (#302); the slot's
        global term, and so every other class, keeps one value."""
        for cls in self._view.all_classes().values():
            if cls.abstract or cls.mixin:
                continue  # no node of its own, so no @type to scope by
            terms = {
                self._term_name(name): multivalued
                for name, multivalued in self._changed_multiplicity(cls)
            }
            terms = {
                term: multivalued
                for term, multivalued in terms.items()
                if term in self.context_body
            }
            if not terms:
                continue
            class_def = self.slot_class_maps.get(self._class_key(cls))  # the stock class terms
            if class_def is None:
                raise SchemaGenerationError(
                    f"class {cls.name}: no context term to scope {sorted(terms)} in (set a class_uri)"
                )
            scoped = class_def.setdefault(CONTEXT_KEY, {})  # the stock may have set range terms
            for term, multivalued in terms.items():
                scoped[term] = self._scoped_entry(scoped.get(term), term, multivalued)

    def _changed_multiplicity(self, cls: ClassDefinition) -> list[tuple[str, bool]]:
        """The slots the class (or an ancestor) uses with another multiplicity than declared: name, multivalued."""
        view = self._view
        # the generator has materialised each slot_usage as a slot `<Class>_<slot>`; name the original
        names = {str(s.usage_slot_name or s.name) for s in view.class_induced_slots(cls.name)}
        used = {name: bool(view.induced_slot(name, cls.name).multivalued) for name in sorted(names)}
        declared = {name: view.get_slot(name, attributes=False) for name in used}
        return [
            (name, multivalued)
            for name, multivalued in used.items()
            if declared[name] is not None and multivalued != bool(declared[name].multivalued)
        ]

    def _class_key(self, cls: ClassDefinition) -> str:
        """The key the stock ``visit_class`` files the class term under."""
        return str(self._curie(cls)) if self.use_curies else str(camelcase(cls.name))

    def _scoped_entry(self, existing: object, term: str, multivalued: bool) -> dict:
        """The scoped term: the stock's scoped one, else a copy of the global; a set only if multivalued."""
        base = existing if existing is not None else self.context_body[term]
        entry = dict(base) if isinstance(base, dict) else {"@id": base}
        entry.pop(CONTAINER_KEY, None)
        if multivalued:
            entry[CONTAINER_KEY] = SET_CONTAINER
        return entry

    def _term_name(self, slot_name: str) -> str:
        """The context term ``visit_slot`` wrote for the slot named ``slot_name``."""
        slot = self._view.get_slot(slot_name)
        return str(underscore(_term_of(str(slot.alias or slot.name), slot)))

    @cached_property
    def _view(self) -> SchemaView:
        """A view of the merged schema the generator was given (it is built from a definition, not a view)."""
        return SchemaView(self.schema)


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
        body[TYPE_KEY] = frame.type_terms[0] if len(frame.type_terms) == 1 else frame.type_terms
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
    body = {
        CONTEXT_KEY: CONTEXT_FILE,
        "@omitGraph": True,
        **frame_json(build_frame(view, cls.name)),
    }
    return json.dumps(body, indent=2, ensure_ascii=False) + "\n"


def framed_classes(view: SchemaView, folder: Path) -> list[ClassDefinition]:
    """The classes that get a frame: the roots of ``folder``, then ``Activity`` and every descendant in the closure.

    An activity is read from the store and sent as a message without being a root, and the
    toolkit's own activity classes belong to every target's closure (message-bus PD-4).
    """
    classes = root_classes(view, folder)
    named = {cls.name for cls in classes}
    if ACTIVITY in view.all_classes():
        classes += [
            view.get_class(name) for name in view.class_descendants(ACTIVITY) if name not in named
        ]
    return classes


def render(schema_path: Path) -> list[GeneratedFile]:
    """``context.jsonld`` and ``<Class>.frame.jsonld`` for every aggregate type and every activity."""
    view = load_schema(schema_path)
    return [
        GeneratedFile(name=CONTEXT_FILE, text=render_context(schema_path)),
        *(
            GeneratedFile(name=f"{cls.name}{FRAME_SUFFIX}", text=render_frame(view, cls))
            for cls in framed_classes(view, schema_path.parent)
        ),
    ]
