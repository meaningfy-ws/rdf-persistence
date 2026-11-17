"""The model-shape test names a field by its slot or by its alias, as the generator did (D-52)."""

from pydantic import BaseModel, Field

from rdf_persistence.testkit.generated.rp_testkit import ClassShape, SlotShape
from rdf_persistence.testkit.model_shape import model_shape_diff


class Slotted(BaseModel):
    """A field named after its slot, with the alias apart (``field_name: slot``)."""

    schema_file: str = Field(alias="schema")


class Aliased(BaseModel):
    """A field named after its alias, the stock rule."""

    title: str = Field(default=...)


def _shape(name: str, slot: str, alias: str) -> list[ClassShape]:
    return [
        ClassShape(
            class_name=name,
            slots=[
                SlotShape(name=slot, required=True, multivalued=False, range="string", alias=alias)
            ],
        )
    ]


def test_a_field_named_after_its_slot_matches_a_shape_that_carries_the_alias() -> None:
    assert model_shape_diff(_shape("Slotted", "schema_file", "schema"), [Slotted]) == []


def test_a_field_named_after_the_alias_still_matches() -> None:
    assert model_shape_diff(_shape("Aliased", "label", "title"), [Aliased]) == []


def test_a_field_with_neither_name_is_still_reported() -> None:
    lines = model_shape_diff(_shape("Aliased", "label", "heading"), [Aliased])

    assert lines == ["field without a slot: Aliased.title", "slot without a field: Aliased.label"]
