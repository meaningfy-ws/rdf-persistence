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
from linkml_runtime.utils.schemaview import SchemaView

from rdf_persistence.generation.generated.rp_generation import GeneratedFile
from rdf_persistence.services.artifacts import (
    COMPONENT_REFERENCES,
    COMPONENTS_FILE,
    DEFINITIONS,
    REF,
    SCHEMAS,
)
from rdf_persistence.services.schema import load_schema, metamodel_importmap
from rdf_persistence.services.schema_structure import (
    apply_defaults,
    is_bookkeeping,
    is_internal,
    json_name,
)

# One JSON Schema definition: JSON data of a library, not a model of ours.
JsonSchema = dict[str, Any]


def _generated(schema_path: Path) -> dict[str, JsonSchema]:
    generator = JsonSchemaGenerator(
        str(schema_path), importmap=metamodel_importmap(), include_null=False
    )
    apply_defaults(generator.schemaview, schema_path.parent)  # PD-8: the same view as the Python
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


def _trimmed(view: SchemaView, name: str, definition: JsonSchema) -> JsonSchema:
    """The definition without the slots the API does not show, its identifier read-only."""
    if name not in view.all_classes() or "properties" not in definition:
        return definition
    hidden = _hidden_properties(view, name)
    identifiers = _identifier_properties(view, name)
    kept = {
        prop: {**body, "readOnly": True} if prop in identifiers else body
        for prop, body in definition["properties"].items()
        if prop not in hidden
    }
    required = [prop for prop in definition.get("required", []) if prop not in hidden]
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


def render(schema_path: Path) -> list[GeneratedFile]:
    """``openapi-components.json``: the component schema of every class of the schema, by name."""
    view = load_schema(schema_path)
    schemas = {
        name: _retargeted(_trimmed(view, name, definition))
        for name, definition in sorted(_generated(schema_path).items())
    }
    text = json.dumps({SCHEMAS: schemas}, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    return [GeneratedFile(name=COMPONENTS_FILE, text=text)]
