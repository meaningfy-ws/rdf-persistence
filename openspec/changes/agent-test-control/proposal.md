<!-- Parents: the owner's question of 2026-11-25 and its evidence (inputs/seed.md, the Langfuse
     traces of skillery 3.22+ sessions); the archived change 2026-11-09-test-lanes (PD-1 to PD-5,
     the lanes and `make test-changed` this EPIC changes); the capability rp-developer-checks. -->

# EPIC: Control the test runs of agent sessions

**Golden-thread parents:** `rp-developer-checks` (the requirements *The unit and feature tests
run in parallel*, *The tests of the changed files run on their own*, *Agents' shell commands do
not poll*); the archived change `2026-11-09-test-lanes`; the gates of
`develop/agents.adoc#gates`.

## Appetite

**MEDIUM.** One new capability, test control for agent sessions: a queue for the heavy lanes, a
selection of the tests a change reaches, and the rules and docs agents follow. Neighbours touched
lightly: the Makefile, `tests/changed.py`, the gate table. The skillery follow-up is its own
change (SMALL), tracked by an issue (DEC-1).

## Why

Agent sessions here spend most of their time waiting for tests, not thinking. In the sessions of
2026-11-22 to 2026-11-25, builders spent 3 to 16 times longer in Bash than in model calls, mostly
waiting for gates; one `make check-all` took 38 min against 13 (inputs/seed.md). Three causes
compound: every lane starts one worker per core while four or five sessions run at once; the
builders' narrow gate, `make test-changed`, falls back to the full fast suite for eight PRs in nine;
and builders poll their gate logs in 10-minute waits the poll hook does not see. Now, because
skillery's own overhead is down to almost nothing, this is what is left.

## Solution outline

1. **One heavy run at a time on the machine.** The heavy lanes queue behind one lock shared by
   every repository; a run that waits says whose run it waits for. Inside the lock a run takes
   nearly all cores, so one run finishes in its table time instead of four running at a quarter.
2. **Builders run only the tests their change reaches.** `make test-changed` selects tests by what
   they executed (pytest-testmon) for Python changes, keeps the folder rules for the files testmon
   cannot see, and stops falling back to the full suite for a change in `core`, a helper or a
   fixture.
3. **The full suite runs once per stage, by the lead,** as today. At stage start the lead also
   seeds the selection data with one run of the fast lane, in a background process, while the
   builders begin.
4. **Agents follow written guards:** which gate each role runs, how to wait for one, and who may
   regenerate or sync the environment; in `AGENTS.md` now and enforced by skillery's hooks later.
5. **A test worker stays near its start-up memory.** Each worker releases the library caches that
   keep old schema views and apps alive when it moves to the next test module, and the worker
   count also respects the free memory, so one lane cannot push the machine into swap
   (inputs/memory.md: workers grow to 2 to 4 GB today).
6. **A page tells an agent how test runs are controlled here,** written after the implementation
   from what was built, so another repository can copy it.

Success is measured in Langfuse (DEC-8).

## Key decisions

- **DEC-1**: Two linked changes. This EPIC builds and documents the mechanism here; a skillery
  issue, opened with this EPIC, specifies the generic part (the template targets, the hook, the
  `test-strategy` and `guardrails` text) for every Meaningfy repository — the owner's choice; it
  is proven in one repository before it is copied. Rejected: skillery first; this repository only.
- **DEC-2**: One lock for every repository on the machine, around the heavy lanes only; narrow
  runs of named files do not take it — the contention is across repositories (MWBv2 sessions share
  the cores). Rejected: one lock per repository; no lock with fewer workers (runs still overlap).
- **DEC-3**: The worker count defaults to the core count minus 3 (17 on the owner's 20 cores),
  at least 1; `PYTEST_N` overrides it — the owner's figure, leaving room for the sessions'
  own processes. Rejected: `-n auto` (all cores); a fixed 4.
- **DEC-4**: pytest-testmon selects the tests of Python changes in `make test-changed`, with no
  spike gate — the owner's choice; it is the only approach measured that sees fixtures (inputs/seed.md).
  Rejected: GitNexus call graph, grimp import graph, ast-grep, Serena (blind to fixtures, too
  coarse or too costly).
- **DEC-5**: The lead seeds the selection data once per worktree at stage start, in a background
  process, queued behind the lock and without coverage (testmon records nothing under coverage) —
  the owner's choice. Rejected: copying another worktree's data.
- **DEC-6**: Builders never run `make test-fast`, `make test`, `make check-all` or the seed; they
  wait for a gate through its completion notice, never `tail --pid`, `tail -f | grep -m1` or a
  `timeout` around a wait; only the lead runs `make generate` or `uv sync` in a shared worktree.
  Written in `AGENTS.md` and `develop/agents.adoc` now; enforced by a skillery hook later (DEC-1).
- **DEC-7**: The documentation for agents is a section of `develop/testing.adoc`, the rules in
  `develop/agents.adoc` (briefs, gates), the gate table of `AGENTS.md` and an entry in
  `questions.adoc`, written after the implementation.
- **DEC-8**: Success is measured in Langfuse over the first epic session after the merge with at
  least three sessions running: a builder's task gate under 3 min at the median; `make check-all`
  under 15 min, queue wait excluded; no builder over 10 % of its wall time waiting on gates.

- **DEC-9**: Memory is bounded in two ways only: a release at each test-module boundary (clear
  the linkml-runtime `SchemaView` and FastAPI dependency caches, collect garbage, return freed
  memory to the system), and a worker count that is also bounded by the available memory — the
  owner's choice after the measurements of `inputs/memory.md` ("is enough"). Rejected: worker
  recycling (unsafe under `--dist loadgroup`); `MALLOC_ARENA_MAX` (no effect on live objects);
  making import-time objects lazy and loading each schema once per process (a library change: the
  kit loads and modifies its own view; it is the follow-up change, with a report to linkml-runtime,
  named in the stage report).

## Rabbit-holes

- Tuning testmon for files it cannot see. The folder rules already map them; do not teach testmon
  about YAML or `.feature` files.
- A scheduler, a queue service or fair sharing between sessions. One `flock` is enough.
- Making CI select tests. CI runs everything, sharded, on runners with no contention.
- Reworking the durations table or the test lanes themselves.

## No-gos

- No change to what the full gates run, their coverage floors or CI's jobs.
- No sharing of selection data between worktrees, branches or machines.
- No test results reused across branches.
- No hook shipped by this repository (`AGENTS.md`: it ships none); the hook is skillery's (DEC-1).
- No change to MWBv2 or any other repository in this EPIC.
- No rework of how tests build schema views or apps (lazy globals, shared views), no worker
  recycling, and no upstream change to linkml-runtime or FastAPI (DEC-9).

---

## What Changes

- The Makefile and `tests/queue.py`: a worker count of cores minus 3, capped by
  `MemAvailable / PYTEST_WORKER_MB`, `PYTEST_N` overriding it; one machine-wide lock
  around the heavy lanes; a new `make test-seed`.
- `make test-changed`: Python changes selected by testmon; the folder rules kept for files testmon
  cannot see; the fallback to `make test-fast` kept only for a file no rule maps and testmon
  cannot see; no selection data means the folder rules, with a hint to the lead.
- A development dependency, `pytest-testmon`; `.testmondata` ignored by git.
- `tests/conftest.py` and `tests/memory.py`: the caches cleared after each test, and the memory
  released at each module boundary.
- `AGENTS.md`, `develop/agents.adoc`, `develop/testing.adoc`, `questions.adoc`: the gates and
  guards of DEC-6 and the page of DEC-7.
- A skillery issue (DEC-1).

## Capabilities

### New Capabilities

### Modified Capabilities
- `rp-developer-checks`: the parallel lanes' worker count and queue; what `make test-changed`
  selects; the seed; the memory release of test workers.

## Impact

Makefile, `tests/changed.py`, `tests/conftest.py`, `tests/memory.py`, `tests/queue.py`,
`tests/testmon_data.py`, `tests/unit/tooling/test_changed.py`,
`tests/unit/tooling/test_lanes.py`, `pyproject.toml`, `uv.lock`, `.gitignore`, `AGENTS.md`,
`docs/modules/ROOT/pages/develop/{agents,testing,index}.adoc`, `questions.adoc`. No library or
generator code changes.
