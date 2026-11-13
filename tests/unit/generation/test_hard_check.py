"""The hard check (task 1.6, PD-11, PD-23): IRIs, titles, descriptions, meanings, paths, mixins."""

from dataclasses import dataclass
from pathlib import Path

import pytest

from rdf_persistence.generation import steps
from rdf_persistence.generation.checks.hard import hard_problems
from rdf_persistence.generation.cli import main
from rdf_persistence.generation.generated.rp_generation import GenerationTarget, HardRule
from rdf_persistence.generation.pipeline import generate
from rdf_persistence.generation.problems import format_problem
from rdf_persistence.services.schema import load_schema

from .conftest import ROOT_SCHEMA, Breaker

METAMODEL = Path(__file__).parents[3] / "rdf_persistence" / "model" / "rp.yaml"
GENERATION_MODEL = (
    Path(__file__).parents[3] / "rdf_persistence" / "generation" / "model" / "rp_generation.yaml"
)


def problems_of(root: Path) -> list[str]:
    return [format_problem(p) for p in hard_problems(load_schema(root), root.parent)]


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
        "    mixins: [Described]\n    slots: [text, about]",
        "    slots: [text, about]",
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
    Fault(HardRule.ANNOTATION, "books.yaml", "rp_path: books", "rp_path: Books", "Book"),
    Fault(HardRule.ANNOTATION, "books.yaml", "rp_path: books", "rp_path: books/all", "Book"),
    Fault(HardRule.ANNOTATION, "books.yaml", "rp_path: books", "rp_path: ''", "Book"),
    Fault(  # T-9: there is no value that opts a file root back into generic writes
        HardRule.ANNOTATION,
        "scans.yaml",
        "rp_path: scans",
        "rp_path: scans\n      rp_writes: generic",
        "Scan",
    ),
    Fault(
        HardRule.ANNOTATION,
        "books.yaml",
        "rp_path: books",
        "rp_path: books\n      rp_iri_type: Bk",
        "Book",
    ),
    # an owned class and a root with one type, and a reserved type
    Fault(
        HardRule.IRI_TYPE,
        "books.yaml",
        "rp_path: books",
        "rp_path: books\n      rp_iri_type: chapter",
        "Book",
    ),
    Fault(
        HardRule.IRI_TYPE,
        "books.yaml",
        "rp_path: books",
        "rp_path: books\n      rp_iri_type: graph",
        "Book",
    ),
    # an attribute of a class (Note.shade) gets the rules of a slot
    Fault(
        HardRule.DESCRIPTION,
        "books.yaml",
        "        description: The colour of the note's paper.\n",
        "",
        "shade",
    ),
    Fault(HardRule.TITLE, "books.yaml", "        title: Shade\n", "", "shade"),
    Fault(HardRule.IRI, "books.yaml", "default_prefix: lib\n", "", "shade"),
    Fault(HardRule.ANNOTATION, "books.yaml", "owned: false", "owned: maybe", "shade"),
    Fault(
        HardRule.UNIQUE_KEY,
        "books.yaml",
        "    slots: [text, about]\n",
        "    slots: [text, about]\n    unique_keys:\n      bad key:\n        unique_key_slots: [text]\n",
        "Note",
    ),
    Fault(
        HardRule.UNIQUE_KEY,
        "books.yaml",
        "    slots: [text, about]\n",
        "    slots: [text, about]\n    unique_keys:\n      a-b:\n        unique_key_slots: [text]\n",
        "Note",
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
    assert len(problems) == 2, f"only the enum and the attribute have no explicit URI: {problems}"


ISBN_DESCRIPTION = "    description: The International Standard Book Number of the book.\n"


def test_the_step_reports_a_slot_without_a_description_by_name(break_toy: Breaker) -> None:
    root = break_toy("books.yaml", ISBN_DESCRIPTION, "")
    target = GenerationTarget(schema_file=ROOT_SCHEMA, package="app.generated")
    found = generate([target], root.parent, (steps.HARD_STEP,), check=True)
    assert len(found) == 1, f"one broken slot, one line: {found}"
    line = format_problem(found[0])
    assert "hard check" in line, "the line names the step"
    assert "isbn" in line, "the line names the slot"


def test_a_run_with_a_missing_description_exits_1_and_writes_nothing(
    break_toy: Breaker, capsys: pytest.CaptureFixture[str]
) -> None:
    root = break_toy("books.yaml", ISBN_DESCRIPTION, "")
    before = sorted(p.name for p in root.parent.iterdir())
    assert main(["--project", str(root.parent / "pyproject.toml")]) == 1, "wrong exit code"
    assert "isbn" in capsys.readouterr().err, "the slot is not named"
    assert sorted(p.name for p in root.parent.iterdir()) == before, "outputs were touched"


def test_the_rp_path_pattern_is_checked_when_the_schema_does_not_import_the_metamodel(
    tmp_path: Path,
) -> None:
    root = tmp_path / "bare.yaml"
    root.write_text(
        "id: https://example.org/bare\nname: bare\nprefixes:\n  linkml: https://w3id.org/linkml/\n"
        "imports:\n  - linkml:types\nclasses:\n  Thing:\n    annotations:\n      rp_path: Not A Path\n",
        encoding="utf-8",
    )
    problems = problems_of(root)
    assert any(f"[{HardRule.ANNOTATION.value}] Thing:" in p for p in problems), problems


def _bare_schema(tmp_path: Path, classes: dict[str, str | None]) -> Path:
    """A schema that does not import the metamodel, with the given root classes (name -> rp_iri_type)."""
    body = ""
    for name, iri_type in classes.items():
        tag = f"      rp_iri_type: {iri_type}\n" if iri_type else ""
        body += (
            f"  {name}:\n    title: {name}\n    description: A {name}.\n"
            f"    is_a: AggregateRoot\n    annotations:\n      rp_path: {name.lower()}\n{tag}"
        )
    root = tmp_path / "bare.yaml"
    root.write_text(
        "id: https://example.org/bare\nname: bare\ndefault_prefix: ex\ntitle: Bare\n"
        "description: A bare schema.\nprefixes:\n  linkml: https://w3id.org/linkml/\n"
        "  ex: https://example.org/bare/\nimports:\n  - linkml:types\nclasses:\n"
        "  AggregateRoot:\n    title: Root\n    description: A root.\n    abstract: true\n" + body,
        encoding="utf-8",
    )
    return root


def _iri_type_problems(root: Path) -> list[str]:
    return [p for p in problems_of(root) if f"[{HardRule.IRI_TYPE.value}]" in p]


def test_two_classes_with_one_explicit_type_are_refused_naming_both(tmp_path: Path) -> None:
    problems = _iri_type_problems(_bare_schema(tmp_path, {"Alpha": "thing", "Beta": "thing"}))
    assert len(problems) == 1 and "Alpha" in problems[0] and "Beta" in problems[0], problems


def test_a_type_equal_to_another_classes_kebab_name_is_refused(tmp_path: Path) -> None:
    problems = _iri_type_problems(
        _bare_schema(tmp_path, {"OntologyFile": None, "Other": "ontology-file"})
    )
    assert len(problems) == 1 and "OntologyFile" in problems[0] and "Other" in problems[0], problems


@pytest.mark.parametrize("word", ["content", "graph", "parts", "access", "meta", "registry"])
def test_a_reserved_type_is_refused(tmp_path: Path, word: str) -> None:
    problems = _iri_type_problems(_bare_schema(tmp_path, {"Alpha": word}))
    assert len(problems) == 1 and "Alpha" in problems[0] and word in problems[0], problems


def test_a_class_named_like_a_reserved_word_is_refused(tmp_path: Path) -> None:
    assert len(_iri_type_problems(_bare_schema(tmp_path, {"Graph": None}))) == 1


def test_distinct_types_pass(tmp_path: Path) -> None:
    root = _bare_schema(tmp_path, {"OntologyFile": None, "Alpha": "alpha-1"})
    kinds = (HardRule.IRI_TYPE.value, HardRule.ANNOTATION.value)
    assert [p for p in problems_of(root) if p.startswith(tuple(f"[{k}]" for k in kinds))] == []


def test_a_bad_iri_type_pattern_is_refused_when_the_schema_does_not_import_the_metamodel(
    tmp_path: Path,
) -> None:
    problems = problems_of(_bare_schema(tmp_path, {"Alpha": "Not A Type"}))
    assert any(f"[{HardRule.ANNOTATION.value}] Alpha:" in p for p in problems), problems
