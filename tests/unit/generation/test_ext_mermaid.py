"""Step 7 (D-8, PD-25): one Mermaid class diagram per module, marking roots and owned parts."""

from pathlib import Path

import pytest

from rdf_persistence.generation.steps import DIAGRAMS_STEP

from .golden import TOY_TARGET, assert_matches_toy, run_toy


@pytest.fixture(scope="module")
def rendered(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return run_toy(DIAGRAMS_STEP, tmp_path_factory.mktemp("diagrams"))


@pytest.fixture(scope="module")
def staged(rendered: Path) -> Path:
    return rendered / str(TOY_TARGET.diagrams)


def block(staged: Path, module: str, name: str) -> str:
    """The lines of ``class <name>`` in a module's diagram, up to its closing brace."""
    lines = (staged / f"{module}.mmd").read_text(encoding="utf-8").splitlines()
    start = lines.index(f"    class {name} {{")
    return "\n".join(lines[start : lines.index("    }", start) + 1])


def test_the_output_equals_the_committed_tree(rendered: Path) -> None:
    assert_matches_toy(rendered, "generated/diagrams/*.mmd")


def test_one_diagram_per_module_of_the_application(staged: Path) -> None:
    names = sorted(p.name for p in staged.iterdir())
    assert names == [
        "books.mmd",
        "library_access.mmd",
        "library_tenant.mmd",
        "scans.mmd",
        "templates.mmd",
    ], "the modules that define classes, and not the metamodel's"


@pytest.mark.parametrize(
    ("module", "name", "stereotype"),
    [
        ("books", "Book", "root"),
        ("books", "Chapter", "owned"),
        ("books", "Note", "owned"),
        ("scans", "Scan", "root"),
        ("library_tenant", "Library", "root"),
        ("library_access", "LibraryAccess", "root"),
    ],
)
def test_roots_and_owned_parts_are_marked(
    staged: Path, module: str, name: str, stereotype: str
) -> None:
    assert f"<<{stereotype}>>" in block(staged, module, name), f"{name} is <<{stereotype}>>"


def test_ownership_is_a_composition_and_a_reference_an_arrow(staged: Path) -> None:
    books = (staged / "books.mmd").read_text(encoding="utf-8")
    scans = (staged / "scans.mmd").read_text(encoding="utf-8")
    assert '    Book "1" *-- "*" Chapter : chapters' in books, "a root composes its chapters"
    assert '    Chapter "1" *-- "*" Note : notes' in books, "a chapter composes its notes"
    assert '    Scan "1" --> "0..1" Book : scan_of' in scans, "a scan refers to its book"


def test_a_class_of_another_module_is_shown_by_name_only(staged: Path) -> None:
    scans = (staged / "scans.mmd").read_text(encoding="utf-8").splitlines()
    assert "    class Book" in scans, "the book is named"
    assert not any(line.startswith("    class Book {") for line in scans), "and not described"
    assert "    class Chapter" not in scans, "nothing else of books is drawn"


def test_an_internal_slot_is_not_drawn(staged: Path) -> None:
    assert "file_key" not in "".join(p.read_text(encoding="utf-8") for p in staged.iterdir())


def test_an_unconfigured_target_writes_nothing(tmp_path: Path) -> None:
    run_toy(DIAGRAMS_STEP, tmp_path, TOY_TARGET.model_copy(update={"diagrams": None}))
    assert not list(tmp_path.iterdir()), "no diagrams folder, no output"


def test_the_output_is_reproducible(staged: Path, tmp_path: Path) -> None:
    again = run_toy(DIAGRAMS_STEP, tmp_path) / str(TOY_TARGET.diagrams)
    first = {p.name: p.read_bytes() for p in staged.iterdir()}
    assert first == {p.name: p.read_bytes() for p in again.iterdir()}, "two runs differ"
