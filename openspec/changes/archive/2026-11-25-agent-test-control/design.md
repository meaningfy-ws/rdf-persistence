> Derives from: the EPIC `agent-test-control` (proposal.md, DEC-1 to DEC-9)

## Context

The lanes are those of `2026-11-09-test-lanes`: every parallel target runs
`$(PARALLEL) = -n auto --dist loadgroup` (`Makefile:54`), and `make test-changed` runs
`uv run python -m tests.changed`, which maps changed files to test folders and exits 3 to make
`make test-fast` run instead (`Makefile:267-274`, `tests/changed.py`). The evidence is
`inputs/seed.md`: contention between sessions, a fallback in eight PRs of nine, builders' 10-minute
waits.

pytest-testmon 2.4.0, read in its source (2026-11-25): it opens its database in WAL mode
(`db.py:29`); it fingerprints the installed packages and the Python version (`db.py:644-680`);
it turns selection off when `-m` or `-k` is given unless `--testmon-forceselect` is set
(`configure.py:65-77`); `--testmon-nocollect` selects without writing; it records nothing under
coverage.py; it cannot see code run in a subprocess.

Constraints: no hook in this repository (`AGENTS.md`); no library or generator code changes outside the testkit (DEC-10); the
full gates and CI keep what they run (proposal.md, No-gos); every Python run goes through `uv`.

## Goals / Non-Goals

**Goals:** one heavy run at a time per machine (DEC-2); a worker count of cores minus 3, capped
by available memory (DEC-3, DEC-9); workers that release memory between modules (DEC-9);
`make test-changed` selecting by execution for Python files (DEC-4); a seed the lead starts in the
background (DEC-5); the guards of DEC-6 and the docs of DEC-7; the skillery issue (DEC-1).

**Non-Goals:** the No-gos of the proposal; teaching testmon about non-Python files; measuring
DEC-8 inside this change (task 4.3, after the merge).

## Decisions

- **PD-1 The queue is a stdlib module, `tests/queue.py`.** `python -m tests.queue -- <cmd…>` opens
  `$XDG_CACHE_HOME/meaningfy/pytest.lock` (`~/.cache/…` when unset; folder created) with
  `os.open(O_RDWR | O_CREAT)`, never truncating and never unlinking it. It tries
  `fcntl.flock(LOCK_EX | LOCK_NB)`; on failure it reads the holder line, prints
  `waiting for the test queue: <holder>` once to stderr (`holder unknown` when the line is empty),
  and blocks on `LOCK_EX`. Holding the lock it writes the holder line
  `<repository folder> <label> <pid> <HH:MM:SS>` with one `pwrite` and `ftruncate` (the label is
  `TEST_QUEUE_LABEL`, which the recipes set to `$@`, else the command's first three words), prints
  `test queue: waited <N>s` when it waited, marks the descriptor inheritable and `os.execvp`s the
  command: the lock lives exactly as long as the command's process, and a signal sent to the
  queued run reaches pytest itself. The kernel releases the lock however the process ends.
  `TEST_QUEUE=<path>` moves the lock (tests use a temporary file); `TEST_QUEUE=off` execs without
  it. `python -m tests.queue --workers` prints the worker count of PD-3. Why a module and not
  `flock(1)`: it exists on macOS, is unit-testable, and is the file skillery copies (DEC-1).
- **PD-2 What queues.** The Makefile defines `PYTEST = uv run python -m tests.queue -- pytest`, and
  `PYTEST = uv run pytest` when `CI` is set (CI runners have no contention; CI's jobs are unchanged).
  Every target that runs `$(PARALLEL)` (`test-unit`, `test-unit-ci`, `test-feature`,
  `test-generator`, `test-fast`, `test-durations`, `profile-tests`), `test-containers` and
  `test-seed` run `TEST_QUEUE_LABEL=$@ $(PYTEST) …` instead of `uv run pytest …`: one `uv run`, so
  no second sync. The queue has no maximum wait: a stuck holder is named by its line and killed by
  the lead (error matrix).
  `make check-all` queues per lane; another session's lane may run between two of its lanes,
  accepted (DEC-8 excludes queue wait). Named-file runs and `make test-changed`'s own runs do not
  queue (DEC-2); its fallback to `make test-fast` does.
- **PD-3 The worker count** (DEC-3, DEC-9). `workers(cpus, available_mb, per_worker_mb)` in
  `tests/queue.py`: the core rule (`cpus - 3` when `cpus > 6`, else `cpus`), capped by
  `available_mb // per_worker_mb`, at least 1. `cpus` from `os.cpu_count()`; `available_mb` from
  `MemAvailable` in `/proc/meminfo` (`None` where there is no `/proc`, e.g. macOS: no memory
  cap); `per_worker_mb` from `PYTEST_WORKER_MB`, default 1536 (a worker's measured working size
  with PD-9's release, inputs/memory.md, plus headroom). The count is taken **after** the lock is
  acquired, so memory the previous lane freed counts: the recipes pass `-n @workers`, and
  `tests.queue` replaces the argument `@workers` by the count, always, with the lock or without it
  (`TEST_QUEUE=off`), and prints `test queue: <N> workers (<cpus> cores, <available> MB available)`,
  or `test queue: <N> workers (<cpus> cores, memory unknown)` when `available_mb` is `None`. `PYTEST_N`, when set, is
  passed literally instead of `@workers`. With `CI` set (no queue) the Makefile computes it at
  parse time: `PYTEST_N := $(shell uv run --no-sync python -m tests.queue --workers)`.
  `PARALLEL = -n $(or $(PYTEST_N),@workers) --dist loadgroup`. Examples: 20 cores and 40 GB
  available → 17; 20 cores and 12 GB → 8; 8 cores, no `/proc` → 5; 4-core runner → 4.
  `make test-changed` uses `PYTEST_CHANGED_N` (default 4) and ignores `PYTEST_N`, which from now
  on sizes the queued lanes only; the target's help text and the docs say so.
- **PD-4 `tests/changed.py` runs the tests itself.** A pure `plan(changed, has_data, existing) ->
  Plan` returns the pytest invocations (argument lists), the hints, and the fallback reasons;
  `main()` checks the selection data (PD-7), runs each invocation in order with `subprocess.run`
  inside the `uv run` that started it, and stops at the first failure. Exit codes: 0 passed or
  nothing to run (pytest's 5, "no tests collected", becomes 0 with `testmon selected no test`);
  pytest's 1, 2, 4 passed through; pytest's 3 becomes 2; **75** means "run `make test-fast`", for
  a fallback reason and for a `GitError` (its message printed first, as today with 3).
  The Makefile recipe runs the module and, on 75 only, `make test-fast`. The one-argument-per-line
  output contract goes.
- **PD-5 The plan.** A file is *testmon-visible* when it is a `*.py` under `rdf_persistence/`,
  `rdf_persistence_generation/` or `tests/`, except a `test_*.py` under `tests/integration/`,
  `tests/e2e/` or `tests/perf/` (those keep their hints) and except anything under
  `tests/fixtures/`, whose Python files are partly golden text compared by tests and never
  executed (`tests/fixtures/library/domain/generated/`); helpers under `tests/e2e/` and
  `tests/integration/` (`tests/e2e/world.py`, `tests/e2e/library_app.py`) are testmon-visible,
  being imported by unit tests.
  - The shared arguments `L` = `<IGNORES> -m "(unit or feature) and not quarantine"`, where
    `IGNORES` is a constant in `tests/changed.py` equal to the Makefile's `UNIT_LANE` ignores
    (`--ignore=tests/integration --ignore=tests/e2e --ignore=tests/perf --ignore=tests/generator/e2e`);
    a `test_lanes.py` test pins the two equal, so the source of truth stays the Makefile.
  - With selection data, one testmon invocation T when any testmon-visible file changed:
    `tests/unit tests/feature [tests/generator] L --testmon --testmon-nocollect --testmon-forceselect -n <PYTEST_CHANGED_N> --dist loadgroup`,
    `tests/generator` left out when the folder invocation below already selects it.
    `--testmon-nocollect`: builders only read, so the selection is "what changed since the seed",
    the same on every run, and failures recorded by the seed stay selected.
    `--testmon-forceselect`: the `-m` filter and testmon's selection combine instead of `-m`
    turning selection off. Then one folder invocation F over the files that are not
    testmon-visible, plus every file under `rdf_persistence_generation/` and `tests/generator/`,
    whose tests run the generator in subprocesses testmon cannot see (their rule:
    `tests/generator/`): `<selected paths> L -n <PYTEST_CHANGED_N, or 0 when only files are selected> --dist loadgroup`.
  - Before planning with data, `testmon_data check` (PD-7) also compares the package fingerprint
    the seed recorded with the current environment (testmon's own `get_system_packages`); a
    mismatch, after a `uv sync` or a rebase that brought a new `uv.lock`, counts as no data, with
    the hint `packages changed since the seed: the lead re-runs make test-seed`, so T never
    re-selects the whole suite unqueued.
  - Without selection data: today's rules for every file, plus the hint
    `no test selection data in this worktree: the lead runs make test-seed`.
  - Fallback (75) in both modes for `pytest.ini`, `Makefile`, `.coveragerc`, `pyproject.toml`,
    `uv.lock` (testmon would re-select almost everything, unqueued), a non-Python file under
    `rdf_persistence/model/`, any file under `tests/fixtures/`, and a file no rule maps; without data also
    for what falls back today.
- **PD-6 The worktree lock.** `.testmondata.lock` in the repository root: a builder's testmon
  invocation holds it shared (`LOCK_SH`), the seed's swap exclusive (`LOCK_EX`) for the swap only.
  Lock order for the seed: the machine lock (the queue) is taken first, for the whole run; the
  worktree lock last, for the swap. Builders never wait for the seed's run, only for its swap.
- **PD-7 The seed and its data.** `make test-seed` first deletes any `.testmondata.seed*` (a
  seed killed before its swap leaves one, which would make the next seed incremental), then runs, queued:
  `TEST_QUEUE_LABEL=$@ TESTMON_DATAFILE=.testmondata.seed $(PYTEST) $(TEST_PATH) $(UNIT_LANE) -m "(unit or feature) $(NOT_QUARANTINE)" --testmon --testmon-forceselect $(PARALLEL) -p no:randomly`
  (slow tests included, no coverage), then `uv run --no-sync python -m tests.testmon_data swap`.
  `tests/testmon_data.py`: `swap` acts only on pytest exit 0 or 1 (passed as an argument): it opens
  `.testmondata.seed` with `sqlite3`, runs `PRAGMA wal_checkpoint(TRUNCATE)`, sets
  `journal_mode=DELETE`, closes it; under the exclusive worktree lock it deletes
  `.testmondata-wal` and `.testmondata-shm` and renames the seed over `.testmondata`. On any other
  exit it deletes the seed files and fails. The target exits 0 after a swap of a passing run, 1
  after a swap of a run with failing tests (the data is kept; the lead reads the failures), and
  pytest's code (≥ 2) with no swap. `check` runs `PRAGMA quick_check` on `.testmondata` and the
  package comparison of PD-5;
  `main()` of PD-4 calls it first. Two failing outcomes, one message each, both then planned as
  without data: damaged prints
  `selection data is damaged: delete .testmondata and ask the lead for make test-seed`; a package
  mismatch prints `packages changed since the seed: the lead re-runs make test-seed`. The lead starts the seed with `run_in_background` at stage start, after
  `make reindex`; builders start at once and get the folder rules until the swap. A stage that
  changes `pyproject.toml` or `uv.lock` re-seeds after `uv sync`.
- **PD-9 Release memory at each module boundary** (DEC-9, DEC-10). `rdf_persistence/testkit/memory.py`
  holds `clear_caches()` and `release_memory()` (exported in `testkit.__all__`; FastAPI imported
  lazily, absent counts as 0 caches, so the testkit runs without the api extras); the hook wrapper
  lives in `rdf_persistence/testkit/memory_plugin.py`, which a project enables with
  `pytest_plugins = ["rdf_persistence.testkit.memory_plugin"]` (this repository: `tests/conftest.py`).
  Below, `release()` means `release_memory()`. Its work:
  call `cache_clear()` on every attribute of `linkml_runtime.utils.schemaview.SchemaView` that has
  one, and on every module-level attribute of `fastapi.dependencies.models` that has one; then
  `gc.collect()`; then, on glibc only, `ctypes.CDLL("libc.so.6").malloc_trim(0)` (skipped quietly
  elsewhere). It returns the number of caches cleared per library. It has two parts:
  `clear_caches()` (the `cache_clear()` calls) and `release()` (`clear_caches()`, then the
  collection and the trim). `tests/conftest.py` gains `pytest_runtest_teardown(item, nextitem)` as
  a hook wrapper (`@pytest.hookimpl(wrapper=True)`) that does its work **after** `yield`, so after
  pytest's own teardown has finalised the fixtures (module-scoped ones at a module boundary) and
  their apps and views are unreferenced; it calls `clear_caches()` after **every** test, because one module can build hundreds of
  services (`tests/unit/api/test_allowed_actions_adversarial.py`: +35 MB per test,
  inputs/memory.md), and `release()` when `nextitem` is `None` or belongs to another module
  (`nextitem.module is not item.module`); `TEST_RELEASE=off` disables both. Clearing a cache is always safe for correctness: a later call recomputes; a view or app a
  module-scoped fixture still holds stays alive and only loses its cached answers. In-process, it
  does not change xdist scheduling or `xdist_group`. Cost: one `gc.collect()` and cache rebuilds
  per module (tens of ms; about 280 modules).
- **PD-8 Ignored files and pins.** `.testmondata*` in `.gitignore`; `pytest-testmon==2.4.0` in the
  development group like the other pytest plugins.

## Algorithm / approach

Worked examples, one parametrized case each of `plan()` in `tests/unit/tooling/test_changed.py`
(T = the testmon invocation of PD-5):

| Changed files | Data | Invocations | Fallback |
|---|---|---|---|
| `rdf_persistence/core/domain/sparql.py` | yes | T | no |
| same | no | none | `rdf_persistence/core/domain/sparql.py: core is imported by every theme; run make test-fast`, plus the seed hint |
| `tests/library_app.py`, `tests/e2e/world.py` (as on review-floors-s1; the case injects `existing`) | yes | T | no |
| same | no | none | `tests/library_app.py: shared test infrastructure or schema`, `tests/e2e/world.py: helper imported by unit tests` |
| `rdf_persistence/persistence/services/session.py`, `docs/x.adoc` | yes | T; F = `tests/unit/tooling/test_check_docs.py L -n 0` | no |
| `rdf_persistence_generation/lock_step.py` | yes | T without `tests/generator`; F = `tests/generator/ L -n 4` | no |
| `tests/fixtures/library/domain/generated/core.py` | yes | none | `tests/fixtures/library/domain/generated/core.py: shared test infrastructure or schema` |
| `rdf_persistence/model/core.yaml` | yes | none | `rdf_persistence/model/core.yaml: shared test infrastructure or schema` |
| `uv.lock` | yes | none | `uv.lock: shared test infrastructure or schema` |
| `tests/integration/store/test_fuseki_store.py` | yes | none; hint `make test-containers` | no |
| nothing | either | none; `nothing to run against develop` | no |

Run twice with no edit in between, `plan()` returns the same invocations and testmon the same
selection (nocollect). From the agent's side, a lead's `make check-all` started while another
session's `make test-fast` holds the lock prints
`waiting for the test queue: …/<other repository> test-fast 41234 14:02:11`, then
`test queue: waited 312s` when it starts. Retrying any queued command is safe: each is a test run
writing only its own reports.

### Anti-patterns
| Don't | Do instead | Why |
|---|---|---|
| Wait on a gate with `timeout N tail --pid=…`, `tail -f log \| grep -m1`, or a loop | `run_in_background`, then the completion notice | the 2.5 h of 10-minute waits (inputs/seed.md) |
| Run `make test-fast` "to be safe" as a builder | `make test-changed`; the lead's gate runs the rest | the full lane under contention is the cost this change removes |
| Copy `.testmondata` from another worktree | `make test-seed` | testmon fingerprints the files of its own tree |
| Run `make generate` or `uv sync` as a builder in a shared worktree | ask the lead | concurrent runs broke the venv and the lock-step tests |
| Run `--testmon` without `--testmon-nocollect` as a builder | `make test-changed` | a writing run makes the next one select nothing |
| Add `-n` to a hand-typed run over a whole lane | name the files, or let the queued lane run | an unqueued lane is the old contention |

## Error matrix

| Failure mode | How it is detected | Expected handling |
|---|---|---|
| A queued run is killed (`kill -9`, closed terminal, background task stopped) | the kernel drops the lock with pytest's process (exec, PD-1) | the next waiter runs; no orphan workers hold the cores unlocked |
| The cache folder is not writable | `OSError` opening the lock | `tests.queue` prints the path and the error, exits 2; `TEST_QUEUE` gets past it |
| A queued target calls another queued target | n/a: only `pytest` commands are wrapped, never a `make` call | no self-deadlock by construction; task 1.2 asserts no recipe wraps `$(MAKE)` |
| A builder runs `make test-changed` while the seed runs | no `.testmondata` yet | folder rules plus the seed hint |
| Builders run while the seed swaps | PD-6's shared/exclusive lock | they wait for the swap only (seconds) |
| The seed is interrupted | pytest exit ≥ 2 | seed files deleted, target fails, old data stays |
| A stale WAL file beside `.testmondata` | swap deletes `-wal`/`-shm` before the rename | the new data is never replayed over |
| `.testmondata` is damaged | `PRAGMA quick_check` before planning | message, then the plan without data |
| pytest internal error (exit 3) | `main()` | becomes 2: the gate fails, no silent fallback |
| testmon selects nothing | pytest exit 5 | 0 with `testmon selected no test` |
| testmon misses a test (non-Python file, subprocess) | the lead's `make check-all` | the stage gate fails; the miss is named in the stage report; a repeated miss gets a folder rule |
| Selection data older than a rebase | testmon compares fingerprints, not commits | a larger, still correct selection |
| Packages changed since the seed (`uv sync`, a rebase bringing `uv.lock`) | `check` compares the package fingerprint (PD-5) | plan without data, with the re-seed hint; T never runs the whole suite unqueued |
| A seed killed before its swap | `.testmondata.seed*` left behind | the next `make test-seed` deletes them first (PD-7) |
| A queue holder hangs or is forgotten (a stuck background run) | every waiter prints the holder line with its pid and start time | no maximum wait; the lead kills that pid (or `TEST_QUEUE=off` as a last resort, said in the stage report) |
| A `GitError` (no base branch, not a checkout) | `main()` | its message, then 75: `make test-fast` runs, as today |
| A linkml-runtime or FastAPI release renames or drops the caches `release()` clears | `release()` reports 0 caches for that library; task 1.3's test asserts ≥ 1 per library | the test fails on the upgrade PR; `release()` is updated there |
| Little memory available when a lane starts | PD-3 counts after the lock | fewer workers (at least 1), printed in the `test queue:` line |
| `/proc/meminfo` missing or unreadable | `available_mb` is `None` | the core rule alone |

## Risks / Trade-offs

- **RISK-1** (outside change: plugin versions; likely low, impact high). A pytest, xdist or testmon
  release breaks selection or the seed. Mitigate: pins; task 2.4 checks selection under xdist with
  `--dist loadgroup` and forceselect before the docs. Accept: deleting `.testmondata` returns every
  builder to the folder rules.
- **RISK-2** (who is hurt: the lead, then a reviewer; likely medium, impact medium). Selection
  misses a broken test until the stage gate, so a fix pass grows. Mitigate: the stage gate is
  unchanged; the generator keeps its folder rule (PD-5); misses are named in stage reports.
  Accept: a miss costs one fix pass, against hours of contention per stage.
- **RISK-3** (outside change: other repositories' sessions; likely high, impact low). Until
  skillery copies the queue (DEC-1), other repositories do not queue. Accept: this repository's
  heavy runs queue among themselves; the skillery issue closes the gap.
- **RISK-4** (who is hurt: the lead; likely medium, impact low). The lead waits in the queue.
  Accept: the wait says whose run and how long; DEC-8 excludes it.
- **RISK-5** (outside change: the machine; likely low, impact low). Mitigate: PD-3 reads the core
  count each run; `PYTEST_N` overrides it.

- **RISK-6** (outside change: library internals; likely medium over a year, impact low).
  `release()` depends on the cache attributes of linkml-runtime and FastAPI. Mitigate: the test of
  task 1.3 fails when either library yields no cache, and the pins make it visible on the upgrade
  PR. Accept: until fixed, memory grows as it does today.

## Delivery decisions

- **D-1** (lead, 2026-11-25): during this stage the builders' task gate is their own test files
  (`uv run pytest <files> -p no:randomly`), `make lint` and `make check-quality`, not
  `make test-changed check-quality`: today's `make test-changed` falls back to the full fast lane at
  `-n auto` for a change under `tests/`, which is the contention this change removes. The lead runs
  `make check-all` once before the PR and after the fix pass.
- **D-2** (lead): the builders work in their own worktrees (`.worktrees/atc-<task>`, branches
  `atc/task-<task>`) off `change/agent-test-control`; the lead merges each finished task into
  `change/agent-test-control` and commits; the plan commit and the implementation go in one PR.
- **D-3** (lead, from task 1.3's report): PD-9's caches are three, not two. Each `ServiceKit`
  builds `Annotated[VerifiedCaller, Depends(kit.gate.caller)]`, which `typing` caches by value, so
  one entry kept the last kit alive; `clear_caches()` also runs `typing`'s registered cache
  clears (`typing._cleanups`, a private CPython list, reached behind `getattr`, absent counts 0).
  `release_memory()` returns a plain index `dict[str, int]` per library (the model guard rejects a
  dataclass in the testkit outside `generated`). Follow-ups, outside this EPIC: build that
  annotation once per class, not per kit (ours, `rdf_persistence/api`); load each schema once per
  process (ours, DEC-9); the per-instance `lru_cache` of `SchemaView` (external, linkml-runtime).
- **D-4** (developer, 2026-11-25): "you can skip the L2+L3 in this epic": no review pass runs on
  this stage; the full gates, the builders' Red tests, the cold reader and the measured evidence
  (`evidence/memory.md`, `evidence/selection.md`) are the check. The developer also lifted the CPU
  and memory restraint for the lead's own runs.

## Open Questions

None. The DEC-8 targets are checked after the merge (task 4.3); a missed target is a new change.
