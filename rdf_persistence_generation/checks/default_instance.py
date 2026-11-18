"""The default-instance check (technical-models PD-6): a slot annotated ``default_instance`` can be built with no argument."""

from collections.abc import Iterator

from linkml_runtime.linkml_model.meta import SchemaDefinition, SlotDefinition
from linkml_runtime.utils.schemaview import SchemaView

from rdf_persistence.services.schema_structure import is_switched_on
from rdf_persistence_generation.generated.rp_generation import (
    CheckProblem,
    GenerationAnnotation,
    HardRule,
)
from rdf_persistence_generation.problems import rule_problem

ANNOTATION = GenerationAnnotation.DEFAULT_INSTANCE
RULE = HardRule.DEFAULT_INSTANCE


def _slots(schema: SchemaDefinition) -> Iterator[SlotDefinition]:
    yield from schema.slots.values()
    for cls in schema.classes.values():
        yield from cls.attributes.values()


def _why_not(view: SchemaView, schema: SchemaDefinition, slot: SlotDefinition) -> Iterator[str]:
    """What stops ``Field(default_factory=<range>)`` from building the slot's default."""
    range_name = str(slot.range or schema.default_range)
    if slot.multivalued:
        yield "it is multivalued, and its default would be one instance, not a list"
    if view.get_class(range_name) is None:
        yield f"its range {range_name} is not a class"
        return
    for needed in view.class_induced_slots(range_name):
        if (needed.required or needed.identifier) and needed.ifabsent is None:
            yield f"{range_name} has the required slot {needed.name} with no ifabsent"


def default_instance_problems(
    view: SchemaView, schemas: list[SchemaDefinition]
) -> Iterator[CheckProblem]:
    """One problem for each reason a slot annotated ``default_instance`` cannot default to a new instance of its range."""
    for schema in schemas:
        yield from _schema_problems(view, schema)


def _schema_problems(view: SchemaView, schema: SchemaDefinition) -> Iterator[CheckProblem]:
    for slot in _slots(schema):
        if _flagged(slot):
            for reason in _why_not(view, schema, slot):
                yield rule_problem(RULE, str(slot.name), f"{ANNOTATION.value}: {reason}")
    yield from _order_problems(view, schema)


def _flagged(slot: SlotDefinition) -> bool:
    return is_switched_on(slot, ANNOTATION)


def _order_problems(view: SchemaView, schema: SchemaDefinition) -> Iterator[CheckProblem]:
    """The generated module builds the default where the class is defined, so the range class comes first."""
    position = {name: index for index, name in enumerate(schema.classes)}
    for holder in schema.classes:
        for slot in view.class_induced_slots(holder):
            if _flagged(slot) and position.get(str(slot.range), -1) >= position[holder]:
                yield rule_problem(
                    RULE,
                    str(slot.name),
                    f"{ANNOTATION.value}: {slot.range} is declared after {holder}, which holds it: "
                    f"declare {slot.range} first",
                )
