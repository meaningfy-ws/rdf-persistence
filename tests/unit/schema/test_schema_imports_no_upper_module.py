"""The ``schema`` package reads the stored-file class and the tenant states from the schema, never from a theme module (PD-8, DEC-6)."""

import ast
from pathlib import Path

import pytest

import rdf_persistence.schema
from rdf_persistence.schema.services import schema_structure
from rdf_persistence.schema.services.schema import load_schema
from rdf_persistence.schema.services.vocabulary import METAMODEL, TENANT_STATE_IRIS

SCHEMA_PACKAGE = Path(next(iter(rdf_persistence.schema.__path__)))
UPPER_MODULES = ("rp_files", "rp_tenancy")


def imported_modules(path: Path) -> set[str]:
    """Every dotted module the file imports, ``from a.b import c`` as ``a.b`` and ``a.b.c``."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
            found.update(f"{node.module}.{alias.name}" for alias in node.names)
    return found


def schema_sources() -> list[Path]:
    return sorted(
        path
        for path in SCHEMA_PACKAGE.rglob("*.py")
        if "generated" not in path.relative_to(SCHEMA_PACKAGE).parts
    )


@pytest.mark.parametrize("path", schema_sources(), ids=lambda p: str(p.relative_to(SCHEMA_PACKAGE)))
def test_no_module_of_schema_imports_the_files_or_tenancy_module(path: Path) -> None:
    upper = {name for name in imported_modules(path) if name.rsplit(".", 1)[-1] in UPPER_MODULES}
    assert not upper, f"{path.name} imports {sorted(upper)}; read it from the schema (PD-8)"


def test_the_schema_sources_are_found() -> None:
    assert any(p.name == "schema_structure.py" for p in schema_sources()), "the walk found nothing"


def test_the_stored_file_class_is_the_class_whose_class_uri_is_rp_stored_file() -> None:
    view = load_schema(METAMODEL)
    named = schema_structure.stored_file_class(view)
    assert named == "StoredFile", "the class named is the one with class_uri rp:StoredFile"
    assert view.get_class(named).class_uri == "rp:StoredFile"


def test_the_tenant_state_iris_are_the_meanings_of_the_tenancy_enum() -> None:
    view = load_schema(METAMODEL)
    values = view.get_enum("TenantState").permissible_values
    expected = {text: view.expand_curie(str(pv.meaning)) for text, pv in values.items()}
    assert {text: str(iri) for text, iri in TENANT_STATE_IRIS.items()} == expected
    assert set(expected) == {"active", "deleting"}, "the states of a tenant"
