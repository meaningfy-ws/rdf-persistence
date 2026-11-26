"""This repository's classifier for the changed-tests planner: the folder rules of its layout.

Run as ``uv run python -m tests.changed`` (``BASE`` names the base, ``PYTEST_CHANGED_N`` the
workers). The planner, the exit codes and the messages are the testkit's
(``rdf_persistence.testkit.changed_tests``); this module keeps only what is ours: which tests cover
a changed path (``classify``), what testmon can see (``is_testmon_visible``) and the ``LAYOUT``. See
openspec/changes/test-control-testkit/design.md (PD-3, PD-4) and, for the folder rules,
openspec/changes/archive/2026-11-09-test-lanes/design.md.
"""

import sys
from pathlib import PurePosixPath

from rdf_persistence.testkit import changed_tests
from rdf_persistence.testkit.generated.rp_testkit import ChangedSelection, ChangedTestsLayout

OUTSIDE_THEMES = frozenset(
    {"testkit"}
)  # package folders that are no theme but have tests of their own (PD-11)
# thematic-structure PD-1, PD-11: rdf_persistence/<theme>/<layer>/ is covered by tests/unit/<theme>/.
# `core` is imported by every theme, so a change in it runs the whole fast suite.
THEMES = frozenset(
    {
        "core",
        "iris",
        "schema",
        "files",
        "provenance",
        "persistence",
        "migrations",
        "access",
        "tenancy",
        "events",
        "collaboration",
        "messaging",
        "api",
    }
)
CORE_THEME = "core"
NO_TEST_ROOTS = frozenset({"openspec", ".claude", "temp"})
SHARED_FILES = frozenset({"pytest.ini", "pyproject.toml", "uv.lock", "Makefile", ".coveragerc"})
# The generator's own pyramid (generator-package PD-9, PD-10): its code selects all of it.
GENERATOR_PACKAGE = "rdf_persistence_generation"
GENERATOR_TESTS = "tests/generator/"
# Where testmon selects (the generator's folder is added unless its rule already selected it), the
# Makefile's UNIT_LANE ignores as relative paths and the marker filter of every lane
# (agent-test-control PD-5). Files under the generator's roots also go through the folder rules,
# since the generator's tests run it in subprocesses that testmon cannot see.
LAYOUT = ChangedTestsLayout(
    testmon_folders=["tests/unit", "tests/feature"],
    extra_testmon_folder="tests/generator",
    extra_selected_by=[GENERATOR_PACKAGE, "tests/generator"],
    ignores=[
        "--ignore=tests/integration",
        "--ignore=tests/e2e",
        "--ignore=tests/perf",
        "--ignore=tests/generator/e2e",
    ],
    markers=["-m", "(unit or feature) and not quarantine"],
    default_workers=4,
)
# A test in test_lanes.py compares the ignores with the Makefile's, as a tuple.
IGNORES = tuple(LAYOUT.ignores)


def _is_shared_infrastructure(parts: tuple[str, ...]) -> bool:
    if len(parts) == 1:
        return parts[0] in SHARED_FILES
    if parts[0] == "rdf_persistence":
        return parts[1] == "model"
    if parts[0] != "tests":
        return False
    return (
        (len(parts) == 2 and parts[1].endswith(".py"))
        or parts[1] == "fixtures"
        or parts[1:] == ("unit", "__init__.py")
    )


# The tests of the rdf_persistence/ files that are in no theme (PD-11).
PACKAGE_TESTS = "tests/unit/package/"
# The test a change under docs/ selects.
DOCS_CHECK_TEST = "tests/unit/tooling/test_check_docs.py"


def _test_folder_of(parts: tuple[str, ...]) -> list[str] | None:
    """The tests that cover a path under tests/ or rdf_persistence/, None if no rule applies."""
    if parts[0] == "tests" and len(parts) > 2 and parts[1] == "unit":
        if len(parts) > 3:
            return [f"tests/unit/{parts[2]}/"]
        # a root-level file that is no test (conftest.py, helpers.py) would collect nothing
        is_test = parts[2].startswith("test_") and parts[2].endswith(".py")
        return [PurePosixPath(*parts).as_posix()] if is_test else None
    if parts[0] == "tests" and len(parts) > 1 and parts[1] == "feature":
        return ["tests/feature/"]
    if parts[0] == GENERATOR_PACKAGE and len(parts) > 1:
        return [GENERATOR_TESTS]
    if parts[0] == "tests" and len(parts) > 2 and parts[1] == "generator":
        return [GENERATOR_TESTS]
    if parts[0] == "rdf_persistence" and len(parts) > 2 and parts[1] in OUTSIDE_THEMES | THEMES:
        return [f"tests/unit/{parts[1]}/"]
    if parts[0] == "rdf_persistence" and len(parts) > 1:
        return [PACKAGE_TESTS]
    return None


def _selection(
    paths: list[str] | None = None, hints: list[str] | None = None, reasons: list[str] | None = None
) -> ChangedSelection:
    return ChangedSelection(paths=paths or [], hints=hints or [], fallback_reasons=reasons or [])


def classify(path: str) -> ChangedSelection:
    """What one changed path selects, hints and falls back on; the first matching rule wins."""
    parts = PurePosixPath(path).parts
    name = parts[-1]
    if parts[0] in NO_TEST_ROOTS or (len(parts) == 1 and name.endswith(".md")):
        return _selection()
    if parts[0] == "docs":
        return _selection([DOCS_CHECK_TEST])
    if _is_shared_infrastructure(parts):
        return _selection(reasons=[f"{path}: shared test infrastructure or schema"])
    if parts[0] == "rdf_persistence" and len(parts) > 1 and parts[1] == CORE_THEME:
        return _selection(reasons=[f"{path}: core is imported by every theme; run make test-fast"])
    if len(parts) > 2 and parts[:2] in {("tests", "integration"), ("tests", "e2e")}:
        if name.startswith("test_") and name.endswith(".py"):
            return _selection(hints=[f"{path}: run make test-containers"])
        return _selection(reasons=[f"{path}: helper imported by unit tests"])
    if parts[:2] == ("tests", "perf"):
        return _selection(hints=[f"{path}: run make test-perf"])
    selected = _test_folder_of(parts)
    if selected is None:
        return _selection(reasons=[f"{path}: no rule maps it to tests"])
    return _selection(selected)


def is_testmon_visible(path: str) -> bool:
    """A Python file testmon tracks: package, generator or tests code that is no golden text."""
    parts = PurePosixPath(path).parts
    if not path.endswith(".py") or parts[0] not in {"rdf_persistence", GENERATOR_PACKAGE, "tests"}:
        return False
    if parts[0] != "tests":
        return True
    if len(parts) > 1 and parts[1] == "fixtures":
        return False
    is_test = parts[-1].startswith("test_")
    return not (len(parts) > 2 and parts[1] in {"integration", "e2e", "perf"} and is_test)


if __name__ == "__main__":
    sys.exit(changed_tests.main(sys.modules[__name__], LAYOUT))
