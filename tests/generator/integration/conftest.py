"""Shared fixtures of the generator's integration tier: the toy library, freshly generated once.

This tier loads no container fixtures plugin: it starts no container (``make test-generator`` runs
in CI without any). ``test_the_tier_loads_no_container_plugin`` guards it.
"""

import importlib
import shutil
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from rdf_persistence_generation.cli import main

from .generated_project import PACKAGE

TOY = Path(__file__).parents[2] / "fixtures" / "library"


@pytest.fixture(scope="session")
def fresh_toy(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The toy library copied and generated once per session by ``rp-generate``; read-only.

    Returns the copy's folder: its schema is ``library.yaml``, its generated documents are in
    ``domain/generated/``, its TypeScript in ``web/src/domain/generated/``.
    """
    folder = tmp_path_factory.mktemp("fresh_toy") / "library"
    shutil.copytree(TOY, folder, ignore=shutil.ignore_patterns("__pycache__", "generated", "web"))
    assert main(["--project", str(folder / "pyproject.toml")]) == 0, "the toy must generate"
    return folder


@pytest.fixture
def project(tmp_path: Path) -> Iterator[Path]:
    """The project folder on ``sys.path``; the generated package is forgotten afterwards."""
    folder = tmp_path / "project"
    sys.path.insert(0, str(folder))
    yield folder
    sys.path.remove(str(folder))
    for name in [n for n in sys.modules if n.split(".")[0] == PACKAGE]:
        del sys.modules[name]
    importlib.invalidate_caches()
