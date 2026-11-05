"""PD-11: before the generators, unlabelled classes lose the required label and roots require a description."""

import ast
from pathlib import Path

import pytest

from rdf_persistence.generation.cli import main
from rdf_persistence.generation.transform import apply_defaults
from rdf_persistence.services.schema import load_schema

from .conftest import ROOT_SCHEMA

METAMODEL = Path(__file__).parents[3] / "rdf_persistence" / "model" / "rp.yaml"


def required(view, cls: str, slot: str) -> bool:
    return bool(view.induced_slot(slot, cls).required)


@pytest.fixture
def transformed(toy_copy: Path):
    view = load_schema(toy_copy / ROOT_SCHEMA)
    apply_defaults(view, toy_copy)
    return view


@pytest.mark.parametrize(
    ("cls", "slot", "expected"),
    [
        ("Chapter", "label", False),  # rp_unlabelled
        ("Note", "label", True),  # labelled, unchanged
        ("Book", "description", True),  # a root
        ("Scan", "description", True),  # a root
        ("LibraryAccess", "description", True),  # a root through TenantAccess
        ("Chapter", "description", False),  # owned, not a root
        ("Library", "description", False),  # the tenant root is not an AggregateRoot
    ],
)
def test_the_transformed_schema(transformed, cls: str, slot: str, expected: bool) -> None:
    assert required(transformed, cls, slot) is expected, f"{cls}.{slot} required != {expected}"


def test_the_metamodel_is_left_untouched() -> None:
    view = load_schema(METAMODEL)
    apply_defaults(view, METAMODEL.parent)
    assert not required(view, "TenantAccess", "description"), "PD-23 exempts the metamodel"


def test_the_generated_toy_classes_reflect_the_transform(toy_copy: Path) -> None:
    assert main(["--project", str(toy_copy / "pyproject.toml")]) == 0, "the toy must generate"
    tree = ast.parse((toy_copy / "generated" / "library.py").read_text(encoding="utf-8"))
    fields = {
        (cls.name, stmt.target.id): ast.unparse(stmt.annotation)
        for cls in tree.body
        if isinstance(cls, ast.ClassDef)
        for stmt in cls.body
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name)
    }
    assert fields[("Chapter", "label")] == "Optional[str]", (
        "an unlabelled class must have an optional label"
    )
    assert fields[("Note", "label")] == "str", "a labelled class must keep a required label"
    assert fields[("Book", "description")] == "str", "a root must require its description"
    assert fields[("Chapter", "description")] == "Optional[str]", (
        "an owned class must not require a description"
    )
