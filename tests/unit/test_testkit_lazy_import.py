"""The container fixtures need the extra ``rdf-persistence[testkit]``; the testkit root does not (PD-16)."""

import importlib
import subprocess
import sys

import pytest

CONTAINERS = "rdf_persistence.testkit.containers"


def test_testkit_root_does_not_import_testcontainers() -> None:
    code = "import sys, rdf_persistence.testkit; sys.exit('testcontainers' in sys.modules)"
    assert subprocess.run([sys.executable, "-I", "-c", code], check=False).returncode == 0


def test_missing_extra_names_the_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "testcontainers", None)  # makes `import testcontainers` fail
    for name in [m for m in sys.modules if m.startswith(CONTAINERS)]:
        monkeypatch.delitem(sys.modules, name)
    with pytest.raises(ImportError, match=r"rdf-persistence\[testkit\]"):
        importlib.import_module(CONTAINERS)
