"""The selection data's swap and check (agent-test-control PD-6, PD-7): `rdf_persistence/testkit/selection_data.py`.

Real SQLite files in `tmp_path`, in WAL mode like testmon's. The worktree lock is proved with a real
child process: no sleeps, the child signals readiness on its stdout pipe and the swap prints a
line on stderr when it starts to wait.
"""

import os
import sqlite3
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from rdf_persistence.testkit import selection_data as testmon_data
from rdf_persistence.testkit.generated.rp_testkit import SelectionDataOutcome
from rdf_persistence.testkit.selection_data import (
    CHECK_EXIT,
    DAMAGED_MESSAGE,
    MESSAGES,
    PACKAGES_MESSAGE,
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
            [PYTHON, "-m", "rdf_persistence.testkit.selection_data", "swap", "0"],
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

    assert check(tmp_path, PACKAGES) is SelectionDataOutcome.SOUND, "same packages, intact file"


def test_check_names_a_damaged_file(tmp_path: Path) -> None:
    (tmp_path / ".testmondata").write_bytes(os.urandom(4096))

    assert check(tmp_path, PACKAGES) is SelectionDataOutcome.DAMAGED, (
        "garbage bytes are damaged data"
    )


def test_check_names_changed_packages(tmp_path: Path) -> None:
    make_data(tmp_path / ".testmondata", packages="alpha 0.9, beta 2.0")

    assert check(tmp_path, PACKAGES) is SelectionDataOutcome.PACKAGES_CHANGED, (
        "the seed saw other packages"
    )


def test_check_of_a_missing_file_is_no_data(tmp_path: Path) -> None:
    assert check(tmp_path, PACKAGES) is SelectionDataOutcome.NO_DATA, "nothing to check"
    assert names(tmp_path) == set(), "checking creates no file"


@pytest.mark.parametrize(
    ("outcome", "message"),
    [
        (
            SelectionDataOutcome.DAMAGED,
            "selection data is damaged: delete .testmondata and run make test-seed",
        ),
        (
            SelectionDataOutcome.PACKAGES_CHANGED,
            "packages changed since the seed: run make test-seed",
        ),
    ],
)
def test_the_messages_are_the_decided_ones(outcome: SelectionDataOutcome, message: str) -> None:
    assert MESSAGES[outcome] == message, "the PD-7 wording, verbatim"
    assert message in {DAMAGED_MESSAGE, PACKAGES_MESSAGE}, "exported under a name"


def test_outcomes_have_distinct_exit_codes() -> None:
    codes = [CHECK_EXIT[o] for o in SelectionDataOutcome]

    assert len(set(codes)) == len(codes), "one exit code per outcome"
    assert CHECK_EXIT[SelectionDataOutcome.SOUND] == 0, "sound exits 0"


def test_check_command_prints_the_message_and_exits_with_the_outcome(tmp_path: Path) -> None:
    (tmp_path / ".testmondata").write_bytes(os.urandom(4096))

    done = subprocess.run(
        [PYTHON, "-m", "rdf_persistence.testkit.selection_data", "check"],
        cwd=tmp_path,
        env=cli_env(),
        capture_output=True,
        text=True,
        check=False,
    )

    assert done.returncode == CHECK_EXIT[SelectionDataOutcome.DAMAGED], (
        "the exit code names the outcome"
    )
    assert DAMAGED_MESSAGE in done.stdout, "the message is printed"


FAKE_SEED_RUN = """
import sqlite3, sys
from pathlib import Path
root = Path(sys.argv[1])
assert not (root / ".testmondata.seed").exists(), "the old seed was not cleaned"
assert not (root / ".testmondata.seed-wal").exists(), "the old seed's side file was not cleaned"
con = sqlite3.connect(root / ".testmondata.seed")
con.execute("CREATE TABLE marker (value TEXT)")
con.execute("INSERT INTO marker VALUES ('new')")
con.commit()
con.close()
sys.exit(int(sys.argv[2]))
"""


def seed_argv(root: Path, exit_code: int) -> list[str]:
    return ["seed", "--", PYTHON, "-c", FAKE_SEED_RUN, str(root), str(exit_code)]


def test_seed_cleans_runs_then_swaps(tmp_path: Path) -> None:
    make_data(tmp_path / ".testmondata", marker="old")
    make_data(tmp_path / ".testmondata.seed", marker="stale")
    (tmp_path / ".testmondata.seed-wal").write_bytes(b"stale")

    code = testmon_data.main(seed_argv(tmp_path, 0), tmp_path)

    assert code == 0, "the child's exit code is passed through the swap"
    assert read_marker(tmp_path / ".testmondata") == "new", "the new seed is the data"
    assert names(tmp_path) == {".testmondata", ".testmondata.lock"}, "no seed file remains"


def test_seed_swaps_nothing_when_pytest_is_interrupted(tmp_path: Path) -> None:
    make_data(tmp_path / ".testmondata", marker="old")

    code = testmon_data.main(seed_argv(tmp_path, 2), tmp_path)

    assert code == 2, "pytest's code is passed through"
    assert read_marker(tmp_path / ".testmondata") == "old", "the earlier data is untouched"
    assert not [n for n in names(tmp_path) if n.startswith(".testmondata.seed")], "no seed file"


def test_seed_stops_before_running_when_the_clean_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def refuse(root: Path) -> None:
        raise PermissionError("denied")

    monkeypatch.setattr(testmon_data, "_delete_seed_files", refuse)  # X3
    marker = tmp_path / "ran"
    command = [PYTHON, "-c", f"open({str(marker)!r}, 'w')"]

    code = testmon_data.main(["seed", "--", *command], tmp_path)

    assert code == 1, "a failed clean is exit 1"
    assert "denied" in capsys.readouterr().err, "the error is printed"
    assert not marker.exists(), "the command was not run"


REPORT_INHERITED_FD = """
import os, sys
try:
    os.fstat(int(sys.argv[1]))
    outcome = "inherited"
except OSError:
    outcome = "closed"
open(sys.argv[2], "w").write(outcome)
"""

KILL_SELF = """
import os, signal
open(os.path.join(os.environ["SEED_ROOT"], ".testmondata.seed"), "w").write("partial")
os.kill(os.getpid(), signal.SIGTERM)
"""


def test_seed_passes_inheritable_fds_to_the_child_so_it_keeps_the_queue_lock(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    report = tmp_path / "report"
    fd = os.open(tmp_path / "queue.lock", os.O_RDWR | os.O_CREAT)
    os.set_inheritable(fd, True)
    try:
        testmon_data.seed(root, [PYTHON, "-c", REPORT_INHERITED_FD, str(fd), str(report)])
    finally:
        os.close(fd)

    assert report.read_text() == "inherited", "the child holds the queue's lock descriptor"


def test_seed_treats_a_child_killed_by_a_signal_as_128_plus_n(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    make_data(tmp_path / ".testmondata", marker="old")
    monkeypatch.setenv("SEED_ROOT", str(tmp_path))

    code = testmon_data.seed(tmp_path, [PYTHON, "-c", KILL_SELF])

    assert code == 143, "SIGTERM is 128 + 15"
    assert read_marker(tmp_path / ".testmondata") == "old", "the earlier data is kept"
    assert not [n for n in names(tmp_path) if n.startswith(".testmondata.seed")], "no seed file"


def test_seed_treats_a_keyboard_interrupt_as_130(tmp_path: Path) -> None:
    make_data(tmp_path / ".testmondata", marker="old")

    def interrupted(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        (tmp_path / ".testmondata.seed").write_text("partial")
        raise KeyboardInterrupt

    code = testmon_data.seed(tmp_path, ["pytest"], run=interrupted)

    assert code == 130, "an interrupt is 128 + SIGINT"
    assert read_marker(tmp_path / ".testmondata") == "old", "the earlier data is kept"
    assert not [n for n in names(tmp_path) if n.startswith(".testmondata.seed")], "no seed file"


def test_seed_with_a_command_that_cannot_start_exits_127_without_swapping(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    make_data(tmp_path / ".testmondata", marker="old")
    make_data(tmp_path / ".testmondata.seed", marker="stale")

    code = testmon_data.seed(tmp_path, ["no-such-executable-for-seed", "--flag"])

    assert code == 127, "a command that cannot start is 127"
    assert "cannot run no-such-executable-for-seed:" in capsys.readouterr().err, "named on stderr"
    assert read_marker(tmp_path / ".testmondata") == "old", "nothing was swapped"


@pytest.mark.parametrize("argv", [["seed"], ["seed", "--"], ["seed", "pytest"]])
def test_seed_without_a_command_is_a_usage_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], argv: list[str]
) -> None:
    code = testmon_data.main(argv, tmp_path)

    assert code == testmon_data.USAGE_EXIT, f"usage error for {argv!r}"
    assert "seed -- <command" in capsys.readouterr().err, "the usage line names seed"


@pytest.mark.parametrize("code", ["²", "٣", "x", "-1", ""])
def test_a_swap_code_that_is_not_ascii_digits_is_a_usage_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], code: str
) -> None:
    got = testmon_data.main(["swap", code], tmp_path)

    assert got == testmon_data.USAGE_EXIT, f"usage error for {code!r}"
    assert "usage:" in capsys.readouterr().err, "the usage line is printed"


def git(root: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.org", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    return done.stdout.strip()


def make_repository(root: Path) -> str:
    """A git repository with one commit; returns that commit's sha."""
    git(root, "init", "-q")
    git(root, "commit", "-q", "--allow-empty", "-m", "first")
    return git(root, "rev-parse", "HEAD")


def fake_run(
    root: Path, exit_code: int, *, commit_during: bool = False
) -> Callable[..., subprocess.CompletedProcess[str]]:
    """A ``run`` seam that writes the seed as pytest would, then exits as told."""

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        make_data(root / ".testmondata.seed", marker="new")
        if commit_during:
            git(root, "commit", "-q", "--allow-empty", "-m", "during the run")
        return subprocess.CompletedProcess(command, exit_code)

    return run


# (is a git repository, exit code, stale commit file, commit made during the run,
#  a tracked file modified at seed time, data after,
#  commit file after: "head" is the sha read before the run)
SEED_COMMIT_CASES = [
    pytest.param(True, 0, None, False, False, "new", "head", id="finished-run-records-the-commit"),
    pytest.param(True, 1, None, False, False, "new", "head", id="failing-tests-still-record-it"),
    pytest.param(
        True, 0, None, True, False, "new", "head", id="a-commit-made-during-the-run-is-later"
    ),
    pytest.param(True, 2, "old\n", False, False, "old", "old\n", id="exit-2-keeps-data-and-file"),
    pytest.param(
        True, 130, "old\n", False, False, "old", "old\n", id="exit-130-keeps-data-and-file"
    ),
    pytest.param(False, 0, None, False, False, "new", None, id="not-a-repository-writes-no-file"),
    pytest.param(
        False, 0, "old\n", False, False, "new", None, id="unknown-sha-removes-a-stale-file"
    ),
    pytest.param(True, 0, None, False, True, "new", None, id="a-dirty-tracked-tree-records-none"),
    pytest.param(
        True, 0, "old\n", False, True, "new", None, id="a-dirty-tracked-tree-removes-a-stale-file"
    ),
]


@pytest.mark.parametrize(
    ("is_repo", "exit_code", "stale", "commit_during", "dirty", "data_after", "commit_after"),
    SEED_COMMIT_CASES,
)
def test_seed_records_the_commit_it_ran_on(
    tmp_path: Path,
    is_repo: bool,
    exit_code: int,
    stale: str | None,
    commit_during: bool,
    dirty: bool,
    data_after: str,
    commit_after: str | None,
) -> None:
    head = make_repository(tmp_path) if is_repo else None
    if dirty:
        (tmp_path / "tracked.txt").write_text("one\n")
        git(tmp_path, "add", "tracked.txt")
        git(tmp_path, "commit", "-q", "-m", "track a file")
        head = git(tmp_path, "rev-parse", "HEAD")
        (tmp_path / "tracked.txt").write_text("two\n")
    make_data(tmp_path / ".testmondata", marker="old")
    commit_file = tmp_path / testmon_data.SEED_COMMIT
    if stale is not None:
        commit_file.write_text(stale)

    code = testmon_data.seed(
        tmp_path, ["pytest"], run=fake_run(tmp_path, exit_code, commit_during=commit_during)
    )

    assert code == exit_code, "the run's exit code is passed through"
    assert read_marker(tmp_path / ".testmondata") == data_after, "the data is swapped or kept"
    expected = f"{head}\n" if commit_after == "head" else commit_after
    actual = commit_file.read_text() if commit_file.exists() else None
    assert actual == expected, "the commit file describes the data beside it"
    assert not [n for n in names(tmp_path) if n.endswith(".tmp")], "no temporary file is left"


def test_swap_without_a_commit_deletes_the_commit_file(tmp_path: Path) -> None:
    make_data(tmp_path / ".testmondata.seed", marker="new")
    (tmp_path / testmon_data.SEED_COMMIT).write_text("old\n")

    swap(tmp_path, 0)

    assert not (tmp_path / testmon_data.SEED_COMMIT).exists(), "the CLI form records nothing"


def test_swap_with_a_commit_writes_it_after_the_rename(tmp_path: Path) -> None:
    make_data(tmp_path / ".testmondata.seed", marker="new")

    swap(tmp_path, 0, commit="abc")

    assert (tmp_path / testmon_data.SEED_COMMIT).read_text() == "abc\n", "sha and a newline"
    assert "SEED_COMMIT" in testmon_data.__all__, "the constant is public"
