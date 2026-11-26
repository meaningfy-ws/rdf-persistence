<!-- PLAN, design half. Parent: EPIC test-control-testkit (proposal.md), DEC-1 to DEC-10. -->

# Design: test control, fixed and shipped in the testkit

## Context

The test-control scripts are three files under `tests/`. `queue.py` (124 lines, stdlib only) is
the user-wide lock and the worker count. `testmon_data.py` (161 lines, stdlib only; it imports
`testmon.common` lazily inside `current_packages()`) handles the seed swap, the data check and
the worktree lock. `changed.py` (335 lines) is the changed-files planner. It imports
`testmon_data`, and its `THEMES` is read by `tests/unit/package/test_theme_*.py` and
`tests/generator/unit/test_boundary_check.py`. Their tests are in `tests/unit/tooling/`
(`test_queue.py`, `test_testmon_data.py`, `test_changed.py`), and `test_lanes.py` pins the
Makefile recipes.

Constraints found:
- The model guard (`rdf_persistence/testkit/guards.py`, scanned layer `testkit`) forbids
  hand-written `BaseModel`, `Enum`/`IntEnum`/`StrEnum` and `@dataclass` classes in the testkit
  outside `generated/`. That covers `testmon_data.Outcome` (an `IntEnum`) as well as `changed.py`'s
  three dataclasses (DEC-8).
- `python -m rdf_persistence.testkit.<m>` imports `rdf_persistence.testkit/__init__.py` first,
  which takes 0.50 s against 0.02 s for `tests.queue` (measured 2026-11-26). Importing
  `rdf_persistence.testkit.generated` alone takes 0.44 s. See RISK-2.
- `runtime-without-extras` (`.importlinter`) already forbids the runtime layers from importing
  `rdf_persistence.testkit`, and with it every submodule.

## Decisions (PD)

- **PD-1 Module names.** `rdf_persistence/testkit/test_queue.py` would collect as a test file, so
  the modules are `rdf_persistence.testkit.run_queue` (from `tests/queue.py`),
  `rdf_persistence.testkit.selection_data` (from `tests/testmon_data.py`) and
  `rdf_persistence.testkit.changed_tests` (the generic part of `tests/changed.py`). They are
  public by module path. They are **not** re-exported from `rdf_persistence.testkit`'s root
  `__all__`, which would load them on every testkit import (DEC-6). Each module docstring states
  its CLI.
- **PD-2 Generated types** (DEC-8), in `rp_testkit.yaml`. No class name starts with `Test`,
  because pytest would try to collect it (counterexample 8):
  - an enum `SelectionDataOutcome` with the values `sound`, `damaged`, `packages_changed` and
    `no_data`;
  - the class `ChangedSelection`, with the multivalued strings `paths`, `hints` and
    `fallback_reasons`;
  - the class `ChangedTestsInvocation`, with the multivalued string `arguments`;
  - the class `ChangedTestsPlan`, with `invocations` (multivalued `ChangedTestsInvocation`,
    inlined as a list), `hints` and `fallback_reasons`;
  - the class `ChangedTestsLayout` (PD-3).

  The generator renders a multivalued slot as `Optional[list] = None`. Every multivalued slot
  therefore has `required: true`, and the code always passes `[]` when a list is empty
  (counterexample 5). `RpModel` forbids extra fields, validates assignment and is not hashable,
  so no model goes into a set or a dict key: `select()` collects path strings (RISK-3).
  Exit codes stay a module constant, `CHECK_EXIT: dict[SelectionDataOutcome, int]`, with the same
  values as today (0, 3, 4, 5), and so do the messages (`MESSAGES`). Callers that compared
  `Outcome.SOUND` compare `SelectionDataOutcome.sound`. A consumer reads the multivalued fields as
  lists, where `changed.py` used tuples. The moved tests may change their bodies, but only in the
  ways listed here (counterexample 7):
  - `Outcome.X` becomes `SelectionDataOutcome.x`;
  - `Outcome.X.value`, or `int(Outcome.X)`, becomes `CHECK_EXIT[SelectionDataOutcome.x]`;
  - a tuple literal compared with a model field becomes a list literal;
  - imports and `-m` module names follow the new paths.

  The list also covers the tests that stay in `tests/unit/tooling/test_changed.py` (TC-12), whose
  tuple comparisons become lists. The lead checks the `git diff -M` against this list.
- **PD-3 The classifier protocol** (DEC-4). `changed_tests` defines
  `class Classifier(Protocol)` with two methods:
  - `classify(path: str) -> ChangedSelection`: what one changed path selects, hints or falls back
    on (today's `_classify`);
  - `is_testmon_visible(path: str) -> bool`: today's `_is_testmon_visible`.
  `typing.Protocol` is not a model class, so the guard allows it; a test pins that.
  Everything else in `changed.py` is generic and moves: `select`, `plan`, `changed_files`, the git
  helpers, `exit_status`, `_workers`, `_run_plan` and `main`. Two values are still
  repository-specific, `plan()`'s testmon folders (`tests/unit`, `tests/feature`,
  `tests/generator`) and `IGNORES`/`MARKERS`. These are passed as a **separate argument**, a
  `ChangedTestsLayout` (PD-2), not as a member of the protocol. Its fields:
  - `testmon_folders`;
  - `extra_testmon_folder`: the generator folder, added when not already selected; optional;
  - `extra_selected_by`: the roots whose files also select that folder, today `GENERATOR_ROOTS`;
  - `ignores`;
  - `markers`;
  - `default_workers`.

  It is data beside DEC-4's two callbacks, and the alternative was hard-coding our folders in the
  testkit. This is a PLAN-level refinement, not a re-shape. The signatures are
  `plan(changed, has_data, existing, workers, classifier, layout)` and
  `main(classifier, layout, *, run=..., data_state=..., lock=...)`, which keeps today's
  injection points for the tests.
- **PD-4 Our `tests/changed.py` after stage 3**: `THEMES`, `OUTSIDE_THEMES`, `CORE_THEME`, the
  folder rules, `classify` and `is_testmon_visible` as module functions, a `LAYOUT`, and
  `if __name__ == "__main__": sys.exit(changed_tests.main(sys.modules[__name__], LAYOUT))`. A
  module that has both functions satisfies the protocol. `tests.changed.THEMES` and `IGNORES`
  keep their names, so the five importers stay as they are. `IGNORES = tuple(LAYOUT.ignores)`,
  because `test_lanes.py` compares it with a tuple (counterexample 6).
- **PD-5 #403-1.** `main()` prints `tests_plan.hints` first, then the fallback reasons, then
  returns 75.
- **PD-6 #403-2.** The `test-changed` recipe runs `uv run --no-sync python -m tests.changed`, and
  the target exports `UV_NO_SYNC = 1` (`test-changed: export UV_NO_SYNC = 1`) so its fallback
  `$(MAKE) test-fast` inherits it and does not sync either (gate run 1, counterexample 2).
- **PD-7 #403-3: the whole seed cycle runs under the queue.** `selection_data` (in stage 1, still
  `tests/testmon_data.py`) gains a subcommand, `seed -- <pytest command…>`. It does three steps
  in one process: it deletes `.testmondata.seed*`, runs the pytest command as a child
  (`subprocess.run`), then calls `swap(root, exit)` and exits with what `swap` returns. The
  recipe line becomes
  `TEST_QUEUE_LABEL=$@ $(SEED_RUN) python -m tests.testmon_data seed -- pytest … $(PARALLEL) …`.
  - Locally, `SEED_RUN = uv run python -m tests.queue --`. The queue holds its lock from the
    clean to the end of the swap, and it replaces `@workers` in the argument list before it
    execs, so the substitution still reaches pytest.
  - Under `CI`, `SEED_RUN = uv run`, with no queue.

  A second seed waits on the queue until the first has swapped. `clean` takes no worktree lock:
  only a seed writes seed files, and only one seed runs at a time per user. The swap keeps its
  exclusive worktree lock (RISK-5). Rejected after gate run 1: a `--before` option on the queue.
  It leaves the swap outside the queue, so a waiting seed could clean or overwrite the first
  seed's file before its swap (counterexample 1).
- **PD-8 #403-4.** Under `ifdef CI`, `PYTEST_N ?= $(shell uv run --no-sync python -m tests.queue --workers 2>/dev/null)`.
  It stays recursive (`?=`), so it is evaluated only when a recipe expands `PARALLEL`. `PARALLEL`
  becomes `-n $(or $(PYTEST_N),$(if $(CI),auto,@workers))`, so plain pytest never sees
  `@workers`.
- **PD-9 #403-5** (DEC-3). `_workers()` parses `PYTEST_CHANGED_N`. A value that is not a decimal
  integer ≥ 1 raises `UsageError`. `main` prints
  `PYTEST_CHANGED_N must be a positive integer, got '<v>'` and returns 2 before any git call.
- **PD-10 #403-6** (DEC-2). `testing.adoc#test-control` and the requirement *Heavy test runs
  queue on the machine* say "every repository that user runs on the machine". The lock file
  stays `0o644`.
- **PD-11 The move, stage 2** (DEC-5). `git mv` keeps the history:
  - `tests/queue.py` becomes `rdf_persistence/testkit/run_queue.py`, and
    `tests/testmon_data.py` becomes `rdf_persistence/testkit/selection_data.py`;
  - their tests go to `tests/unit/testkit/test_run_queue.py` and
    `test_selection_data.py`, where only the edits that PD-2 permits are made (DEC-7);
  - the Makefile, `test_lanes.py`, `tests/changed.py` and `testing.adoc` point at the new
    paths;
  - no file remains at the old paths.
  The worktree lock keeps the file name `.testmondata.lock`, and the user-wide lock keeps its
  path (rabbit-hole: the old and new code exclude each other).
- **PD-12 Proof by module name and wheel contents** (DEC-7). The editable install puts the
  repository root on `sys.path`, so `-I` alone does not keep `tests/` away (counterexample 4).
  The proof has two parts:
  - **(a)** A unit test runs each module by its name from `cwd=tmp_path`:
    - `python -I -m rdf_persistence.testkit.run_queue --workers` prints a positive count and
      exits 0;
    - `selection_data check` exits 5, since there is no data;
    - `changed_tests` with a bad `PYTEST_CHANGED_N` exits 2.
  - **(b)** The lead, once per stage, runs `uv build --wheel --out-dir temp/wheel` and checks
    that `unzip -l` lists `rdf_persistence/testkit/run_queue.py`, `selection_data.py` and
    `changed_tests.py`. This is too slow for a unit test.
- **PD-13 The guard** (DEC-7), as a unit test rather than an import-linter contract. A
  `forbidden` contract cannot cover modules that sit inside the forbidden package, and
  `generated` itself imports the library (counterexample 3).
  `tests/unit/testkit/test_test_control_imports.py` parses each of the three modules with `ast`.
  It asserts that their **direct** imports are only standard-library modules, `testmon` (lazy,
  inside a function), `rdf_persistence.testkit.generated.rp_testkit` and, for `changed_tests`,
  `rdf_persistence.testkit.selection_data`. The rationale is "no direct coupling to the library",
  not "light at runtime": importing the generated module loads the library anyway (RISK-2).
  `runtime-without-extras` already keeps the runtime layers off the testkit.
- **PD-14 Public surface.** The public-surface snapshot (`make refresh-snapshot`) gains the
  three modules. Their public names: `run_queue.workers`, `run_queue.main`;
  `selection_data.check`, `.swap`, `.seed`, `.worktree_lock`, `.current_packages`, `.main`;
  `changed_tests.Classifier`, `.select`, `.plan`, `.changed_files`, `.main`, `.GitError`,
  `.UsageError`. Everything else is `_`-prefixed.
- **PD-15 Docs.** `user-manual/test.adoc` gains a section, *Test control for your project*: the
  Makefile lines and a minimal classifier. `develop/testing.adoc#test-control` names the
  modules. `questions.adoc` gains "How do I queue and select my project's tests with the
  testkit?". The CHANGELOG `[Unreleased]` gets an *Added* entry.

## Algorithm (stage 3's `changed_tests.main`)

1. Parse `PYTEST_CHANGED_N` (PD-9); on error, exit 2.
2. `git rev-parse --show-toplevel`, chdir, `changed_files(BASE)`; a `GitError` gives exit 75.
3. `data_state(root)`; print its message.
4. `plan(changed, sound, exists, workers, classifier, layout)`:
   - with data, split the changed paths by `classifier.is_testmon_visible`; any path under
     `layout.extra_selected_by` also goes to the folder rules;
   - `select(rest, exists, classifier)`;
   - add the no-data hint;
   - fallback reasons → an empty plan;
   - otherwise one testmon run and/or one folder run.
5. Print the hints, then the fallback reasons (PD-5) → 75; no runs → 0; otherwise run each
   invocation under the shared worktree lock when it uses testmon.

## Error matrix

| Input or state | Today | After |
|---|---|---|
| Fallback with no data and a package file changed | reasons only, 75 | hints (`make test-seed`), reasons, 75 (PD-5) |
| `pyproject.toml` changed, `make test-changed` | silently syncs `.venv` | no sync; the change falls back to `test-fast` (PD-6) |
| Two `make test-seed` in one worktree | the second deletes the first's live seed | the second waits on the queue until the first has swapped (PD-7) |
| Seed 1's pytest has exited, seed 2 waiting | seed 2 could start before swap 1 | the swap runs inside seed 1's queued process, so seed 2 starts after it (PD-7) |
| The seed's clean fails (permission) | n/a | `seed` prints the error and exits 1 before pytest (PD-7) |
| `uv.lock` changed, `test-changed` falls back | the fallback's `uv run` syncs | `UV_NO_SYNC=1` is exported to the sub-make (PD-6) |
| The library does not import (a syntax error mid-edit, stale generated code), stage 2 on | n/a | `run_queue` fails with a traceback; `test-changed` exits 1, not 75. Accepted (RISK-6): the traceback names the broken file, and the named-file narrow check still works |
| `CI` set, `uv` missing, `make lint` | `uv: not found` printed | nothing printed; `PYTEST_N` empty; `PARALLEL` is `-n auto` (PD-8) |
| `PYTEST_CHANGED_N=abc` / `0` / `-1` / `2.5` | traceback, exit 1 / `-n 0` / `-n -1` / traceback | the message, exit 2 (PD-9) |
| A seed from before the move, `test-changed` after it | n/a | same lock file and path, so they exclude each other (PD-11) |
| A consumer without pytest-testmon calls `selection_data check` | n/a | `ModuleNotFoundError` names `testmon`: the docs list `pytest-testmon` as a requirement (PD-15) |
| A classifier returns a path that does not exist | as today | as today: a folder is a fallback, a file is dropped |

## Anti-patterns

- Re-exporting the modules from the testkit root (PD-1): every testkit user would pay the import.
- A shim left at `tests/queue.py` (DEC-5).
- Rewriting test bodies during the move. Only the edits that PD-2 permits are made, or the move
  proves nothing (DEC-7).
- A config-file reader for the layout (DEC-4 no-go).
- Releasing the queue before the swap (PD-7): any seed step outside the queued process races
  the next seed.
- A generated class named `Test…` (PD-2): pytest tries to collect it.

## Worked examples

1. **Seed** (PD-7). Locally, `make test-seed` runs
   `uv run python -m tests.queue -- python -m tests.testmon_data seed -- pytest tests -m "…" --testmon --testmon-forceselect -n @workers --dist loadgroup -p no:randomly`.
   The queue takes the lock and replaces `@workers` with `13`. `seed` deletes
   `.testmondata.seed`, runs pytest, which exits 1 because one test failed, swaps (exit 1), and
   the queue's process ends, releasing the lock.
2. **Fallback with hints** (PD-5, PD-6). There is no `.testmondata`, and `rdf_persistence/iris/x.py`
   and `pyproject.toml` have changed. stderr shows
   `no test selection data in this worktree: the lead runs make test-seed`, then
   `pyproject.toml: shared test infrastructure or schema`, and the exit is 75. `make test-fast`
   runs with `UV_NO_SYNC=1`.
3. **A consumer's classifier** (PD-3). Its `tests/changed.py` defines
   `classify(path)`, which returns `ChangedSelection(paths=["tests/unit/app/"], hints=[], fallback_reasons=[])`
   for `src/app/…`, and `is_testmon_visible(path)`, which returns `path.endswith(".py")`. It
   also defines
   `LAYOUT = ChangedTestsLayout(testmon_folders=["tests/unit"], extra_selected_by=[], ignores=["--ignore=tests/e2e"], markers=["-m", "unit"], default_workers=4)`,
   and ends with `sys.exit(changed_tests.main(sys.modules[__name__], LAYOUT))`.

## Test plan

| TC | Stage | Test (red first) | Proves |
|---|---|---|---|
| TC-1 | 1 | `test_changed.py::test_a_fallback_still_prints_the_hints_first` | #403-1 |
| TC-2 | 1 | `test_lanes.py::test_test_changed_runs_the_module_without_syncing` | #403-2 |
| TC-3 | 1 | `test_testmon_data.py::test_seed_cleans_runs_then_swaps` (pytest command faked by a script that checks the old seed is gone and writes a new one); `::test_seed_swaps_nothing_when_pytest_is_interrupted` (exit 2: the earlier `.testmondata` stays); `::test_seed_without_a_command_is_a_usage_error`; `test_lanes.py::test_the_whole_seed_cycle_runs_inside_the_queue` (replaces `..._before_it_starts` and `test_the_seed_exits_as_the_swap_says`) | #403-3 |
| TC-4 | 1 | `test_lanes.py::test_on_ci_the_worker_count_is_quiet_and_lazy` (reads the Makefile text); `test_lanes.py::test_on_ci_without_a_count_pytest_gets_auto` (`make -n test-unit CI=1 PYTEST_N=` prints `-n auto`) | #403-4 |
| TC-5 | 1 | `test_changed.py::test_a_bad_worker_count_is_a_usage_error` (parametrized: `abc`, `0`, `-1`, `2.5`) | #403-5 |
| TC-6 | 1 | `make check-docs` | #403-6 |
| TC-7 | 2 | the moved `test_run_queue.py`, `test_selection_data.py`: green with only PD-2's permitted edits (`git diff -M` shows nothing else) | DEC-7 |
| TC-8 | 2, 3 | `tests/unit/testkit/test_test_control_installed.py` (PD-12) | DEC-7 |
| TC-9 | 2, 3 | `tests/unit/testkit/test_test_control_imports.py` (PD-13): direct imports allow-listed; a planted `import rdf_persistence.persistence` in a tmp copy of one module fails it naming the line | DEC-7 |
| TC-10 | 2, 3 | the model guard over `rdf_persistence/testkit` passes (existing `test_model_guard.py`) | DEC-8 |
| TC-11 | 3 | `tests/unit/testkit/test_changed_tests.py`: the generic tests of today's `test_changed.py` against a tiny fake classifier | DEC-4 |
| TC-12 | 3 | `tests/unit/tooling/test_changed.py` keeps the layout tests (`classify`, the theme rules) against our classifier, with only PD-2's permitted edits | DEC-4 |
| TC-13 | each | `make check-all` green; the lead runs `make test-seed` then `make test-changed` once on the branch | DEC-7 |

Scenarios: the spec deltas in `specs/`.

## Risks

- **RISK-1** (from the Q&A, accepted). MWB2's copies drift from ours until it adopts the
  testkit. Likelihood high, impact low (dev tooling). After stage 1 merges, the stage-1 diff is
  posted on MWB2 #129. After stage 3's release, the adoption comment follows (DEC-10).
- **RISK-2** (attack). `python -m rdf_persistence.testkit.run_queue` pays about 0.5 s of testkit
  import on every queued lane, and under `CI` at parse time, once per `make` that expands
  `PARALLEL`. Likelihood certain, impact low: lanes take minutes, and PD-8 makes CI's call lazy.
  Accepted. If it hurts, make the testkit root lazy (PEP 562), which is review-floors 3.2's
  ground, not this change's.
- **RISK-3** (attack). Pydantic models where `changed.py` had frozen dataclasses: equality and
  hashing differ (models are unhashable). Mitigation: `select()` collects path
  strings, never models, so a test pins that `plan()` gives the same output for today's
  parametrized cases (TC-11, TC-12).
- **RISK-4** (attack). `review-floors` stage 3 is in flight and touches `tests/unit/testkit/`
  (`test_streams.py`, the lazy-import test). Its 3.2 test asserts that the testkit root does not
  load the stream or service modules. Our modules are not imported by the root (PD-1), so the two
  do not collide. A rebase conflict is possible in `docs/.../test.adoc`. Accepted, and the lead
  rebases.

- **RISK-5** (gate run 1, accepted). The swap takes the exclusive worktree lock while the seed
  holds the user-wide queue. A long `test-changed` in that worktree holds the shared lock and
  stalls every heavy lane of that user until it ends. Likelihood low: the lead seeds at stage
  start, before builders run. Impact: a wait, never a deadlock, because no path holds the
  worktree lock and then waits on the queue.
- **RISK-7** (lead, accepted). The parked change `test-memory-followups` (worktree
  `.worktrees/test-memory-followups`) plans a seed spike that may add a coverage flag to the
  seed recipe. Whichever lands second rebases onto the other's recipe line. Its flag fits inside
  PD-7's `seed -- pytest …` command unchanged.
- **RISK-6** (gate run 1, accepted). From stage 2, a library that does not import breaks the
  queue and `test-changed` (see the error matrix). Mitigation: the traceback names the file.

## Lanes for moved or rewritten tests

`test_queue.py`, `test_testmon_data.py` and the generic part of `test_changed.py` move from
`tests/unit/tooling/` to `tests/unit/testkit/`. Both folders are in CI's sharded unit lane
(`make test-unit-ci`), and the same assertions still hold. `test_lanes.py` stays in
`tests/unit/tooling/` and changes only its pinned strings.

## Open Questions

None.
