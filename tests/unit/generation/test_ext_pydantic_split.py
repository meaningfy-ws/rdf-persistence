"""Golden test and behaviour of the split gen-pydantic extension (PD-24, PD-25)."""

import ast
import importlib
import shutil
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic import ValidationError

from rdf_persistence.domain.generated.rp_files import StoredFile
from rdf_persistence.generation.extensions.pydantic_split import (
    TOOLKIT_PACKAGE,
    metamodel_module,
    render_modules,
)

from .golden import assert_matches_golden

TOY_MODULES = [
    "__init__.py",
    "books.py",
    "library.py",
    "library_access.py",
    "library_tenant.py",
    "scans.py",
]


def parse(folder: Path, module: str) -> ast.Module:
    return ast.parse((folder / module).read_text(encoding="utf-8"))


def imports_from(tree: ast.Module, module: str) -> set[str]:
    return {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and "." * node.level + (node.module or "") == module
        for alias in node.names
    }


def enum_members(tree: ast.Module, enum: str) -> list[str]:
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == enum)
    return [t.id for n in cls.body if isinstance(n, ast.Assign) for t in n.targets]  # type: ignore[union-attr]


def test_the_toy_python_output_matches_the_golden_files(
    generated_toy: Path, tmp_path: Path
) -> None:
    for module in sorted(generated_toy.glob("*.py")):
        shutil.copy(module, tmp_path / module.name)
    assert_matches_golden("pydantic_split", tmp_path)


def test_one_module_is_written_per_schema_module(generated_toy: Path) -> None:
    written = sorted(p.name for p in generated_toy.glob("*.py"))
    assert written == TOY_MODULES, "the split run must write one module per schema module"


def test_a_class_stays_in_the_module_that_declares_it(generated_toy: Path) -> None:
    declared = {
        n.name for n in parse(generated_toy, "books.py").body if isinstance(n, ast.ClassDef)
    }
    assert {"Book", "Chapter", "Note"} <= declared, "Book, Chapter and Note belong in books.py"


def test_a_class_of_a_sibling_module_is_imported_relatively(generated_toy: Path) -> None:
    assert "Book" in imports_from(parse(generated_toy, "scans.py"), ".books"), (
        "scans.py must import Book from its sibling module"
    )


def test_an_application_imports_the_metamodel_from_the_top_level_package(
    generated_toy: Path,
) -> None:
    names = imports_from(parse(generated_toy, "scans.py"), "rdf_persistence")
    assert {"AggregateRoot", "Described", "StoredFile", "Tracked"} <= names, (
        "an application's metamodel imports must come from the public package (DEC-6)"
    )


@pytest.mark.parametrize(
    ("name", "toolkit", "expected"),
    [
        ("rp_core", True, f"{TOOLKIT_PACKAGE}.rp_core"),
        ("rp_core", False, "rdf_persistence"),
    ],
)
def test_the_metamodel_module_to_import_from(name: str, toolkit: bool, expected: str) -> None:
    assert metamodel_module(name, toolkit=toolkit) == expected, (
        f"{name} in a {'toolkit' if toolkit else 'application'} run"
    )


@pytest.mark.parametrize(
    ("module", "enum", "members"),
    [
        ("books.py", "Genre", ["FICTION", "NONFICTION", "POETRY"]),
    ],
)
def test_enum_members_are_the_permissible_value_keys_in_upper_snake_case(
    generated_toy: Path, module: str, enum: str, members: list[str]
) -> None:
    assert enum_members(parse(generated_toy, module), enum) == members, (
        f"{enum} members must come from the keys, not the titles"
    )


def test_an_enum_member_keeps_the_value_of_its_key() -> None:
    from rdf_persistence.domain.generated.rp_core import RegistryKind

    assert RegistryKind.LOADED_GRAPH.value == "loaded_graph", "the stored value is the key"


def test_an_internal_slot_is_marked_for_the_api_layer() -> None:
    extra = StoredFile.model_fields["file_key"].json_schema_extra
    assert extra == {"rp_internal": True}, "an internal slot must carry the marker"


def test_an_internal_slot_is_still_dumped_for_the_mapper() -> None:
    dumped = StoredFile(file_key="k").model_dump()
    assert dumped["file_key"] == "k", "the mapper must still persist internal slots"


def test_a_slot_that_is_not_internal_has_no_marker() -> None:
    assert StoredFile.model_fields["file_name"].json_schema_extra is None, (
        "only internal slots are marked"
    )


@pytest.fixture
def toy_package(generated_toy: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """The generated toy folder made importable as the package ``rp_toy_generated``."""
    link = generated_toy.parent / "rp_toy_generated"
    link.symlink_to(generated_toy, target_is_directory=True)
    monkeypatch.syspath_prepend(str(generated_toy.parent))
    yield "rp_toy_generated"
    for name in [m for m in sys.modules if m.split(".")[0] == "rp_toy_generated"]:
        del sys.modules[name]
    link.unlink()


def test_the_generated_modules_import_and_build_models(toy_package: str) -> None:
    library = importlib.import_module(f"{toy_package}.library")
    chapter = library.Chapter(id="https://example.org/c1", number=1)
    assert chapter.label is None, "an unlabelled chapter needs no label"
    with pytest.raises(ValidationError, match="label"):
        library.Note(id="https://example.org/n1", text="x")


ENUM_MODULE = """
id: https://example.org/ns/colours
name: colours
title: Colours
description: A module with an enum.
prefixes: {c: "https://example.org/ns/c#", linkml: "https://w3id.org/linkml/"}
default_prefix: c
imports: [linkml:types]
enums:
  Colour:
    title: Colour
    description: A colour.
    permissible_values:
      light_red: {title: Light red, description: Light red., meaning: "c:LightRed"}
"""

USER_MODULE = """
id: https://example.org/ns/paint
name: paint
title: Paint
description: A module using the enum of another.
prefixes: {c: "https://example.org/ns/c#", linkml: "https://w3id.org/linkml/"}
default_prefix: c
imports: [linkml:types, colours]
classes:
  Paint:
    title: Paint
    description: A paint.
    attributes:
      colour: {range: Colour, title: Colour, description: Its colour.}
"""


def test_an_enum_declared_in_another_module_is_imported_not_repeated(tmp_path: Path) -> None:
    (tmp_path / "colours.yaml").write_text(ENUM_MODULE, encoding="utf-8")
    (tmp_path / "paint.yaml").write_text(USER_MODULE, encoding="utf-8")
    files = {f.name: f.text for f in render_modules(tmp_path / "paint.yaml")}
    tree = ast.parse(files["paint.py"])
    declared = {n.name for n in tree.body if isinstance(n, ast.ClassDef)}
    assert "Colour" in imports_from(tree, ".colours"), "the enum must be imported from its module"
    assert "Colour" not in declared, "the enum must not be declared again"
    assert enum_members(ast.parse(files["colours.py"]), "Colour") == ["LIGHT_RED"], (
        "the member comes from the key, not the title"
    )


@pytest.mark.parametrize(
    ("slot", "ignored"),
    [("label", True), ("description", False), ("id", False)],
)
def test_a_field_an_unlabelled_class_relaxes_carries_a_type_ignore(
    generated_toy: Path, slot: str, ignored: bool
) -> None:
    """Chapter makes the label of ``Described`` optional (PD-11); mypy needs the override marked."""
    lines = (generated_toy / "books.py").read_text(encoding="utf-8").splitlines()
    chapter = lines[lines.index("class Chapter(Described):") :]
    line = next(line for line in chapter if line.startswith(f"    {slot}:"))
    assert line.endswith("# type: ignore[assignment]") is ignored, (
        f"Chapter.{slot}: the ignore belongs on a field that loosens its base class's, and only there"
    )
