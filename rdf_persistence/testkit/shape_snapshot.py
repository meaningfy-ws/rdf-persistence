"""The model-shape snapshot (PD-27 item 6): reviewed class shapes, read from a schema."""

from collections.abc import Iterable
from pathlib import Path

import yaml
from linkml_runtime.utils.schemaview import SchemaView

from rdf_persistence.generation.generated.rp_generation import ClassShape, SlotShape
from rdf_persistence.services.schema_structure import generation_view

_FLAGS = ("required", "multivalued", "range")


def class_shapes(schema_paths: Iterable[str | Path]) -> list[ClassShape]:
    """The shape of every class (mixins and abstract ones too) in the closure of the schemas.

    Mixins are included because the generated code has a class for each of them. A class that
    several closures share is listed once. The shapes are those of the schema after the generation
    defaults (an unlabelled class's label, an aggregate root's description), as the code has them.
    Classes and slots are sorted by name.
    """
    found: dict[str, ClassShape] = {}
    for path in schema_paths:
        view = generation_view(path)
        for name in view.all_classes():
            found.setdefault(name, _shape_of(view, name))
    return [found[name] for name in sorted(found)]


def _shape_of(view: SchemaView, class_name: str) -> ClassShape:
    slots = [
        SlotShape(
            name=s.name,
            required=bool(s.required),
            multivalued=bool(s.multivalued),
            range=s.range or view.schema.default_range or "string",
        )
        for s in view.class_induced_slots(class_name)
    ]
    return ClassShape(class_name=class_name, slots=sorted(slots, key=lambda s: s.name))


def write_snapshot(path: str | Path, shapes: list[ClassShape]) -> None:
    """Write the shapes as YAML rows."""
    rows = [shape.model_dump() for shape in shapes]
    Path(path).write_text(yaml.safe_dump(rows, sort_keys=False), encoding="utf-8")


def read_snapshot(path: str | Path) -> list[ClassShape]:
    """Read the shapes written by :func:`write_snapshot`."""
    rows = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or []
    return [ClassShape.model_validate(row) for row in rows]


def snapshot_diff(old: list[ClassShape], new: list[ClassShape]) -> list[str]:
    """Human-readable lines for what differs between two lists of shapes; empty if none."""
    before = {c.class_name: c for c in old}
    after = {c.class_name: c for c in new}
    lines = [f"class removed: {name}" for name in before.keys() - after.keys()]
    lines += [f"class added: {name}" for name in after.keys() - before.keys()]
    for name in before.keys() & after.keys():
        lines += _slot_lines(name, before[name].slots or [], after[name].slots or [])
    return sorted(lines)


def _slot_lines(class_name: str, old: list[SlotShape], new: list[SlotShape]) -> list[str]:
    before = {s.name: s for s in old}
    after = {s.name: s for s in new}
    lines = [f"slot removed: {class_name}.{n}" for n in before.keys() - after.keys()]
    lines += [_added_line(class_name, after[n]) for n in after.keys() - before.keys()]
    lines += [_changed_line(class_name, before[n], after[n]) for n in before.keys() & after.keys()]
    return [line for line in lines if line]


def _added_line(class_name: str, slot: SlotShape) -> str:
    return (
        f"slot added: {class_name}.{slot.name} "
        f"(required={slot.required}, multivalued={slot.multivalued}, range={slot.range})"
    )


def _changed_line(class_name: str, old: SlotShape, new: SlotShape) -> str:
    """The line for a slot whose flags differ; an empty string when it is unchanged."""
    changes = [
        f"{flag} {getattr(old, flag)} -> {getattr(new, flag)}"
        for flag in _FLAGS
        if getattr(old, flag) != getattr(new, flag)
    ]
    return f"slot changed: {class_name}.{new.name}: {', '.join(changes)}" if changes else ""
