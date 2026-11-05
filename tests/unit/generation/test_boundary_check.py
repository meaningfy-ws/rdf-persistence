"""The boundary check (task 1.7, PD-23): ownership of the aggregate's parts and module kinds."""

from dataclasses import dataclass
from pathlib import Path

import pytest

from rdf_persistence.generation import steps
from rdf_persistence.generation.checks.boundary import boundary_problems
from rdf_persistence.generation.cli import main
from rdf_persistence.generation.generated.rp_generation import BoundaryRule, GenerationTarget
from rdf_persistence.generation.pipeline import Step, generate
from rdf_persistence.services.schema import load_schema

from .conftest import ROOT_SCHEMA, Breaker

MODEL_DIR = Path(__file__).parents[3] / "rdf_persistence"
METAMODEL = MODEL_DIR / "model" / "rp.yaml"
GENERATION_MODEL = MODEL_DIR / "generation" / "model" / "rp_generation.yaml"

NOTES_OWNED = "    range: Note\n    multivalued: true\n    inlined_as_list: true\n    annotations:\n      owned: true\n"
NOTES_REFERENCED = "    range: Note\n    multivalued: true\n    inlined_as_list: true\n"
BOOK_SLOTS = "slots: [isbn, authors, published, genre, chapters]"
BOOK_IMPORTS = "  - rdf_persistence/model/rp_annotations\nannotations:\n  module_kind: domain"
ACCESS_IMPORT = "  - rdf_persistence/model/rp_annotations\n  - library_access\nannotations:\n  module_kind: domain"
TENANCY_IMPORT = "  - rdf_persistence/model/rp_annotations\n  - rdf_persistence/model/rp_tenancy\nannotations:\n  module_kind: domain"


def problems_of(root: Path) -> list[str]:
    return boundary_problems(load_schema(root), root.parent)


@dataclass(frozen=True)
class Edit:
    """Replace the first ``old`` by ``new`` in ``module``."""

    module: str
    old: str
    new: str


@dataclass(frozen=True)
class Fault:
    """Planted edits; ``rule`` must name ``element`` and every word of ``mentions``."""

    rule: BoundaryRule
    edits: tuple[Edit, ...]
    element: str
    mentions: tuple[str, ...] = ()


FAULTS = (
    Fault(BoundaryRule.Ownership, (Edit("books.yaml", NOTES_OWNED, NOTES_REFERENCED),), "Note"),
    Fault(
        BoundaryRule.Reference,
        (Edit("books.yaml", NOTES_OWNED, NOTES_REFERENCED),),
        "notes",
        ("Note",),
    ),
    Fault(
        BoundaryRule.Ownership,
        (Edit("books.yaml", BOOK_SLOTS, "slots: [isbn, authors, published, genre]"),),
        "Chapter",
    ),
    Fault(
        BoundaryRule.Ownership,
        (Edit("library_tenant.yaml", "      graph: meta\n", ""),),
        "Library",
    ),
    Fault(
        BoundaryRule.Reference,
        (Edit("scans.yaml", "range: Book", "range: Chapter"),),
        "scan_of",
        ("Chapter",),
    ),
    Fault(
        BoundaryRule.Module_kind,
        (Edit("books.yaml", BOOK_IMPORTS, ACCESS_IMPORT),),
        "books",
        ("library_access", "access"),
    ),
    Fault(
        BoundaryRule.Module_kind,
        (Edit("books.yaml", BOOK_IMPORTS, TENANCY_IMPORT),),
        "books",
        ("rp_tenancy",),
    ),
    Fault(
        BoundaryRule.Module_kind,
        (
            Edit("books.yaml", BOOK_IMPORTS, ACCESS_IMPORT),
            Edit("library_access.yaml", "module_kind: access", "module_kind: technical"),
        ),
        "books",
        ("library_access", "technical"),
    ),
)

PASSING = (
    pytest.param((Edit("scans.yaml", "range: Book", "range: Principal"),), id="reference-by-iri"),
    pytest.param(
        (Edit("scans.yaml", "slots: [scan_of]", "slots: [scan_of, chapters]"),),
        id="owned-by-two-roots",
    ),
)


def plant(break_toy: Breaker, edits: tuple[Edit, ...]) -> Path:
    root = break_toy(*(edits[0].module, edits[0].old, edits[0].new))
    for edit in edits[1:]:
        root = break_toy(edit.module, edit.old, edit.new)
    return root


def test_the_toy_library_passes(toy_copy: Path) -> None:
    assert problems_of(toy_copy / ROOT_SCHEMA) == [], "the toy library must pass its boundary check"


@pytest.mark.parametrize("root", [METAMODEL, GENERATION_MODEL], ids=["metamodel", "generation"])
def test_the_toolkits_own_schemas_pass(root: Path) -> None:
    assert problems_of(root) == [], f"{root.name} must pass the boundary check"


@pytest.mark.parametrize("fault", FAULTS, ids=lambda f: f"{f.rule}-{f.element}-{len(f.edits)}")
def test_a_planted_fault_is_reported_with_its_rule_and_element(
    break_toy: Breaker, fault: Fault
) -> None:
    problems = problems_of(plant(break_toy, fault.edits))
    expected = f"[{fault.rule.value}] {fault.element}:"
    matching = [p for p in problems if expected in p]
    assert matching, f"{expected!r} not in {problems}"
    for word in fault.mentions:
        assert any(word in p for p in matching), f"{word!r} is not named in {matching}"


@pytest.mark.parametrize("edits", PASSING)
def test_an_allowed_variant_passes(break_toy: Breaker, edits: tuple[Edit, ...]) -> None:
    assert problems_of(plant(break_toy, edits)) == [], "this variant is allowed"


def test_every_rule_has_a_row_in_the_table() -> None:
    assert {f.rule for f in FAULTS} == set(BoundaryRule), "a boundary rule has no planted fault"


def test_a_domain_module_importing_the_access_module_names_both_modules(
    break_toy: Breaker, capsys: pytest.CaptureFixture[str]
) -> None:
    root = break_toy("books.yaml", BOOK_IMPORTS, ACCESS_IMPORT)
    target = GenerationTarget(schema_file=ROOT_SCHEMA, package="app.generated")
    found = generate(
        [target], root.parent, (Step("boundary check", steps.boundary_check),), check=True
    )
    assert len(found) == 1, f"one bad import, one line: {found}"
    assert "books" in found[0], "the importing module is not named"
    assert "library_access" in found[0], "the imported module is not named"
    before = sorted(p.name for p in root.parent.iterdir())
    assert main(["--project", str(root.parent / "pyproject.toml")]) == 1, "wrong exit code"
    assert "library_access" in capsys.readouterr().err, "the CLI does not name the imported module"
    assert sorted(p.name for p in root.parent.iterdir()) == before, "outputs were touched"


def test_check_mode_runs_the_boundary_check(break_toy: Breaker) -> None:
    root = break_toy("books.yaml", NOTES_OWNED, NOTES_REFERENCED)
    assert main(["--project", str(root.parent / "pyproject.toml"), "--check"]) == 1, (
        "--check skipped the boundary check"
    )
