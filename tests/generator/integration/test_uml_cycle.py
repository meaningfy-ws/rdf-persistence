"""IT-2 of uml-to-linkml (SPIKE-2, PD-14, PD-27): the converter's own import-cycle round trip.

Two UML packages whose classes refer to each other (``books`` <-> ``shelves``) must not become two
modules that import each other: ``rp-generate`` writes such modules without complaint, but the
generated package fails with a circular ``ImportError`` (see ``test_module_import_cycle.py``).
The converter writes the packages of a cycle as ONE module, named after the first package in path
order, and reports a ``merged-cycle`` line. Here the command runs on an Enterprise Architect file
built in ``tmp_path``, then ``rp-generate`` runs on its output and the generated package is
imported.
"""

import importlib
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
import yaml

from rdf_persistence_generation.cli import main as generate
from rdf_persistence_generation.uml.cli import main as uml2linkml
from tests.generator.uml_qea import QeaBuilder

PACKAGE = "cycle_app"
ROOT_NAME = "app"
LIBRARY = "MODEL/library"  # the subtree package by its path
PREFIXES = """\
schema_base: https://example.org/ns/library/
default_prefix: lib
version: "1"
prefixes:
  lib: https://example.org/ns/library#
"""
PYPROJECT = f"""\
[tool.rp-generate]
schema = "{ROOT_NAME}.yaml"
package = "{PACKAGE}.domain.generated"
python = "{PACKAGE}/domain/generated"
migrations = "migrations"
"""
MERGED_CYCLE = "merged-cycle"
FIRST_PACKAGE = "books"
SECOND_PACKAGE = "shelves"


def build_cyclic_library(path: Path) -> Path:
    """A ``.qea`` with ``books`` and ``shelves``: a Book and a Shelf that point at each other."""
    builder = QeaBuilder(path)
    model = builder.package("MODEL")
    library = builder.package("library", parent=model, note="The library model.")
    books = builder.package(FIRST_PACKAGE, parent=library, note="The books package.")
    shelves = builder.package(SECOND_PACKAGE, parent=library, note="The shelves package.")
    book = builder.cls(books, "lib:Book", stereotype="root", note="A book on a shelf.")
    shelf = builder.cls(
        shelves, "lib:Shelf", stereotype="root", note="A shelf that features a book."
    )
    builder.association(book, shelf, role="lib:shelf", card="0..1", note="The shelf of the book.")
    builder.association(shelf, book, role="lib:featured", card="0..1", note="The featured book.")
    return builder.finish()


@pytest.fixture
def project(tmp_path: Path) -> Iterator[Path]:
    """The project folder on ``sys.path``; the generated package is forgotten afterwards."""
    folder = tmp_path / "project"
    folder.mkdir()
    sys.path.insert(0, str(folder))
    yield folder
    sys.path.remove(str(folder))
    for name in [n for n in sys.modules if n.split(".")[0] == PACKAGE]:
        del sys.modules[name]
    importlib.invalidate_caches()


def convert_into(project: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Run ``rp-uml2linkml`` on the cyclic library into the project's model folder."""
    prefixes = tmp_path / "prefixes.yaml"
    prefixes.write_text(PREFIXES, encoding="utf-8")
    code = uml2linkml(
        [
            str(build_cyclic_library(tmp_path / "library.qea")),
            "--package",
            LIBRARY,
            "--prefixes",
            str(prefixes),
            "--out",
            str(project),
            "--root-name",
            ROOT_NAME,
        ]
    )
    assert code == 0, capsys.readouterr().err


def test_the_packages_of_a_cycle_become_one_module_with_a_merged_cycle_line(
    project: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    convert_into(project, tmp_path, capsys)

    modules = sorted(file.name for file in project.glob(f"{ROOT_NAME}_*.yaml"))
    merged = yaml.safe_load((project / f"{ROOT_NAME}_{FIRST_PACKAGE}.yaml").read_text("utf-8"))
    report = (project / f"{ROOT_NAME}.uml-report.txt").read_text(encoding="utf-8")
    assert modules == [f"{ROOT_NAME}_{FIRST_PACKAGE}.yaml"], (
        "one module, named after the first package"
    )
    assert sorted(merged["classes"]) == ["Book", "Shelf"], "the module holds both packages' classes"
    merged_lines = [line for line in report.splitlines() if line.startswith(MERGED_CYCLE)]
    assert len(merged_lines) == 1, "the report has exactly one merged-cycle line"
    assert FIRST_PACKAGE in merged_lines[0], "the line names the first package"
    assert SECOND_PACKAGE in merged_lines[0], "the line names the second package"


def test_the_merged_module_generates_and_the_package_imports(
    project: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    convert_into(project, tmp_path, capsys)

    (project / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")
    (project / PACKAGE / "domain").mkdir(parents=True)
    (project / PACKAGE / "__init__.py").write_text("")
    (project / PACKAGE / "domain" / "__init__.py").write_text("")
    assert generate(["--project", str(project / "pyproject.toml")]) == 0, capsys.readouterr().err

    generated = importlib.import_module(f"{PACKAGE}.domain.generated.{ROOT_NAME}_{FIRST_PACKAGE}")
    book = generated.Book(
        id="https://example.org/ns/library#book-1",
        label="A book",
        shelf="https://example.org/ns/library#shelf-1",
    )
    assert str(book.shelf) == "https://example.org/ns/library#shelf-1", (
        "the generated merged module builds a Book that refers to a Shelf"
    )
