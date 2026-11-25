"""Map the files changed against a base branch to the test folders that cover them.

Run as ``uv run python -m tests.changed``. Prints the pytest arguments, one per line (paths, then
``-n`` and its value, then ``--dist loadgroup``); nothing when no test is to run. Reasons and hints go to stderr. Exit 3 means
"run make test-fast"; see openspec/changes/archive/2026-11-09-test-lanes/design.md (PD-1 to PD-5).
"""

import os
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

FALLBACK_EXIT = 3
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
# The same distribution as the Makefile's PARALLEL: tests in one xdist_group share a worker.
DIST = ("--dist", "loadgroup")
# The Makefile's UNIT_LANE ignores as relative paths, and the marker filter of every lane
# (agent-test-control PD-5); a test in test_lanes.py pins the first to the Makefile.
IGNORES = (
    "--ignore=tests/integration",
    "--ignore=tests/e2e",
    "--ignore=tests/perf",
    "--ignore=tests/generator/e2e",
)
MARKERS = ("-m", "(unit or feature) and not quarantine")
TESTMON = ("--testmon", "--testmon-nocollect", "--testmon-forceselect")
NO_DATA_HINT = "no test selection data in this worktree: the lead runs make test-seed"
DEFAULT_WORKERS = 4
# Files whose tests testmon cannot see: the generator's tests run it in subprocesses.
GENERATOR_ROOTS = (GENERATOR_PACKAGE, "tests/generator")


@dataclass(frozen=True)
class Selection:
    paths: tuple[str, ...]
    hints: tuple[str, ...]
    fallback_reasons: tuple[str, ...]


class GitError(Exception):
    """Git is missing, this is not a checkout, or the base does not exist."""


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


def _classify(path: str) -> Selection:
    """What one changed path selects, hints and falls back on; the first matching rule wins."""
    parts = PurePosixPath(path).parts
    name = parts[-1]
    if parts[0] in NO_TEST_ROOTS or (len(parts) == 1 and name.endswith(".md")):
        return Selection((), (), ())
    if parts[0] == "docs":
        return Selection((DOCS_CHECK_TEST,), (), ())
    if _is_shared_infrastructure(parts):
        return Selection((), (), (f"{path}: shared test infrastructure or schema",))
    if parts[0] == "rdf_persistence" and len(parts) > 1 and parts[1] == CORE_THEME:
        return Selection((), (), (f"{path}: core is imported by every theme; run make test-fast",))
    if len(parts) > 2 and parts[:2] in {("tests", "integration"), ("tests", "e2e")}:
        if name.startswith("test_") and name.endswith(".py"):
            return Selection((), (f"{path}: run make test-containers",), ())
        return Selection((), (), (f"{path}: helper imported by unit tests",))
    if parts[:2] == ("tests", "perf"):
        return Selection((), (f"{path}: run make test-perf",), ())
    selected = _test_folder_of(parts)
    if selected is None:
        return Selection((), (), (f"{path}: no rule maps it to tests",))
    return Selection(tuple(selected), (), ())


def select(paths: Sequence[str], existing: Callable[[str], bool]) -> Selection:
    """The selection for changed paths; `existing` says whether a selected path is still there."""
    chosen: set[str] = set()
    hints: list[str] = []
    reasons: list[str] = []
    for path in paths:
        one = _classify(path)
        chosen.update(one.paths)
        hints += one.hints
        reasons += one.fallback_reasons
        reasons += [
            f"{path}: {folder} does not exist; run make test-fast"
            for folder in one.paths
            if folder.endswith("/") and not existing(folder)
        ]
    folders = [p for p in chosen if p.endswith("/")]
    kept = sorted(
        p for p in chosen if existing(p) and not any(p != f and p.startswith(f) for f in folders)
    )
    return Selection(tuple(kept), tuple(hints), tuple(reasons))


def pytest_arguments(paths: Sequence[str], pytest_n: str | None) -> list[str]:
    """The pytest arguments for a selection: nothing when it is empty, else paths then -n."""
    if not paths:
        return []
    one_process = all(not p.endswith("/") for p in paths)
    return [*paths, "-n", pytest_n or ("0" if one_process else "auto"), *DIST]


@dataclass(frozen=True)
class Invocation:
    """One pytest run: its argument list, without the interpreter."""

    arguments: tuple[str, ...]


@dataclass(frozen=True)
class Plan:
    invocations: tuple[Invocation, ...]
    hints: tuple[str, ...]
    fallback_reasons: tuple[str, ...]


def _is_testmon_visible(path: str) -> bool:
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


def _is_generator_file(path: str) -> bool:
    return any(path == root or path.startswith(f"{root}/") for root in GENERATOR_ROOTS)


def _folder_invocation(paths: Sequence[str], workers: int) -> Invocation:
    one_process = all(not p.endswith("/") for p in paths)
    return Invocation(
        (*paths, *IGNORES, *MARKERS, "-n", "0" if one_process else str(workers), *DIST)
    )


def _testmon_invocation(workers: int, with_generator: bool) -> Invocation:
    folders = ("tests/unit", "tests/feature", *(("tests/generator",) if with_generator else ()))
    return Invocation((*folders, *IGNORES, *MARKERS, *TESTMON, "-n", str(workers), *DIST))


def plan(
    changed: Sequence[str],
    has_data: bool,
    existing: Callable[[str], bool],
    workers: int = DEFAULT_WORKERS,
) -> Plan:
    """The pytest runs for the changed files (agent-test-control PD-4, PD-5).

    With selection data, testmon selects for the files it can see (one run) and the folder rules
    cover the rest and the generator's files; without it, the folder rules cover every file.
    A fallback reason or nothing selected means no run.
    """
    if has_data:
        visible = any(_is_testmon_visible(p) for p in changed)
        rest = [p for p in changed if not _is_testmon_visible(p) or _is_generator_file(p)]
    else:
        visible, rest = False, list(changed)
    selection = select(rest, existing)
    hints = selection.hints
    if not has_data and changed:
        hints = (*hints, NO_DATA_HINT)
    if selection.fallback_reasons:
        return Plan((), hints, selection.fallback_reasons)
    runs: list[Invocation] = []
    if visible:
        with_generator = GENERATOR_TESTS not in selection.paths
        runs.append(_testmon_invocation(workers, with_generator))
    if selection.paths:
        runs.append(_folder_invocation(selection.paths, workers))
    return Plan(tuple(runs), hints, ())


def _git(*args: str) -> str:
    try:
        done = subprocess.run(["git", *args], capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError) as error:
        detail = getattr(error, "stderr", None) or str(error)
        raise GitError(f"git {' '.join(args)}: {detail.strip()}") from error
    return done.stdout


def changed_files(base: str) -> list[str]:
    """Files changed against the merge base with `base`: committed, uncommitted, untracked."""
    try:
        merge_base = _git("merge-base", "--end-of-options", "HEAD", base).strip()
    except GitError as error:
        raise GitError(f"{error} (is `{base}` a local branch? try BASE=origin/{base})") from error
    tracked = _git("diff", "--name-only", "--no-renames", merge_base).splitlines()
    untracked = _git("ls-files", "--others", "--exclude-standard").splitlines()
    return sorted({*tracked, *untracked})


def main() -> int:
    base = os.environ.get("BASE", "develop")
    try:
        os.chdir(_git("rev-parse", "--show-toplevel").strip())
        changed = changed_files(base)
    except GitError as error:
        print(f"{error}; running make test-fast", file=sys.stderr)
        return FALLBACK_EXIT
    selection = select(changed, lambda path: Path(path).exists())
    if selection.fallback_reasons:
        print(*selection.fallback_reasons, sep="\n", file=sys.stderr)
        return FALLBACK_EXIT
    for hint in selection.hints:
        print(hint, file=sys.stderr)
    arguments = pytest_arguments(selection.paths, os.environ.get("PYTEST_N"))
    if not arguments:
        print(f"nothing to run against {base}", file=sys.stderr)
        return 0
    # shortcut: the Makefile splits these lines on whitespace, so a path with a space breaks it;
    # switch to NUL-separated output if such a path ever appears.
    print(*arguments, sep="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
