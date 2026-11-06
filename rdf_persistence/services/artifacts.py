"""The names of the artefacts a run writes next to the classes, and of the keys inside them, in one place for the steps, the service and the testkit."""

SHAPES_FILE = "shapes.ttl"
CONTEXT_FILE = "context.jsonld"
FRAME_SUFFIX = ".frame.jsonld"
COMPONENTS_FILE = "openapi-components.json"

# The JSON-LD keywords the toolkit reads and writes.
CONTEXT_KEY = "@context"
TYPE_KEY = "@type"
ID_KEY = "@id"

# The components file: one JSON Schema fragment per class under ``SCHEMAS``, whose references point
# into an OpenAPI document's ``components/schemas`` (``COMPONENT_REFERENCES``) rather than the
# ``$defs`` of the standalone schema ``gen-json-schema`` wrote (``DEFINITIONS``).
SCHEMAS = "schemas"
REF = "$ref"
DEFINITIONS = "#/$defs/"
COMPONENT_REFERENCES = "#/components/schemas/"
