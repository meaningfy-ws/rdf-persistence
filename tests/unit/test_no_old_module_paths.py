"""No file names the old module path of a row of ``LAYOUT`` that is on (thematic-structure TC-04).

Python files are read as text (a docstring, a comment and a ``mock.patch("...")`` string all count) and
through ``ast`` (``from rdf_persistence.services import session`` names the module without writing its
dotted path). Other files (docs, YAML, TOML, the Makefile, ``.importlinter``) are read as text, for the
dotted path and the file path, the root ``*.md`` and ``setup.cfg`` among them. ``openspec/``, the
changelog and this test are out of the scan; a Python file that does not parse is reported; a shim
that must name its old path, and the test of that shim, are listed in ``EXEMPT`` by the stage that adds it.
"""

import ast
import re
from pathlib import Path

import pytest

from tests.unit import test_theme_layout
from tests.unit.test_theme_layout import turned_on_pairs

ROOT = Path(__file__).resolve().parents[2]
SCANNED = ("rdf_persistence", "rdf_persistence_generation", "tests", "docs", ".github")
SCANNED_FILES = (
    "Makefile",
    "pyproject.toml",
    "setup.cfg",
    "pytest.ini",
    "ruff.toml",
    "mypy.ini",
    ".coveragerc",
    ".importlinter",
    ".pre-commit-config.yaml",
    "sonar-project.properties",
)
SKIPPED_SUFFIXES = frozenset({".pyc", ".png", ".svg", ".whl", ".json", ".csv", ".ico", ".lock"})
SKIPPED_PARTS = frozenset({"__pycache__", "node_modules", ".venv", "golden", "generated"})
THIS_FILE = "tests/unit/test_no_old_module_paths.py"
# Files that may name an old path: each stage that adds a shim lists the shim's test here, with the why.
EXEMPT: frozenset[str] = frozenset(
    {
        THIS_FILE,
        "CHANGELOG.md",
        # stage 2: the `domain.base` shim (PD-8) names its own path, so do its test, the model guard that
        # still forbids the shim's `RpModel` as a base until stage 8 (PD-4 a), and that guard's test; and
        # the layout guard's own test, which plants old paths in synthetic trees.
        "rdf_persistence/domain/base.py",
        "tests/unit/core/test_domain_base_shim.py",
        "rdf_persistence/testkit/guards.py",
        "tests/unit/testkit/test_guards.py",
        "tests/unit/test_theme_layout.py",
    }
)


def _files(root: Path) -> list[Path]:
    found = [root / name for name in SCANNED_FILES if (root / name).is_file()]
    found += [p for p in root.glob("*.md") if p.is_file()]
    for folder in SCANNED:
        found += [
            p
            for p in (root / folder).rglob("*")
            if p.is_file()
            and not SKIPPED_PARTS & set(p.relative_to(root).parts)
            and p.suffix not in SKIPPED_SUFFIXES
        ]
    return sorted(found)


def _patterns(pairs: tuple[tuple[str, str], ...]) -> list[tuple[str, re.Pattern[str]]]:
    """For each old module: the dotted path and the file path, each not followed by a name character."""
    return [
        (old, re.compile(f"{re.escape(form)}(?![\\w])"))
        for old, _ in pairs
        for form in (old, old.replace(".", "/"))
    ]


def _imported_modules(tree: ast.AST) -> list[tuple[int, str]]:
    """``(line, dotted path)`` of every module an import statement names, ``from a import b`` as ``a.b``."""
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found += [(node.lineno, alias.name) for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            found += [(node.lineno, f"{node.module}.{alias.name}") for alias in node.names]
    return found


def old_path_hits(root: Path, pairs: tuple[tuple[str, str], ...]) -> list[str]:
    """``file:line: old path`` for every use of the old path of a row that is on, under ``root``."""
    hits: list[str] = []
    patterns = _patterns(pairs)
    for path in _files(root):
        name = path.relative_to(root).as_posix()
        if name in EXEMPT:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        found = {
            (n, old)
            for n, line in enumerate(text.splitlines(), 1)
            for old, rx in patterns
            if rx.search(line)
        }
        if path.suffix == ".py":
            try:
                tree = ast.parse(text)
            except SyntaxError as error:
                hits.append(f"{name}: cannot be parsed, so its imports are unchecked ({error.msg})")
            else:
                olds = {old for old, _ in pairs}
                found |= {
                    (n, old)
                    for n, dotted in _imported_modules(tree)
                    for old in olds
                    if dotted == old
                }
        hits += [f"{name}:{n}: {old}" for n, old in sorted(found)]
    return hits


def test_no_file_names_the_old_path_of_a_row_that_is_on():
    hits = old_path_hits(ROOT, turned_on_pairs())

    assert hits == [], "old module paths still in use:\n" + "\n".join(hits)


# --- the guard on a planted tree ------------------------------------------------------------

OLD = "rdf_persistence.services.session"
NEW = "rdf_persistence.persistence.services.session"
PAIRS = ((OLD, NEW),)


def _plant(root: Path, name: str, text: str) -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_a_mock_patch_string_with_the_old_path_fails_naming_the_file_and_line(tmp_path):
    """TC-04: ``mock.patch`` of a module path once its row is on."""
    _plant(
        tmp_path,
        "tests/unit/test_x.py",
        f'from unittest import mock\n\n\ndef test_x():\n    mock.patch("{OLD}.open_session")\n',
    )

    assert old_path_hits(tmp_path, PAIRS) == [f"tests/unit/test_x.py:5: {OLD}"]


@pytest.mark.parametrize(
    ("name", "text", "line"),
    [
        ("rdf_persistence/api/a.py", f"import {OLD}\n", 1),
        ("rdf_persistence/api/b.py", "from rdf_persistence.services import session\n", 1),
        ("rdf_persistence/api/c.py", f"from {OLD} import open_session\n", 1),
        ("rdf_persistence/api/d.py", f'"""Doc."""\n\nx = 1  # see {OLD}\n', 3),
        ("docs/modules/ROOT/pages/a.adoc", f"one\ntwo `{OLD}`.\n", 2),
        ("docs/modules/ROOT/pages/b.adoc", "see rdf_persistence/services/session.py\n", 1),
        (".importlinter", f"modules =\n    {OLD}\n", 2),
        ("Makefile", f"x:\n\t@ uv run python -m {OLD}\n", 2),
    ],
)
def test_every_way_to_name_the_old_module_is_found(tmp_path, name, text, line):
    _plant(tmp_path, name, text)

    hits = old_path_hits(tmp_path, PAIRS)

    assert [h.rsplit(":", 1)[0] for h in hits] == [f"{name}:{line}"], hits


@pytest.mark.parametrize("name", ["setup.cfg", "README.md", "CONTRIBUTING.md"])
def test_a_root_file_naming_the_old_path_is_found(tmp_path, name):
    _plant(tmp_path, name, "per-file-ignores =\n    rdf_persistence/services/session.py\n")

    assert [h.rsplit(":", 1)[0] for h in old_path_hits(tmp_path, PAIRS)] == [f"{name}:2"]


def test_a_python_file_that_does_not_parse_is_reported_and_still_text_scanned(tmp_path):
    _plant(tmp_path, "tests/unit/test_broken.py", f"def (:\n    '{OLD}'\n")

    hits = old_path_hits(tmp_path, PAIRS)

    assert any(h.startswith("tests/unit/test_broken.py: cannot be parsed") for h in hits), hits
    assert f"tests/unit/test_broken.py:2: {OLD}" in hits, "the text scan still ran"


@pytest.mark.parametrize(
    ("name", "text"),
    [
        ("rdf_persistence/api/a.py", f"import {NEW}\n"),
        ("rdf_persistence/api/b.py", "from rdf_persistence.services import sessions\n"),
        ("rdf_persistence/api/c.py", f"x = '{OLD}s.thing'\n"),
        ("rdf_persistence/api/d.py", "from rdf_persistence.persistence.services import session\n"),
        ("openspec/changes/x/design.md", f"{OLD}\n"),
        ("CHANGELOG.md", f"{OLD}\n"),
        ("tests/unit/test_no_old_module_paths.py", f"{OLD}\n"),
    ],
)
def test_the_new_path_a_lookalike_and_the_exempt_files_are_not_hits(tmp_path, name, text):
    _plant(tmp_path, name, text)

    assert old_path_hits(tmp_path, PAIRS) == [], f"{name} must not be a hit"


def test_a_row_that_is_off_is_not_searched(tmp_path):
    _plant(tmp_path, "rdf_persistence/api/a.py", f"import {OLD}\n")

    assert old_path_hits(tmp_path, ()) == [], "no pair, no hit"


def test_the_pairs_of_a_theme_turned_on_are_its_old_and_new_paths(monkeypatch):
    monkeypatch.setattr(test_theme_layout, "TURNED_ON", frozenset({"persistence"}))

    pairs = dict(turned_on_pairs())

    assert pairs[OLD] == NEW, "session moves into the persistence theme"
    assert "rdf_persistence.adapters.sparql_protocol" not in pairs, (
        "a created module has no old path"
    )
