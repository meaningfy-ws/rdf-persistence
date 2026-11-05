"""The model-shape test (PD-27 item 5): generated pydantic fields against the schema's induced slots."""

import typing
from collections.abc import Iterable

from linkml_runtime.utils.formatutils import underscore
from pydantic import BaseModel
from pydantic.fields import FieldInfo

from rdf_persistence.generation.generated.rp_generation import ClassShape, SlotShape


def model_shape_diff(shapes: list[ClassShape], models: Iterable[type[BaseModel]]) -> list[str]:
    """Where the pydantic fields of the generated classes differ from the shapes (name, required,
    multivalued); empty when they agree. Catches stale or hand-edited generated code."""
    by_name = {m.__name__: m for m in models}
    lines: list[str] = []
    for shape in shapes:
        model = by_name.get(shape.class_name)
        if model is None:
            lines.append(f"class without a generated model: {shape.class_name}")
        else:
            lines += _field_lines(shape, model)
    return lines


def _field_lines(shape: ClassShape, model: type[BaseModel]) -> list[str]:
    fields = model.model_fields
    slots = {underscore(s.name): s for s in shape.slots or []}
    lines = [f"field without a slot: {shape.class_name}.{n}" for n in fields if n not in slots]
    for key, slot in slots.items():
        if key in fields:
            lines += _flag_lines(shape.class_name, slot, fields[key])
        else:
            lines.append(f"slot without a field: {shape.class_name}.{slot.name}")
    return lines


def _flag_lines(class_name: str, slot: SlotShape, field: FieldInfo) -> list[str]:
    in_code = {"required": field.is_required(), "multivalued": _is_list(field)}
    return [
        f"field differs: {class_name}.{slot.name}: {flag} {in_code[flag]} in code, "
        f"{getattr(slot, flag)} in schema"
        for flag in in_code
        if in_code[flag] != getattr(slot, flag)
    ]


def _is_list(field: FieldInfo) -> bool:
    annotation = field.annotation
    members = (
        typing.get_args(annotation)
        if typing.get_origin(annotation) is typing.Union
        else (annotation,)
    )
    return any(typing.get_origin(m) is list for m in members)
