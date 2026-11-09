<!-- Parents: rp-developer-checks (the lanes and gates); rp-testkit (TokenSigner);
     the candidate change test-profiling, folded in (DEC-1).
     Seeds, intake measurements and the developer's answers: inputs/seed.md. -->

# EPIC: Run only the relevant tests while developing, the whole suite once per stage

> Shaped 2026-11-09 from the developer's request (Q-1 to Q-4 in inputs/seed.md).

**Golden-thread parents:** `rp-developer-checks` (the checks a developer and CI run),
`rp-testkit` (`TokenSigner`), and the candidate change `test-profiling`, which this EPIC supersedes.

## Appetite

**MEDIUM.** One new capability (developer test lanes: a `slow` marker, a changed-files selection,
a profile command) with its tests and docs, plus one small speed-up of the toy app's set-up.
Existing lanes, CI jobs and coverage floors stay as they are.

## Why

The unit and feature tests take about 6 min 45 s of wall time and 27 min of CPU on a 12-core laptop
(3682 tests, 2026-11-09), and `make check-all` 7 to 16 min. Today a developer or agent runs most of
that after every task, because the only lanes split by test kind, not by what changed. Feedback
during development is slow, and agents wait minutes for an answer they could have in seconds.

## Solution outline

Three tiers, each with one make target:

- **While developing and per task**: `make test-changed` runs the test folders that match the files
  changed against `develop`, slow tests in them included, without coverage. A change to shared
  test infrastructure or a file no rule maps falls back to `make test-fast`.
- **When unsure**: `make test-fast` runs every unit and feature test not marked `slow`, without
  coverage.
- **Once per stage, before the PR**: `make check-all` and `make test-containers`, unchanged: every
  test, with the coverage floors. CI runs the full lanes as today.

A test that takes seconds on its own (it runs a tool, a subprocess or a whole generation) carries
`@pytest.mark.slow`. `make profile-tests` prints the slowest tests so the marks and the timings table
stay true; it replaces the candidate `test-profiling`.

The freshness check of the generated code runs once per session instead of once per xdist worker
(≈ 4 s each), and the toy app's set-up gets cheap: the toy's signer reuses one RSA key per worker process instead of
generating a new key for every test, which is about 0.5 s of each set-up's 0.6 s.

Success is measured: a single changed test file runs in ≤ 10 s, the `domain` folder in ≤ 10 s, the
`services` folder in ≤ 40 s (laptop, wall, no coverage; today 7.3 s, 5.8 s and 33 s, with the
freshness cost included); the timings table records them, `test-fast`, and the entrypoint folder
before and after.

## Key decisions

- **DEC-1**: Fold the candidate `test-profiling` into this EPIC; its proposal and the changes README
  say so; its inputs stay. Source: Q-1. Rejected: two changes on the same table.
- **DEC-2**: A slow test is marked per test with `@pytest.mark.slow`, registered in `pytest.ini`.
  The test-kind markers (`unit`, `feature`, …) stay path-based in `tests/conftest.py`. Source: Q-3.
  Rejected: a file table in `conftest.py` (marks fast tests in the same file); an automatic
  duration threshold (machine-dependent, needs a cache).
- **DEC-3**: The selection of changed tests is a small mapping script in the test tree plus a make
  target, from `git diff` against the merge base with `develop` and untracked files. Rejected:
  `pytest-testmon` (a new dependency, poor fit with `pytest-xdist`, coverage database to keep).
- **DEC-4**: The developer lanes run without coverage; the coverage floors are checked only by the
  lanes that have them today (`test`, `test-unit`, `test-feature`, so `check-all` and CI).
  Rejected: coverage in every lane (slows each test, and a partial run cannot meet a floor anyway).
- **DEC-5**: Gates: per task `make test-changed` + `make check-quality` + `make clean-code`;
  `make check-all` + `make test-containers` once before the PR, as today. `make test-fast` is the
  fallback, not a gate. Source: Q-4. Rejected: `test-fast` per task (1 to 2 min more per task).
- **DEC-6**: The set-up speed-up reuses the expensive immutable part (the RSA key) per worker
  process; every test still gets a fresh app, store and file store. Source: the intake profile
  (inputs/seed.md), Q-2. Rejected: one app per module with a store reset between tests (state
  shared between tests, for the same gain).
- **DEC-7**: `TokenSigner` gains an optional keyword `key` for its first signing key; without it,
  behaviour is unchanged. An additive public testkit change: consumers' tests pay the same 0.5 s.
  Rejected: a cache inside `TokenSigner` (two signers would silently share a key).
- **DEC-8**: The freshness check (`testkit/freshness.py`) runs once per session, in the xdist
  controller, not again in each worker. Source: the plan review (design.md § Plan review): ≈ 4 s
  per worker turned a 2-test file into 22 s with `-n auto`. Rejected: dropping the check from the
  developer lanes (stale generated code would then pass unnoticed).

## Rabbit-holes

- **A perfect dependency map.** The mapper is folder-level and deliberately coarse; a change in
  `services/` that breaks `entrypoints/` tests is caught by `check-all` before the PR, and the
  developer can run `make test-fast`. No import-graph analysis.
- **Tuning every slow test.** This EPIC marks them; making any one of them faster is its own change.
- **Profiling machinery.** `--durations` is enough; no profiler, no dashboard, no trend tracking.
- **xdist start-up for tiny selections.** A `PYTEST_N` variable lets a developer run one folder
  serially; no automatic choice.

## No-gos

- Changing CI jobs, the coverage floors, or what `check-all` and `test-containers` run.
- Skipping slow tests anywhere a stage gate or CI runs.
- New dependencies (no `pytest-testmon`, no profiler).
- Sharing an app, a store or a file store between tests.
- Making individual slow tests faster (beyond the toy's key and the freshness guard).
- Selecting container tests (`integration`, `e2e`) by change: they stay in `make test-containers`.

---

## What Changes

- `pytest.ini`: the `slow` marker registered.
- Slow tests in `tests/unit/` (and `tests/feature/` if any) decorated with `@pytest.mark.slow`.
- `Makefile`: new targets `test-fast`, `test-changed`, `profile-tests`; variable `PYTEST_N`.
- A changed-files mapping script under `tests/` with its unit test.
- `rdf_persistence/testkit/freshness.py`: no check in xdist workers.
- `rdf_persistence/testkit/tokens.py`: `TokenSigner(key=...)`, optional, additive.
- `tests/toy_service.py`: the toy's signer starts from one key per worker process.
- Docs: `develop/agents.adoc` (the gates), `develop/testing.adoc` (when to mark `slow`),
  `develop/index.adoc` (the timings table and lanes), `questions.adoc`; `AGENTS.md` gate line.
- `openspec/changes/test-profiling/proposal.md` and `openspec/changes/README.md`: superseded note.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `rp-developer-checks`: developer lanes (`test-changed`, `test-fast`), the `slow` marker, the
  profile command and the timings table (from `test-profiling`).
- `rp-testkit`: `TokenSigner` takes an optional first key.
- `rp-generation`: the freshness check runs once per session under xdist.

## Impact

- Developer tooling, tests and docs; one additive keyword in the public testkit; the freshness
  plugin skips xdist workers (consumers' parallel runs get faster too).
- No change to the package's runtime code, its dependencies, CI or the coverage floors.
