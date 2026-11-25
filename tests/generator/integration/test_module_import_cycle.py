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
PLAQUE = """\
  Plaque:
    title: Plaque
    description: A plaque; a part owned by a shelf, declared beside the books.
    class_uri: lib:Plaque
    mixins: [Described]
"""
SHELF_WITH_PLAQUE = SHELF.replace("slots: [featured]", "slots: [featured, plaque]")
PLAQUE_SLOT = """\
  plaque:
    title: Plaque
    description: The plaque of the shelf; it lives in the shelf's graph.
    slot_uri: lib:plaque
    range: Plaque
    inlined: true
    annotations:
      owned: true
"""
ROOT_A = """\
  Root:
    title: Root
    description: A root in the first module, referred to from the second.
    class_uri: lib:Root
    mixins: [AggregateRoot, Described]
    annotations:
      rp_path: roots
      database: tenant
  Child:
    title: Child
    description: A root in the first module whose parent is in the second.
    class_uri: lib:Child
    is_a: Base
    annotations:
      rp_path: children
      database: tenant
"""
BASE_B = """\
  Base:
    title: Base
    description: A root in the second module, the parent of a class of the first.
    class_uri: lib:Base
    mixins: [AggregateRoot, Described]
    annotations:
      rp_path: bases
      database: tenant
  Holder:
    title: Holder
    description: A root in the second module that refers to a root of the first.
    class_uri: lib:Holder
    mixins: [AggregateRoot, Described]
    slots: [held]
    annotations:
      rp_path: holders
      database: tenant
"""
HELD_SLOT = """\
  held:
    title: Held
    description: The root the holder holds, another aggregate, stored as its IRI.
    slot_uri: lib:held
    range: Root
"""


def _root(name: str, parent: str | None = None) -> str:
    """A root class, optionally the child of ``parent`` (a class of another module)."""
    own = "    is_a: " + parent + "\n" if parent else "    mixins: [AggregateRoot, Described]\n"
    return (
        f"  {name}:\n    title: {name}\n    description: The root {name}.\n"
        f"    class_uri: lib:{name}\n{own}"
        f"    annotations:\n      rp_path: {name.lower()}s\n      database: tenant\n"
    )


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


@pytest.mark.parametrize("first", ["app_books", "app_shelves"])
def test_two_domain_modules_that_import_each_other_generate_and_import(
    importable: Path, capsys: pytest.CaptureFixture[str], first: str
) -> None:
    """G-1 (#208): modules that import each other write Python that loads in any order, and a
    class names a part of the other module (``Shelf.plaque``, a ``Plaque`` of ``app_books``)."""
    pyproject = _write_project(
        importable,
        {
            "app_books": _module("app_books", ("app_shelves",), BOOK + PLAQUE, SHELF_SLOT),
            "app_shelves": _module(
                "app_shelves",
                ("app_books",),
                SHELF_WITH_PLAQUE,
                FEATURED_SLOT + PLAQUE_SLOT,
            ),
        },
    )

    run_code, run_error = main(["--project", str(pyproject)]), capsys.readouterr().err
    check_code, check_error = (
        main(["--check", "--project", str(pyproject)]),
        capsys.readouterr().err,
    )

    assert "hard check" not in run_error, run_error
    assert run_code == 0, run_error
    assert check_code == 0, check_error
    modules = {
        name: importlib.import_module(f"{PACKAGE}.domain.generated.{name}")
        for name in (first, "app_books" if first == "app_shelves" else "app_shelves")
    }
    shelf = modules["app_shelves"].Shelf(
        id="https://example.org/ns/library#shelf-1",
        label="Front",
        plaque={"id": "https://example.org/ns/library#plaque-1", "label": "Gold"},
    )
    assert isinstance(shelf.plaque, modules["app_books"].Plaque), "the part was not built"
    assert shelf.plaque.label == "Gold", "the part lost its data"


@pytest.mark.parametrize("first", ["app_a", "app_b"])
def test_a_parent_in_one_module_and_a_reference_back_load_in_any_order(
    importable: Path, capsys: pytest.CaptureFixture[str], first: str
) -> None:
    """The half-load cycle (PD-3): ``app_a.Child`` has its parent in ``app_b`` (needed at load) and
    ``app_b.Holder`` refers back to ``app_a.Root`` (annotation only, deferred): it loads."""
    pyproject = _write_project(
        importable,
        {
            "app_a": _module("app_a", ("app_b",), ROOT_A, ""),
            "app_b": _module("app_b", ("app_a",), BASE_B, HELD_SLOT),
        },
    )

    code = main(["--project", str(pyproject)])

    assert code == 0, capsys.readouterr().err
    a = importlib.import_module(f"{PACKAGE}.domain.generated.{first}")
    other = "app_b" if first == "app_a" else "app_a"
    b = importlib.import_module(f"{PACKAGE}.domain.generated.{other}")
    modules = {first: a, other: b}
    holder = modules["app_b"].Holder(
        id="https://example.org/ns/library#holder-1",
        label="Holder",
        held="https://example.org/ns/library#root-1",
    )
    assert str(holder.held) == "https://example.org/ns/library#root-1", "the reference is lost"
    assert issubclass(modules["app_a"].Child, modules["app_b"].Base), "the parent is not applied"


def test_two_modules_whose_classes_inherit_from_each_other_are_refused(
    importable: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """PD-3: each module needs a parent from the other while it loads, so no order loads it:
    refused at the python step, naming both modules and both parents. D-5: files an earlier run
    wrote are left byte-identical (spec ``rp-generation`` scenario 3)."""
    pyproject = _write_project(
        importable,
        {
            "app_a": _module("app_a", ("app_b",), _root("Child", "Base") + _root("Root"), ""),
            "app_b": _module("app_b", ("app_a",), _root("Other") + _root("Base"), ""),
        },
    )
    first_code, first_error = main(["--project", str(pyproject)]), capsys.readouterr().err
    generated = importable / PACKAGE / "domain" / "generated"
    first = {file.name: file.read_bytes() for file in sorted(generated.iterdir()) if file.is_file()}
    assert first_code == 0, first_error
    assert first, "the first run wrote no file"

    (importable / "app_b.yaml").write_text(
        _module("app_b", ("app_a",), _root("Other", "Root") + _root("Base"), "")
    )
    code = main(["--project", str(pyproject)])
    error = capsys.readouterr().err

    assert code == 1, "a cycle that cannot load was accepted"
    assert any(" python: " in line for line in error.splitlines()), (
        f"no python: problem line: {error}"
    )
    for name in ("app_a", "app_b", "Root", "Base"):
        assert name in error, f"{name} is not named: {error}"
    second = {
        file.name: file.read_bytes() for file in sorted(generated.iterdir()) if file.is_file()
    }
    assert second == first, "a refused run changed the files the first run wrote"
