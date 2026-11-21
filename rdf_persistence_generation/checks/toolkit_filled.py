"""The toolkit-filled check (PD-20): a use case leaves alone the slots the toolkit fills, and never requires a payload."""

from collections.abc import Iterator

from linkml_runtime.linkml_model.meta import ClassDefinition
from linkml_runtime.utils.schemaview import SchemaView

from rdf_persistence.core.domain.generated.rp_core import RpAnnotation
from rdf_persistence.schema.services.schema_structure import flag
from rdf_persistence_generation.generated.rp_generation import CheckProblem, HardRule
from rdf_persistence_generation.problems import rule_problem


def _redeclared(cls: ClassDefinition, filled: set[str]) -> Iterator[CheckProblem]:
    for name in sorted({*cls.slot_usage, *cls.attributes} & filled):
        yield rule_problem(
            HardRule.TOOLKIT_FILLED,
            cls.name,
            f"gives slot_usage or an attribute for {name}, which the toolkit fills: "
            f"remove it from {cls.name}",
        )


def _required_payloads(view: SchemaView, cls: ClassDefinition) -> Iterator[CheckProblem]:
    for slot in view.class_induced_slots(cls.name):
        if flag(slot, RpAnnotation.PAYLOAD) and slot.required:
            yield rule_problem(
                HardRule.TOOLKIT_FILLED,
                cls.name,
                f"requires the payload slot {slot.name}, which a stored record drops: "
                "make it optional",
            )


def _aliases(
    view: SchemaView, cls: ClassDefinition, filled: dict[str, str]
) -> Iterator[CheckProblem]:
    """A slot of ``cls`` under another name with the IRI of a slot the toolkit fills."""
    uris = {uri: name for name, uri in filled.items()}
    for slot in view.class_induced_slots(cls.name):
        uri = str(view.get_uri(slot, expand=True))
        if slot.name not in filled and uri in uris:
            yield rule_problem(
                HardRule.TOOLKIT_FILLED,
                cls.name,
                f"the slot {slot.name} has the slot_uri of {uris[uri]}, which the toolkit fills: "
                f"give {slot.name} a slot_uri of its own",
            )


def toolkit_filled_slots(view: SchemaView) -> dict[str, str]:
    """The slots annotated ``toolkit_filled: true`` in ``view``, each name with its expanded ``slot_uri``."""
    return {
        name: str(view.get_uri(slot, expand=True))
        for name, slot in view.all_slots(attributes=False).items()
        if flag(slot, RpAnnotation.TOOLKIT_FILLED)
    }


def toolkit_filled_problems(
    view: SchemaView, classes: list[ClassDefinition]
) -> Iterator[CheckProblem]:
    """One problem for each slot a class narrows, redeclares or aliases though the toolkit fills it, and each required payload slot."""
    filled = toolkit_filled_slots(view)
    for cls in classes:
        yield from _redeclared(cls, set(filled))
        yield from _aliases(view, cls, filled)
        yield from _required_payloads(view, cls)
