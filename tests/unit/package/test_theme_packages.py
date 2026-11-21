"""A theme package and its layer packages hold a docstring and nothing else (thematic-structure PD-9, TC-06).

Importing a theme then imports nothing more, so no cycle can hide in an ``__init__``. The folders
under ``generated/`` are written by the generator and are not read.
"""

import ast
from pathlib import Path

from tests.changed import THEMES

ROOT = Path(__file__).resolve().parents[3]
PACKAGE = ROOT / "rdf_persistence"


def _inits(package: Path, themes: frozenset[str] = THEMES) -> list[Path]:
    """The ``__init__.py`` of each theme folder that exists and of every folder below it, but ``generated``."""
    return sorted(
        path
        for theme in themes
        if (package / theme).is_dir()
        for path in (package / theme).rglob("__init__.py")
        if "generated" not in path.relative_to(package).parts
    )


def init_problems(package: Path, themes: frozenset[str] = THEMES) -> list[str]:
    """``file: what`` for each ``__init__.py`` of a theme that is not a docstring alone."""
    problems = []
    for path in _inits(package, themes):
        body = ast.parse(path.read_text(encoding="utf-8")).body
        name = path.relative_to(package.parent).as_posix()
        if not ast.get_docstring(ast.Module(body=body, type_ignores=[])):
            problems.append(f"{name}: no docstring")
        elif len(body) > 1:
            problems.append(f"{name}: holds {len(body) - 1} statement(s) beside its docstring")
    return problems


def test_every_init_of_a_theme_is_a_docstring_alone():
    assert _inits(PACKAGE), "no theme folder found: the scan reads nothing"

    assert init_problems(PACKAGE) == [], "theme packages that are not docstring-only"


def test_the_core_theme_and_its_three_layers_have_an_init():
    present = {p.relative_to(PACKAGE).as_posix() for p in _inits(PACKAGE, frozenset({"core"}))}

    assert present == {
        "core/__init__.py",
        "core/domain/__init__.py",
        "core/services/__init__.py",
        "core/adapters/__init__.py",
    }


def _plant(root: Path, rel: str, text: str) -> None:
    path = root / "rdf_persistence" / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_an_init_without_a_docstring_is_named(tmp_path):
    _plant(tmp_path, "core/__init__.py", "")

    assert init_problems(tmp_path / "rdf_persistence") == [
        "rdf_persistence/core/__init__.py: no docstring"
    ]


def test_an_init_that_re_exports_is_named(tmp_path):
    _plant(tmp_path, "core/domain/__init__.py", '"""Core."""\n\nfrom os import path\n')

    assert init_problems(tmp_path / "rdf_persistence") == [
        "rdf_persistence/core/domain/__init__.py: holds 1 statement(s) beside its docstring"
    ]


def test_an_init_under_generated_is_not_read(tmp_path):
    _plant(tmp_path, "core/services/generated/__init__.py", "")
    _plant(tmp_path, "core/__init__.py", '"""Core."""\n')

    assert init_problems(tmp_path / "rdf_persistence") == []
