"""The selection data's swap and check (agent-test-control PD-6, PD-7): `tests/testmon_data.py`.

Real SQLite files in `tmp_path`, in WAL mode like testmon's. The worktree lock is proved with a real
child process: no sleeps, the child signals readiness on its stdout pipe and the swap prints a
line on stderr when it starts to wait.
"""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from tests import testmon_data
from tests.testmon_data import (
    DAMAGED_MESSAGE,
    PACKAGES_MESSAGE,
    Outcome,
    check,
    swap,
)

REPO = Path(__file__).resolve().parents[3]
PYTHON = sys.executable
PACKAGES = "alpha 1.0, beta 2.0"

HOLD_SHARED = """
import fcntl, os, sys
fd = os.open(sys.argv[1], os.O_RDWR | os.O_CREAT)
fcntl.flock(fd, fcntl.LOCK_SH)
print("ready", flush=True)
sys.stdin.read()
"""


def make_data(path: Path, packages: str = PACKAGES, marker: str = "x") -> None:
    """A testmon-like database in WAL mode, left with its -wal file beside it (not checkpointed)."""
    con = sqlite3.connect(path)
    con.execute("PRAGMA journal_mode = WAL")
    con.execute("PRAGMA wal_autocheckpoint = 0")
    con.execute(
        "CREATE TABLE environment (id INTEGER PRIMARY KEY, environment_name TEXT,"
        " system_packages TEXT, python_version TEXT)"
    )
    con.execute("CREATE TABLE marker (value TEXT)")
    con.execute("INSERT INTO environment VALUES (1, 'default', ?, '3.12')", (packages,))
    con.execute("INSERT INTO marker VALUES (?)", (marker,))
    con.commit()
    con.close()


def read_marker(path: Path) -> str:
    con = sqlite3.connect(path)
    try:
        return con.execute("SELECT value FROM marker").fetchone()[0]
    finally:
        con.close()


def journal_mode(path: Path) -> str:
    con = sqlite3.connect(path)
    try:
        return con.execute("PRAGMA journal_mode").fetchone()[0]
    finally:
        con.close()


def cli_env() -> dict[str, str]:
    """The command runs in the worktree root (the cwd); the test's root is a tmp dir."""
    return {**os.environ, "PYTHONPATH": str(REPO)}


def names(root: Path) -> set[str]:
    return {p.name for p in root.iterdir()}


@pytest.mark.parametrize("pytest_exit", [0, 1])
@pytest.mark.parametrize("stale_wal", [False, True])
def test_swap_after_a_finished_run_leaves_one_readable_delete_mode_file(
    tmp_path: Path, pytest_exit: int, stale_wal: bool
) -> None:
    make_data(tmp_path / ".testmondata", marker="old")
    make_data(tmp_path / ".testmondata.seed", marker="new")
    if stale_wal:
        (tmp_path / ".testmondata-wal").write_bytes(b"stale bytes from an older run")
        (tmp_path / ".testmondata-shm").write_bytes(b"stale")

    code = swap(tmp_path, pytest_exit)

    assert code == pytest_exit, "the swap passes pytest's 0 or 1 through"
    assert read_marker(tmp_path / ".testmondata") == "new", "the seed's data replaced the old"
    assert journal_mode(tmp_path / ".testmondata") == "delete", "the data is left in DELETE mode"
    assert names(tmp_path) == {".testmondata", ".testmondata.lock"}, "no seed, -wal or -shm remains"


@pytest.mark.parametrize("pytest_exit", [2, 3, 4, 130])
def test_swap_after_an_interrupted_run_deletes_the_seed_and_keeps_the_old_data(
    tmp_path: Path, pytest_exit: int
) -> None:
    make_data(tmp_path / ".testmondata", marker="old")
    make_data(tmp_path / ".testmondata.seed", marker="new")

    code = swap(tmp_path, pytest_exit)

    assert code == pytest_exit, "pytest's code is passed through"
    assert read_marker(tmp_path / ".testmondata") == "old", "the old data is kept"
    assert not [n for n in names(tmp_path) if n.startswith(".testmondata.seed")], "no seed file"


def test_swap_without_a_seed_fails_and_keeps_the_old_data(tmp_path: Path) -> None:
    make_data(tmp_path / ".testmondata", marker="old")

    code = swap(tmp_path, 0)

    assert code == testmon_data.NO_SEED_EXIT, "a missing seed is a failure, not a swap"
    assert read_marker(tmp_path / ".testmondata") == "old", "the old data is kept"


def test_swap_waits_for_a_shared_holder_and_swaps_once_it_is_gone(tmp_path: Path) -> None:
    make_data(tmp_path / ".testmondata", marker="old")
    make_data(tmp_path / ".testmondata.seed", marker="new")
    holder = subprocess.Popen(
        [PYTHON, "-c", HOLD_SHARED, str(tmp_path / ".testmondata.lock")],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    swapper = None
    try:
        assert holder.stdout.readline().strip() == "ready", "the holder has the shared lock"
        swapper = subprocess.Popen(
            [PYTHON, "-m", "tests.testmon_data", "swap", "0"],
            cwd=tmp_path,
            env=cli_env(),
            stderr=subprocess.PIPE,
            text=True,
        )
        assert "waiting" in swapper.stderr.readline(), "the swap says it waits for the lock"
        assert swapper.poll() is None, "the swap is blocked while a builder holds the lock"
        assert read_marker(tmp_path / ".testmondata") == "old", "nothing is renamed yet"
        assert journal_mode(tmp_path / ".testmondata.seed") == "delete", (
            "the checkpoint happens before the lock, so the lock covers only the rename"
        )
        holder.kill()
        holder.wait()
        assert swapper.wait(timeout=30) == 0, "the swap finishes once the holder is gone"
    finally:
        holder.kill()
        if swapper is not None:
            swapper.kill()
            swapper.wait()
        holder.wait()
    assert read_marker(tmp_path / ".testmondata") == "new", "the seed's data is in place"


def test_check_passes_a_sound_file(tmp_path: Path) -> None:
    make_data(tmp_path / ".testmondata")

    assert check(tmp_path, PACKAGES) is Outcome.SOUND, "same packages, intact file"


def test_check_names_a_damaged_file(tmp_path: Path) -> None:
    (tmp_path / ".testmondata").write_bytes(os.urandom(4096))

    assert check(tmp_path, PACKAGES) is Outcome.DAMAGED, "garbage bytes are damaged data"


def test_check_names_changed_packages(tmp_path: Path) -> None:
    make_data(tmp_path / ".testmondata", packages="alpha 0.9, beta 2.0")

    assert check(tmp_path, PACKAGES) is Outcome.PACKAGES_CHANGED, "the seed saw other packages"


def test_check_of_a_missing_file_is_no_data(tmp_path: Path) -> None:
    assert check(tmp_path, PACKAGES) is Outcome.NO_DATA, "nothing to check"
    assert names(tmp_path) == set(), "checking creates no file"


@pytest.mark.parametrize(
    ("outcome", "message"),
    [
        (
            Outcome.DAMAGED,
            "selection data is damaged: delete .testmondata and ask the lead for make test-seed",
        ),
        (
            Outcome.PACKAGES_CHANGED,
            "packages changed since the seed: the lead re-runs make test-seed",
        ),
    ],
)
def test_the_messages_are_the_decided_ones(outcome: Outcome, message: str) -> None:
    assert outcome.message == message, "the PD-7 wording, verbatim"
    assert message in {DAMAGED_MESSAGE, PACKAGES_MESSAGE}, "exported under a name"


def test_outcomes_have_distinct_exit_codes() -> None:
    codes = [o.value for o in Outcome]

    assert len(set(codes)) == len(codes), "one exit code per outcome"
    assert Outcome.SOUND.value == 0, "sound exits 0"


def test_check_command_prints_the_message_and_exits_with_the_outcome(tmp_path: Path) -> None:
    (tmp_path / ".testmondata").write_bytes(os.urandom(4096))

    done = subprocess.run(
        [PYTHON, "-m", "tests.testmon_data", "check"],
        cwd=tmp_path,
        env=cli_env(),
        capture_output=True,
        text=True,
        check=False,
    )

    assert done.returncode == Outcome.DAMAGED.value, "the exit code names the outcome"
    assert DAMAGED_MESSAGE in done.stdout, "the message is printed"
