"""Step 5b (PD-24): the OpenAPI component schemas, from ``gen-json-schema`` and trimmed to what the API shows.

Nothing is written by hand: LinkML's JSON Schema generator describes every class of the schema. This
module trims its output: it drops the slots the API never shows (the bookkeeping the session writes,
the ``internal`` slots), marks the identifier read-only since the service assigns it, and points the
references into an OpenAPI document's ``components/schemas``. The result is one file next to the
context; the service reads it when it builds its OpenAPI document, so a running service needs no
generator. A standalone JSON Schema file is not a v1 artefact: this one is a fragment of the OpenAPI
document.
"""

import json
from pathlib import Path
from typing import Any

from linkml.generators.jsonschemagen import JsonSchemaGenerator
from linkml_runtime.linkml_model.meta import SlotDefinition
from linkml_runtime.utils.schemaview import SchemaView
from rdflib import XSD, URIRef

from rdf_persistence.core.services.artifacts import (
    COMPONENT_REFERENCES,
    COMPONENTS_FILE,
    DEFINITIONS,
    REF,
    SCHEMAS,
)
from rdf_persistence.schema.services.schema import SERVED_SCHEMAS, load_schema, metamodel_importmap
from rdf_persistence.schema.services.schema_structure import (
    apply_defaults,
    is_bookkeeping,
    is_internal,
    json_name,
)
from rdf_persistence_generation.config import toolkit_roots
from rdf_persistence_generation.exceptions import SchemaGenerationError
from rdf_persistence_generation.generated.rp_generation import GeneratedFile

# One JSON Schema definition: JSON data of a library, not a model of ours.
JsonSchema = dict[str, Any]


def _generated(schema_path: Path) -> dict[str, JsonSchema]:
    generator = JsonSchemaGenerator(
        str(schema_path), importmap=metamodel_importmap(), include_null=False
    )
    apply_defaults(
        generator.schemaview, schema_path.parent, roots=toolkit_roots()
    )  # PD-8: the same view as the Python
    definitions: dict[str, JsonSchema] = json.loads(generator.serialize())["$defs"]
    return definitions


def _hidden_properties(view: SchemaView, class_name: str) -> set[str]:
    """The JSON names of the slots of a class that the API never shows."""
    return {
        json_name(slot)
        for slot in view.class_induced_slots(class_name)
        if is_bookkeeping(slot) or is_internal(slot)
    }


def _identifier_properties(view: SchemaView, class_name: str) -> set[str]:
    """The JSON names of the identifier slots of a class."""
    return {json_name(slot) for slot in view.class_induced_slots(class_name) if slot.identifier}


PROPERTIES_KEY = "properties"  # the key of a JSON Schema definition that holds its slots
TYPE_PROPERTY = (
    "type"  # a plain JSON read carries it, and a write may name it (services.documents.TYPE_KEYS)
)
TYPE_SCHEMA: JsonSchema = {
    "type": "string",
    "description": "The class of the node: its name or IRI. Set by the service on a read; "
    "a write may name the class or one of its subclasses.",
}


STRING_SCHEMA: JsonSchema = {"type": "string"}
# The ranges a read gives as a JSON string holding the lexical form (DEC-8, PD-8); the stock generator says number.
STRING_RANGES = frozenset({XSD.decimal, XSD.float})
ITEMS_KEY = "items"
ARRAY_TYPE = "array"
KEPT_ON_REWRITE = ("title", "description")  # a bound such as ``minimum`` means nothing on a string


def _is_string_range(view: SchemaView, slot: SlotDefinition) -> bool:
    """Whether the slot's range is, or derives from, ``xsd:decimal`` or ``xsd:float``."""
    if slot.range not in view.all_types():
        return False
    return any(
        URIRef(view.expand_curie(view.get_type(ancestor).uri)) in STRING_RANGES
        for ancestor in view.type_ancestors(slot.range)
        if view.get_type(ancestor).uri
    )


def _as_string(body: JsonSchema) -> JsonSchema:
    """``body`` as a string schema: its item schema when it is a list, keeping its title and description."""
    if body.get("type") == ARRAY_TYPE:
        return {**body, ITEMS_KEY: STRING_SCHEMA}
    return {**{key: body[key] for key in KEPT_ON_REWRITE if key in body}, **STRING_SCHEMA}


def _string_properties(view: SchemaView, class_name: str) -> set[str]:
    """The JSON names of the slots of a class that a read gives as strings though the stock schema says number."""
    return {
        json_name(slot)
        for slot in view.class_induced_slots(class_name)
        if _is_string_range(view, slot)
    }


def _shown_properties(view: SchemaView, name: str, definition: JsonSchema) -> dict[str, JsonSchema]:
    """The properties the API shows: strings where a read gives text, the identifier read-only."""
    hidden = _hidden_properties(view, name)
    identifiers = _identifier_properties(view, name)
    strings = _string_properties(view, name)
    shown = {}
    for prop, body in definition["properties"].items():
        if prop in hidden:
            continue
        body = _as_string(body) if prop in strings else body
        shown[prop] = {**body, "readOnly": True} if prop in identifiers else body
    return shown


def _trimmed(view: SchemaView, name: str, definition: JsonSchema) -> JsonSchema:
    """The definition without the slots the API does not show, its identifier read-only."""
    if name not in view.all_classes() or PROPERTIES_KEY not in definition:
        return definition
    hidden = _hidden_properties(view, name)
    kept = _shown_properties(view, name, definition)
    required = [prop for prop in definition.get("required", []) if prop not in hidden]
    kept.setdefault(TYPE_PROPERTY, TYPE_SCHEMA)
    trimmed = {**definition, "properties": kept}
    if required:
        trimmed["required"] = required
    else:
        trimmed.pop("required", None)
    return trimmed


def _retargeted(node: Any) -> Any:
    """``node`` with its references pointing into the OpenAPI document's components."""
    if isinstance(node, dict):
        return {
            key: value.replace(DEFINITIONS, COMPONENT_REFERENCES)
            if key == REF and isinstance(value, str)
            else _retargeted(value)
            for key, value in node.items()
        }
    if isinstance(node, list):
        return [_retargeted(value) for value in node]
    return node


def _declared(schema_path: Path) -> set[str]:
    """The classes and enums the file at ``schema_path`` declares, not those it imports."""
    declared = load_schema(schema_path).schema
    return {*declared.classes, *declared.enums}


def _refuse_import_of_a_later_schema(schema_path: Path, later: list[Path]) -> None:
    """Refuse a served schema that imports one listed after it in ``SERVED_SCHEMAS``.

    Raises:
        SchemaGenerationError: ``schema_path`` imports a served schema in ``later``; it names both.
    """
    view = load_schema(schema_path)
    imported = {*view.all_classes(), *view.all_enums()} - _declared(schema_path)
    for served in later:
        if imported & _declared(served):
            raise SchemaGenerationError(
                f"{schema_path.name} imports {served.name}, which SERVED_SCHEMAS lists after it: "
                "list a schema before the ones that import it"
            )


def _left_out(schema_path: Path) -> set[str]:
    """The classes and enums that another served schema than ``schema_path`` publishes.

    The service merges the files of the served schemas and refuses a name in two of them (PD-10).
    A served schema leaves out what a served schema listed before it generates (its imports of
    another served schema, and of a metamodel module both import), except a class it declares
    itself: a class two served schemas declare stays in both files, so the merge refuses it. A
    schema that is not served leaves out everything the served schemas declare.

    Raises:
        SchemaGenerationError: The schema imports a served schema listed after it.
    """
    resolved = [served.resolve() for served in SERVED_SCHEMAS]
    if schema_path.resolve() not in resolved:
        return {name for served in SERVED_SCHEMAS for name in _declared(served)}
    position = resolved.index(schema_path.resolve())
    _refuse_import_of_a_later_schema(schema_path, list(SERVED_SCHEMAS[position + 1 :]))
    earlier = {name for served in SERVED_SCHEMAS[:position] for name in _generated(served)}
    return earlier - _declared(schema_path)


def render(schema_path: Path) -> list[GeneratedFile]:
    """``openapi-components.json``: the component schema of every class of the schema, by name.

    A class that another served schema publishes is left out (see ``_left_out``).
    """
    view = load_schema(schema_path)
    left_out = _left_out(schema_path)
    schemas = {
        name: _retargeted(_trimmed(view, name, definition))
        for name, definition in sorted(_generated(schema_path).items())
        if name not in left_out
    }
    text = json.dumps({SCHEMAS: schemas}, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    return [GeneratedFile(name=COMPONENTS_FILE, text=text)]
