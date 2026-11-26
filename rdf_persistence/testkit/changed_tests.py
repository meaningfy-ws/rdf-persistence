"""Run the tests that cover the files changed against a base branch (test-control-testkit PD-3).

A project supplies a classifier, a module or object with ``classify(path)`` and
``is_testmon_visible(path)`` (the ``Classifier`` protocol), and a ``ChangedTestsLayout``; then
``sys.exit(changed_tests.main(classifier, layout))`` in its own ``tests/changed.py`` and
``python -m tests.changed`` runs the tests of the change. ``BASE`` names the base (default
``develop``), ``PYTEST_CHANGED_N`` the workers.

The planner makes the pytest runs and exits with their status: 0 passed or nothing to run,
pytest's 1, 2 and 4 as they are, pytest's 3 as 2, 2 for a bad ``PYTEST_CHANGED_N``, and 75 for "run
the project's full fast suite"; reasons, hints and messages go to stderr. Run on its own, with no
classifier, the module prints its usage and exits 2.
"""

import os
import subprocess
import sys
from collections.abc import Callable, Sequence
from contextlib import AbstractContextManager, nullcontext
from pathlib import Path
from typing import Protocol

from rdf_persistence.testkit.generated.rp_testkit import (
    ChangedSelection,
    ChangedTestsInvocation,
    ChangedTestsLayout,
    ChangedTestsPlan,
    SelectionDataOutcome,
)
from rdf_persistence.testkit.selection_data import MESSAGES, check, current_packages, worktree_lock

FALLBACK_EXIT = 75
NO_TESTS_EXIT = 5  # pytest: no test collected
USAGE_EXIT = 2
# pytest's exit status to ours (PD-4); a status not listed (a crash, a signal) is 1.
PYTEST_STATUS = {0: 0, 1: 1, 2: 2, 3: 2, 4: 4, NO_TESTS_EXIT: 0}
# The same distribution as the Makefile's PARALLEL: tests in one xdist_group share a worker.
DIST = ("--dist", "loadgroup")
TESTMON = ("--testmon", "--testmon-nocollect", "--testmon-forceselect")
NO_DATA_HINT = "no test selection data in this worktree: the lead runs make test-seed"


class Classifier(Protocol):
    """What a project says about a changed path."""

    def classify(self, path: str) -> ChangedSelection:
        """What one changed path selects, hints and falls back on."""
        ...

    def is_testmon_visible(self, path: str) -> bool:
        """Whether testmon tracks the file, so its selection covers a change to it."""
        ...


class GitError(Exception):
    """Git is missing, this is not a checkout, or the base does not exist."""


class UsageError(Exception):
    """An input of the run is wrong (PYTEST_CHANGED_N); the exit status is 2."""


def select(
    paths: Sequence[str], existing: Callable[[str], bool], classifier: Classifier
) -> ChangedSelection:
    """The selection for changed paths; `existing` says whether a selected path is still there."""
    chosen: set[str] = set()  # strings, never models: a model is not hashable (RISK-3)
    hints: list[str] = []
    reasons: list[str] = []
    for path in paths:
        one = classifier.classify(path)
        chosen.update(one.paths)
        hints += one.hints
        reasons += one.fallback_reasons
        reasons += [
            f"{path}: {folder} does not exist; run make test-fast"
            for folder in one.paths
            if folder.endswith("/") and not existing(folder)
        ]
    return ChangedSelection(paths=_kept(chosen, existing), hints=hints, fallback_reasons=reasons)


def _kept(chosen: set[str], existing: Callable[[str], bool]) -> list[str]:
    """The chosen paths that still exist and lie in no other chosen folder, sorted."""
    folders = [p for p in chosen if p.endswith("/")]
    return sorted(
        p for p in chosen if existing(p) and not any(p != f and p.startswith(f) for f in folders)
    )


def _is_extra_file(path: str, layout: ChangedTestsLayout) -> bool:
    return any(path == root or path.startswith(f"{root}/") for root in layout.extra_selected_by)


def _folder_invocation(
    paths: Sequence[str], workers: int, layout: ChangedTestsLayout
) -> ChangedTestsInvocation:
    one_process = all(not p.endswith("/") for p in paths)
    arguments = [*paths, *layout.ignores, *layout.markers]
    arguments += ["-n", "0" if one_process else str(workers), *DIST]
    return ChangedTestsInvocation(arguments=arguments)


def _testmon_invocation(
    workers: int, with_extra: bool, layout: ChangedTestsLayout
) -> ChangedTestsInvocation:
    folders = [*layout.testmon_folders]
    if with_extra and layout.extra_testmon_folder:
        folders.append(layout.extra_testmon_folder)
    arguments = [*folders, *layout.ignores, *layout.markers, *TESTMON]
    arguments += ["-n", str(workers), *DIST]
    return ChangedTestsInvocation(arguments=arguments)


def _split(
    changed: Sequence[str], has_data: bool, classifier: Classifier, layout: ChangedTestsLayout
) -> tuple[bool, list[str]]:
    """Whether testmon has a run, and the paths the folder rules cover."""
    if not has_data:
        return False, list(changed)
    visible = any(classifier.is_testmon_visible(p) for p in changed)
    rest = [p for p in changed if not classifier.is_testmon_visible(p) or _is_extra_file(p, layout)]
    return visible, rest


def _extra_selected(selection: ChangedSelection, layout: ChangedTestsLayout) -> bool:
    extra = layout.extra_testmon_folder
    return extra is not None and f"{extra.rstrip('/')}/" in selection.paths


def plan(  # noqa: PLR0913 - the signature PD-3 fixes: today's three arguments, the classifier and the layout
    changed: Sequence[str],
    has_data: bool,
    existing: Callable[[str], bool],
    workers: int,
    classifier: Classifier,
    layout: ChangedTestsLayout,
) -> ChangedTestsPlan:
    """The pytest runs for the changed files (agent-test-control PD-4, PD-5).

    With selection data, testmon selects for the files it can see (one run) and the folder rules
    cover the rest and the files under the layout's extra roots; without it, the folder rules cover
    every file. A fallback reason or nothing selected means no run.
    """
    visible, rest = _split(changed, has_data, classifier, layout)
    selection = select(rest, existing, classifier)
    hints = list(selection.hints)
    if not has_data and changed:
        hints.append(NO_DATA_HINT)
    if selection.fallback_reasons:
        return ChangedTestsPlan(
            invocations=[], hints=hints, fallback_reasons=selection.fallback_reasons
        )
    runs: list[ChangedTestsInvocation] = []
    if visible:
        runs.append(_testmon_invocation(workers, not _extra_selected(selection, layout), layout))
    if selection.paths:
        runs.append(_folder_invocation(selection.paths, workers, layout))
    return ChangedTestsPlan(invocations=runs, hints=hints, fallback_reasons=[])


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


Runner = Callable[[Sequence[str]], int]
DataState = Callable[[Path], SelectionDataOutcome]
Lock = Callable[[Path], AbstractContextManager[None]]


def _run_pytest(arguments: Sequence[str]) -> int:
    return subprocess.run(["pytest", *arguments], check=False).returncode


def _data_state(root: Path) -> SelectionDataOutcome:
    return check(root, current_packages())


def _say_waiting() -> None:
    print("waiting for the worktree lock: a seed swap holds it", file=sys.stderr, flush=True)


def _shared_lock(root: Path) -> AbstractContextManager[None]:
    return worktree_lock(root, exclusive=False, on_wait=_say_waiting)


def exit_status(pytest_exit: int) -> int:
    """Our exit status for one pytest run: 5 passes, 3 becomes 2, 1, 2 and 4 stay, the rest is 1."""
    return PYTEST_STATUS.get(pytest_exit, 1)


def _workers(default: int) -> int:
    """The workers of PYTEST_CHANGED_N: a decimal integer of 1 or more, or `default` if unset."""
    value = os.environ.get("PYTEST_CHANGED_N")  # noqa: TID251 - the command line is this module's config boundary
    if not value:
        return default
    if not (value.isascii() and value.isdigit() and int(value) >= 1):
        raise UsageError(f"PYTEST_CHANGED_N must be a positive integer, got '{value}'")
    return int(value)


def _run_plan(
    invocations: Sequence[ChangedTestsInvocation], root: Path, run: Runner, lock: Lock
) -> int:
    for invocation in invocations:
        uses_data = TESTMON[0] in invocation.arguments
        with lock(root) if uses_data else nullcontext():
            pytest_exit = run(invocation.arguments)
        if pytest_exit == NO_TESTS_EXIT:
            what = "testmon selected no test" if uses_data else "no test collected"
            print(what, file=sys.stderr)
        status = exit_status(pytest_exit)
        if status != 0:
            return status
    return 0


def main(
    classifier: Classifier,
    layout: ChangedTestsLayout,
    *,
    run: Runner = _run_pytest,
    data_state: DataState = _data_state,
    lock: Lock = _shared_lock,
) -> int:
    """Run the tests of the files changed against BASE; the exit codes are PD-4's."""
    try:
        workers = _workers(layout.default_workers)
    except UsageError as error:
        print(error, file=sys.stderr)
        return USAGE_EXIT
    base = os.environ.get("BASE", "develop")  # noqa: TID251 - the command line is this module's config boundary
    try:
        root = Path(_git("rev-parse", "--show-toplevel").strip())
        os.chdir(root)
        changed = changed_files(base)
    except GitError as error:
        print(f"{error}; running make test-fast", file=sys.stderr)
        return FALLBACK_EXIT
    outcome = data_state(root)
    if outcome in MESSAGES:
        print(MESSAGES[outcome], file=sys.stderr)
    with_data = outcome is SelectionDataOutcome.SOUND
    tests_plan = plan(changed, with_data, lambda p: Path(p).exists(), workers, classifier, layout)
    for hint in tests_plan.hints:
        print(hint, file=sys.stderr)
    if tests_plan.fallback_reasons:
        print(*tests_plan.fallback_reasons, sep="\n", file=sys.stderr)
        return FALLBACK_EXIT
    if not tests_plan.invocations:
        print(f"nothing to run against {base}", file=sys.stderr)
        return 0
    return _run_plan(tests_plan.invocations, root, run, lock)


def _usage() -> int:
    """What running the module by name does: it has no classifier, so it says how to use it."""
    try:
        _workers(1)  # a bad PYTEST_CHANGED_N is reported first, as ``main`` does
    except UsageError as error:
        print(error, file=sys.stderr)
        return USAGE_EXIT
    print(
        "usage: a project's tests/changed.py calls "
        "sys.exit(changed_tests.main(classifier, layout)); see the user manual, "
        "'Test control for your project'",
        file=sys.stderr,
    )
    return USAGE_EXIT


if __name__ == "__main__":
    sys.exit(_usage())
