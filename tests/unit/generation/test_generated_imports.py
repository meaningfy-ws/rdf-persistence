"""PD-27 item 7: every generated Python module imports (the generated code compiles)."""

import importlib
import pkgutil

import pytest

import rdf_persistence.domain.generated
import rdf_persistence.generation.generated
from tests.fixtures.library import generated as toy_generated

PACKAGES = [rdf_persistence.domain.generated, rdf_persistence.generation.generated, toy_generated]


def generated_modules() -> list[str]:
    return sorted(
        info.name
        for package in PACKAGES
        for info in pkgutil.walk_packages(package.__path__, f"{package.__name__}.")
    )


@pytest.mark.parametrize("module", generated_modules())
def test_the_generated_module_imports(module: str) -> None:
    assert importlib.import_module(module), f"{module} failed to import"
