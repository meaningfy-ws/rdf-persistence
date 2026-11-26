"""Swap and check the test-selection data (agent-test-control PD-6, PD-7).

Run from the repository root as ``uv run python -m tests.testmon_data swap <pytest-exit-code>`` or
``... check``. ``swap`` moves ``.testmondata.seed`` over ``.testmondata`` after a seed run that
ended with pytest's exit 0 or 1, under the exclusive worktree lock; any other exit deletes the seed
files. ``check`` exits 0 for sound data and a distinct code, with a message, for each other
outcome. ``seed -- <command...>`` is the seed's whole cycle in one process (test-control-testkit
PD-7): it deletes the seed files, runs the command, then swaps; the queue holds its lock
throughout. ``worktree_lock`` is the shared/exclusive ``.testmondata.lock`` of PD-6, also used by
``tests/changed.py``.
"""

import fcntl
import os
import sqlite3
import subprocess
import sys
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from enum import IntEnum
from pathlib import Path

DATA = ".testmondata"
SEED = ".testmondata.seed"
LOCK = ".testmondata.lock"
SIDE_FILES = (".testmondata-wal", ".testmondata-shm")
FINISHED_RUN_EXITS = (0, 1)  # pytest: all passed, some failed; the data is complete either way
NO_SEED_EXIT = 70
USAGE_EXIT = 64

DAMAGED_MESSAGE = (
    "selection data is damaged: delete .testmondata and ask the lead for make test-seed"
)
PACKAGES_MESSAGE = "packages changed since the seed: the lead re-runs make test-seed"


class Outcome(IntEnum):
    """What `check` found; the value is the exit code of ``check``."""

    SOUND = 0
    DAMAGED = 3
    PACKAGES_CHANGED = 4
    NO_DATA = 5

    @property
    def message(self) -> str:
        return _MESSAGES.get(self, "")


_MESSAGES = {Outcome.DAMAGED: DAMAGED_MESSAGE, Outcome.PACKAGES_CHANGED: PACKAGES_MESSAGE}


@contextmanager
def worktree_lock(
    root: Path, *, exclusive: bool, on_wait: Callable[[], None] | None = None
) -> Iterator[None]:
    """Hold ``.testmondata.lock`` under ``root``, shared (builders) or exclusive (the swap).

    ``on_wait`` is called once when the lock is not free at once, before blocking.
    """
    fd = os.open(root / LOCK, os.O_RDWR | os.O_CREAT, 0o644)
    mode = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
    try:
        try:
            fcntl.flock(fd, mode | fcntl.LOCK_NB)
        except BlockingIOError:
            if on_wait is not None:
                on_wait()
            fcntl.flock(fd, mode)
        yield
    finally:
        os.close(fd)  # closing releases the flock


def _delete(*paths: Path) -> None:
    for path in paths:
        path.unlink(missing_ok=True)


def _delete_seed_files(root: Path) -> None:
    _delete(*(p for p in root.iterdir() if p.name.startswith(SEED)))


def _fold_into_one_file(seed: Path) -> None:
    con = sqlite3.connect(seed)
    try:
        con.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchall()
        con.execute("PRAGMA journal_mode = DELETE").fetchall()
    finally:
        con.close()


def _say_waiting() -> None:
    print("waiting for the worktree lock: a builder's run holds it", file=sys.stderr, flush=True)


def swap(root: Path, pytest_exit: int) -> int:
    """Make the seed the selection data; returns the code ``main`` exits with."""
    seed = root / SEED
    if pytest_exit not in FINISHED_RUN_EXITS:
        _delete_seed_files(root)
        return pytest_exit
    if not seed.exists():
        print(f"no {SEED} to swap in", file=sys.stderr)
        return NO_SEED_EXIT
    _fold_into_one_file(seed)
    with worktree_lock(root, exclusive=True, on_wait=_say_waiting):
        _delete(*(root / name for name in SIDE_FILES))
        seed.rename(root / DATA)
    return pytest_exit


def seed(root: Path, command: Sequence[str]) -> int:
    """Clean the seed files, run ``command`` (it writes the seed), swap; the swap's code (PD-7).

    The child inherits the environment, so ``TESTMON_DATAFILE`` reaches pytest. The caller holds
    any queue lock; none is taken here.
    """
    try:
        _delete_seed_files(root)
    except OSError as error:
        print(f"cannot clean the seed files: {error}", file=sys.stderr)
        return 1
    exit_code = subprocess.run(list(command), check=False).returncode
    return swap(root, exit_code)


def _seed_packages(con: sqlite3.Connection) -> list[str]:
    rows = con.execute("SELECT system_packages FROM environment").fetchall()
    return [row[0] for row in rows]


def check(root: Path, packages: str) -> Outcome:
    """Is ``.testmondata`` intact and recorded under the current ``packages``?"""
    data = root / DATA
    if not data.exists():
        return Outcome.NO_DATA
    try:
        con = sqlite3.connect(f"{data.as_uri()}?mode=ro", uri=True)
        try:
            if con.execute("PRAGMA quick_check").fetchone() != ("ok",):
                return Outcome.DAMAGED
            seen = _seed_packages(con)
        finally:
            con.close()
    except sqlite3.DatabaseError:
        return Outcome.DAMAGED
    if seen and packages not in seen:
        return Outcome.PACKAGES_CHANGED
    return Outcome.SOUND


def current_packages() -> str:
    """The package string testmon records, by testmon's own functions (it drops patch versions)."""
    from testmon.common import drop_patch_version, get_system_packages

    return drop_patch_version(get_system_packages())


def main(argv: Sequence[str], root: Path | None = None) -> int:
    root = root or Path.cwd()
    match list(argv):
        case ["swap", code] if code.isdigit():
            return swap(root, int(code))
        case ["seed", "--", first, *rest]:
            return seed(root, [first, *rest])
        case ["check"]:
            outcome = check(root, current_packages())
            if outcome.message:
                print(outcome.message)
            return int(outcome)
        case _:
            print(
                "usage: python -m tests.testmon_data swap <pytest-exit-code> | check"
                " | seed -- <command...>",
                file=sys.stderr,
            )
            return USAGE_EXIT


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
