"""Queue heavy test runs on the machine and size their workers.

Run as ``uv run python -m rdf_persistence.testkit.run_queue -- <command...>``: takes the machine-wide lock
(``$XDG_CACHE_HOME/meaningfy/pytest.lock``, or ``TEST_QUEUE=<path>``; ``TEST_QUEUE=off`` for none),
replaces the argument ``@workers`` by the worker count, and execs the command with the lock
descriptor inherited, so the lock lives exactly as long as the command's process.
``python -m rdf_persistence.testkit.run_queue --workers`` prints the count. See
openspec/changes/agent-test-control/design.md (PD-1, PD-3).
"""

import fcntl
import os
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

WORKERS_TOKEN = "@workers"
QUEUE_OFF = "off"  # TEST_QUEUE=off: no lock
DEFAULT_WORKER_MB = 1536
CORE_RESERVE = 3  # cores left to the machine when there are more than CORE_THRESHOLD
CORE_THRESHOLD = 6
USAGE_EXIT = 2
LABEL_WORDS = 3
MEMINFO = Path("/proc/meminfo")


def workers(cpus: int | None, available_mb: int | None, per_worker_mb: int) -> int:
    """The core rule, capped by the memory available, at least 1."""
    if cpus is None:
        return 1
    count = cpus - CORE_RESERVE if cpus > CORE_THRESHOLD else cpus
    if available_mb is not None:
        count = min(count, available_mb // per_worker_mb)
    return max(1, count)


def mem_available_mb(meminfo: str | None) -> int | None:
    """MemAvailable of a /proc/meminfo text in MB; None when absent."""
    for line in (meminfo or "").splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) // 1024
    return None


def read_meminfo() -> str | None:
    try:
        return MEMINFO.read_text()
    except OSError:
        return None


def lock_path(environ: Mapping[str, str]) -> Path:
    cache = environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(cache) / "meaningfy" / "pytest.lock"


def _holder_line(environ: Mapping[str, str], command: Sequence[str]) -> str:
    label = environ.get("TEST_QUEUE_LABEL") or " ".join(command[:LABEL_WORDS])
    return f"{Path.cwd().name} {label} {os.getpid()} {time.strftime('%H:%M:%S')}"


def _acquire(path: Path) -> tuple[int, int | None]:
    """Open the lock and take it; returns the descriptor and the seconds waited (None: no wait)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fd, None
    except BlockingIOError:
        pass
    holder = os.pread(fd, 512, 0).decode(errors="replace").strip() or "holder unknown"
    print(f"waiting for the test queue: {holder}", file=sys.stderr, flush=True)
    started = time.monotonic()
    fcntl.flock(fd, fcntl.LOCK_EX)
    return fd, round(time.monotonic() - started)


def _announce(holder_fd: int, line: str) -> None:
    data = line.encode()
    os.pwrite(holder_fd, data, 0)
    os.ftruncate(holder_fd, len(data))


def _take_the_queue(environ: Mapping[str, str], command: Sequence[str]) -> bool:
    """Take the lock (unless ``TEST_QUEUE=off``) and keep it for the exec; False: it cannot be opened."""
    setting = environ.get("TEST_QUEUE")
    if setting == QUEUE_OFF:
        return True
    path = Path(setting) if setting else lock_path(environ)
    try:
        fd, waited = _acquire(path)
    except OSError as error:
        print(f"cannot open the test queue lock {path}: {error}", file=sys.stderr)
        return False
    _announce(fd, _holder_line(environ, command))
    os.set_inheritable(fd, True)
    if waited is not None:
        print(f"test queue: waited {waited}s", file=sys.stderr, flush=True)
    return True


def main(
    argv: Sequence[str],
    environ: Mapping[str, str],
    *,
    cpu_count: Callable[[], int | None] = os.cpu_count,
    read_meminfo: Callable[[], str | None] = read_meminfo,
    execute: Callable[[str, list[str]], object] = os.execvp,
) -> int:
    per_worker_mb = int(environ.get("PYTEST_WORKER_MB") or DEFAULT_WORKER_MB)
    cpus, available = cpu_count(), None
    if list(argv) == ["--workers"]:
        print(workers(cpus, mem_available_mb(read_meminfo()), per_worker_mb))
        return 0
    command = list(argv[1:] if argv[:1] == ["--"] else argv)
    if not command:
        print(
            "usage: python -m rdf_persistence.testkit.run_queue [--workers | -- <command...>]",
            file=sys.stderr,
        )
        return USAGE_EXIT
    if not _take_the_queue(environ, command):
        return USAGE_EXIT
    if WORKERS_TOKEN in command:
        available = mem_available_mb(read_meminfo())  # after the lock: memory freed counts
        count = workers(cpus, available, per_worker_mb)
        memory = f"{available} MB available" if available is not None else "memory unknown"
        print(f"test queue: {count} workers ({cpus} cores, {memory})", file=sys.stderr, flush=True)
        command = [str(count) if word == WORKERS_TOKEN else word for word in command]
    execute(command[0], command)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:], os.environ))  # noqa: TID251 - the command line is this module's config boundary
