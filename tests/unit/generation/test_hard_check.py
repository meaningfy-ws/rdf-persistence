"""The hard check (task 1.6, PD-11, PD-23): IRIs, titles, descriptions, meanings, paths, mixins."""

from dataclasses import dataclass
from pathlib import Path

import pytest

from rdf_persistence.generation import steps
from rdf_persistence.generation.checks.hard import hard_problems
from rdf_persistence.generation.cli import main
from rdf_persistence.generation.generated.rp_generation import GenerationTarget, HardRule
from rdf_persistence.generation.pipeline import Step, generate
from rdf_persistence.services.schema import load_schema

from .conftest import ROOT_SCHEMA, Breaker

METAMODEL = Path(__file__).parents[3] / "rdf_persistence" / "model" / "rp.yaml"
GENERATION_MODEL = (
    Path(__file__).parents[3] / "rdf_persistence" / "generation" / "model" / "rp_generation.yaml"
)


def problems_of(root: Path) -> list[str]:
    return hard_problems(load_schema(root), root.parent)


@dataclass(frozen=True)
class Fault:
    """One planted fault: replace ``old`` by ``new`` in ``module``; ``rule`` must name ``element``."""

    rule: HardRule
    module: str
    old: str
    new: str
    element: str


FAULTS = (
    Fault(
        HardRule.DESCRIPTION,
        "books.yaml",
        "    description: The International Standard Book Number of the book.\n",
        "",
        "isbn",
    ),
    Fault(
        HardRule.DESCRIPTION,
        "books.yaml",
        "        description: Invented narrative.\n",
        "",
        "fiction",
    ),
    Fault(
        HardRule.DESCRIPTION,
        "books.yaml",
        "    description: The literary genres a book can belong to.\n",
        "",
        "Genre",
    ),
    Fault(HardRule.TITLE, "books.yaml", "    title: Book\n", "", "Book"),
    Fault(HardRule.TITLE, "books.yaml", "    title: Publication date\n", "", "published"),
    Fault(HardRule.MEANING, "books.yaml", "        meaning: schema:Fiction\n", "", "fiction"),
    Fault(HardRule.IRI, "books.yaml", "default_prefix: lib\n", "", "Genre"),
    Fault(HardRule.RP_PATH, "books.yaml", "      rp_path: books\n", "", "Book"),
    Fault(HardRule.RP_PATH, "scans.yaml", "      rp_path: scans\n", "", "Scan"),
    Fault(
        HardRule.DESCRIBED,
        "books.yaml",
        "    mixins: [Described]\n    slots: [text]",
        "    slots: [text]",
        "Note",
    ),
    Fault(
        HardRule.DESCRIBED,
        "scans.yaml",
        "[AggregateRoot, Described, Tracked, StoredFile]",
        "[AggregateRoot, Tracked, StoredFile]",
        "Scan",
    ),
    Fault(HardRule.ANNOTATION, "books.yaml", "database: tenant", "database: sytem", "Book"),
    Fault(HardRule.ANNOTATION, "library_tenant.yaml", "graph: meta", "graph: tenant", "Library"),
    Fault(
        HardRule.ANNOTATION, "books.yaml", "module_kind: domain", "module_kind: dommain", "books"
    ),
    Fault(HardRule.ANNOTATION, "books.yaml", "owned: true", "owned: maybe", "chapters"),
    Fault(
        HardRule.ANNOTATION, "books.yaml", "rp_unlabelled: true", "rp_unlabelled: sure", "Chapter"
    ),
)


def test_the_toy_library_passes(toy_copy: Path) -> None:
    assert problems_of(toy_copy / ROOT_SCHEMA) == [], "the toy library must pass its own hard check"


@pytest.mark.parametrize("root", [METAMODEL, GENERATION_MODEL], ids=["metamodel", "generation"])
def test_the_toolkits_own_schemas_pass(root: Path) -> None:
    assert problems_of(root) == [], f"{root.name} must pass the hard check"


@pytest.mark.parametrize("fault", FAULTS, ids=lambda f: f"{f.rule}-{f.element}")
def test_a_planted_fault_is_reported_with_its_rule_and_element(
    break_toy: Breaker, fault: Fault
) -> None:
    root = break_toy(fault.module, fault.old, fault.new)
    problems = problems_of(root)
    expected = f"[{fault.rule.value}] {fault.element}:"
    assert any(expected in problem for problem in problems), f"{expected!r} not in {problems}"


def test_a_fault_names_only_the_broken_element(break_toy: Breaker) -> None:
    root = break_toy(
        "books.yaml", "    description: The International Standard Book Number of the book.\n", ""
    )
    assert len(problems_of(root)) == 1, "one planted fault must give one problem"


def test_every_rule_has_a_row_in_the_table() -> None:
    assert {f.rule for f in FAULTS} == set(HardRule), "a hard rule has no planted fault"


def test_an_unlabelled_class_still_needs_the_described_mixin(break_toy: Breaker) -> None:
    root = break_toy(
        "books.yaml",
        "    mixins: [Described]\n    slots: [number, notes]",
        "    slots: [number, notes]",
    )
    expected = f"[{HardRule.DESCRIBED.value}] Chapter:"
    assert any(expected in p for p in problems_of(root)), "rp_unlabelled only relaxes the label"


def test_a_missing_default_prefix_names_only_elements_without_an_explicit_uri(
    break_toy: Breaker,
) -> None:
    problems = problems_of(break_toy("books.yaml", "default_prefix: lib\n", ""))
    assert len(problems) == 1, f"only the enum has no explicit URI: {problems}"


ISBN_DESCRIPTION = "    description: The International Standard Book Number of the book.\n"


def test_the_step_reports_a_slot_without_a_description_by_name(break_toy: Breaker) -> None:
    root = break_toy("books.yaml", ISBN_DESCRIPTION, "")
    target = GenerationTarget(schema_file=ROOT_SCHEMA, package="app.generated")
    found = generate([target], root.parent, (Step("hard check", steps.hard_check),), check=True)
    assert len(found) == 1, f"one broken slot, one line: {found}"
    assert "hard check" in found[0], "the line names the step"
    assert "isbn" in found[0], "the line names the slot"


def test_a_run_with_a_missing_description_exits_1_and_writes_nothing(
    break_toy: Breaker, capsys: pytest.CaptureFixture[str]
) -> None:
    root = break_toy("books.yaml", ISBN_DESCRIPTION, "")
    before = sorted(p.name for p in root.parent.iterdir())
    assert main(["--project", str(root.parent / "pyproject.toml")]) == 1, "wrong exit code"
    assert "isbn" in capsys.readouterr().err, "the slot is not named"
    assert sorted(p.name for p in root.parent.iterdir()) == before, "outputs were touched"
