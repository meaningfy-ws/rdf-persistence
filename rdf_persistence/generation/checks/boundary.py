"""The boundary check (task 1.7, PD-23): what each aggregate owns, what it refers to, who imports whom."""

from collections.abc import Iterator
from pathlib import Path

from linkml_runtime.linkml_model.meta import ClassDefinition, SchemaDefinition
from linkml_runtime.utils.schemaview import SchemaView

from rdf_persistence.domain.generated.rp_core import ModuleKind, RpAnnotation
from rdf_persistence.generation.generated.rp_generation import (
    BoundaryRule,
    CheckProblem,
    TargetKind,
)
from rdf_persistence.generation.problems import rule_problem
from rdf_persistence.services.schema_structure import (
    ACTIVITY,
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
REFERENCE_CLASSES = ("Principal", ACTIVITY)
FORBIDDEN_FOR_DOMAIN = (ModuleKind.TECHNICAL.value, ModuleKind.ACCESS.value)


def technical_classes(schemas: list[SchemaDefinition]) -> list[ClassDefinition]:
    """The classes of the modules annotated ``module_kind: technical``; a class is told apart by object, not by name."""
    return [
        cls
        for schema in schemas
        if annotation(schema, RpAnnotation.MODULE_KIND) == ModuleKind.TECHNICAL.value
        for cls in schema.classes.values()
    ]


def _is_activity(view: SchemaView, class_name: str) -> bool:
    return ACTIVITY in view.class_ancestors(class_name)


def _use_cases(view: SchemaView, classes: list[ClassDefinition]) -> set[str]:
    """A use case is a message, never stored by itself (PD-20), so it needs no owner."""
    return {cls.name for cls in classes if _is_activity(view, cls.name)}


def _ownership_problems(
    view: SchemaView, classes: list[ClassDefinition], technical: list[ClassDefinition]
) -> Iterator[CheckProblem]:
    """Technical classes are exempt, and what they own does not count: a request shape is never stored."""
    exempt = {id(cls) for cls in technical}
    stored = [cls for cls in classes if id(cls) not in exempt]
    roots = {root.name for root in aggregate_roots(view, classes)}
    kept = roots | owned_classes(view, stored) | _use_cases(view, stored)
    for cls in stored:
        if cls.mixin or cls.abstract or cls.name in kept or is_tenant_root(cls):
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
                    f"of {cls.name} points to {slot.range}, which is neither a root nor a reference class: "
                    f"annotate the slot owned: true to hold {slot.range} inline, "
                    f"or make {slot.range} an aggregate root, "
                    "or point the slot at a root, Principal or Activity",
                )


def _direction_problems(view: SchemaView, classes: list[ClassDefinition]) -> Iterator[CheckProblem]:
    """PD-20: the stored model never refers to a use case, so a slot of a class that is not an activity does not range over one."""
    names = {cls.name for cls in classes}
    use_cases = {
        name
        for name in names
        if _is_activity(view, name) and AGGREGATE_ROOT not in view.class_ancestors(name)
    }
    for cls in classes:
        if _is_activity(view, cls.name):
            continue
        induced = {slot.name: slot for slot in view.class_induced_slots(cls.name)}
        for name in sorted(declared_slots(cls) & induced.keys()):
            if induced[name].range in use_cases:
                yield rule_problem(
                    BoundaryRule.ACTIVITY_DIRECTION,
                    name,
                    f"of {cls.name} ranges over {induced[name].range}, a use case: the stored model "
                    "does not refer to the activities module; "
                    "range over Activity, or move the slot to the activity class",
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


def target_kind_problems(view: SchemaView, folder: Path, kind: TargetKind) -> list[CheckProblem]:
    """The modules of ``folder`` that do not match the ``kind`` the target declares (PD-9).

    A technical target holds only modules annotated ``module_kind: technical``; a domain target holds none.
    """
    kind = TargetKind(kind)  # a validated model holds the value, a caller may pass the member
    technical = ModuleKind.TECHNICAL.value
    problems = []
    for schema in own_schemas(view, folder):
        is_technical = annotation(schema, RpAnnotation.MODULE_KIND) == technical
        if kind == TargetKind.TECHNICAL and not is_technical:
            message = f"is not annotated module_kind: {technical}, in a target of kind {kind.value}"
        elif kind == TargetKind.DOMAIN and is_technical:
            message = f"is a {technical} module in a target of kind {kind.value}"
        else:
            continue
        problems.append(rule_problem(BoundaryRule.TARGET_KIND, schema.name, message))
    return problems


def boundary_problems(view: SchemaView, folder: Path) -> list[CheckProblem]:
    """Every problem of the schemas kept in ``folder``, in a stable order.

    The toolkit's own schemas get the import rule but not the class rules (PD-23), and neither do the
    classes of a module annotated ``module_kind: technical``, which are never stored (D-49).
    """
    schemas = own_schemas(view, folder)
    classes = [] if is_toolkit_schema(folder) else own_classes(schemas)
    technical = technical_classes(schemas)
    exempt = {id(cls) for cls in technical}
    stored = [cls for cls in classes if id(cls) not in exempt]
    return [
        *_ownership_problems(view, classes, technical),
        *_reference_problems(view, stored),
        *_direction_problems(view, classes),
        *_module_problems(view, schemas),
    ]
