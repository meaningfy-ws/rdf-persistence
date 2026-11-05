"""Shared fixtures of the generation tests: a private, breakable copy of the toy library."""

import shutil
from collections.abc import Callable
from pathlib import Path

import pytest

from rdf_persistence.generation.cli import main

TOY = Path(__file__).parents[2] / "fixtures" / "library"
ROOT_SCHEMA = "library.yaml"

Breaker = Callable[[str, str, str], Path]


@pytest.fixture
def toy_copy(tmp_path: Path) -> Path:
    """The toy library copied to ``tmp_path``; returns the folder."""
    folder = tmp_path / "library"
    shutil.copytree(TOY, folder, ignore=shutil.ignore_patterns("__pycache__", "generated"))
    return folder


@pytest.fixture
def break_toy(toy_copy: Path) -> Breaker:
    """Replace the first ``old`` by ``new`` in one module of the copy; return the root schema path."""

    def apply(module: str, old: str, new: str) -> Path:
        path = toy_copy / module
        text = path.read_text(encoding="utf-8")
        assert old in text, f"{old!r} is not in {module}: the planted fault would plant nothing"
        path.write_text(text.replace(old, new, 1), encoding="utf-8")
        return toy_copy / ROOT_SCHEMA

    return apply


@pytest.fixture(scope="session")
def generated_toy(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The toy library generated once per session by ``rp-generate``; read-only, returns its output folder."""
    folder = tmp_path_factory.mktemp("toy") / "library"
    shutil.copytree(TOY, folder, ignore=shutil.ignore_patterns("__pycache__", "generated"))
    assert main(["--project", str(folder / "pyproject.toml")]) == 0, "the toy must generate"
    return folder / "generated"
