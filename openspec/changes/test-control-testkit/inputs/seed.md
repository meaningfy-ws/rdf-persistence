# Seed: issue #403 (secondary; never groomed)

Copied 2026-11-26 from https://github.com/meaningfy-ws/rdf-persistence/issues/403.

## agent-test-control: six findings from the MWB2 copy (hints dropped on fallback, test-changed syncs, seed cleanup race, CI parse-time shell)

Found while copying `agent-test-control` (v0.15.0) into mapping-workbench-v2 (change `mwb2-test-control`, PR meaningfy-ws/mapping-workbench-v2#129). MWB2 copies `tests/queue.py` and `tests/testmon_data.py` byte for byte and has its own `tests/changed.py` with the toolkit's shape. MWB2 fixed 1 and 2 in its own files; the rest are left to the toolkit (and to the OPEN-2 follow-up: one maintained copy in the testkit).

1. **`tests/changed.py` `main()` drops the hints on a fallback.** When `plan()` returns fallback reasons, `main()` prints only the reasons and returns 75. `NO_DATA_HINT` and `<path>: run make test-containers` are never printed. Reproduction: no `.testmondata`, change only a non-test package file, run `make test-changed`; stderr carries no `make test-seed` hint. Fix: print `tests_plan.hints` before the fallback reasons.
2. **`make test-changed` runs `uv run python -m tests.changed` without `--no-sync`.** After a `pyproject.toml` or `uv.lock` change, a builder's task gate silently syncs the shared `.venv`. That breaks the guard "only the lead runs `uv sync`" and turns the selection data into "packages changed". The seed's `swap` already uses `--no-sync`.
3. **`test-seed` deletes `.testmondata.seed*` before taking the queue lock.** A second `make test-seed` in the same worktree deletes the first run's live seed database, and a failed run's cleanup deletes the other run's files. Only the lead seeds, so this is unlikely but silent. Fix: do the cleanup inside the queued command or under the exclusive worktree lock.
4. **Under `CI`, `PYTEST_N := $(shell uv run --no-sync python -m tests.queue --workers)` runs on every make call, for every target.** It prints noise (`uv: not found`) in jobs without uv. If it fails, `PYTEST_N` is empty and plain pytest gets `-n @workers`. Fix: a deferred `PYTEST_N ?= $(shell …)`, or silence stderr.
5. **`PYTEST_CHANGED_N=abc` raises a traceback (exit 1) in `_workers()`**, which reads as a test failure. A value of 0 or less reaches `-n` unchecked.
6. **The lock is per user, not per machine.** The default lock is under each user's `~/.cache`, while `develop/testing.adoc#test-control` says the queue covers every repository on the machine. A shared `TEST_QUEUE` path created `0o644` refuses other users (exit 2). Fix the wording, or make the file group-writable.


## OPEN-2 (from the issue)

"one maintained copy in the testkit": MWB2 copies `tests/queue.py` and `tests/testmon_data.py` byte for byte and keeps its own `tests/changed.py` with the toolkit's shape (MWB2 change `mwb2-test-control`, PR meaningfy-ws/mapping-workbench-v2#129).

