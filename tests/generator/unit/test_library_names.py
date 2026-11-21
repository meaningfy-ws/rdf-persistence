"""The library names of a generated module go under ``_`` aliases a schema class cannot take (#243)."""

from pathlib import Path

import pytest

from rdf_persistence_generation.extensions.pydantic_split import alias_heads, alias_leaf, render


@pytest.mark.parametrize(
    ("expression", "aliased"),
    [
        ("Optional[str]", "_Optional[str]"),
        ("Optional[Optional]", "_Optional[Optional]"),  # the leaf is the schema's class
        ("Optional[list[Union[Field, Any]]]", "_Optional[list[_Union[Field, Any]]]"),
        ('Union[Literal["é", "b"], Optional[int]]', '_Union[_Literal["é", "b"], _Optional[int]]'),
        ("datetime ", "datetime "),
    ],
)
def test_the_subscripted_library_names_are_aliased_and_the_leaves_kept(
    expression: str, aliased: str
) -> None:
    assert alias_heads(expression) == aliased


SIMPLE_DICT = """\
id: https://example.org/ns/prices
name: prices
prefixes:
  linkml: https://w3id.org/linkml/
  ex: https://example.org/ns/prices#
default_prefix: ex
imports: [linkml:types]
classes:
  Rate:
    attributes:
      code: {identifier: true}
      amount: {range: decimal}
  Catalogue:
    attributes:
      rates: {range: Rate, multivalued: true, inlined: true}
"""


def test_the_value_type_of_a_simple_dict_slot_is_aliased(tmp_path: Path) -> None:
    """The stock generator reads a simple dict's value type apart from every other range (#243)."""
    schema = tmp_path / "prices.yaml"
    schema.write_text(SIMPLE_DICT, encoding="utf-8")

    (module,) = [f for f in render(schema) if f.name == "prices.py"]

    rates = next(line for line in module.text.splitlines() if line.strip().startswith("rates:"))
    assert "_Decimal" in rates, rates
    assert "[Decimal" not in rates, rates


def test_a_type_leaf_is_aliased_only_when_it_is_a_library_name() -> None:
    assert (alias_leaf("Decimal"), alias_leaf("Any"), alias_leaf("str")) == (
        "_Decimal",
        "_Any",
        "str",
    )
