"""No test file imports a test module (test-debt-paydown PD-8).

A test module that another test module imports is two things at once: a set of tests and a library
of helpers. Collecting the importer collects the source's tests again under a second name, and a
rename of the source breaks an unrelated file. Helpers live in a helper module beside their users
(or in a ``conftest.py`` when they are fixtures); a test module is imported by nobody.

The checker reads every ``tests/**/*.py`` with ``ast``, helpers and ``conftest.py`` files included,
and names each import of a module called ``test_*`` in the five forms an import takes: ``from
tests.pkg.test_x import name``, ``from .test_x import name``, ``from tests.pkg import test_x``,
``from . import test_x`` and ``import tests.pkg.test_x``. A relative import is resolved against the
package folder of the file that holds it.
"""

import ast
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
TESTS = "tests"
TEST_MODULE = re.compile(r"^test_[a-z0-9_]+$")


def _is_test_module(dotted: str) -> bool:
    return bool(TEST_MODULE.match(dotted.rsplit(".", 1)[-1]))


def _package_of(relative: Path) -> list[str]:
    """The dotted package a file belongs to, as parts: ``tests/unit/a/b.py`` is ``tests.unit.a``."""
    return list(relative.parent.parts)


def _module_of(node: ast.ImportFrom, package: list[str]) -> str:
    """The dotted module a ``from`` statement names, a relative one resolved against ``package``."""
    base = package[: len(package) - (node.level - 1)] if node.level else []
    return ".".join([*base, *([node.module] if node.module else [])])


def _imported_test_modules(tree: ast.AST, package: list[str]) -> list[tuple[int, str]]:
    """The ``(line, dotted name)`` of every test module the tree imports."""
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found += [(node.lineno, a.name) for a in node.names if _is_test_module(a.name)]
        elif isinstance(node, ast.ImportFrom):
            module = _module_of(node, package)
            if module and _is_test_module(module):
                found.append((node.lineno, module))
            found += [
                (node.lineno, f"{module}.{a.name}") for a in node.names if _is_test_module(a.name)
            ]
    return found


def cross_test_imports(root: Path) -> list[str]:
    """One message per import of a test module in any file below ``root/tests``."""
    messages: list[str] = []
    for path in sorted((root / TESTS).rglob("*.py")):
        relative = path.relative_to(root)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative.as_posix())
        messages += [
            f"{relative.as_posix()}:{line} imports the test module {module}"
            for line, module in _imported_test_modules(tree, _package_of(relative))
        ]
    return messages


def _tests_tree(root: Path, files: dict[str, str]) -> None:
    for relative, source in files.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source, encoding="utf-8")


@pytest.mark.parametrize(
    ("importer", "source", "module"),
    [
        (
            "tests/unit/a/test_user.py",
            "from tests.unit.b.test_source import helper\n",
            "tests.unit.b.test_source",
        ),
        (
            "tests/unit/a/test_user.py",
            "from .test_source import helper\n",
            "tests.unit.a.test_source",
        ),
        (
            "tests/unit/a/test_user.py",
            "from tests.unit.b import test_source\n",
            "tests.unit.b.test_source",
        ),
        (
            "tests/unit/a/test_user.py",
            "from . import test_source\n",
            "tests.unit.a.test_source",
        ),
        (
            "tests/unit/a/test_user.py",
            "import tests.unit.b.test_source\n",
            "tests.unit.b.test_source",
        ),
        (
            "tests/unit/a/helpers.py",
            "from ..b.test_source import helper\n",
            "tests.unit.b.test_source",
        ),
        (
            "tests/unit/a/conftest.py",
            "def fixture() -> None:\n    from tests.unit.b.test_source import helper\n",
            "tests.unit.b.test_source",
        ),
    ],
    ids=[
        "from-absolute-test-module",
        "from-relative-test-module",
        "from-package-import-test-module",
        "from-dot-import-test-module",
        "import-dotted-test-module",
        "from-parent-relative-in-a-helper",
        "import-inside-a-function-in-a-conftest",
    ],
)
def test_an_import_of_a_test_module_is_named(
    tmp_path: Path, importer: str, source: str, module: str
) -> None:
    """Each of the five import forms, in a test, a helper or a conftest, names the importer."""
    _tests_tree(tmp_path, {importer: source})

    line = next(n for n, text in enumerate(source.splitlines(), 1) if "import" in text)

    assert cross_test_imports(tmp_path) == [
        f"{importer}:{line} imports the test module {module}"
    ], "the checker did not name the import of a test module"


@pytest.mark.parametrize(
    "source",
    [
        "from tests.unit.b.helpers import helper\n",
        "from tests.unit.b import helpers\n",
        "from . import helpers, conftest\n",
        "import tests.unit.b.helpers\n",
        "from tests.unit.b.testkit import helper\n",
        "from rdf_persistence.testkit import fakes\n",
        "import pytest\n",
    ],
    ids=[
        "helper-module",
        "helper-imported-as-module",
        "sibling-helpers",
        "dotted-helper",
        "name-that-only-starts-alike",
        "library-testkit",
        "third-party",
    ],
)
def test_an_import_that_is_not_of_a_test_module_is_left_alone(tmp_path: Path, source: str) -> None:
    """Helpers, conftests and a name that merely starts with ``test`` are not test modules."""
    _tests_tree(tmp_path, {"tests/unit/a/test_user.py": source})

    assert cross_test_imports(tmp_path) == [], "the checker flagged an import of a helper"


def test_no_test_file_imports_a_test_module() -> None:
    """G-3: a test module is imported by nobody; its helpers live in a helper module."""
    assert cross_test_imports(REPO) == [], "a test file imports a test module"
