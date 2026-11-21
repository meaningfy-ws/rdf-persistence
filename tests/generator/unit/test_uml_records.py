"""The UML converter's records are generated models; ``UmlRule`` is the rule catalogue (uml-to-linkml PD-2)."""

import re

import pytest
from linkml_runtime.utils.schemaview import SchemaView

from rdf_persistence_generation.config import GENERATION_MODEL
from rdf_persistence_generation.generated.rp_generation import UmlRule

PD_2_RULES = frozenset(
    {
        "no_rule",
        "activity_root",
        "package_module",
        "class_iri",
        "abstract_class",
        "generalisation",
        "attribute_slot",
        "association_slot",
        "enumeration",
        "dependency_enum_slot",
        "notes_description",
        "root_class",
        "boundary_owned",
        "not_generated",
        "shared_slot",
        "toolkit_slot",
        "tenant_root",
        "title",
        "class_annotation",
        "unique_key",
        "abstract_root",
        "shared_slot_across_packages",
        "toolkit_mixins",
        "left_out_link",
        "role_run_state",  # the role rules of uml-roles-and-workflows PD-3 have no R-n
        "role_definition",
        "role_duplicate",
    }
)
WITHOUT_A_RULE_NUMBER = frozenset(
    {"no_rule", "activity_root", "role_run_state", "role_definition", "role_duplicate"}
)
RULE_NUMBER = re.compile(r"\bR-\d+\b")


def test_uml_rule_has_exactly_the_values_of_pd_2() -> None:
    """Fails when a rule value is added, dropped or renamed without PD-2 being amended."""
    assert {rule.value for rule in UmlRule} == PD_2_RULES, "UmlRule differs from PD-2's list"


@pytest.mark.parametrize("value", sorted(PD_2_RULES - WITHOUT_A_RULE_NUMBER))
def test_every_uml_rule_description_names_its_rule_number(value: str) -> None:
    """Fails when a rule's description stops citing the R-n of the rule table it implements."""
    view = SchemaView(str(GENERATION_MODEL))
    description = view.get_enum("UmlRule").permissible_values[value].description or ""
    assert RULE_NUMBER.search(description), f"{value} does not name its R-n: {description!r}"
