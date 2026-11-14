"""Schema-level facts of the metamodel that the generated classes cannot show."""

from pathlib import Path

import pytest

from rdf_persistence.services.schema import SERVICE_SCHEMA, load_schema
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


@pytest.mark.parametrize(
    ("schema", "class_name", "slot", "slot_uri"),
    [
        (MODEL / "rp.yaml", "Grant", "target", "ODRL:target"),
        (SERVICE_SCHEMA, "Page", "items", "rp:items"),
        (LIBRARY / "library.yaml", "Grant", "target", "ODRL:target"),
        (MODEL / "rp.yaml", "Comment", "has_target", "oa:hasTarget"),
        (MODEL / "rp.yaml", "Comment", "body_value", "oa:bodyValue"),
        (MODEL / "rp.yaml", "Comment", "motivated_by", "oa:motivatedBy"),
        (MODEL / "rp.yaml", "Comment", "comment_audience", "rp:audience"),
        (MODEL / "rp.yaml", "Comment", "comment_references", "dcterms:references"),
        (MODEL / "rp.yaml", "Comment", "replies_to", "rp:repliesTo"),
    ],
)
def test_a_slot_name_shared_across_the_imports_keeps_its_own_predicate(
    schema: Path, class_name: str, slot: str, slot_uri: str
) -> None:
    """A new module's slot must not take the name of another's (one slot namespace per closure)."""
    induced = load_schema(schema).induced_slot(slot, class_name)
    assert induced.slot_uri == slot_uri, (
        f"{class_name}.{slot} is {induced.slot_uri}, not {slot_uri}"
    )
