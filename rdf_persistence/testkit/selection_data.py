"""Swap and check the test-selection data; see the user manual, ``user-manual/test.adoc``,
section *Test control for your project*.

Run from the repository root as
``uv run python -m rdf_persistence.testkit.selection_data swap <pytest-exit-code>`` or ``... check``. ``swap`` moves ``.testmondata.seed`` over ``.testmondata`` after a seed run that
ended with pytest's exit 0 or 1, under the exclusive worktree lock; any other exit deletes the seed
files. ``check`` exits 0 for sound data and a distinct code, with a message, for each other
outcome. ``seed -- <command...>`` is the seed's whole cycle in one process: it deletes the seed
files, reads the commit ``HEAD`` is on, runs the command, then swaps and records that commit in
``.testmondata.commit`` (``SEED_COMMIT``), beside the data it describes: a swap deletes the file
first and writes it back only when it was given a commit, so a ``swap <exit>`` from the command
line, or a worktree with no readable commit, leaves none. The queue holds its lock throughout.
``worktree_lock`` is the
shared/exclusive ``.testmondata.lock``, also used by ``changed_tests``.
"""

import fcntl
import os
import sqlite3
import subprocess
import sys
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path

from rdf_persistence.testkit.generated.rp_testkit import SelectionDataOutcome

__all__ = [
    "CHECK_EXIT",
    "MESSAGES",
    "SEED_COMMIT",
    "check",
    "current_packages",
    "main",
    "seed",
    "swap",
    "worktree_lock",
]

DATA = ".testmondata"
SEED = ".testmondata.seed"
LOCK = ".testmondata.lock"
SEED_COMMIT = ".testmondata.commit"  # the sha of HEAD the seed ran on, beside the data it describes
SIDE_FILES = (".testmondata-wal", ".testmondata-shm")
FINISHED_RUN_EXITS = (0, 1)  # pytest: all passed, some failed; the data is complete either way
NO_SEED_EXIT = 70
USAGE_EXIT = 64

DAMAGED_MESSAGE = "selection data is damaged: delete .testmondata and run make test-seed"
PACKAGES_MESSAGE = "packages changed since the seed: run make test-seed"


CHECK_EXIT: dict[SelectionDataOutcome, int] = {  # an index: the exit code of ``check`` per outcome
    SelectionDataOutcome.SOUND: 0,
    SelectionDataOutcome.DAMAGED: 3,
    SelectionDataOutcome.PACKAGES_CHANGED: 4,
    SelectionDataOutcome.NO_DATA: 5,
}
MESSAGES: dict[SelectionDataOutcome, str] = {  # an index: what ``check`` prints per outcome
    SelectionDataOutcome.DAMAGED: DAMAGED_MESSAGE,
    SelectionDataOutcome.PACKAGES_CHANGED: PACKAGES_MESSAGE,
}


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


def _write_commit(root: Path, commit: str) -> None:
    temporary = root / f"{SEED_COMMIT}.tmp"
    temporary.write_text(commit + "\n")
    os.replace(temporary, root / SEED_COMMIT)


def _head_commit(root: Path) -> str | None:
    """The sha of ``HEAD`` under ``root``; ``None`` without git, a repository or a commit."""
    try:
        done = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    sha = done.stdout.strip()
    return sha if done.returncode == 0 and sha else None


def swap(root: Path, pytest_exit: int, *, commit: str | None = None) -> int:
    """Make the seed the selection data; returns the code ``main`` exits with.

    The commit file goes before the rename and, when ``commit`` is given, comes back after it, so
    it always describes the data beside it.
    """
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
        _delete(root / SEED_COMMIT)
        seed.rename(root / DATA)
        if commit is not None:
            _write_commit(root, commit)
    return pytest_exit


def seed(
    root: Path,
    command: Sequence[str],
    run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> int:
    """Clean the seed files, run ``command`` (it writes the seed), swap; the swap's code (PD-7).

    The child inherits the environment, so ``TESTMON_DATAFILE`` reaches pytest, and the inheritable
    descriptors, so the queue's lock stays held (``close_fds=False``). A child killed by signal n
    counts as ``128 + n``, an interrupt of this process as 130; both leave the earlier data. A
    command that cannot start exits 127 with no swap.
    """
    try:
        _delete_seed_files(root)
    except OSError as error:
        print(f"cannot clean the seed files: {error}", file=sys.stderr)
        return 1
    commit = _head_commit(root)  # before the run: a commit made during it counts as later
    try:
        returncode = run(list(command), check=False, close_fds=False).returncode
    except KeyboardInterrupt:
        return swap(root, 130, commit=commit)
    except OSError as error:
        print(f"cannot run {command[0]}: {error}", file=sys.stderr)
        return 127
    exit_code = 128 - returncode if returncode < 0 else returncode
    return swap(root, exit_code, commit=commit)


def _seed_packages(con: sqlite3.Connection) -> list[str]:
    rows = con.execute("SELECT system_packages FROM environment").fetchall()
    return [row[0] for row in rows]


def check(root: Path, packages: str) -> SelectionDataOutcome:
    """Is ``.testmondata`` intact and recorded under the current ``packages``?"""
    data = root / DATA
    if not data.exists():
        return SelectionDataOutcome.NO_DATA
    try:
        con = sqlite3.connect(f"{data.as_uri()}?mode=ro", uri=True)
        try:
            if con.execute("PRAGMA quick_check").fetchone() != ("ok",):
                return SelectionDataOutcome.DAMAGED
            seen = _seed_packages(con)
        finally:
            con.close()
    except sqlite3.DatabaseError:
        return SelectionDataOutcome.DAMAGED
    if seen and packages not in seen:
        return SelectionDataOutcome.PACKAGES_CHANGED
    return SelectionDataOutcome.SOUND


def current_packages() -> str:
    """The package string testmon records, by testmon's own functions (it drops patch versions)."""
    from testmon.common import (  # type: ignore[import-untyped]  # testmon ships no types
        drop_patch_version,
        get_system_packages,
    )

    return str(drop_patch_version(get_system_packages()))


def main(argv: Sequence[str], root: Path | None = None) -> int:
    root = root or Path.cwd()
    match list(argv):
        case ["swap", code] if code.isascii() and code.isdigit():
            return swap(root, int(code))
        case ["seed", "--", first, *rest]:
            return seed(root, [first, *rest])
        case ["check"]:
            outcome = check(root, current_packages())
            if outcome in MESSAGES:
                print(MESSAGES[outcome])
            return CHECK_EXIT[outcome]
        case _:
            print(
                "usage: python -m rdf_persistence.testkit.selection_data swap <pytest-exit-code> | check"
                " | seed -- <command...>",
                file=sys.stderr,
            )
            return USAGE_EXIT


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
