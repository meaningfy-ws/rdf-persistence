"""The dependence check (dependent-aggregates PD-12, DEC-7; A-10, A-12): a dependent class is well formed.

A class annotated ``rp_dependent_on: <slot>`` is a dependent aggregate (a part) of the root its slot
points to (its whole). The annotation is read from the first class of the ``is_a`` chain that carries
it, so it may sit on an abstract base. The rules, each one check:

- the annotated class is a served root, or an abstract class whose concrete subclasses all are;
- a subclass does not re-annotate with another slot;
- for each concrete part, the induced slot (after ``slot_usage``) exists, is required and is single-valued;
- its range is a served root, or an abstract class whose concrete subclasses all are, never the tenant
  root nor a root the toolkit writes;
- no cycle of dependence, found over concrete classes after expanding each range to its concrete subclasses.
"""

from collections.abc import Iterator

from linkml_runtime.linkml_model.meta import ClassDefinition, SlotDefinition
from linkml_runtime.utils.schemaview import SchemaView

from rdf_persistence.core.domain.generated.rp_core import RpAnnotation
from rdf_persistence.schema.services.schema_structure import (
    annotation_text,
    is_tenant_root,
    is_toolkit_written,
    served_roots,
)
from rdf_persistence_generation.generated.rp_generation import BoundaryRule, CheckProblem
from rdf_persistence_generation.problems import rule_problem

TAG = RpAnnotation.RP_DEPENDENT_ON


def _own_pointer(view: SchemaView, name: str) -> str | None:
    """The slot the class itself names in ``rp_dependent_on``; None when it names none."""
    return annotation_text(view.get_class(name), TAG) or None


def _pointer_of(view: SchemaView, name: str) -> str | None:
    """The pointer slot of a class: the one of the first class of its ``is_a`` chain that names one; mixins do not count."""
    return next(
        (
            pointer
            for ancestor in view.class_ancestors(name, mixins=False)
            if (pointer := _own_pointer(view, ancestor))
        ),
        None,
    )


def _inherited_pointer(view: SchemaView, name: str) -> str | None:
    """The slot a class's ``is_a`` ancestors name, leaving out the class itself."""
    return next(
        (
            pointer
            for ancestor in view.class_ancestors(name, mixins=False)
            if ancestor != name and (pointer := _own_pointer(view, ancestor))
        ),
        None,
    )


def _concrete(view: SchemaView, name: str) -> list[str]:
    """The concrete classes of ``name`` and its ``is_a`` descendants, sorted."""
    return sorted(
        found
        for found in view.class_descendants(name, mixins=False)
        if not view.get_class(found).abstract and not view.get_class(found).mixin
    )


def _induced(view: SchemaView, name: str, slot: str) -> SlotDefinition | None:
    return next((s for s in view.class_induced_slots(name) if s.name == slot), None)


def _all_served(view: SchemaView, name: str, served: set[str]) -> bool:
    """True when ``name`` is a served root, or an abstract class whose concrete subclasses all are."""
    concrete = _concrete(view, name)
    return bool(concrete) and all(found in served for found in concrete)


def _placement_problems(
    view: SchemaView, annotated: list[ClassDefinition], served: set[str]
) -> Iterator[CheckProblem]:
    for cls in annotated:
        if not _all_served(view, str(cls.name), served):
            yield rule_problem(
                BoundaryRule.DEPENDENCE,
                str(cls.name),
                f"carries rp_dependent_on: {_own_pointer(view, str(cls.name))} but is not a served "
                "aggregate root, nor an abstract class whose concrete subclasses all are: "
                "annotate a root with a path, or an abstract base of such roots",
            )


def _re_annotation_problems(
    view: SchemaView, annotated: list[ClassDefinition]
) -> Iterator[CheckProblem]:
    for cls in annotated:
        name = str(cls.name)
        own, inherited = _own_pointer(view, name), _inherited_pointer(view, name)
        if inherited is not None and inherited != own:
            yield rule_problem(
                BoundaryRule.DEPENDENCE,
                name,
                f"names the slot {own} but an ancestor names {inherited}: a subclass may not "
                "re-annotate with another slot, so drop the annotation or use the same slot",
            )


def _missing_slot_problems(view: SchemaView, parts: list[str]) -> Iterator[CheckProblem]:
    for name in parts:
        pointer = str(_pointer_of(view, name))
        if _induced(view, name, pointer) is None:
            yield rule_problem(
                BoundaryRule.DEPENDENCE,
                name,
                f"names the pointer slot {pointer}, which is not a slot of {name}",
            )


def _requirement_problems(view: SchemaView, parts: list[str]) -> Iterator[CheckProblem]:
    for name in parts:
        pointer = str(_pointer_of(view, name))
        slot = _induced(view, name, pointer)
        if slot is not None and not slot.required:
            yield rule_problem(
                BoundaryRule.DEPENDENCE,
                name,
                f"pointer slot {pointer} is not required in {name}: a part cannot exist without its whole",
            )


def _cardinality_problems(view: SchemaView, parts: list[str]) -> Iterator[CheckProblem]:
    for name in parts:
        pointer = str(_pointer_of(view, name))
        slot = _induced(view, name, pointer)
        if slot is not None and slot.multivalued:
            yield rule_problem(
                BoundaryRule.DEPENDENCE,
                name,
                f"pointer slot {pointer} is multivalued in {name}: a part has one whole",
            )


def _why_not_servable(view: SchemaView, range_: str, served: set[str]) -> str | None:
    """Why a range cannot be a whole; None when every concrete class it covers is a served root."""
    concrete = _concrete(view, range_)
    if not concrete:
        return f"{range_} has no concrete class"
    for name in concrete:
        cls = view.get_class(name)
        if is_tenant_root(cls):
            return f"{name} is the tenant root, which no delete removes"
        if is_toolkit_written(cls):
            return f"{name} is a root the toolkit writes, which no route serves"
        if name not in served:
            return f"{name} is not a served aggregate root"
    return None


def _range_problems(view: SchemaView, parts: list[str], served: set[str]) -> Iterator[CheckProblem]:
    for name in parts:
        pointer = str(_pointer_of(view, name))
        slot = _induced(view, name, pointer)
        if slot is None:
            continue
        range_ = str(slot.range)
        why = (
            _why_not_servable(view, range_, served)
            if range_ in view.all_classes()
            else f"{range_} is not a class"
        )
        if why is not None:
            yield rule_problem(
                BoundaryRule.DEPENDENCE,
                name,
                f"pointer slot {pointer} ranges over {range_}, which cannot be a whole: {why}",
            )


def _edges(view: SchemaView, parts: list[str]) -> list[tuple[str, str]]:
    """``part -> whole`` over concrete classes: each range expanded to its concrete subclasses that are parts."""
    found: list[tuple[str, str]] = []
    for name in parts:
        slot = _induced(view, name, str(_pointer_of(view, name)))
        if slot is not None and str(slot.range) in view.all_classes():
            found += [(name, whole) for whole in _concrete(view, str(slot.range)) if whole in parts]
    return found


def _cycles(edges: list[tuple[str, str]]) -> list[tuple[str, ...]]:
    """Every elementary cycle once, as its classes in order, starting from the smallest name."""
    found: list[tuple[str, ...]] = []
    for start in sorted({part for part, _ in edges}):

        def walk(node: str, path: tuple[str, ...], start: str = start) -> None:
            for part, whole in edges:
                if part != node:
                    continue
                if whole == start:
                    found.append(path)
                elif whole > start and whole not in path:
                    walk(whole, (*path, whole))

        walk(start, (start,))
    return found


def _cycle_problems(view: SchemaView, parts: list[str]) -> Iterator[CheckProblem]:
    for cycle in _cycles(_edges(view, parts)):
        order = " -> ".join((*cycle, cycle[0]))
        slots = ", ".join(str(_pointer_of(view, name)) for name in cycle)
        yield rule_problem(
            BoundaryRule.DEPENDENCE,
            cycle[0],
            f"cycle of dependence {order} (through the slots {slots}): a whole cannot depend on its own part",
        )


def dependence_problems(view: SchemaView, classes: list[ClassDefinition]) -> list[CheckProblem]:
    """Every problem of the dependent classes among ``classes``, in a stable order."""
    served = {str(root.name) for root in served_roots(view)}
    annotated = [cls for cls in classes if _own_pointer(view, str(cls.name))]
    parts = sorted(
        {
            found
            for cls in annotated
            for found in _concrete(view, str(cls.name))
            if found in served and _pointer_of(view, found)
        }
    )
    return [
        *_placement_problems(view, annotated, served),
        *_re_annotation_problems(view, annotated),
        *_missing_slot_problems(view, parts),
        *_requirement_problems(view, parts),
        *_cardinality_problems(view, parts),
        *_range_problems(view, parts, served),
        *_cycle_problems(view, parts),
    ]
