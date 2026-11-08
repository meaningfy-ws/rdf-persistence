"""The hard check (task 1.6): IRIs, titles, descriptions, meanings, paths, IRI types and mixins of the schema."""

import re
from collections.abc import Iterator
from functools import cache
from pathlib import Path

from linkml_runtime.linkml_model.meta import (
    ClassDefinition,
    Element,
    PermissibleValue,
    SchemaDefinition,
)
from linkml_runtime.utils.schemaview import SchemaView

from rdf_persistence.domain.generated.rp_core import (
    DatabaseKind,
    GraphKind,
    ModuleKind,
    RpAnnotation,
)
from rdf_persistence.generation.generated.rp_generation import CheckProblem, HardRule
from rdf_persistence.generation.problems import rule_problem
from rdf_persistence.services.schema import PACKAGE_DIR, load_schema
from rdf_persistence.services.schema_structure import (
    aggregate_roots,
    annotation,
    annotation_text,
    inherits_from_metamodel,
    is_tenant_root,
    is_toolkit_schema,
    own_classes,
    own_schemas,
    owned_classes,
)

# The metaslot each element rule requires: a rule id is not an attribute name.
ELEMENT_METASLOTS = ((HardRule.TITLE, "title"), (HardRule.DESCRIPTION, "description"))
VALUE_METASLOTS = (*ELEMENT_METASLOTS, (HardRule.MEANING, "meaning"))
DESCRIBED = "Described"
CORE_MODEL = PACKAGE_DIR / "model" / "rp_core.yaml"
URL_SEGMENT = "url_segment"  # the slot of rp_core whose pattern every route segment follows
BOOLEAN = ("true", "false")
# The segments the IRI layout owns; no class may take one as its type (PD-8).
RESERVED_IRI_TYPES = ("content", "graph", "parts", "access", "meta", "registry")
PATTERNED_ANNOTATIONS = (RpAnnotation.RP_PATH, RpAnnotation.RP_IRI_TYPE)
KEBAB_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
# Every annotation the toolkit reads, and the values it accepts (the enums of rp_core). rp_path takes
# a pattern instead, checked on its own.
ALLOWED_ANNOTATIONS = {
    RpAnnotation.DATABASE: tuple(kind.value for kind in DatabaseKind),
    RpAnnotation.GRAPH: tuple(kind.value for kind in GraphKind),
    RpAnnotation.MODULE_KIND: tuple(kind.value for kind in ModuleKind),
    RpAnnotation.OWNED: BOOLEAN,
    RpAnnotation.INTERNAL: BOOLEAN,
    RpAnnotation.RP_UNLABELLED: BOOLEAN,
    RpAnnotation.BOOKKEEPING: BOOLEAN,
}


def _has_default_prefix(schema: SchemaDefinition) -> bool:
    return bool(schema.default_prefix) and schema.default_prefix in (schema.prefixes or {})


def _element_problems(
    element: object, name: str, explicit_iri: str | None, schema: SchemaDefinition
) -> Iterator[CheckProblem]:
    if not explicit_iri and not _has_default_prefix(schema):
        yield rule_problem(
            HardRule.IRI, name, "no IRI: no explicit URI and no default_prefix in prefixes"
        )
    for rule, metaslot in ELEMENT_METASLOTS:
        if not getattr(element, metaslot, None):
            yield rule_problem(rule, name, f"no {metaslot}")


def _unique_key_problems(cls: ClassDefinition) -> Iterator[CheckProblem]:
    """A key name ends up in the names of generated validators, so it must be an identifier."""
    for key in cls.unique_keys.values():
        name = str(key.unique_key_name)
        if not (name.isidentifier() and name.isascii()):
            yield rule_problem(
                HardRule.UNIQUE_KEY, cls.name, f"unique key {name!r} is not an identifier"
            )


def _schema_problems(schema: SchemaDefinition) -> Iterator[CheckProblem]:
    for cls in schema.classes.values():
        yield from _element_problems(cls, cls.name, cls.class_uri, schema)
        for attribute in cls.attributes.values():
            yield from _element_problems(attribute, attribute.name, attribute.slot_uri, schema)
        yield from _unique_key_problems(cls)
    for slot in schema.slots.values():
        yield from _element_problems(slot, slot.name, slot.slot_uri, schema)
    for enum in schema.enums.values():
        yield from _element_problems(enum, enum.name, enum.enum_uri, schema)
        for value in enum.permissible_values.values():
            yield from _value_problems(enum.name, value)


def _value_problems(enum: str, value: PermissibleValue) -> Iterator[CheckProblem]:
    name = value.text
    for rule, metaslot in VALUE_METASLOTS:
        if not getattr(value, metaslot, None):
            yield rule_problem(rule, name, f"permissible value of {enum} has no {metaslot}")


def _annotated_elements(schema: SchemaDefinition) -> Iterator[Element]:
    yield schema
    for cls in schema.classes.values():
        yield cls
        yield from cls.attributes.values()
    yield from schema.slots.values()
    yield from schema.enums.values()


@cache
def _path_pattern() -> str:
    """The pattern an ``rp_path`` value must match: the one of the metamodel's ``url_segment`` slot."""
    return str(load_schema(CORE_MODEL).get_slot(URL_SEGMENT).pattern)


def _annotation_problems(schema: SchemaDefinition, path_pattern: str) -> Iterator[CheckProblem]:
    for element in _annotated_elements(schema):
        name = str(element.name)
        for tag, allowed in ALLOWED_ANNOTATIONS.items():
            value = annotation(element, tag)
            if value is not None and value not in allowed:
                yield rule_problem(
                    HardRule.ANNOTATION, name, f"{tag.value}: {value!r} is not one of {allowed}"
                )
        for tag in PATTERNED_ANNOTATIONS:
            text = annotation_text(element, tag)
            if text is not None and not re.fullmatch(path_pattern, text):
                yield rule_problem(
                    HardRule.ANNOTATION,
                    name,
                    f"{tag.value}: {text!r} does not match {path_pattern}",
                )


def _inherited_path(view: SchemaView, cls: ClassDefinition) -> bool:
    ancestry = view.class_ancestors(cls.name, mixins=False)
    return any(annotation(view.get_class(name), RpAnnotation.RP_PATH) for name in ancestry)


def _path_problems(view: SchemaView, roots: list[ClassDefinition]) -> Iterator[CheckProblem]:
    for root in roots:
        if not is_tenant_root(root) and not _inherited_path(view, root):
            yield rule_problem(
                HardRule.RP_PATH, root.name, "an aggregate root needs the rp_path annotation"
            )


def _described_problems(
    view: SchemaView, classes: list[ClassDefinition], roots: list[ClassDefinition]
) -> Iterator[CheckProblem]:
    own = {cls.name for cls in classes}
    owned = owned_classes(view, classes)
    for cls in roots + [c for c in classes if c.name in owned and c not in roots]:
        if inherits_from_metamodel(view, cls, own):
            continue
        if DESCRIBED not in view.class_ancestors(cls.name):
            yield rule_problem(
                HardRule.DESCRIBED, cls.name, "a root or owned class includes Described"
            )


def iri_type_of(cls: ClassDefinition) -> str:
    """The ``{type}`` of the IRIs of ``cls``: its ``rp_iri_type``, else its name in kebab case."""
    return (
        annotation_text(cls, RpAnnotation.RP_IRI_TYPE) or KEBAB_BOUNDARY.sub("-", cls.name).lower()
    )


def _iri_type_problems(
    view: SchemaView, classes: list[ClassDefinition], roots: list[ClassDefinition]
) -> Iterator[CheckProblem]:
    """PD-8: roots and owned classes (the ones the toolkit mints IRIs for) have distinct, unreserved types."""
    owned = owned_classes(view, classes)
    minted = [
        cls
        for cls in classes
        if (cls in roots or cls.name in owned) and not cls.mixin and not cls.abstract
    ]
    by_type: dict[str, list[str]] = {}
    for cls in minted:
        by_type.setdefault(iri_type_of(cls), []).append(cls.name)
    for iri_type, names in by_type.items():
        if iri_type in RESERVED_IRI_TYPES:
            yield rule_problem(
                HardRule.IRI_TYPE, names[0], f"the type {iri_type!r} is reserved by the IRI layout"
            )
        if len(names) > 1:
            yield rule_problem(
                HardRule.IRI_TYPE, names[0], f"{', '.join(names)} share the type {iri_type!r}"
            )


def _class_problems(view: SchemaView, classes: list[ClassDefinition]) -> Iterator[CheckProblem]:
    roots = aggregate_roots(view, classes)
    yield from _path_problems(view, roots)
    yield from _described_problems(view, classes, roots)
    yield from _iri_type_problems(view, classes, roots)


def hard_problems(view: SchemaView, folder: Path) -> list[CheckProblem]:
    """Every problem of the schemas kept in ``folder``, in a stable order.

    The toolkit's own schemas get the element rules but not the root and owned-class rules (PD-23).
    """
    schemas = own_schemas(view, folder)
    classes = (
        [] if is_toolkit_schema(folder) else own_classes(schemas)
    )  # PD-23: its roots are its own
    return [
        *(p for schema in schemas for p in _schema_problems(schema)),
        *(p for schema in schemas for p in _annotation_problems(schema, _path_pattern())),
        *_class_problems(view, classes),
    ]
