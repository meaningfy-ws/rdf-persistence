"""Library tests do not import the generator, but for the files that use it as a tool (generator-package PD-9).

The generator has its own pyramid under ``tests/generator/``, measured against its own package. A
test of the library that imports ``rdf_persistence_generation`` would blur the two, so each such
file is named in ``TOOL_USERS``, the files that run the generator on the library's own schemas as
a tool. The checker reads every test file outside ``tests/generator/`` with ``ast``: ``import``
statements, and the string constants of ``pytest_plugins`` and of ``import_module`` calls. It fails
on a file that imports the generator without being listed, and on a listed file that no longer does.
"""

import ast
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
GENERATOR = "rdf_persistence_generation"
GENERATOR_TESTS = "tests/generator/"
PLUGINS_NAME = "pytest_plugins"
IMPORT_FUNCTIONS = frozenset({"import_module"})

TOOL_USERS = frozenset(
    {
        "tests/conftest.py",
        "tests/unit/entrypoints/test_service_written.py",
        "tests/unit/services/test_replace_internal_values.py",
        "tests/integration/api/test_router.py",
        "tests/unit/services/test_collaboration_workflow_adversarial.py",
        "tests/unit/services/test_collaboration_discussion_adversarial.py",
        "tests/unit/provenance/test_activity_shape.py",
        "tests/unit/persistence/test_mapper.py",
        "tests/feature/test_technical_models.py",
    }
)


def _is_generator(module: str) -> bool:
    return module == GENERATOR or module.startswith(f"{GENERATOR}.")


def _string_constants(node: ast.AST) -> list[str]:
    return [
        n.value for n in ast.walk(node) if isinstance(n, ast.Constant) and isinstance(n.value, str)
    ]


def _called_name(call: ast.Call) -> str:
    function = call.func
    if isinstance(function, ast.Attribute):
        return function.attr
    return function.id if isinstance(function, ast.Name) else ""


def _named_modules(tree: ast.AST) -> list[str]:
    """Every module a tree imports, loads as a plugin, or passes to ``import_module``."""
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.append(node.module)
        elif isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == PLUGINS_NAME for t in node.targets
        ):
            modules += _string_constants(node.value)
        elif isinstance(node, ast.Call) and _called_name(node) in IMPORT_FUNCTIONS:
            modules += [c for arg in node.args[:1] for c in _string_constants(arg)]
    return modules


def generator_users(root: Path) -> set[str]:
    """The test files below ``root/tests`` outside the generator's folder that name the generator."""
    found: set[str] = set()
    for path in sorted((root / "tests").rglob("*.py")):
        relative = path.relative_to(root).as_posix()
        if relative.startswith(GENERATOR_TESTS):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
        if any(_is_generator(module) for module in _named_modules(tree)):
            found.add(relative)
    return found


def problems(root: Path, tool_users: frozenset[str]) -> list[str]:
    """One message per unlisted file that uses the generator and per listed file that does not."""
    users = generator_users(root)
    unlisted = [
        f"{path} imports {GENERATOR} and is not in TOOL_USERS"
        for path in sorted(users - tool_users)
    ]
    stale = [
        f"{path} is in TOOL_USERS but no longer imports {GENERATOR}"
        for path in sorted(tool_users - users)
    ]
    return unlisted + stale


def _tests_tree(root: Path, files: dict[str, str]) -> None:
    for relative, source in files.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source, encoding="utf-8")


@pytest.mark.parametrize(
    "source",
    [
        f"import {GENERATOR}\n",
        f"import {GENERATOR}.config as config\n",
        f"from {GENERATOR}.cli import main\n",
        f'pytest_plugins = ["{GENERATOR}.testkit.freshness"]\n',
        f'pytest_plugins = ["pytester", "{GENERATOR}.testkit.freshness"]\n',
        f'import importlib\nmodule = importlib.import_module("{GENERATOR}.config")\n',
        f'from importlib import import_module\nmodule = import_module("{GENERATOR}")\n',
        f"def test_x() -> None:\n    from {GENERATOR}.generated import rp_generation\n",
    ],
    ids=[
        "import",
        "import-as",
        "from-import",
        "plugin-list",
        "plugin-among-others",
        "importlib-call",
        "import-module-call",
        "import-inside-a-function",
    ],
)
def test_a_library_test_naming_the_generator_is_named_by_the_checker(
    tmp_path: Path, source: str
) -> None:
    """TC-27: each way of reaching the generator is found, and the file is named."""
    _tests_tree(tmp_path, {"tests/unit/services/test_thing.py": source})

    assert problems(tmp_path, frozenset()) == [
        f"tests/unit/services/test_thing.py imports {GENERATOR} and is not in TOOL_USERS"
    ], "the checker did not name the file that reaches the generator"


@pytest.mark.parametrize(
    "source",
    [
        "import rdf_persistence\n",
        "from rdf_persistence.testkit import freshness\n",
        'pytest_plugins = ["pytester", "rdf_persistence.testkit.freshness"]\n',
        f'path = "{GENERATOR}"\nlabel = "{GENERATOR}.cli"\n',
        f'import rdf_persistence_generation_extra as extra\nname = "{GENERATOR}x"\n',
    ],
    ids=["library-import", "library-plugin-path", "library-plugin", "plain-strings", "other-name"],
)
def test_a_library_test_not_reaching_the_generator_is_left_alone(
    tmp_path: Path, source: str
) -> None:
    """TC-27: the library's own modules, plain strings and a name that merely starts alike pass."""
    _tests_tree(tmp_path, {"tests/unit/services/test_thing.py": source})

    assert problems(tmp_path, frozenset()) == [], "the checker flagged a file that is not a user"


def test_the_generators_own_tests_may_import_it(tmp_path: Path) -> None:
    """TC-27: ``tests/generator/`` is the generator's pyramid and is not read."""
    _tests_tree(tmp_path, {"tests/generator/unit/test_cli.py": f"import {GENERATOR}\n"})

    assert problems(tmp_path, frozenset()) == [], "a generator test was flagged"


def test_a_listed_tool_user_passes(tmp_path: Path) -> None:
    """TC-27: a file in ``TOOL_USERS`` that imports the generator raises nothing."""
    _tests_tree(tmp_path, {"tests/unit/services/test_thing.py": f"import {GENERATOR}\n"})

    assert problems(tmp_path, frozenset({"tests/unit/services/test_thing.py"})) == [], (
        "a listed tool user was flagged"
    )


def test_a_listed_file_that_no_longer_imports_the_generator_is_named_as_stale(
    tmp_path: Path,
) -> None:
    """TC-28a: an entry whose file imports no generator module is named."""
    _tests_tree(tmp_path, {"tests/unit/services/test_thing.py": "import json\n"})

    assert problems(tmp_path, frozenset({"tests/unit/services/test_thing.py"})) == [
        f"tests/unit/services/test_thing.py is in TOOL_USERS but no longer imports {GENERATOR}"
    ], "the stale entry was not named"


def test_a_listed_file_that_does_not_exist_is_named_as_stale(tmp_path: Path) -> None:
    """TC-28a: an entry whose file was deleted or renamed is stale too."""
    _tests_tree(tmp_path, {"tests/unit/test_other.py": "import json\n"})

    assert problems(tmp_path, frozenset({"tests/unit/gone.py"})) == [
        f"tests/unit/gone.py is in TOOL_USERS but no longer imports {GENERATOR}"
    ], "the missing file was not named"


def test_tool_users_are_the_nine_files_of_the_design() -> None:
    """TC-28: the eight of PD-9 and the one D-13 adds, so a tenth is a decision, not an edit."""
    assert len(TOOL_USERS) == 9, "TOOL_USERS differs from the nine files of design PD-9 and D-13"


def test_the_repository_tests_keep_the_two_pyramids_apart() -> None:
    """TC-28: no library test outside ``TOOL_USERS`` imports the generator, and no entry is stale."""
    assert problems(REPO, TOOL_USERS) == [], "the library tests and the generator's are mixed"
