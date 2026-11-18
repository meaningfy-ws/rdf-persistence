"""Attacks on the cleanup of the generated e2e package (TC-54, adversarial).

TC-54 checks the cleanup after a test that passed. The cases that leave a ``toy_e2e`` behind for the
next test are the failing ones: a test body that raises, a package that cannot be imported.
"""

import importlib
import sys
from pathlib import Path
from types import ModuleType

import pytest

from tests.generator.e2e.test_generated_library_served import PACKAGE, generated_toy

pytestmark = pytest.mark.slow


def _leftovers(tmp_path: Path) -> tuple[list[str], bool]:
    modules = [n for n in sys.modules if n == PACKAGE or n.startswith(f"{PACKAGE}.")]
    return modules, str(tmp_path) in sys.path


def test_a_failing_test_body_leaves_neither_modules_nor_path_behind(tmp_path: Path) -> None:
    with pytest.raises(AssertionError, match="the test failed"), generated_toy(tmp_path):
        raise AssertionError("the test failed")
    modules, on_path = _leftovers(tmp_path)
    assert not modules, f"{modules} still in sys.modules after a failing test"
    assert not on_path, "tmp_path is still on sys.path after a failing test"


def test_a_generated_package_that_cannot_be_imported_leaves_nothing_behind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = importlib.import_module

    def broken(name: str, *args: object) -> ModuleType:
        if name == f"{PACKAGE}.generated":  # the generator itself imports other packages
            raise ImportError(f"{name} is broken")
        return real(name, *args)  # type: ignore[arg-type]

    monkeypatch.setattr(importlib, "import_module", broken)
    with pytest.raises(ImportError, match="is broken"), generated_toy(tmp_path):
        pytest.fail("the block must not run")
    monkeypatch.undo()
    _, on_path = _leftovers(tmp_path)
    assert not on_path, "tmp_path is still on sys.path after a failed import"
