"""The dependence check (dependent-aggregates PD-12, DEC-7; attack A-10, A-12).

One schema per row under ``tests/generator/fixtures/dependence``: each refusal names its class and
slot (a cycle, its classes in order), and is made by one check, so a table row fails when that check
is removed.
"""

from dataclasses import dataclass
from pathlib import Path

import pytest

from rdf_persistence_generation.checks import dependence
from rdf_persistence_generation.generated.rp_generation import BoundaryRule

from .checks import boundary_problems

FIXTURES = Path(__file__).parents[1] / "fixtures" / "dependence"
RULE = f"[{BoundaryRule.DEPENDENCE.value}]"


@dataclass(frozen=True)
class Refusal:
    """A schema the check refuses: the fixture, the class it names, the words the line holds, and the check that finds it."""

    fixture: str
    element: str
    mentions: tuple[str, ...]
    check: str


REFUSALS = (
    Refusal("refused_not_required", "Result", ("run", "not required"), "_requirement_problems"),
    Refusal("refused_multivalued", "Result", ("runs", "multivalued"), "_cardinality_problems"),
    Refusal("refused_over_non_root", "Result", ("plain", "Plain"), "_range_problems"),
    Refusal(
        "refused_over_toolkit_written_root",
        "Result",
        ("ledger", "Ledger", "toolkit"),
        "_range_problems",
    ),
    Refusal(
        "refused_over_tenant_root", "Result", ("estate", "Estate", "tenant root"), "_range_problems"
    ),
    Refusal("refused_slot_missing", "Result", ("owner", "not a slot"), "_missing_slot_problems"),
    Refusal("refused_on_non_root", "Note", ("run", "not a served"), "_placement_problems"),
    Refusal(
        "refused_re_annotation",
        "Metric",
        ("batch", "run", "another slot"),
        "_re_annotation_problems",
    ),
    Refusal(
        "refused_relaxed_by_slot_usage",
        "Artefact",
        ("run", "not required"),
        "_requirement_problems",
    ),
    Refusal(
        "refused_cycle_two", "Alpha", ("Alpha -> Beta -> Alpha", "alpha", "beta"), "_cycle_problems"
    ),
    Refusal("refused_cycle_self", "Node", ("Node -> Node", "parent"), "_cycle_problems"),
    Refusal(
        "refused_cycle_through_subclass",
        "Xray",
        ("Xray -> Zulu -> Xray", "yankee", "xray"),
        "_cycle_problems",
    ),
    Refusal("refused_cycle_own_superclass", "Leaf", ("Leaf -> Leaf", "parent"), "_cycle_problems"),
)
ACCEPTED = ("ok_served_root", "ok_abstract_range", "ok_abstract_base", "ok_chain")


def dependence_lines(fixture: str) -> list[str]:
    """The lines of the boundary check of one fixture that carry the dependence rule."""
    return [p for p in boundary_problems(FIXTURES / f"{fixture}.yaml") if RULE in p]


@pytest.mark.parametrize("refusal", REFUSALS, ids=lambda r: r.fixture)
def test_a_refused_schema_gives_one_problem_naming_its_class_and_slot(refusal: Refusal) -> None:
    lines = dependence_lines(refusal.fixture)
    assert len(lines) == 1, f"one planted fault, one dependence problem: {lines}"
    assert lines[0].startswith(f"{RULE} {refusal.element}:"), f"wrong element: {lines[0]}"
    for word in refusal.mentions:
        assert word in lines[0], f"{word!r} is not named in {lines[0]}"


@pytest.mark.parametrize("fixture", ACCEPTED)
def test_an_accepted_schema_passes_the_whole_boundary_check(fixture: str) -> None:
    found = boundary_problems(FIXTURES / f"{fixture}.yaml")
    assert found == [], f"{fixture} must pass: {found}"


@pytest.mark.parametrize("refusal", REFUSALS, ids=lambda r: r.fixture)
def test_a_refusal_is_lost_when_its_check_is_removed(
    refusal: Refusal, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert hasattr(dependence, refusal.check), f"no check named {refusal.check}"
    monkeypatch.setattr(dependence, refusal.check, lambda *args, **kwargs: iter(()))  # X3
    lines = dependence_lines(refusal.fixture)
    assert lines == [], f"{refusal.check} is not what refuses {refusal.fixture}: {lines}"


def test_every_fixture_on_disk_has_a_row() -> None:
    on_disk = {path.stem for path in FIXTURES.glob("*.yaml")}
    rows = {r.fixture for r in REFUSALS} | set(ACCEPTED)
    assert on_disk == rows, f"fixtures without a row, or rows without a fixture: {on_disk ^ rows}"
