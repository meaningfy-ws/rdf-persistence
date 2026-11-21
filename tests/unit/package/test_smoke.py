"""Smoke test — proves the package imports and exposes a version.

Keeps ``make test`` green on a fresh skeleton before any real code exists.
Replace or extend with genuine unit tests as the package grows; do not delete
the import assertion — it is the cheapest guard against a broken package layout
(missing ``__init__.py``, bad ``pyproject`` package discovery, etc.).
"""

import importlib
import tomllib
from pathlib import Path


def test_version_matches_pyproject() -> None:
    """``__version__`` is the ``pyproject.toml`` version, the one file release-please bumps (TC-01)."""
    pyproject = Path(__file__).resolve().parents[3] / "pyproject.toml"
    declared = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["version"]
    module = importlib.import_module("rdf_persistence")
    assert module.__version__ == declared, "the package version is the declared one"
    assert declared, "a version is declared"
