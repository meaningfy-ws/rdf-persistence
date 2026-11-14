"""The generated classes and the generated shapes agree on every constraint case (PD-27 item 3)."""

from dataclasses import replace
from pathlib import Path

import pytest
from linkml_runtime.linkml_model.meta import ClassDefinition, SlotDefinition
from linkml_runtime.utils.schemaview import SchemaView
from pydantic import BaseModel
from rdflib import Graph

from rdf_persistence.generation.generated.rp_generation import ConstraintCase, ConstraintKind
from rdf_persistence.services.schema import load_schema
from rdf_persistence.services.schema_structure import keyed_slots
from rdf_persistence.testkit.conformance import (
    Conformance,
    coverage_problems,
    generated_classes,
    load_cases,
    run,
    used_kinds,
    verdict_problems,
)

ROOT = Path(__file__).parents[3]
METAMODEL = ROOT / "rdf_persistence" / "model" / "rp.yaml"
TOY = ROOT / "tests" / "fixtures" / "library" / "library.yaml"
CASES = ROOT / "tests" / "fixtures" / "conformance" / "cases.yaml"
INSTANCES = CASES.parent / "instances"
TEXT = {".py", ".ttl", ".jsonld", ".json", ".yaml"}
SCHEMAS = pytest.mark.parametrize("schema", [METAMODEL, TOY], ids=["metamodel", "toy"])

# The kinds each schema's own classes use; neither uses cardinality, value bounds or any_of.
K = ConstraintKind
USED_BY_METAMODEL = {
    K.REQUIRED,
    K.RANGE_TYPE,
    K.RANGE_ENUM,
    K.PATTERN,
    K.IDENTIFIER,
    K.CLOSED,
    K.EXACTLY_ONE_OF,
    K.UNIQUE_KEYS,
}
USED_BY_TOY = {
    K.REQUIRED,
    K.RANGE_TYPE,
    K.RANGE_ENUM,
    K.PATTERN,
    K.IDENTIFIER,
    K.CLOSED,
    K.UNIQUE_KEYS,
}

GRANT_BASE = {"assignee": "https://example.org/u/1", "target": "https://example.org/t/1"}


def test_the_cases_file_is_a_list_of_constraint_cases() -> None:
    cases = load_cases(CASES)
    assert cases, "the cases file must hold rows"
    assert all(isinstance(c, ConstraintCase) for c in cases), "every row is a ConstraintCase"


@SCHEMAS
def test_every_case_row_is_accepted_and_refused_alike_by_classes_and_shapes(schema: Path) -> None:
    assert verdict_problems(Conformance.of(schema), load_cases(CASES)) == [], (
        "classes and shapes must agree"
    )


@SCHEMAS
def test_every_constraint_kind_a_schema_uses_has_a_row(schema: Path) -> None:
    assert coverage_problems(Conformance.of(schema), load_cases(CASES)) == [], (
        "a used kind has no case"
    )


@SCHEMAS
def test_run_reports_nothing_for_the_committed_cases(schema: Path) -> None:
    assert run(schema, CASES) == [], "the committed cases must pass"


def test_every_row_names_a_class_one_of_the_two_schemas_generates() -> None:
    known = generated_classes(METAMODEL) | generated_classes(TOY)
    unknown = [c.class_name for c in load_cases(CASES) if c.class_name not in known]
    assert unknown == [], "a row names a class that no schema generates"


@pytest.mark.parametrize(
    ("schema", "expected"), [(METAMODEL, USED_BY_METAMODEL), (TOY, USED_BY_TOY)], ids=["mm", "toy"]
)
def test_used_kinds_are_read_from_the_schema(schema: Path, expected: set[ConstraintKind]) -> None:
    assert used_kinds(schema) == expected, "the kinds read from SchemaView drifted"


def test_a_grant_with_both_a_role_and_an_action_is_refused_by_class_and_shape() -> None:
    conformance = Conformance.of(METAMODEL)
    both = {**GRANT_BASE, "role": "admin", "action": "read"}
    only_role = {**GRANT_BASE, "role": "admin"}
    assert not conformance.class_accepts("Grant", both), "the class must refuse role and action"
    assert not conformance.shapes_accept("Grant", both), "the shape must refuse role and action"
    assert conformance.class_accepts("Grant", only_role), "the class must accept a role alone"
    assert conformance.shapes_accept("Grant", only_role), "the shape must accept a role alone"


def _write_case(folder: Path, kind: ConstraintKind, class_name: str, **files: str) -> Path:
    """Write instance files (name -> YAML text) and a cases file with one row; return the cases file."""
    for name, text in files.items():
        (folder / f"{name}.yaml").write_text(text, encoding="utf-8")
    row = ConstraintCase(
        kind=kind,
        class_name=class_name,
        valid=[f"{n}.yaml" for n in files if n.startswith("good")],
        invalid=[f"{n}.yaml" for n in files if n.startswith("bad")],
    )
    cases = folder / "cases.yaml"
    cases.write_text(
        f"- kind: {row.kind}\n  class_name: {row.class_name}\n"
        f"  valid: {row.valid}\n  invalid: {row.invalid}\n",
        encoding="utf-8",
    )
    return cases


BOOK = "id: https://example.org/library/b1\nlabel: A\ndescription: B\n"


def test_a_class_and_shape_that_disagree_are_reported_naming_the_case() -> None:
    # Shapes that say nothing accept a Book without a label, which the class refuses.
    lenient = replace(Conformance.of(TOY), shapes=Graph())
    row = ConstraintCase(
        kind=K.REQUIRED, class_name="Book", invalid=[str(INSTANCES / "book-no-label.yaml")]
    )
    problems = verdict_problems(lenient, [row])
    assert len(problems) == 1, f"one disagreement expected, got {problems}"
    assert "required Book book-no-label.yaml" in problems[0], "the case must be named"
    assert "disagree" in problems[0], "the problem must say classes and shapes disagree"


def test_an_instance_both_sides_accept_but_the_row_calls_invalid_is_reported(
    tmp_path: Path,
) -> None:
    cases = _write_case(tmp_path, K.REQUIRED, "Book", bad_fine=BOOK)
    problems = verdict_problems(Conformance.of(TOY), load_cases(cases))
    assert len(problems) == 1, f"one wrong verdict expected, got {problems}"
    assert "required Book bad_fine.yaml" in problems[0], "the case must be named"


def test_a_missing_kind_is_reported_naming_every_missing_kind(tmp_path: Path) -> None:
    cases = _write_case(tmp_path, K.REQUIRED, "Book", good_book=BOOK)
    (problem,) = coverage_problems(Conformance.of(TOY), load_cases(cases))
    missing = USED_BY_TOY - {K.REQUIRED}
    assert all(kind.value in problem for kind in missing), f"every missing kind is named: {problem}"
    assert "required" not in problem.split(":", 1)[1], "a covered kind must not be named"


def test_run_lists_the_verdict_and_the_coverage_problems_together(tmp_path: Path) -> None:
    cases = _write_case(tmp_path, K.REQUIRED, "Book", bad_fine=BOOK)
    problems = run(TOY, cases)
    assert len(problems) == 2, f"a wrong verdict and a coverage gap expected, got {problems}"


def test_a_schema_that_no_rp_generate_entry_generates_is_refused(tmp_path: Path) -> None:
    lonely = tmp_path / "lonely.yaml"
    lonely.write_text("id: https://example.org/lonely\nname: lonely\n", encoding="utf-8")
    with pytest.raises(LookupError, match="rp-generate"):
        run(lonely, CASES)


def test_a_book_without_an_id_is_refused_by_class_and_shape_alike() -> None:
    no_id = INSTANCES / "book-no-id.yaml"
    row = ConstraintCase(kind=K.IDENTIFIER, class_name="Book", invalid=[str(no_id)])
    assert verdict_problems(Conformance.of(TOY), [row]) == [], (
        "classes and shapes must agree on a missing id"
    )


INTERNAL_ONLY = """
id: https://example.org/ns/internal
name: internal
default_prefix: s
prefixes: {s: "https://example.org/ns/s#", linkml: "https://w3id.org/linkml/"}
default_range: string
imports: [linkml:types]
classes:
  Thing:
    slots: [hidden]
slots:
  hidden:
    required: true
    annotations: {internal: true}
"""


def test_an_internal_slot_adds_no_constraint_kind() -> None:
    # The shapes make an internal slot optional, so a required case on it has no verdict to agree on.
    view = SchemaView(INTERNAL_ONLY)
    thing = replace(Conformance.of(TOY), view=view, models={"Thing": BaseModel})
    assert K.REQUIRED not in thing.used_kinds(), "an internal slot is no public requirement"


def test_a_key_across_aggregates_is_no_unique_keys_constraint() -> None:
    """TC-03: the scoped key of Book has no validator and no shape; Grant's in-aggregate key keeps both."""
    assert K.UNIQUE_KEYS not in Conformance.of(TOY).class_kinds("Book"), "isbn_key is scoped"
    assert K.UNIQUE_KEYS in Conformance.of(METAMODEL).class_kinds("Grant"), "grant_key is not"


def test_a_key_across_aggregates_is_no_keyed_slot_validator_or_shape() -> None:
    """TC-03: no slot holding Books is keyed by isbn_key, and nothing generated mentions it."""
    toy = load_schema(TOY)
    # no toy slot holds Book objects, so a Shelf that does makes a regression of the filter visible
    toy.add_class(
        ClassDefinition(
            name="Shelf",
            attributes={
                "books": SlotDefinition(name="books", range="Book", multivalued=True, inlined=True)
            },
        )
    )
    keys = {
        key.unique_key_name
        for cls in toy.all_classes().values()
        for _, key in keyed_slots(toy, cls)
    }
    assert "isbn_key" not in keys, "isbn_key governs no slot"
    generated = ROOT / "tests" / "fixtures" / "library" / "generated"
    mentions = [
        p.name
        for p in generated.rglob("*")
        if p.is_file() and p.suffix in TEXT and "isbn_key" in p.read_text()
    ]
    assert mentions == [], "no generated validator, shape or model names isbn_key"
    grants = load_schema(METAMODEL)
    assert any(
        key.unique_key_name == "grant_key"
        for _, key in keyed_slots(grants, grants.get_class("TenantAccess"))
    ), "Grant's key is still a keyed slot"
