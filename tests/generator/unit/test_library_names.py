"""The library names of a generated module go under ``_`` aliases a schema class cannot take (#243)."""

import pytest

from rdf_persistence_generation.extensions.pydantic_split import alias_heads, alias_leaf


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


def test_a_type_leaf_is_aliased_only_when_it_is_a_library_name() -> None:
    assert (alias_leaf("Decimal"), alias_leaf("Any"), alias_leaf("str")) == (
        "_Decimal",
        "_Any",
        "str",
    )
