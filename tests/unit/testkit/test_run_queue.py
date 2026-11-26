"""The machine-wide test queue (agent-test-control PD-1, PD-3): `rdf_persistence/testkit/run_queue.py`.

Pure rules and the argument handling run in-process with injected seams (cpu count, meminfo text,
the exec call). The lock itself is proved with real child processes: no sleeps, a child signals
readiness on its stdout pipe.
"""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from rdf_persistence.testkit import run_queue as queue

REPO = Path(__file__).resolve().parents[3]
PYTHON = sys.executable
HOLDER_LINE = "some-repo make-test-unit 4242 10:11:12"

HOLD_LOCK = """
import fcntl, os, sys
fd = os.open(sys.argv[1], os.O_RDWR | os.O_CREAT)
fcntl.flock(fd, fcntl.LOCK_EX)
os.pwrite(fd, sys.argv[2].encode(), 0)
os.ftruncate(fd, len(sys.argv[2].encode()))
print("ready", flush=True)
sys.stdin.read()
"""
READY_THEN_WAIT = "import sys; print('ready', flush=True); sys.stdin.read()"
MEMINFO = "MemTotal:       65536000 kB\nMemFree:         1000 kB\nMemAvailable:   41943040 kB\n"


@pytest.mark.parametrize(
    ("cpus", "available_mb", "expected"),
    [
        (20, 40960, 17),
        (20, 12288, 8),
        (20, 1000, 1),
        (8, None, 5),
        (7, None, 4),
        (6, None, 6),
        (4, None, 4),
        (1, None, 1),
        (None, None, 1),
        (None, 40960, 1),
    ],
)
def test_workers_follow_cores_capped_by_memory(cpus, available_mb, expected):
    assert queue.workers(cpus, available_mb, 1536) == expected, "the worker count is wrong"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (MEMINFO, 40960),
        ("MemTotal: 1 kB\n", None),
        ("", None),
        (None, None),
    ],
)
def test_mem_available_is_read_from_meminfo_text(text, expected):
    assert queue.mem_available_mb(text) == expected, "MemAvailable was misread"


class Exec:
    """A stand-in for os.execvp that records the call instead of replacing the process."""

    def __init__(self):
        self.calls = []

    def __call__(self, file, argv):
        self.calls.append((file, list(argv)))


def run_in_process(argv, tmp_path, *, meminfo=MEMINFO, cpus=20, **env):
    lock = env.pop("TEST_QUEUE", str(tmp_path / "pytest.lock"))
    environ = {"TEST_QUEUE": lock, **env}
    execute = Exec()
    code = queue.main(
        argv,
        environ,
        cpu_count=lambda: cpus,
        read_meminfo=lambda: meminfo,
        execute=execute,
    )
    return code, execute.calls, Path(lock)


def test_the_workers_token_is_replaced_and_announced(tmp_path, capsys):
    _, calls, _ = run_in_process(["--", "pytest", "-n", "@workers", "tests"], tmp_path)
    assert calls == [("pytest", ["pytest", "-n", "17", "tests"])], "the token was not replaced"
    assert "test queue: 17 workers (20 cores, 40960 MB available)" in capsys.readouterr().err, (
        "the count line is missing or wrong"
    )


def test_the_count_line_says_memory_unknown_without_meminfo(tmp_path, capsys):
    _, calls, _ = run_in_process(["--", "pytest", "-n", "@workers"], tmp_path, meminfo=None, cpus=8)
    assert calls[0][1] == ["pytest", "-n", "5"], "no memory cap expected without meminfo"
    assert "test queue: 5 workers (8 cores, memory unknown)" in capsys.readouterr().err, (
        "the unknown-memory line is wrong"
    )


def test_the_token_is_replaced_with_the_queue_off(tmp_path):
    code, calls, lock = run_in_process(
        ["--", "pytest", "-n", "@workers"], tmp_path, TEST_QUEUE="off"
    )
    assert code == 0, "the module should hand over to the command"
    assert calls[0][1] == ["pytest", "-n", "17"], "the token must be replaced when the queue is off"
    assert not lock.exists(), "the queue off must open no lock file"
    assert list(tmp_path.iterdir()) == [], "the queue off must create nothing"


def test_a_literal_count_runs_unchanged(tmp_path, capsys):
    _, calls, _ = run_in_process(["--", "pytest", "-n", "3"], tmp_path)
    assert calls[0][1] == ["pytest", "-n", "3"], "a literal count must be left alone"
    assert "workers" not in capsys.readouterr().err, "no count line without the token"


def test_the_worker_memory_is_configurable(tmp_path):
    _, calls, _ = run_in_process(
        ["--", "pytest", "-n", "@workers"],
        tmp_path,
        meminfo="MemAvailable: 12582912 kB\n",
        PYTEST_WORKER_MB="4096",
    )
    assert calls[0][1][-1] == "3", "12288 MB at 4096 MB each is 3 workers"


def test_workers_flag_prints_the_count(tmp_path, capsys):
    code, calls, lock = run_in_process(["--workers"], tmp_path)
    assert (code, calls) == (0, []), "--workers runs no command"
    assert capsys.readouterr().out.strip() == "17", "--workers must print the count"
    assert not lock.exists(), "--workers must not take the lock"


@pytest.mark.parametrize(
    ("env", "expected"),
    [
        ({"TEST_QUEUE_LABEL": "test-unit"}, "test-unit"),
        ({}, "pytest -n 3"),
    ],
)
def test_the_holder_line_carries_the_label(tmp_path, env, expected):
    _, _, lock = run_in_process(["--", "pytest", "-n", "3", "tests"], tmp_path, **env)
    line = lock.read_text()
    parts = line.split()
    assert parts[0] == Path.cwd().name, "the line must start with the repository folder"
    assert " ".join(parts[1:-2]) == expected, "the label is wrong"
    assert parts[-2] == str(os.getpid()), "the line must carry the pid"
    assert time.strptime(parts[-1], "%H:%M:%S"), "the time must be HH:MM:SS"


def test_a_shorter_holder_line_leaves_no_residue(tmp_path):
    lock = tmp_path / "pytest.lock"
    lock.write_text("x" * 300)
    run_in_process(["--", "pytest"], tmp_path, TEST_QUEUE=str(lock))
    assert "x" not in lock.read_text(), "the old line must be truncated away"


def test_the_default_lock_is_under_the_cache_folder(tmp_path):
    execute = Exec()
    queue.main(
        ["--", "pytest"],
        {"XDG_CACHE_HOME": str(tmp_path)},
        cpu_count=lambda: 4,
        read_meminfo=lambda: None,
        execute=execute,
    )
    assert (tmp_path / "meaningfy" / "pytest.lock").is_file(), "the default lock path is wrong"


def test_an_unwritable_lock_folder_exits_2_naming_the_path(tmp_path, capsys):
    blocker = tmp_path / "file"
    blocker.write_text("")
    lock = blocker / "sub" / "pytest.lock"
    code, calls, _ = run_in_process(["--", "pytest"], tmp_path, TEST_QUEUE=str(lock))
    assert code == 2, "an unwritable folder must exit 2"
    assert calls == [], "no command may run"
    assert str(lock) in capsys.readouterr().err, "the message must name the path"


def run_queue(args, lock, **env):
    inherited = {k: v for k, v in os.environ.items() if k != "TEST_QUEUE_LABEL"}
    full = {**inherited, "TEST_QUEUE": str(lock), **env}
    return subprocess.Popen(
        [PYTHON, "-m", "rdf_persistence.testkit.run_queue", "--", *args],
        cwd=REPO,
        env=full,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


@pytest.mark.parametrize("code", [0, 3])
def test_a_free_lock_execs_the_command_and_keeps_its_exit_code(tmp_path, code):
    process = run_queue([PYTHON, "-c", f"import sys; sys.exit({code})"], tmp_path / "l")
    process.communicate()
    assert process.returncode == code, "the module's exit code is the command's"


def test_the_command_holds_the_lock_it_inherits(tmp_path):
    lock = tmp_path / "l"
    code = (
        "import fcntl, os; fd = os.open(os.environ['TEST_QUEUE'], os.O_RDWR);"
        "\ntry:\n fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB); print('free')"
        "\nexcept BlockingIOError: print('held')"
    )
    process = run_queue([PYTHON, "-c", code], lock)
    out, _ = process.communicate()
    assert out.strip() == "held", "the lock must be held while the command runs"


@pytest.mark.parametrize(
    ("holder", "shown"),
    [(HOLDER_LINE, HOLDER_LINE), ("", "holder unknown")],
)
def test_a_held_lock_is_waited_for_and_named(tmp_path, holder, shown):
    lock = tmp_path / "l"
    child = subprocess.Popen(
        [PYTHON, "-c", HOLD_LOCK, str(lock), holder],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    assert child.stdout.readline().strip() == "ready", "the holder never took the lock"
    waiter = run_queue([PYTHON, "-c", "print('ran')"], lock)
    first = waiter.stderr.readline().strip()
    child.kill()
    child.wait()
    out, err = waiter.communicate()
    assert first == f"waiting for the test queue: {shown}", "the waiting line is wrong"
    assert out.strip() == "ran", "the command must run once the lock is free"
    assert "test queue: waited" in err, "the wait must be reported"
    assert err.count("waiting for the test queue") == 0, "the waiting line is printed once"
    assert lock.exists(), "the lock file must never be unlinked"


def test_sigterm_reaches_the_command_and_frees_the_lock(tmp_path):
    lock = tmp_path / "l"
    process = run_queue([PYTHON, "-c", READY_THEN_WAIT], lock)
    assert process.stdout.readline().strip() == "ready", "the command never started"
    process.send_signal(signal.SIGTERM)
    process.wait()
    assert process.returncode == -signal.SIGTERM, "the signal must reach the command itself"
    fd = os.open(lock, os.O_RDWR)
    try:
        import fcntl

        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        pytest.fail("the lock is still held after the command died")
    finally:
        os.close(fd)
        process.stdout.close()
        process.stderr.close()
        process.stdin.close()
