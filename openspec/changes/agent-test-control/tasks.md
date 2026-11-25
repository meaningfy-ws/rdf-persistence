EPIC: agent-test-control (proposal.md). Decisions: proposal.md DEC-1 to DEC-9; design.md PD-1 to PD-9.

> Derives from: the EPIC `agent-test-control`.

Every task: its **Red** test is written first and seen failing; a docs task's proof is
`make check-docs` and the named review. No real sleeps in tests: a child process signals readiness
on a pipe. Task gate `make test-changed check-quality`; the lead runs `make check-all` once before
the PR and once after the fix pass. Commit body `Refs: agent-test-control <task> <PD>`. One stage,
branch `change/agent-test-control` off `develop`, one PR. Tasks marked **Lead** change
dependencies, the environment or the docs agents read; the lead does them (DEC-6). Ids follow
this repository's convention: `DEC-n` is in proposal.md, `PD-n` in design.md, plain, no anchors.

## 1. The queue and the worker count

- [ ] 1.1 PD-1, PD-3, unit. `tests/queue.py`, `tests/unit/tooling/test_queue.py`, each test with
  a temporary `TEST_QUEUE` path. Red:
  `workers(cpus, available_mb, per_worker_mb)` as one parametrized table (20 cores with 40960,
  12288 and 1000 MB at 1536 → 17, 8, 1; 8 cores, `None` → 5; 7 → 4; 6 → 6; 4 → 4; 1 → 1; `cpus`
  `None` → 1), and `MemAvailable` read from a sample `/proc/meminfo` text;
  a command holding `-n @workers` runs with the count in its place and the module prints
  `test queue: <N> workers (<cpus> cores, <MB> MB available)`, or `…, memory unknown)` with no
  `/proc/meminfo`; the token is replaced with `TEST_QUEUE=off` too; a command with `-n 3` runs
  unchanged;
  a free lock execs the command and its exit code is the module's (0 and 3);
  a held lock: a child holds `flock` and writes `ready` to a pipe; the module, started after
  `ready`, prints `waiting for the test queue:` with the child's holder line on stderr; the test
  reads that line first, then kills the child, then asserts the module ran the command, printed
  `test queue: waited`, and the lock file still exists (never unlinked);
  an empty holder line prints `holder unknown`; the holder line carries `TEST_QUEUE_LABEL` when
  set, else the command's first three words;
  SIGTERM to a queued run whose command is a child that writes `ready` then waits: the command's
  process is gone and the lock is free afterwards (exec, PD-1);
  `TEST_QUEUE=off` opens no file; an unwritable folder exits 2 naming the path.
- [ ] 1.2 PD-2, PD-3, unit, after 1.1. The Makefile: `PYTEST`, `PYTEST_N`, `PARALLEL`. Red in
  `tests/unit/tooling/test_lanes.py`: every recipe line holding `$(PARALLEL)`, and that of
  `test-containers`, runs `TEST_QUEUE_LABEL=$@ $(PYTEST)` and no bare `uv run pytest`; no recipe
  wraps `$(MAKE)` in `$(PYTEST)`; `make --no-print-directory --eval 'pn:;@echo $(PYTEST_N) $(PYTEST)' pn`
  run with an explicit child environment (`CI` and `PYTEST_N` removed) prints an empty count
  with `tests.queue`, and `$(PARALLEL)` holds `-n @workers`; with `CI=1` added it prints the
  `workers()` value and `uv run pytest`; with `PYTEST_N=3` added `$(PARALLEL)` holds `-n 3`; `test-changed`'s recipe holds neither `$(PYTEST)` nor `PYTEST_N`; `IGNORES` of
  `tests/changed.py` equals the `--ignore` options of the Makefile's `UNIT_LANE` (PD-5), compared
  after replacing `$(TEST_PATH)` with `tests`.

- [ ] 1.3 PD-9, DEC-10, unit (parallel with 1.1). `rdf_persistence/testkit/memory.py`,
  `rdf_persistence/testkit/memory_plugin.py`, the two names in `testkit.__all__` (the lead
  refreshes the public-surface snapshot), the opt-in line in `tests/conftest.py`, `tests/unit/tooling/test_memory.py`. Red: `release()` reports at least one
  cache cleared for linkml-runtime and one for FastAPI (RISK-6); building three `ToyService()`
  apps, dropping them and calling `release()` leaves no `ServiceKit` alive (`gc.get_objects()`
  count back to its value before the three); a hook test with fake items: `clear_caches` is
  called after every test, `release` when `nextitem` is `None` or in another module and not when
  it is in the same module, and neither with `TEST_RELEASE=off` (both functions injected, not
  patched); a module-scoped fixture holding a `ToyService()` leaves no `ServiceKit` alive once the
  hook wrapper has run for the module's last test (the wrapper's work after `yield`, PD-9).
  A second measured check: `tests/unit/api/test_allowed_actions_adversarial.py` on one process,
  maximum RSS before and after (+35 MB per test before). **Lead:** both measurements are one-off
  runs the lead makes through the queue (`TEST_QUEUE_LABEL=measure uv run python -m tests.queue --
  /usr/bin/time -v pytest …`), not the builder. They prove the `@manual` scenarios of the
  requirement *A test worker releases memory between test modules*. A miss (600 MB, or more than
  10 % added wall time) means the task is not done: the lead takes the figures to the developer,
  who decides. The first measurement, recorded with the second in `evidence/memory.md`:
  `tests/feature -m "feature and not slow" -n 0 --no-cov -p no:randomly` before and after; the target is a maximum RSS under 600 MB (1.97 GB before, inputs/memory.md)
  and no added wall time over 10 %.

## 2. Selection by execution

- [ ] 2.1 **Lead.** PD-8: `uv add --dev pytest-testmon==2.4.0`, the `.gitignore` line, `uv sync`.
  Red: none (a dependency); guard: `make test-fast` passes unchanged.
- [ ] 2.2 PD-4, PD-5, unit, after 2.1. `plan()` in `tests/changed.py`. Red in
  `tests/unit/tooling/test_changed.py`: the eleven rows of design.md's worked-examples table as one
  parametrized table over `plan(changed, has_data, existing)`, asserting the invocations T and F
  as full argument lists (PD-5), the hints, and the fallback reasons as quoted in the table; plus
  `plan()` called twice gives equal results. The existing
  tests of `select()` stay green with their assertions unchanged; the tests of `pytest_arguments`
  move to the invocation lists, case by case.
- [ ] 2.3 PD-4, PD-6, unit, after 2.2 and 1.2 (both edit the Makefile and `test_lanes.py`).
  `main()`: the exit-code table of PD-4, the shared worktree lock around T, `PYTEST_CHANGED_N`;
  the Makefile's `test-changed` recipe falls back on 75 only.
  Red: `main()` with an injected runner (a parameter, not a patch) maps 0, 1, 2, 3, 4, 5 as PD-4
  and stops at the first failing invocation; a `GitError` returns 75 with its message; the
  existing `test_main_exits_with_the_fallback_status_when_core_changed` and
  `test_main_exits_with_the_status_its_listing_calls_for` change from 3 to 75 and nothing else; a child holding the worktree lock exclusive makes
  `main()` wait until the child is killed (pattern of 1.1); in `test_lanes.py`, the recipe tests
  for 75, not 3.
- [ ] 2.4 **Lead.** PD-6, PD-7, after 2.3. `tests/testmon_data.py` and `make test-seed`. Red in
  `tests/unit/tooling/test_testmon_data.py`, on real SQLite files in `tmp_path`: `swap` with exit
  0 and 1 leaves one `.testmondata` in DELETE journal mode, readable, and no `-wal`/`-shm`
  beside it, also when a stale `.testmondata-wal` existed; `swap` with exit 2 deletes the seed
  files and keeps the old data; a child holding `.testmondata.lock` shared makes `swap` wait
  until the child is killed, and `swap` holds the lock only around deleting `-wal`/`-shm` and the
  rename (PD-7; pattern of 1.1); `check` passes a sound file, gives the damaged message of PD-7
  for a file with garbage bytes, and the packages message of PD-7 for a file whose
  `environment.system_packages` row differs from the current environment's.
  In `test_lanes.py`: `test-seed` deletes `.testmondata.seed*` first, runs
  `TEST_QUEUE_LABEL=$@ TESTMON_DATAFILE=.testmondata.seed $(PYTEST)`, then the swap with pytest's exit code, and exits as PD-7.
- [ ] 2.5 **Lead.** RISK-1, after 2.4, in a separate worktree off this branch (never the shared
  one). `make test-seed` in the background; then, on a scratch commit applying PR #388's change to
  `rdf_persistence/core/domain/sparql.py`, `make test-changed` twice. Record in
  `evidence/selection.md`: the seed's wall time; the tests selected (count, and that
  `tests/unit/core/test_sparql.py` is among them); the same count on the second run; xdist with
  `--dist loadgroup`; the run's wall time against `make test-fast`'s; and that a test made to fail
  before the seed is selected again. Remove the worktree.

## 3. Guards and the documentation for agents (after 1 and 2)

- [ ] 3.1 **Lead.** DEC-6. `AGENTS.md`, *Working here*: the gate table's task-gate row loses
  "(`make test-fast check-quality` after changing `domain` or a port)" and reads
  `make test-changed check-quality`; a `make test-seed` row, the lead's, at stage start in the
  background; one guard paragraph: builders never run by hand `make test-fast` (it runs only as
  `make test-changed`'s fallback), `make test`,
  `make check-all`, `make test-seed` or `--testmon`; they wait through the completion
  notice, never `tail --pid`, `tail -f … | grep -m1` or a `timeout` around a wait; only the lead
  runs `make generate` or `uv sync` in a shared worktree. Proof: `make check-bindings`, review.
- [ ] 3.2 **Lead.** DEC-6, DEC-7. `develop/agents.adoc`: in `#gates`, the first paragraph's "or
  `make test-fast check-quality` after changing `domain` or a port in `services`, or when unsure
  what the change reaches" goes; the table's `make test-changed` row says the selection of PD-5
  and `PYTEST_CHANGED_N=` (not `PYTEST_N=`); the `make test-fast` row says "the fallback of
  `make test-changed` only; never by hand in a task"; a `make test-seed` row (lead, stage start,
  background). The brief checklist gains the guards of 3.1 as one item; `#never-poll` names the
  two `tail` forms.
  Proof: `make check-docs`.
- [ ] 3.3 **Lead.** DEC-7, after 2.5. `develop/testing.adoc`, section `[#test-control]` *How test
  runs are controlled*: the queue (what queues, the two lines it prints, `TEST_QUEUE`, `CI`); the
  worker counts (`PYTEST_N` for the queued lanes only, `PYTEST_CHANGED_N`); the selection (testmon
  read-only for Python files, folder rules for the rest and the generator, the fallback); the seed
  (who, when, how it lands, re-seed after `uv sync`); what each role runs; the anti-patterns of
  design.md; and *Copying it to another repository* (`tests/queue.py`, `tests/testmon_data.py`,
  `plan()` of `tests/changed.py`, the Makefile and `.gitignore` lines, the pin). A `questions.adoc`
  entry, "How are test runs controlled when several agent sessions share a machine?"; a
  `make test-seed` row in the durations table (`develop/index.adoc`) with 2.5's time. In
  `develop/index.adoc`'s target table: `make test`'s "(`pytest -n auto`)" becomes "(`PYTEST_N`
  workers, queued)"; `make test-changed`'s "`BASE=` and `PYTEST_N=` override the base and the
  worker count" becomes "`BASE=` and `PYTEST_CHANGED_N=`"; a `make test-seed` row. The help text
  of `test-changed` likewise. Proof: `make check-docs`; a cold reader (a fresh subagent given only the
  page) answers which gate a builder runs, how it waits, and what `waiting for the test queue`
  means.

## 4. Close

- [ ] 4.1 DEC-1. The skillery issue, opened with this PLAN; after the merge, a comment with the
  merged file list and 2.5's times.
- [ ] 4.2 The lead's full gates, the review set of `develop/agents.adoc#challenge` for one stage
  (L2+L3 and the full review on the same PR), the fix pass, the PR, the merge.
- [ ] 4.3 DEC-8, after the merge. From Langfuse, over the first epic session with at least three
  sessions running: builders' task-gate wall time (median); `make check-all` wall time minus the
  `test queue: waited` seconds; each builder's share of wall time waiting on gates. Recorded in
  `evidence/measure.md` against the targets; a missed target goes to the developer.
- [ ] 4.4 Archive the change (`spec-stewardship`).

## Roadmap

- [ ] 1.1 · [ ] 1.3 · [ ] 1.2 · [ ] 2.1 · [ ] 2.2 · [ ] 2.3 · [ ] 2.4 · [ ] 2.5 · [ ] 3.1 · [ ] 3.2 · [ ] 3.3 · [ ] 4.1 · [ ] 4.2 · [ ] 4.3 · [ ] 4.4

1.1, 1.3 and 2.2 can run in parallel (different files; 2.1 before 2.2); 1.2 after 1.1; 2.3 after
2.2 and 1.2.

## Verification

`make check-all`; `openspec validate agent-test-control --strict`; the clarity gate
(`evidence/clarity-gate.md`); 2.5's record and 4.3's measures.
