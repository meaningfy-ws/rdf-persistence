"""No file names the old module path of a row of ``LAYOUT`` that is on (thematic-structure TC-04).

Python files are read as text (a docstring, a comment and a ``mock.patch("...")`` string all count) and
through ``ast`` (``from rdf_persistence.services import session`` names the module without writing its
dotted path). Other files (docs, YAML, TOML, the Makefile, ``.importlinter``) are read as text, for the
dotted path and the file path, the root ``*.md`` and ``setup.cfg`` among them. ``openspec/``, the
changelog and this test are out of the scan; a Python file that does not parse is reported; a file that
must name an old path (a probe that it is gone, the guard that still refuses it) is listed in ``EXEMPT``.
"""

import ast
import re
from pathlib import Path

import pytest

from tests.unit import test_theme_layout
from tests.unit.test_theme_layout import PLACED, Placed, turned_on_pairs

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
        # the model guard still forbids the removed `rdf_persistence.domain.base.RpModel` as a base, so a
        # consumer's stale generated code is named (PD-4 a), and that guard's test; the layout guard's own
        # test, which plants old paths in synthetic trees.
        "rdf_persistence/testkit/guards.py",
        "tests/unit/testkit/test_guards.py",
        "tests/unit/test_theme_layout.py",
        # stage 2 (D-13 S2): the probe that an old import path is a ModuleNotFoundError names the paths
        # that never existed or are gone, which is the point of the probe; it still names
        # `rdf_persistence.domain.generated` (two lines), so it stays.
        "tests/unit/test_technical_split.py",
        # stage 8: the probe that the two removed shim paths cannot be imported names them.
        "tests/unit/test_deprecated_paths_removed.py",
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


def moved_generated_pairs(
    placed: tuple[Placed, ...] = PLACED,
) -> tuple[tuple[str, str], ...]:
    """The (old, new) generated module of each group whose every row is on: the old module is gone.

    A group with a row still off keeps its old module for the classes not yet moved, so it is not scanned.
    """
    standing: dict[str, str] = {}
    for row in placed:
        if all(other.on for other in placed if other.old == row.old):
            standing.setdefault(row.old, row.new)
    return tuple(standing.items())


def test_no_file_names_the_old_path_of_a_row_that_is_on():
    hits = old_path_hits(ROOT, turned_on_pairs() + moved_generated_pairs())

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


OLD_WIRE = "rdf_persistence.adapters.generated.rp_wire"


def test_a_moved_generated_module_path_is_found(tmp_path):
    """The old ``rp_wire`` of the persistence and access themes: a docstring naming it is a hit."""
    _plant(tmp_path, "rdf_persistence/testkit/x.py", f'"""Records of ``{OLD_WIRE}``."""\n')

    hits = old_path_hits(tmp_path, moved_generated_pairs())

    assert hits == [f"rdf_persistence/testkit/x.py:1: {OLD_WIRE}"]


def test_a_generated_module_with_a_group_still_off_is_not_scanned(monkeypatch):
    monkeypatch.setattr(test_theme_layout, "TURNED_ON", frozenset({"persistence"}))

    assert OLD_WIRE not in dict(moved_generated_pairs()), "access still has classes in rp_wire"

    monkeypatch.setattr(test_theme_layout, "TURNED_ON", frozenset({"persistence", "access"}))

    assert OLD_WIRE in dict(moved_generated_pairs()), "every row of rp_wire is on"


def test_the_pairs_of_a_theme_turned_on_are_its_old_and_new_paths(monkeypatch):
    monkeypatch.setattr(test_theme_layout, "TURNED_ON", frozenset({"persistence"}))

    pairs = dict(turned_on_pairs())

    assert pairs[OLD] == NEW, "session moves into the persistence theme"
    assert "rdf_persistence.adapters.sparql_protocol" not in pairs, (
        "a created module has no old path"
    )


TEST_PATH = re.compile(r"\btests/(?:unit|integration|feature|e2e|perf)/[\w/]+\.(?:py|feature)\b")


def _named_test_paths() -> list[tuple[str, str]]:
    """Test paths named by the docs, the feature files and the docstrings of the test modules."""
    texts = [(p, p.read_text("utf-8")) for p in (ROOT / "docs").rglob("*.adoc")]
    texts += [(p, p.read_text("utf-8")) for p in (ROOT / "tests").rglob("*.feature")]
    for path in (ROOT / "tests").rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        doc = ast.get_docstring(ast.parse(path.read_text("utf-8")))
        if doc:
            texts.append((path, doc))
    return [
        (path.relative_to(ROOT).as_posix(), named)
        for path, text in texts
        for named in TEST_PATH.findall(text)
    ]


def test_every_test_path_a_doc_or_a_test_docstring_names_exists():
    """A move of a test file leaves no doc, feature file or docstring pointing at the old place."""
    missing = sorted(
        {
            f"{where} names {named}"
            for where, named in _named_test_paths()
            if not (ROOT / named).exists()
        }
    )

    assert missing == []
