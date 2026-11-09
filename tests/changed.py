"""Map the files changed against a base branch to the test folders that cover them.

Run as ``uv run python -m tests.changed``. Prints the pytest arguments, one per line (paths, then
``-n`` and its value); nothing when no test is to run. Reasons and hints go to stderr. Exit 3 means
"run make test-fast"; see openspec/changes/test-lanes/design.md (PD-1 to PD-5).
"""

import os
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

FALLBACK_EXIT = 3
LAYERS = frozenset({"domain", "services", "adapters", "entrypoints", "generation", "testkit"})
NO_TEST_ROOTS = frozenset({"openspec", ".claude", "temp"})
SHARED_FILES = frozenset({"pytest.ini", "pyproject.toml", "uv.lock", "Makefile", ".coveragerc"})
DOMAIN_FOLDER = "tests/unit/domain/"


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


def root_unit_tests() -> list[str]:
    """The test files at the root of tests/unit, relative to the repository root."""
    return sorted(p.as_posix() for p in Path("tests/unit").glob("test_*.py"))


def _test_folder_of(parts: tuple[str, ...], root_tests: Sequence[str]) -> list[str] | None:
    """The tests that cover a path under tests/ or rdf_persistence/, None if no rule applies."""
    if parts[0] == "tests" and len(parts) > 2 and parts[1] == "unit":
        if len(parts) > 3:
            return [f"tests/unit/{parts[2]}/"]
        # a root-level file that is no test (conftest.py, helpers.py) would collect nothing
        is_test = parts[2].startswith("test_") and parts[2].endswith(".py")
        return [PurePosixPath(*parts).as_posix()] if is_test else None
    if parts[0] == "tests" and len(parts) > 1 and parts[1] == "feature":
        return ["tests/feature/"]
    if parts[0] == "rdf_persistence" and len(parts) > 2 and parts[1] in LAYERS:
        return [f"tests/unit/{parts[1]}/"]
    if parts[0] == "rdf_persistence" and len(parts) > 1:
        return list(root_tests)
    return None


def _classify(path: str, root_tests: Sequence[str]) -> Selection:
    """What one changed path selects, hints and falls back on; the first matching rule wins."""
    parts = PurePosixPath(path).parts
    name = parts[-1]
    if parts[0] in NO_TEST_ROOTS or (len(parts) == 1 and name.endswith(".md")):
        return Selection((), (), ())
    if parts[0] == "docs":
        return Selection(("tests/unit/test_check_docs.py",), (), ())
    if _is_shared_infrastructure(parts):
        return Selection((), (), (f"{path}: shared test infrastructure or schema",))
    if len(parts) > 2 and parts[:2] in {("tests", "integration"), ("tests", "e2e")}:
        if name.startswith("test_") and name.endswith(".py"):
            return Selection((), (f"{path}: run make test-containers",), ())
        return Selection((), (), (f"{path}: helper imported by unit tests",))
    if parts[:2] == ("tests", "perf"):
        return Selection((), (f"{path}: run make test-perf",), ())
    selected = _test_folder_of(parts, root_tests)
    if selected is None:
        return Selection((), (), (f"{path}: no rule maps it to tests",))
    return Selection(tuple(selected), (), ())


def select(
    paths: Sequence[str], existing: Callable[[str], bool], root_tests: Sequence[str]
) -> Selection:
    """The selection for changed paths; `root_tests` are the test files at the root of tests/unit."""
    chosen: set[str] = set()
    hints: list[str] = []
    reasons: list[str] = []
    for path in paths:
        one = _classify(path, root_tests)
        chosen.update(one.paths)
        hints += one.hints
        reasons += one.fallback_reasons
    folders = [p for p in chosen if p.endswith("/")]
    kept = sorted(
        p for p in chosen if existing(p) and not any(p != f and p.startswith(f) for f in folders)
    )
    return Selection(tuple(kept), tuple(hints), tuple(reasons))


def pytest_arguments(paths: Sequence[str], pytest_n: str | None) -> list[str]:
    """The pytest arguments for a selection: nothing when it is empty, else paths then -n."""
    if not paths:
        return []
    one_process = all(not p.endswith("/") for p in paths) or list(paths) == [DOMAIN_FOLDER]
    return [*paths, "-n", pytest_n or ("0" if one_process else "auto")]


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
    selection = select(changed, lambda path: Path(path).exists(), root_unit_tests())
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
