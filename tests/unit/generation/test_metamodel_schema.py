"""Schema-level facts of the metamodel that the generated classes cannot show."""

from pathlib import Path

import pytest

from rdf_persistence.services.schema import load_schema
from rdf_persistence.services.schema_structure import is_internal

MODEL = Path(__file__).parents[3] / "rdf_persistence" / "model"
LIBRARY = Path(__file__).parents[2] / "fixtures" / "library"


@pytest.mark.parametrize(
    ("schema", "name", "class_uri"),
    [
        (MODEL / "rp.yaml", "Grant", "ODRL:Permission"),
        (MODEL / "rp.yaml", "Prohibition", "ODRL:Prohibition"),
    ],
)
def test_stored_rule_is_typed_as_its_odrl_class(schema: Path, name: str, class_uri: str) -> None:
    view = load_schema(schema)
    assert view.get_class(name).class_uri == class_uri, f"{name} is not typed {class_uri}"


@pytest.mark.parametrize("name", ["Grant", "Prohibition"])
def test_rules_share_one_abstract_rule_class(name: str) -> None:
    view = load_schema(MODEL / "rp.yaml")
    assert view.get_class(name).is_a == "Rule", f"{name} does not extend Rule"
    assert view.get_class("Rule").abstract, "Rule must be abstract"


def test_database_name_is_internal() -> None:
    slot = load_schema(MODEL / "rp.yaml").get_slot("database_name")
    assert is_internal(slot), "database_name must be marked internal"
