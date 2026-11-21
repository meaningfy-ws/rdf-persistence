"""SPIKE-2 of uml-to-linkml (PD-14): two domain modules that import each other generate and import.

The converter will write one module per UML package, and real packages refer to each other in
cycles. This guards the question: does ``rp-generate`` accept ``app_books`` <-> ``app_shelves``?
The same two classes in ONE module (the PD-27 fallback) are generated alongside as the control.
"""

import importlib
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from rdf_persistence_generation.cli import main

PACKAGE = "cycle_app"
HEADER = """\
id: https://example.org/ns/library/{name}
name: {name}
title: {title}
description: {description}
prefixes:
  lib: https://example.org/ns/library#
  linkml: https://w3id.org/linkml/
  rp: https://meaningfy.ws/ns/rdf-persistence#
default_prefix: lib
default_range: string
imports:
  - linkml:types
  - rdf_persistence/model/rp_core
  - rdf_persistence/model/rp_annotations
{extra_imports}annotations:
  module_kind: domain
"""
BOOK = """\
  Book:
    title: Book
    description: A book; an aggregate root that stands on a shelf.
    class_uri: lib:Book
    mixins: [AggregateRoot, Described]
    slots: [shelf]
    annotations:
      rp_path: books
      database: tenant
"""
SHELF = """\
  Shelf:
    title: Shelf
    description: A shelf; an aggregate root that features a book.
    class_uri: lib:Shelf
    mixins: [AggregateRoot, Described]
    slots: [featured]
    annotations:
      rp_path: shelves
      database: tenant
"""
SHELF_SLOT = """\
  shelf:
    title: Shelf
    description: The shelf the book stands on, another aggregate, stored as its IRI.
    slot_uri: lib:shelf
    range: Shelf
"""
FEATURED_SLOT = """\
  featured:
    title: Featured
    description: The book the shelf features, another aggregate, stored as its IRI.
    slot_uri: lib:featured
    range: Book
"""
PYPROJECT = f"""\
[tool.rp-generate]
schema = "app.yaml"
package = "{PACKAGE}.domain.generated"
python = "{PACKAGE}/domain/generated"
migrations = "migrations"
"""


def _module(name: str, imports: tuple[str, ...], classes: str, slots: str) -> str:
    extra = "".join(f"  - {other}\n" for other in imports)
    header = HEADER.format(
        name=name,
        title=f"{name} module",
        description=f"The {name} module of the import-cycle spike.",
        extra_imports=extra,
    )
    return f"{header}\nclasses:\n{classes}\nslots:\n{slots}"


def _write_project(folder: Path, modules: dict[str, str]) -> Path:
    """Write the project: its pyproject, a root schema importing the modules, the modules."""
    folder.mkdir()
    (folder / "pyproject.toml").write_text(PYPROJECT)
    root = HEADER.format(
        name="app",
        title="Cycle application",
        description="The root schema of the import-cycle spike.",
        extra_imports="".join(f"  - {name}\n" for name in modules),
    ).removesuffix("annotations:\n  module_kind: domain\n")
    root = root.replace("title: Cycle application\n", 'title: Cycle application\nversion: "1"\n')
    (folder / "app.yaml").write_text(root)
    (folder / PACKAGE / "domain").mkdir(parents=True)
    (folder / PACKAGE / "__init__.py").write_text("")
    (folder / PACKAGE / "domain" / "__init__.py").write_text("")
    for name, text in modules.items():
        (folder / f"{name}.yaml").write_text(text)
    return folder / "pyproject.toml"


@pytest.fixture
def importable(tmp_path: Path) -> Iterator[Path]:
    """``tmp_path`` on ``sys.path`` for the test; the generated package is forgotten afterwards."""
    sys.path.insert(0, str(tmp_path / "project"))
    yield tmp_path / "project"
    sys.path.remove(str(tmp_path / "project"))
    for name in [n for n in sys.modules if n.split(".")[0] == PACKAGE]:
        del sys.modules[name]
    importlib.invalidate_caches()


def _build_a_book_on_a_shelf() -> None:
    books = importlib.import_module(f"{PACKAGE}.domain.generated.app_books")
    book = books.Book(
        id="https://example.org/ns/library#book-1",
        label="Dune",
        shelf="https://example.org/ns/library#shelf-1",
    )
    assert (book.label, str(book.shelf)) == ("Dune", "https://example.org/ns/library#shelf-1")


def test_two_domain_modules_that_import_each_other_are_refused_by_the_import_check(
    importable: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """SPIKE-2 (PD-14): the split modules import each other at module level, so the package fails
    with a circular ImportError (#208; the converter merges a cycle into one module, PD-27). The
    run and the check import what was written and say so, naming the module (#242)."""
    pyproject = _write_project(
        importable,
        {
            "app_books": _module("app_books", ("app_shelves",), BOOK, SHELF_SLOT),
            "app_shelves": _module("app_shelves", ("app_books",), SHELF, FEATURED_SLOT),
        },
    )

    run_code, run_error = main(["--project", str(pyproject)]), capsys.readouterr().err
    check_code, check_error = (
        main(["--check", "--project", str(pyproject)]),
        capsys.readouterr().err,
    )

    for code, error in ((run_code, run_error), (check_code, check_error)):
        assert code == 1, "a package that cannot be imported passed"
        assert "import check" in error, error
        assert f"{PACKAGE}.domain.generated.app_books" in error, "the module is not named"
        assert "ImportError" in error, "the exception is not named"


def test_the_same_two_classes_in_one_module_generate_and_import(
    importable: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The PD-27 fallback: the packages of a cycle merged into one module."""
    merged = _module("app_books", (), BOOK + SHELF, SHELF_SLOT + FEATURED_SLOT)
    pyproject = _write_project(importable, {"app_books": merged})

    code = main(["--project", str(pyproject)])

    assert code == 0, capsys.readouterr().err
    _build_a_book_on_a_shelf()
