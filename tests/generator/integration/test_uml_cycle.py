"""IT-2 of uml-to-linkml (SPIKE-2, PD-14, PD-27): the converter's own import-cycle round trip.

Two UML packages whose classes refer to each other (``books`` <-> ``shelves``) become two modules
that import each other, one per package (generator-module-cycles, DEC-4); ``rp-generate`` writes
Python that loads (see ``test_module_import_cycle.py``). Here the command runs on an Enterprise
Architect file built in ``tmp_path``, then ``rp-generate`` runs on its output and the generated
package is imported. Packages of different kinds in a cycle convert, and the boundary check
refuses them.
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


def build_cyclic_library(
    path: Path, first: str = FIRST_PACKAGE, first_kind: str | None = None
) -> Path:
    """A ``.qea`` with ``first`` and ``shelves``: a Book and a Shelf that point at each other.

    ``first_kind`` tags the first package ``module_kind`` (a package of another kind than its
    partner, DEC-4).
    """
    builder = QeaBuilder(path)
    model = builder.package("MODEL")
    library = builder.package("library", parent=model, note="The library model.")
    books = builder.package(first, parent=library, note="The first package.")
    shelves = builder.package(SECOND_PACKAGE, parent=library, note="The shelves package.")
    if first_kind:
        builder.tag(builder.package_element(books), "module_kind", first_kind)
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


def convert_into(
    project: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    first: str = FIRST_PACKAGE,
    first_kind: str | None = None,
) -> None:
    """Run ``rp-uml2linkml`` on the cyclic library into the project's model folder."""
    prefixes = tmp_path / "prefixes.yaml"
    prefixes.write_text(PREFIXES, encoding="utf-8")
    code = uml2linkml(
        [
            str(build_cyclic_library(tmp_path / "library.qea", first, first_kind)),
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


def _module_text(project: Path, package: str) -> dict:
    return yaml.safe_load((project / f"{ROOT_NAME}_{package}.yaml").read_text("utf-8"))


def _set_up_package(project: Path) -> None:
    (project / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")
    (project / PACKAGE / "domain").mkdir(parents=True)
    (project / PACKAGE / "__init__.py").write_text("")
    (project / PACKAGE / "domain" / "__init__.py").write_text("")


def test_the_packages_of_a_cycle_become_two_modules_that_import_each_other(
    project: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    convert_into(project, tmp_path, capsys)

    modules = sorted(file.name for file in project.glob(f"{ROOT_NAME}_*.yaml"))
    books = _module_text(project, FIRST_PACKAGE)
    shelves = _module_text(project, SECOND_PACKAGE)
    report = (project / f"{ROOT_NAME}.uml-report.txt").read_text(encoding="utf-8")
    assert modules == [
        f"{ROOT_NAME}_{FIRST_PACKAGE}.yaml",
        f"{ROOT_NAME}_{SECOND_PACKAGE}.yaml",
    ], "one module per package"
    assert sorted(books["classes"]) == ["Book"], "the first module holds its own class only"
    assert sorted(shelves["classes"]) == ["Shelf"], "the second module holds its own class only"
    assert f"{ROOT_NAME}_{SECOND_PACKAGE}" in books["imports"], "the first imports the second"
    assert f"{ROOT_NAME}_{FIRST_PACKAGE}" in shelves["imports"], "the second imports the first"
    assert MERGED_CYCLE not in report, f"the report has a merged-cycle line: {report}"


def test_the_converted_cycle_generates_and_the_package_imports(
    project: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    convert_into(project, tmp_path, capsys)

    _set_up_package(project)
    assert generate(["--project", str(project / "pyproject.toml")]) == 0, capsys.readouterr().err

    importlib.import_module(f"{PACKAGE}.domain.generated.{ROOT_NAME}_{SECOND_PACKAGE}")
    books = importlib.import_module(f"{PACKAGE}.domain.generated.{ROOT_NAME}_{FIRST_PACKAGE}")
    book = books.Book(
        id="https://example.org/ns/library#book-1",
        label="A book",
        shelf="https://example.org/ns/library#shelf-1",
    )
    assert str(book.shelf) == "https://example.org/ns/library#shelf-1", (
        "a Book of the first module refers to a Shelf of the second"
    )


def test_a_converted_cycle_between_kinds_is_refused_by_the_boundary_check(
    project: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Spec scenario "packages of different kinds that refer to each other"."""
    convert_into(project, tmp_path, capsys, first="library", first_kind="access")
    capsys.readouterr()

    _set_up_package(project)
    code = generate(["--project", str(project / "pyproject.toml")])
    error = capsys.readouterr().err

    assert code == 1, f"a domain module importing an access one was accepted: {error}"
    lines = [line for line in error.splitlines() if "boundary check" in line]
    assert lines, f"no boundary check line: {error}"
    for name in (f"{ROOT_NAME}_shelves", f"{ROOT_NAME}_library"):
        assert any(name in line for line in lines), f"{name} is not named: {error}"
