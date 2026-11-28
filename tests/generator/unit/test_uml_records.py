"""The UML converter's records are generated models; ``UmlRule`` is the rule catalogue (uml-to-linkml PD-2)."""

import re

import pytest
from linkml_runtime.utils.schemaview import SchemaView
from pydantic import ValidationError

from rdf_persistence_generation.config import GENERATION_MODEL
from rdf_persistence_generation.generated.rp_generation import (
    CheckProblem,
    ReportKind,
    ReportLine,
    UmlAggregates,
    UmlClass,
    UmlComposition,
    UmlDiagram,
    UmlElement,
    UmlModel,
    UmlName,
    UmlObject,
    UmlOwnedEnd,
    UmlPartOf,
    UmlReach,
    UmlRule,
)

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
        "cardinality_unbounded",
        "role_run_state",  # the role rules of uml-roles-and-workflows PD-3 have no R-n
        "role_definition",
        "role_duplicate",
        "workflow_node",  # the workflow rules of uml-roles-and-workflows PD-5 have no R-n
        "workflow_initial",
        "workflow_transition",
        "workflow_definition",
        "workflow_duplicate",
        "workflow_class",
    }
)
WITHOUT_A_RULE_NUMBER = frozenset(
    {
        "no_rule",
        "activity_root",
        "role_run_state",
        "role_definition",
        "role_duplicate",
        "workflow_node",
        "workflow_initial",
        "workflow_transition",
        "workflow_definition",
        "workflow_duplicate",
        "workflow_class",
    }
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


# ---- aggregate-composition, task 1.2: the records the tree and the conventions read and return ----


def _composition(**changes: object) -> UmlComposition:
    return UmlComposition(**{"composition_id": 7, "whole_id": 1, "part_id": 2, **changes})


def test_a_composition_names_its_whole_and_its_part_and_is_plain_by_default() -> None:
    """PD-1: one record per composition; `own_graph` is false and stereotype and role are absent unless set."""
    composition = _composition()
    assert (composition.whole_id, composition.part_id) == (1, 2), "whole and part are kept apart"
    assert composition.own_graph is False, "a composition is not an own graph by default"
    assert composition.uml_stereotype is None, "no stereotype unless drawn"
    assert composition.role is None, "no role unless written on the composition"


@pytest.mark.parametrize("missing", ["composition_id", "whole_id", "part_id"])
def test_a_composition_without_an_end_or_an_id_is_refused(missing: str) -> None:
    """Negative case of the row above: the three ids are required."""
    values = {"composition_id": 7, "whole_id": 1, "part_id": 2}
    del values[missing]
    with pytest.raises(ValidationError):
        UmlComposition(**values)


def test_a_model_holds_compositions_and_diagrams() -> None:
    """PD-1, PD-12: `UmlModel` gains `uml_compositions` and `uml_diagrams`, empty by default."""
    assert UmlModel().uml_compositions is None, "no composition unless the reader reads one"
    model = UmlModel(
        uml_compositions=[_composition()],
        uml_diagrams=[UmlDiagram(diagram_id=3, name="Library · aggregates", package_id=4)],
    )
    assert model.uml_compositions[0].composition_id == 7, "the composition is kept"
    assert model.uml_diagrams[0].diagram_id == 3, "the diagram is kept"


def test_a_diagram_carries_membership_only() -> None:
    """PD-12: elements and hidden connectors are ids; no geometry slot exists."""
    diagram = UmlDiagram(
        diagram_id=3,
        name="Library · aggregates",
        package_id=4,
        diagram_type="Logical",
        element_ids=[1, 2],
        hidden_connector_ids=[9],
    )
    assert diagram.element_ids == [1, 2], "member elements"
    assert diagram.hidden_connector_ids == [9], "connectors the diagram hides"
    assert diagram.diagram_type == "Logical", "the diagram type as written"
    with pytest.raises(ValidationError):
        UmlDiagram(diagram_id=3, name="x", package_id=4, rect_top=1)


def test_an_object_holds_the_classes_it_realises() -> None:
    """PD-11: `UmlObject.realised_ids` is multivalued and absent by default."""
    assert UmlObject(object_id=1, uml_name="admin").realised_ids is None, (
        "nothing realised by default"
    )
    realised = UmlObject(object_id=1, uml_name="admin", realised_ids=[5, 6])
    assert realised.realised_ids == [5, 6], "both targets are kept so the converter can refuse two"


def test_an_element_is_not_a_drawn_root_by_default() -> None:
    """PD-5: `is_drawn_root` is the stereotype's fact and defaults to false, `is_root` is derived."""
    uml_class = UmlClass(object_id=1, name="Book", object_type="Class", package_id=2)
    element = UmlElement(uml_class=uml_class, resolved_name=UmlName(name="Book"), label="Book")
    assert element.is_drawn_root is False, "not drawn root by default"
    drawn = element.model_copy(update={"is_drawn_root": True})
    assert (drawn.is_drawn_root, drawn.is_root) == (True, False), (
        "drawn and derived roots are two facts"
    )


def test_the_aggregates_record_keeps_its_rows_and_findings() -> None:
    """PD-19: the pass returns one record; rows are models, not dicts (P-0007)."""
    empty = UmlAggregates()
    for name in (
        "root_ids",
        "part_of",
        "reached_from",
        "owned_ends",
        "left_inside_ids",
        "problems",
        "report_lines",
    ):
        assert getattr(empty, name) is None, f"{name} is empty by default"
    assert empty.tenant_root_id is None, "no tenant root by default"
    aggregates = UmlAggregates(
        root_ids=[1],
        tenant_root_id=9,
        part_of=[
            UmlPartOf(part_id=2, whole_id=1, composition_id=7),
            UmlPartOf(part_id=2, whole_id=3, composition_id=8),
        ],
        reached_from=[UmlReach(part_id=2, top_ids=[1, 3])],
        owned_ends=[UmlOwnedEnd(link_id=11, holder_id=1)],
        left_inside_ids=[4],
        problems=[CheckProblem(message="x")],
        report_lines=[
            ReportLine(report_kind=ReportKind.ROOT, element="Book", message="parts Chapter")
        ],
    )
    assert [(row.part_id, row.whole_id) for row in aggregates.part_of] == [(2, 1), (2, 3)], (
        "one row per (part, whole)"
    )
    assert aggregates.part_of[0].own_graph is False, "a part-of row is plain by default"
    assert aggregates.reached_from[0].top_ids == [1, 3], "a part reached from two tops"
    assert (aggregates.owned_ends[0].link_id, aggregates.owned_ends[0].holder_id) == (11, 1), (
        "an owned end"
    )


@pytest.mark.parametrize(
    ("model", "values"),
    [
        (UmlPartOf, {"part_id": 2, "whole_id": 1}),
        (UmlPartOf, {"part_id": 2, "composition_id": 7}),
        (UmlReach, {"top_ids": [1]}),
        (UmlOwnedEnd, {"link_id": 11}),
        (UmlOwnedEnd, {"holder_id": 1}),
    ],
)
def test_a_row_of_the_aggregates_record_needs_its_ids(
    model: type, values: dict[str, object]
) -> None:
    """Negative case: each row type refuses a missing id."""
    with pytest.raises(ValidationError):
        model(**values)


NEW_REPORT_KINDS = (
    "root",
    "deprecated_root",
    "boundary_disagrees",
    "composition_named",
    "aggregates_diagram",
    "composition_diagram",
    "unprefixed_name",
    "unused_enumeration",
    "drawn_toolkit_parent",
    "tenant_required_pointer",
)


@pytest.mark.parametrize("value", NEW_REPORT_KINDS)
def test_the_report_kind_has_the_values_of_pd_13(value: str) -> None:
    """PD-13: each new kind exists and has a `meaning` and a description."""
    assert ReportKind(value).value == value, f"{value} is a ReportKind"
    permissible = SchemaView(str(GENERATION_MODEL)).get_enum("ReportKind").permissible_values[value]
    assert permissible.description, f"{value} has a description"
    assert permissible.meaning, f"{value} has a meaning"


def test_an_unknown_report_kind_is_refused() -> None:
    """Negative case of the table above."""
    with pytest.raises(ValueError):
        ReportKind("not_a_kind")
