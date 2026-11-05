"""The hard check (task 1.6): IRIs, titles, descriptions, meanings, paths and mixins of the schema."""

from collections.abc import Iterator
from pathlib import Path

from linkml_runtime.linkml_model.meta import ClassDefinition, PermissibleValue, SchemaDefinition
from linkml_runtime.utils.schemaview import SchemaView

from rdf_persistence.generation.checks.scope import (
    aggregate_roots,
    annotation,
    inherits_from_metamodel,
    is_tenant_root,
    is_toolkit_schema,
    own_classes,
    own_schemas,
    owned_classes,
)
from rdf_persistence.generation.generated.rp_generation import HardRule

DESCRIBED = "Described"
BOOLEAN = ("true", "false")
# Every annotation the toolkit reads, and the values it accepts (rp_core's comments list them).
ALLOWED_ANNOTATIONS = {
    "database": ("tenant", "system"),
    "graph": ("meta",),
    "module_kind": ("domain", "technical", "access"),
    "owned": BOOLEAN,
    "internal": BOOLEAN,
    "rp_unlabelled": BOOLEAN,
}


def _problem(rule: HardRule, element: str, message: str) -> str:
    return f"[{rule.value}] {element}: {message}"


def _has_default_prefix(schema: SchemaDefinition) -> bool:
    return bool(schema.default_prefix) and schema.default_prefix in (schema.prefixes or {})


def _element_problems(
    element: object, name: str, explicit_iri: str | None, schema: SchemaDefinition
) -> Iterator[str]:
    if not explicit_iri and not _has_default_prefix(schema):
        yield _problem(
            HardRule.IRI, name, "no IRI: no explicit URI and no default_prefix in prefixes"
        )
    for field in (HardRule.TITLE, HardRule.DESCRIPTION):
        if not getattr(element, field.value, None):
            yield _problem(field, name, f"no {field.value}")


def _schema_problems(schema: SchemaDefinition) -> Iterator[str]:
    for cls in schema.classes.values():
        yield from _element_problems(cls, cls.name, cls.class_uri, schema)
    for slot in schema.slots.values():
        yield from _element_problems(slot, slot.name, slot.slot_uri, schema)
    for enum in schema.enums.values():
        yield from _element_problems(enum, enum.name, enum.enum_uri, schema)
        for value in enum.permissible_values.values():
            yield from _value_problems(enum.name, value)


def _value_problems(enum: str, value: PermissibleValue) -> Iterator[str]:
    name = value.text
    for field in (HardRule.TITLE, HardRule.DESCRIPTION, HardRule.MEANING):
        if not getattr(value, field.value, None):
            yield _problem(field, name, f"permissible value of {enum} has no {field.value}")


def _annotation_problems(schema: SchemaDefinition) -> Iterator[str]:
    elements = [schema, *schema.classes.values(), *schema.slots.values(), *schema.enums.values()]
    for element in elements:
        for tag, allowed in ALLOWED_ANNOTATIONS.items():
            value = annotation(element, tag)
            if value is not None and value not in allowed:
                yield _problem(
                    HardRule.ANNOTATION, element.name, f"{tag}: {value!r} is not one of {allowed}"
                )


def _inherited_path(view: SchemaView, cls: ClassDefinition) -> bool:
    ancestry = view.class_ancestors(cls.name, mixins=False)
    return any(annotation(view.get_class(name), "rp_path") for name in ancestry)


def _path_problems(view: SchemaView, roots: list[ClassDefinition]) -> Iterator[str]:
    for root in roots:
        if not is_tenant_root(root) and not _inherited_path(view, root):
            yield _problem(
                HardRule.RP_PATH, root.name, "an aggregate root needs the rp_path annotation"
            )


def _described_problems(
    view: SchemaView, classes: list[ClassDefinition], roots: list[ClassDefinition]
) -> Iterator[str]:
    own = {cls.name for cls in classes}
    owned = owned_classes(view, classes)
    for cls in roots + [c for c in classes if c.name in owned and c not in roots]:
        if inherits_from_metamodel(view, cls, own):
            continue
        if DESCRIBED not in view.class_ancestors(cls.name):
            yield _problem(HardRule.DESCRIBED, cls.name, "a root or owned class includes Described")


def _class_problems(view: SchemaView, classes: list[ClassDefinition]) -> Iterator[str]:
    roots = aggregate_roots(view, classes)
    yield from _path_problems(view, roots)
    yield from _described_problems(view, classes, roots)


def hard_problems(view: SchemaView, folder: Path) -> list[str]:
    """Every problem of the schemas kept in ``folder``, one line each, in a stable order.

    The toolkit's own schemas get the element rules but not the root and owned-class rules (PD-23).
    """
    schemas = own_schemas(view, folder)
    classes = (
        [] if is_toolkit_schema(folder) else own_classes(schemas)
    )  # PD-23: its roots are its own
    return [
        *(p for schema in schemas for p in _schema_problems(schema)),
        *(p for schema in schemas for p in _annotation_problems(schema)),
        *_class_problems(view, classes),
    ]
