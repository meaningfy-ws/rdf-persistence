"""PD-8: the base-model template writes the import of ``RpModel`` the run's reader can use."""

import ast
from pathlib import Path

import pytest
from mypy import api as mypy_api

from rdf_persistence.testkit import assert_public_imports
from rdf_persistence_generation.extensions.pydantic_split import METAMODEL_DIR
from rdf_persistence_generation.extensions.pydantic_split import render as render_modules

from .golden import TOY

TOY_GENERATED = TOY / "domain" / "generated"
TOP_PACKAGE = "rdf_persistence"
BASE_MODEL = "RpModel"
TOOLKIT_BASE_MODULE = "rdf_persistence.core.domain.base"  # the `core` path (PD-8)
MYPY_GENERATED = Path(__file__).parents[3] / "rdf_persistence_generation" / "mypy-generated.ini"


def base_model_imports(text: str) -> list[ast.ImportFrom]:
    """The ``from <module> import RpModel`` statements of a generated module."""
    return [
        node
        for node in ast.walk(ast.parse(text))
        if isinstance(node, ast.ImportFrom) and BASE_MODEL in {alias.name for alias in node.names}
    ]


def toy_modules() -> list[Path]:
    return sorted(p for p in TOY_GENERATED.glob("*.py") if p.name != "__init__.py")


@pytest.mark.parametrize("module", toy_modules(), ids=lambda p: p.name)
def test_a_consumer_module_imports_the_base_model_from_the_top_package(module: Path) -> None:
    """TC-18"""
    found = base_model_imports(module.read_text(encoding="utf-8"))
    assert [node.module for node in found] == [TOP_PACKAGE], (
        f"{module.name} must import {BASE_MODEL} from {TOP_PACKAGE} (PD-8)"
    )
    assert_public_imports(module)


def test_the_toy_library_type_checks_with_the_generated_code_settings() -> None:
    """TC-18"""
    out, err, status = mypy_api.run(
        ["--config-file", str(MYPY_GENERATED), "--no-incremental", str(TOY_GENERATED)]
    )
    assert status == 0, f"mypy rejects the toy library:\n{out}{err}"


def test_the_toolkits_own_metamodel_imports_the_base_model_by_its_module_path() -> None:
    """TC-19: the top package imports the generated metamodel, so the toolkit cannot import from it."""
    files = {f.name: f.text for f in render_modules(METAMODEL_DIR / "rp.yaml")}
    importers = {name: base_model_imports(text) for name, text in files.items()}
    importing = {name: found for name, found in importers.items() if found}
    assert importing, "no metamodel module imports the base model: the test sees nothing"
    assert {name: [n.module for n in found] for name, found in importing.items()} == {
        name: [TOOLKIT_BASE_MODULE] for name in importing
    }, f"the toolkit's run must name the module of {BASE_MODEL}, never {TOP_PACKAGE}"
