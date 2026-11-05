"""The boundary check (task 1.7, PD-23): what each aggregate owns, what it refers to, who imports whom."""

from collections.abc import Iterator
from pathlib import Path

from linkml_runtime.linkml_model.meta import ClassDefinition, SchemaDefinition
from linkml_runtime.utils.schemaview import SchemaView

from rdf_persistence.domain.generated.rp_core import ModuleKind, RpAnnotation
from rdf_persistence.generation.generated.rp_generation import BoundaryRule, CheckProblem
from rdf_persistence.generation.problems import rule_problem
from rdf_persistence.services.schema_structure import (
    AGGREGATE_ROOT,
    aggregate_roots,
    annotation,
    declared_slots,
    is_owned,
    is_tenant_root,
    is_toolkit_schema,
    own_classes,
    own_schemas,
    owned_classes,
)

# Classes reached by IRI, never owned (PD-23).
REFERENCE_CLASSES = ("Principal", "Activity")
FORBIDDEN_FOR_DOMAIN = (ModuleKind.TECHNICAL.value, ModuleKind.ACCESS.value)


def _ownership_problems(view: SchemaView, classes: list[ClassDefinition]) -> Iterator[CheckProblem]:
    roots = {root.name for root in aggregate_roots(view, classes)}
    owned = owned_classes(view, classes)
    for cls in classes:
        if cls.mixin or cls.abstract or cls.name in roots | owned or is_tenant_root(cls):
            continue
        yield rule_problem(
            BoundaryRule.OWNERSHIP, cls.name, "is neither an aggregate root nor owned by any root"
        )


def _may_be_referred_to(view: SchemaView, range_: str) -> bool:
    ancestors = view.class_ancestors(range_)
    return AGGREGATE_ROOT in ancestors or any(name in ancestors for name in REFERENCE_CLASSES)


def _reference_problems(view: SchemaView, classes: list[ClassDefinition]) -> Iterator[CheckProblem]:
    for cls in classes:
        induced = {slot.name: slot for slot in view.class_induced_slots(cls.name)}
        for name in sorted(declared_slots(cls) & induced.keys()):
            slot = induced[name]
            is_class_range = slot.range in view.all_classes()
            if is_class_range and not is_owned(slot) and not _may_be_referred_to(view, slot.range):
                yield rule_problem(
                    BoundaryRule.REFERENCE,
                    name,
                    f"of {cls.name} points to {slot.range}, which is neither a root nor a reference class",
                )


def module_name(entry: str) -> str:
    """The module an ``imports`` entry names: its last segment, without a path or a prefix."""
    return entry.split("/")[-1].split(":")[-1]


def _imported(view: SchemaView, schema: SchemaDefinition) -> Iterator[SchemaDefinition]:
    by_name = {other.name: other for other in view.schema_map.values()}
    for imported in schema.imports:
        found = by_name.get(module_name(imported))
        if found is not None:
            yield found


def _module_problems(view: SchemaView, schemas: list[SchemaDefinition]) -> Iterator[CheckProblem]:
    for schema in schemas:
        if annotation(schema, RpAnnotation.MODULE_KIND) != ModuleKind.DOMAIN.value:
            continue
        for imported in _imported(view, schema):
            kind = annotation(imported, RpAnnotation.MODULE_KIND)
            if kind in FORBIDDEN_FOR_DOMAIN:
                yield rule_problem(
                    BoundaryRule.MODULE_KIND,
                    schema.name,
                    f"is a domain module and imports {imported.name}, a {kind} module",
                )


def boundary_problems(view: SchemaView, folder: Path) -> list[CheckProblem]:
    """Every problem of the schemas kept in ``folder``, in a stable order.

    The toolkit's own schemas get the import rule but not the class rules (PD-23).
    """
    schemas = own_schemas(view, folder)
    classes = [] if is_toolkit_schema(folder) else own_classes(schemas)
    return [
        *_ownership_problems(view, classes),
        *_reference_problems(view, classes),
        *_module_problems(view, schemas),
    ]
