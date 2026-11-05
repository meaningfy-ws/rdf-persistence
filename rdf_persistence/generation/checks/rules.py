"""The unsupported-rules check (PD-24): what the generated classes and shapes would silently ignore.

On a class only ``exactly_one_of``, ``any_of`` and ``unique_keys`` are enforced; LinkML's ``rules``
(pre- and postconditions), ``all_of`` and ``none_of`` fail instead. On a slot, an attribute or a
``slot_usage`` ``all_of``, ``none_of`` and ``exactly_one_of`` are ignored by gen-pydantic and gen-shacl
alike, and so is an ``any_of`` alternative that says anything but a range; only ``any_of`` as a union
of ranges is rendered by both (``Union[...]`` and ``sh:or``), so only that passes.
"""

from collections.abc import Iterable, Iterator

from linkml_runtime.linkml_model.meta import ClassDefinition, SlotDefinition
from linkml_runtime.utils.schemaview import SchemaView

from rdf_persistence.generation.generated.rp_generation import CheckProblem

UNSUPPORTED = ("rules", "all_of", "none_of")
UNSUPPORTED_ON_SLOTS = ("all_of", "none_of", "exactly_one_of")
RANGE = "range"


def _says_more_than_a_range(alternative: object) -> bool:
    stated = {k for k, v in vars(alternative).items() if v not in (None, [], {})}
    return stated != {RANGE}


def _slot_problems(where: str, slot: SlotDefinition) -> Iterator[CheckProblem]:
    for rule in UNSUPPORTED_ON_SLOTS:
        if getattr(slot, rule):
            yield CheckProblem(
                element=where,
                message=f"`{rule}` is not supported on a slot; use a range, a pattern or a class rule",
            )
    if any(_says_more_than_a_range(alternative) for alternative in slot.any_of or []):
        yield CheckProblem(
            element=where, message="`any_of` is supported on a slot only as a union of ranges"
        )


def _class_slots(cls: ClassDefinition) -> Iterator[tuple[str, SlotDefinition]]:
    for slot in cls.attributes.values():
        yield f"{cls.name}.{slot.name}", slot
    for slot in cls.slot_usage.values():
        yield f"{cls.name}.{slot.name}", slot


def _class_rule_problems(classes: Iterable[ClassDefinition]) -> Iterator[CheckProblem]:
    for cls in classes:
        for rule in UNSUPPORTED:
            if getattr(cls, rule):
                yield CheckProblem(
                    element=cls.name,
                    message=f"`{rule}` is not supported; use exactly_one_of, any_of or unique_keys",
                )


def _own_slot_problems(slots: Iterable[SlotDefinition]) -> Iterator[CheckProblem]:
    for slot in slots:
        yield from _slot_problems(f"slot {slot.name}", slot)


def _declared_slot_problems(classes: Iterable[ClassDefinition]) -> Iterator[CheckProblem]:
    for cls in classes:
        for where, slot in _class_slots(cls):
            yield from _slot_problems(where, slot)


def rules_problems(view: SchemaView) -> list[CheckProblem]:
    """One line for each class, slot, attribute or slot_usage of the schema's closure that declares an unsupported rule."""
    classes = view.all_classes().values()
    return [
        *_class_rule_problems(classes),
        *_own_slot_problems(view.all_slots(attributes=False).values()),
        *_declared_slot_problems(classes),
    ]
