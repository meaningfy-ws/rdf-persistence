> Derives from: EPIC `test-lanes` (proposal.md, shaped 2026-11-09); answers and intake profile in
> inputs/seed.md; the plan attack and gate findings of 2026-11-09 are folded in (§ Plan review).

## Context

The unit and feature tests take ≈ 6 min 45 s wall and 27 min CPU on a 12-core laptop without
coverage (3682 tests, 2026-11-09). Three costs dominate (inputs/seed.md, § Plan review):

1. Tests that run whole tools or generations (10 to 62 s each).
2. A fresh `ToyService` per entrypoint test, whose 2048-bit RSA key alone costs ≈ 0.5 s of an
   ≈ 0.6 s set-up (≈ 10 s on a saturated machine).
3. The freshness check (`rdf_persistence/testkit/freshness.py`, `pytest_sessionstart`) runs in the
   xdist controller **and in every worker**, ≈ 4 s each: a 2-test file takes 7.3 s with `-n 0`,
   22.1 s wall and 73 s CPU with `-n auto`, 3.1 s without the plugin.

Measured baselines for one selection (laptop, 2026-11-09, no coverage, wall time):

| Selection | `-n 0` | `-n 4` | `-n auto` |
|---|---|---|---|
| one 2-test file | 7.3 s | | 22.1 s |
| `tests/unit/domain/` (641 tests) | 5.8 s | 12.6 s | |
| `tests/unit/services/` (991 tests) | | | 32.9 s |

Today's lanes split by test kind (`UNIT_LANE`, markers `unit`, `feature`, `integration`, `e2e`,
`perf`, stamped by path in `tests/conftest.py`). Coverage flags live only in `test`, `test-unit`,
`test-feature`, `test-containers`, `coverage-report` (`COV_FLAGS`). The gates in
`develop/agents.adoc` ask for "the affected test folders" per task, by hand.

## Goals / Non-Goals

**Goals:**
- `make test-changed` after a change in one layer: a single changed test file ≤ 10 s, the
  `domain` folder ≤ 10 s, the `services` folder ≤ 40 s (wall, laptop, no coverage). Measured in
  task 1.4, and the `services` folder again in task 2.3; a miss is reported, not chased beyond this EPIC's scope.
- A no-coverage lane without slow tests, `make test-fast`, for "I am not sure what I broke"
  (DEC-2, DEC-4).
- A repeatable profile and a true timings table (DEC-1).
- The freshness check once per session (DEC-8) and a cheaper `ToyService` set-up without shared
  state (DEC-6, DEC-7).

**Non-Goals:** the EPIC's No-gos: CI, coverage floors and the stage gates are unchanged; no new
dependency; no per-test tuning; container tests are not selected by change.

## Decisions

Settled in the EPIC: DEC-1 to DEC-8. New, taken while planning:

- **PD-1 Where the mapper lives.** `tests/changed.py`, run as `uv run python -m tests.changed`
  (as `Makefile` already runs `python -m tests.dump_openapi`). It is test tooling of this repo, not
  part of the package; `tests/` is linted and type-checked (`PYTHON_PATHS`). Rejected:
  `rdf_persistence/testkit/` (public API no consumer needs, with git assumptions); a shell script
  in the `Makefile` (untestable rules).
- **PD-2 Output contract.** stdout: the pytest arguments, one per line: the selected paths, then
  `-n` and its value (PD-5). stderr: one line per reason (fallback, container hint, nothing
  changed). Exit 0 with arguments, or with none when nothing is to run; exit 3 means "run
  `test-fast`"; any other exit is an error.
- **PD-3 Changed files.** The mapper works from the repository top (`git rev-parse
  --show-toplevel`), because `git ls-files` prints paths relative to the current directory.
  Base: `git merge-base HEAD $BASE`, `BASE` defaults to `develop`. Changed files:
  `git diff --name-only --no-renames <merge-base>` (committed and uncommitted; `--no-renames`
  keeps both sides of a move) plus `git ls-files --others --exclude-standard` (untracked).
  Selected paths that no longer exist are dropped after mapping.
- **PD-4 What "slow" means.** A test is slow when the set-up plus call phases that
  `--durations` reports for it, run alone (`uv run pytest <node id> -p no:randomly
  --durations=0 -n 0`), add up to 2 s or more. Session start-up (collection, the freshness check)
  does not count. Candidates come from `make profile-tests`. Every slow test carries
  `@pytest.mark.slow` on its own definition (DEC-2); no module `pytestmark`, which `pytest.ini`
  and `tests/conftest.py` forbid. Entrypoint tests that are slow only through the `ToyService`
  set-up are not marked: stage 2 fixes them.
- **PD-5 Workers.** The mapper chooses `-n 0` when the selection is files only or only the
  `tests/unit/domain/` folder (5.8 s serial against 12.6 s with 4 workers), `-n auto` otherwise. `PYTEST_N` set in the
  environment overrides the choice (`make test-changed PYTEST_N=4`). `test-fast` and
  `profile-tests` use `-n auto`. The existing lanes keep `-n auto`.
- **PD-6 The toy key.** `tests/toy_service.py` holds one key per process (`functools.cache` over
  a function that generates it) and builds its signer as `TokenSigner(key=toy_key())`. xdist
  workers are processes, so each worker generates one key. `World` in
  `tests/unit/entrypoints/test_library_app.py` uses the same key. `tests/integration/api/` builds
  `ToyService` too, so the container lane changes with it (`make test-containers` in task 2.4).
- **PD-7 The freshness guard.** `pytest_sessionstart` returns at once when `session.config` has
  `workerinput` (an xdist worker). The controller's check runs before xdist starts its workers
  (xdist's own `pytest_sessionstart` is `trylast`), so a stale tree still stops the whole session
  once. T-5 proves both.

## Algorithm / approach

### Mapping rules (`tests/changed.py`, first matching rule wins, per changed path)

`<dir>` is one folder level below `tests/unit/`; `**` matches zero or more folders.

| # | Changed path | Selects |
|---|---|---|
| 1 | `openspec/**`, `.claude/**`, `temp/**`, `*.md` at the root | nothing |
| 2 | `docs/**` | `tests/unit/test_check_docs.py` |
| 3 | `pytest.ini`, `pyproject.toml`, `uv.lock`, `Makefile`, `.coveragerc`, `tests/*.py` (`conftest.py`, `__init__.py`, `toy.py`, `toy_service.py`, `dump_openapi.py`, `changed.py`), `tests/fixtures/**`, `tests/unit/__init__.py`, `rdf_persistence/model/**` | **fallback** (exit 3) |
| 4 | `tests/integration/**/test_*.py`, `tests/e2e/**/test_*.py` | nothing; stderr names it with `make test-containers` |
| 5 | any other file under `tests/integration/` or `tests/e2e/` (helpers such as `e2e/library_app.py`, which unit tests import) | **fallback** (exit 3) |
| 6 | `tests/perf/**` | nothing; stderr names it with `make test-perf` |
| 7 | `tests/unit/test_*.py` (root level) | the file itself |
| 8 | `tests/unit/<dir>/**`, any file (tests import other test modules: `test_router`, `test_documents`, …) | `tests/unit/<dir>/` |
| 9 | `tests/feature/**` | `tests/feature/` |
| 10 | `rdf_persistence/<layer>/**`, layer ∈ domain, services, adapters, entrypoints, generation, testkit (their `generated/` folders included) | `tests/unit/<layer>/` |
| 11 | any other `rdf_persistence/*` file (`__init__.py`, `py.typed`) | every root-level `tests/unit/test_*.py`, expanded to real file names |
| 12 | anything else (`.github/**`, `.importlinter`, `ruff.toml`, `mypy.ini`, …) | **fallback** (exit 3) |

`rdf_persistence/model/**` falls back because unit tests in several folders read the schemas
directly (`services/test_schema_structure.py`, `entrypoints/test_service_written.py`).
`.importlinter`, `ruff.toml` and `mypy.ini` are checked by `make check-quality` anyway; the
fallback for them is the safe default, not a need.

Then: any fallback → exit 3, the stderr lines naming every path that caused it. Otherwise drop
selected files that lie inside a selected folder, drop paths that do not exist, sort. If paths
remain, print them and then `-n` and its value (PD-5). If none remain, print nothing on stdout
(never a lone `-n`, which would make pytest run its whole `testpaths`) and write to stderr
"nothing to run against <base>" after any hints; exit 0.

The mapping is a pure function `select(paths: Sequence[str], existing: Callable[[str], bool]) ->
Selection`, `Selection` a frozen dataclass (`paths: tuple[str, ...]`, `hints: tuple[str, ...]`,
`fallback_reasons: tuple[str, ...]`); the git listing is a separate function; `main()` joins them
and renders the arguments. Local test tooling, so a dataclass, not a LinkML model.

### Worked example

Changes against `develop`: `rdf_persistence/services/artifacts.py`,
`tests/unit/services/test_replace_internal_values.py` (untracked),
`openspec/changes/x/design.md`, `tests/integration/api/test_routes.py`.
Rules 10, 8, 1, 4 → `tests/unit/services/` twice (one kept), a hint for the integration file.
stdout `tests/unit/services/` and `-n` `auto`; stderr
`tests/integration/api/test_routes.py: container test, run make test-containers`; exit 0.

### Make targets

```make
PROFILE_MARK ?= unit or feature

test-fast:     ## Unit and feature tests not marked slow, in parallel, no coverage (developer lane)
	@ uv run pytest $(TEST_PATH) $(UNIT_LANE) -n auto -m "(unit or feature) and not slow"

test-changed:  ## The tests of the files changed against BASE (default develop), slow ones included, no coverage
	@ args=$$(uv run python -m tests.changed); status=$$?; \
	  if [ $$status -eq 3 ]; then $(MAKE) --no-print-directory test-fast; \
	  elif [ $$status -ne 0 ]; then exit $$status; \
	  elif [ -n "$$args" ]; then uv run pytest $$args $(UNIT_LANE) -m "unit or feature"; fi

profile-tests: ## The 15 slowest unit and feature tests, set-up and call apart, no coverage
	@ uv run pytest $(TEST_PATH) $(UNIT_LANE) -n auto -q -m "$(PROFILE_MARK)" --durations=15
```

This works as written: make runs each recipe line with `bash -o pipefail -c` and no `-e`, so the
assignment does not abort on exit 3. `BASE` and `PYTEST_N` reach the mapper as environment
variables (`make test-changed BASE=origin/develop` exports a command-line variable).
The arguments are split on whitespace, which is safe because no path in this repo has a space; the
mapper carries a `shortcut:` comment saying a path with one would need NUL-separated output.

### Tests (written first)

- **T-1** `tests/unit/test_changed.py`: table-driven over the 12 mapping rules, one row each,
  plus: the worked example; hints only (a changed container test) and a lone deleted test file
  give empty stdout; `tests/e2e/library_app.py` falls back; a `model/*.yaml` falls back;
  a changed `test_router.py` selects its folder; rule 11 expands to real files; a selected file
  inside a selected folder is dropped; a deleted test file selects nothing; fallback wins over
  paths; nothing changed; PD-5's `-n` choice and the `PYTEST_N` override.
- **T-2** the git listing in a temporary repository (`git init`, a `develop` branch, a commit on a
  feature branch, an uncommitted edit, an untracked file, a deleted file, a rename): all listed,
  both sides of the rename. It runs `git` subprocesses; if it passes 2 s alone (PD-4) it is
  marked `slow`.
- **T-3** `tests/unit/testkit/`: the three `rp-testkit` scenarios (`TokenSigner(key=…)`).
- **T-4** `tests/unit/test_markers.py` (exists): `slow` is registered, and `-m "not slow"`
  deselects a marked test (pytester).
- **T-5** `tests/unit/testkit/test_freshness_plugin.py` (moved by R-2) (exists): a worker session
  (`workerinput` set) skips the check; a stale project under `-n 2` (pytester) stops the session
  with one message.
- Make targets are checked by running them in the task (reported with time and count), not by a
  test that shells out to make (it would itself be slow).

Idempotency: every target only reads the tree; running one twice gives the same selection.

### Anti-patterns

| Don't | Do instead | Why |
|---|---|---|
| Mark entrypoint tests `slow` because their set-up is slow under load | Fix the set-up (stage 2) | They are fast alone; marking hides them from the fast lane |
| Count wall time of a one-test run as the test's time | Count `--durations` set-up + call | Session start-up is ≈ 4 s and not the test's (PD-4) |
| Add `--cov` to a developer lane | Leave coverage to `test`, `test-unit`, `test-feature` | A partial run cannot meet the floor (DEC-4) |
| Grow the mapper into an import-graph analysis | Select the folder, or fall back | Rabbit-hole; `check-all` catches cross-layer breaks |
| Module `pytestmark = pytest.mark.slow` | Decorate each slow test | `pytest.ini` forbids per-file `pytestmark`; DEC-2 |
| Cache the key inside `TokenSigner` | Pass `key=` from the toy | Two signers would silently share a key (DEC-7) |
| Share a `ToyService`, store or file store between tests | Share only the key | No-go; state leaks between tests |
| `-n auto` for a handful of tests | `-n 0` (PD-5) | xdist start-up costs more than the run |

## Error matrix

| Failure mode | How it is detected | Expected handling |
|---|---|---|
| `develop` (or `BASE`) does not exist locally | `git merge-base` fails | stderr names it and suggests `BASE=origin/develop`; exit 3 (fallback) |
| Not a git checkout / git missing | `git` exits non-zero or is absent | stderr says so; exit 3 |
| Run from a subfolder | — | the mapper `chdir`s to `git rev-parse --show-toplevel` first (PD-3) |
| A file moved between layers | `--no-renames` lists both sides | both folders selected |
| A changed path matches no rule | rule 12 | exit 3, stderr names the path |
| Shared infrastructure, a schema or a container helper changed | rules 3, 5 | exit 3, stderr names the file |
| A selected test file was deleted | path no longer exists | dropped; if nothing remains, "nothing to run" |
| Paths with spaces | none in this repo | `shortcut:` comment in the mapper (§ Make targets) |
| Only container or perf tests changed | rules 4, 6 | exit 0, no pytest run, hints on stderr |
| Stale generated code under xdist | the controller's freshness check | the session stops once, before workers start (PD-7, T-5) |
| A slow test breaks while developing in another folder | not in that folder's selection | caught by `check-all` before the PR, and by CI (RISK-1) |
| A test relied on two `ToyService`s having different keys | full suite after task 2.1; adversarial tester | that test builds its own `TokenSigner()` or rotates; never revert to per-test keys |
| `rotate` after `key=` returned the given key | T-3 | `rotate` always generates (spec) |
| An unmarked slow test enters the fast lane | `make profile-tests PROFILE_MARK="(unit or feature) and not slow"` when the timings table is refreshed | mark it (PD-4) |

## Risks / Trade-offs

- **RISK-1** A slow test breaks unseen until the stage gate. Likelihood medium, impact low (found
  before the PR, one fix). Mitigation: `test-changed` includes slow tests of the matched folders;
  `check-all` before the PR; CI runs everything.
- **RISK-2** The mapper misses a cross-layer break (a services change breaking entrypoint tests).
  Likelihood medium, impact low. Accepted: per-task runs are a fast signal, not a proof; the stage
  gate is the proof. Run `make test-fast` when a port or a shared model changes.
- **RISK-3** The shared key hides a test that needed distinct keys. Likelihood low (the plan
  review found none; `test_service_kit.py:79` swaps the signer per instance, still safe), impact
  medium (a security test passing for the wrong reason). Mitigation: the adversarial tester after
  task 2.1.
- **RISK-4** xdist start-up costs more than a small selection. Mitigated by PD-5 and PD-7;
  `PYTEST_N` overrides.
- **RISK-5** New slow tests go unmarked and the fast lane drifts. Likelihood medium, impact low.
  Mitigation: the profile with `PROFILE_MARK` when the timings table is refreshed; `testing.adoc`
  states the 2 s rule.
- **RISK-6** Skipping the freshness check in workers lets a worker run on stale code. Likelihood
  none in practice: workers share the controller's tree and start after its check. T-5 pins it.
- Trade-off: decorating per test (DEC-2) is more precise than a file table and easier to forget;
  RISK-5 covers it.

## Plan review (2026-11-09)

An independent attack and clarity-gate pass scored the first draft 7/10 and found ten defects,
all folded in above: the per-worker freshness cost and the wrong `-n auto` default (PD-5, PD-7,
DEC-8); a wrong recipe caveat (§ Make targets); rule 11's glob; `tests/e2e/library_app.py`
imported by a unit test (rule 5); schemas read directly by unit tests (rule 3); test modules
importing each other (rule 8); renames (PD-3); module `pytestmark` against `pytest.ini` (PD-4);
wall time skewed by start-up (PD-4); `World`'s own `TokenSigner()` and the container lane's
`ToyService` (PD-6); `git ls-files` relative paths (PD-3).

## Delivery findings

- **F-1 (task 1.1, 2026-11-09).** With the freshness guard, `tests/unit/test_smoke.py` (2 tests)
  takes 22.5 s wall and 61 s CPU with `-n auto` (before: 22.1 s, 73 s) and 5.3 s with `-n 0`. The
  guard saves ≈ 1 s CPU per worker; the rest of xdist's cost is each worker importing the stack.
  So PD-5 (one process for small selections) carries the inner-loop speed, not DEC-8. DEC-8 stays:
  it is correct and cheap, and saves CPU on every parallel run.

- **F-2 (task 1.2, 2026-11-09).** Of 59 candidates from a parallel profile (6 min 2 s, 3711
  tests), 26 tests average 2 s or more per run alone and carry `@pytest.mark.slow` (24 in
  `generation/`, `services/test_session_find.py`, `test_packaging.py`; 2 in `entrypoints/` whose
  own work exceeds the toy set-up). `make test-fast`: 3736 tests in 3 min 3 s wall (18 min 44 s
  CPU), against ≈ 6 min for the full no-coverage run. What remains slow under load is the
  entrypoint `ToyService` set-up (stage 2) and module- or session-scoped generation fixtures
  (`shed_project`, `generated_toy`, `partial`, …): their cost is paid once per worker by whichever
  test runs first, so marking that test only moves the cost to the next one. Those are not
  chased (Rabbit-holes: tuning every slow test).

## Stage 1 review (2026-11-09)

Lenses L1, L2, L3 and L4+L5, no P1. Accepted (the fix lands before the PR):

- **R-1** (L1, L2, L4) A non-test file at the root of `tests/unit/` (a future `conftest.py`,
  `helpers.py`) is passed to pytest and collects nothing (exit 5). It falls back (rule 12); a T-1 row.
- **R-2** (L3) Tests do not always live in their layer's folder: the freshness plugin
  (`rdf_persistence/testkit/freshness.py`) is tested in `tests/unit/generation/`. Move
  `test_freshness_plugin.py` to `tests/unit/testkit/` (absolute imports of its helpers).
- **R-3** (L3) `select()` reads the file system for rule 11. It takes the root-level unit test
  files as a parameter; `main()` globs.
- **R-4** (L2) `main()` has no test: one parametrised test over nothing-to-run (exit 0, empty
  stdout), fallback (exit 3) and `GitError` (exit 3).
- **R-5** (L2) The stale-tree-on-workers test passes with or without the guard. Add a fresh-tree
  test under `-n 2` that counts the checks (a pytester conftest wrapping `_project_report`): one.
- **R-6** (L2) T-1: a message on every assertion; a test that the rows cover rules 1 to 12; a rule-8
  row for `tests/unit/entrypoints/test_router.py`.
- **R-7** (L3) A test that `LAYERS` equals the package's layer folders.
- **R-8** (L4) `_classify` returns a `Selection` instead of three positional lists.
- **R-9** (L1) `test-changed` splits the arguments on newlines only and without globbing
  (`set -f; IFS=$$'\n'`); `git merge-base --end-of-options`.
- **R-10** (L4) `pytest.ini`: the marker comment and the `slow` line wrapped at ≈ 100 columns.
  `Makefile`: `PROFILE_MARK` beside `UNIT_LANE`; progress and done lines on the three targets.
- **R-11** (L4) Docs: "after changing `domain` or a port in `services`, run `make test-fast`" in
  `develop/agents.adoc` and `AGENTS.md`; `questions.adoc` says "a few seconds to a minute", as
  `index.adoc` does; the `check-all` row re-measured.
- **R-12** (L2) The freshness plugin tests that build a project per test: re-measure alone on an
  idle machine (PD-4) and mark those at 2 s or more.

Rejected: constants for every path string in `tests/changed.py` (the strings are the rule table,
read once; L4 P3); `git -z` output (non-ASCII names already fall back safely; L1 P3).

## Open Questions

None. The lead's choices (PD-1 to PD-7, DEC-6's turn from a shared app to a shared key, DEC-8)
are recorded in inputs/seed.md; the developer may overrule them.
