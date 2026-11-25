"""Shared fixtures of the generation tests: a private, breakable copy of the toy library."""

import shutil
from pathlib import Path

import pytest

from rdf_persistence_generation.cli import main
from tests.generator.theme_map import THEME_OF_ROOT, theme_package

from .golden import ROOT_SCHEMA, TOY, Breaker


@pytest.fixture
def toy_copy(tmp_path: Path) -> Path:
    """The toy library copied to ``tmp_path``; returns the folder."""
    folder = tmp_path / "library"
    shutil.copytree(
        TOY, folder, ignore=shutil.ignore_patterns("__pycache__", "generated", "golden")
    )
    return folder


METAMODEL_DIR = Path(__file__).parents[3] / "rdf_persistence" / "model"
TOOLKIT_DOMAIN = theme_package(THEME_OF_ROOT["rp"])


def _entry(schema: str, package: str) -> str:
    return (
        f'[[tool.rp-generate]]\nschema = "model/{schema}.yaml"\npackage = "{package}"\n'
        'regenerate-command = "make generate"\nopenapi = false\n'
    )


def toolkit_domain_targets() -> str:
    """The ``pyproject.toml`` text of the toolkit's five domain targets over a copy of the metamodel's folder."""
    entries = [_entry(root, theme_package(theme)) for root, theme in THEME_OF_ROOT.items()]
    return "\n".join(entries)


# The modules that read ``TOOLKIT_ROOTS`` by name, so a test can make a temporary folder the toolkit's own.
ROOTS_USERS = (
    "rdf_persistence_generation.config",
    "rdf_persistence_generation.steps",
    "rdf_persistence_generation.checks.python_package",
    "rdf_persistence_generation.checks.hard",
    "rdf_persistence_generation.checks.boundary",
    "rdf_persistence_generation.components",
    "rdf_persistence_generation.lock_step",
    "rdf_persistence_generation.extensions.shacl",
    "rdf_persistence_generation.extensions.typescript",
    "rdf_persistence_generation.extensions.pydantic_split",
)


@pytest.fixture
def toolkit_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A project folder holding a copy of the metamodel, treated as the toolkit's own, and a pyproject for it."""
    shutil.copytree(
        METAMODEL_DIR,
        tmp_path / "model",
        ignore=shutil.ignore_patterns("migrations", "__pycache__", "generated"),
    )
    for module in ROOTS_USERS:
        monkeypatch.setattr(f"{module}.TOOLKIT_ROOTS", (tmp_path.resolve(),))  # X1
    (tmp_path / "pyproject.toml").write_text(toolkit_domain_targets(), encoding="utf-8")
    return tmp_path


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
    return folder / "domain" / "generated"
