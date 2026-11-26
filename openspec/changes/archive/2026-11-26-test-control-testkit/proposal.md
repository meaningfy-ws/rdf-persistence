<!-- Parents: openspec/specs/rp-developer-checks (the test queue, the changed-file selection, the
     seed); openspec/specs/rp-testkit; archived 2026-11-25-agent-test-control (PD-1 to PD-7, DEC-10,
     D-3). Issue #403 and its OPEN-2. Seeds: inputs/seed.md; answers: inputs/qa.md. -->

# EPIC: Test control, fixed and shipped in the testkit

## Appetite

LARGE: three concerns (six fixes, two modules moved, one planner extracted behind a callback), a
new public testkit API, and the first consumer migrating off its copies. Three stages, three PRs.

## Why

`agent-test-control` (0.15.0) works here, but copying it into MWB2 found six defects (#403). Two of
them break guards that builders rely on: `make test-changed` can sync the shared `.venv`, and
`make test-seed` can delete another run's seed database. MWB2 copies our three scripts by hand, so
every fix has to be copied twice and the copies already differ. One maintained copy in the testkit
ends that.

## Solution outline

1. **The fixes, in place** (stage 1). Each of #403's six findings gets a red test and a fix in the
   current `tests/` scripts and Makefile, so MWB2 can copy the result at once.
2. **The queue and the selection data move to the testkit** (stage 2). `tests/queue.py` and
   `tests/testmon_data.py` become `rdf_persistence.testkit` modules, run with `python -m`. Our
   Makefile calls them there, and the `tests/` copies are deleted.
3. **The changed-tests planner moves too** (stage 3). The testkit owns the planning, the pytest
   runs, the exit codes, the testmon handling and the worktree lock. A repository passes a
   classifier: which tests a changed path selects, and which paths testmon can see. Our
   `tests/changed.py` shrinks to that classifier.

Outcome: a consumer gets the queue, the seed and `test-changed` from the toolkit it already
depends on, writes only its classifier, and gets later fixes by upgrading.

## Key decisions

- **DEC-1**: #403 and its OPEN-2 are one EPIC. The fixes land first, in the current files, so the
  move carries fixed code. Rejected: fixes only, with OPEN-2 left as its own issue.
- **DEC-2**: The lock stays per user, under `$XDG_CACHE_HOME`. `develop/testing.adoc#test-control`
  is corrected to say it queues every repository *that user* runs. Rejected: a group-writable,
  machine-wide lock, since one account runs every agent on this machine.
- **DEC-3**: A `PYTEST_CHANGED_N` that is not a positive integer is a usage error: one line naming
  the value, exit 2. Rejected: warning and falling back to the default, which hides a typo.
- **DEC-4**: All three scripts move. `changed.py`'s repository-specific part stays in the
  repository as a classifier callback (`classify(path)`, `is_testmon_visible(path)`), and the
  testkit owns everything else. Rejected: a layout as data, or a `pyproject.toml` table. Both have
  to anticipate every repository's quirks (our generator roots, our docs test).
- **DEC-5**: The modules run as `python -m rdf_persistence.testkit.<module>`. The `tests/` copies
  are deleted, with no shims and no console scripts. Rejected: `[project.scripts]` entries, which
  add public surface for a shorter Makefile line.
- **DEC-6**: The moved modules are public testkit API under semver, documented with the rest of
  the testkit. Breaking them is MAJOR. Rejected: marking them provisional.
- **DEC-7**: What the EPIC proves: one red test per #403 finding; the moved tests pass with only
  their imports changed; `python -m` works from the installed package, not from `tests/`; the full
  gates are green with the new paths; an import-linter contract keeps runtime layers off the new
  modules.
- **DEC-8**: The planner's value types (`Selection`, `Invocation`, `Plan`) are generated from
  `rp_testkit.yaml`, per LinkML as the single source and the testkit's model guard (archived D-3).
  Rejected: plain tuples, which make a weaker public API.
- **DEC-9**: Three stages, one PR each: S1 the fixes, S2 queue and selection data, S3 the
  planner. Each stage is green and releasable alone. Rejected: two stages, which give a bigger
  second review.
- **DEC-10**: When stage 3 is released, a comment on MWB2 #129 names this change and the release,
  so MWB2's OPEN-2 change plans its swap (D-12). Rejected: opening a new MWB2 issue.

## Rabbit-holes

- **The classifier's seam.** `plan()` today mixes generic steps (the testmon split, the fallbacks)
  with layout ones (the generator roots, the docs test). Cut only along the two callbacks of DEC-4.
  A third callback is a re-shape, not a silent addition.
- **The worktree lock and the seed swap.** `testmon_data`'s `worktree_lock` is shared by the seed
  and `test-changed`. Moving it must keep the lock file's path, or a seed run from before the
  upgrade and a `test-changed` run from after it will not exclude each other.
- **Finding 3's ordering.** The cleanup must run under the queue lock *and* before pytest opens
  `.testmondata.seed`. Either the queued command is a small shell sequence, or the cleanup moves
  into `testmon_data` as a subcommand run inside the queue.
- **CI's parse-time shell** (finding 4). The fix touches every `make` call under `CI`. Check the
  three CI jobs that use `PYTEST_N`.

## No-gos

- No machine-wide or cross-user lock (DEC-2).
- No layout-as-data or `pyproject.toml` configuration for the planner (DEC-4).
- No console scripts, and no shims left in `tests/` (DEC-5).
- No change to the exit codes of PD-4 (0, 1, 2, 4, 75), to the worker rule of PD-3, or to the
  lane definitions.
- No changes in MWB2's repository. Its adoption is its own change (DEC-10).
- None of the archived D-3's follow-ups (building the annotation once per class, loading each
  schema once per process, `SchemaView`'s cache).

---

## What Changes

- `tests/changed.py`: hints printed on a fallback (#403-1); a bad `PYTEST_CHANGED_N` is exit 2
  (#403-5, DEC-3). Stage 3 reduces it to a classifier.
- Makefile: `test-changed` with `--no-sync` (#403-2); the seed cleanup under the queue lock
  (#403-3); under `CI`, no stderr noise and no `@workers` reaching plain pytest (#403-4). Stages 2
  and 3 point every call at the testkit modules.
- `develop/testing.adoc#test-control`: the lock is per user (#403-6, DEC-2). The testkit's user
  manual gains the queue, the seed and the changed-tests planner.
- New public testkit modules: the queue, the selection data, and the changed-tests planner with its
  classifier protocol (DEC-4 to DEC-6). New generated classes in `rp_testkit.yaml` (DEC-8).
- `tests/queue.py`, `tests/testmon_data.py`: deleted in stage 2. Their tests move to
  `tests/unit/testkit/`.
- `.importlinter`: a contract keeping the runtime layers off the new modules (DEC-7).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `rp-developer-checks`: the six #403 behaviours; the queue, the seed and `test-changed` are run
  from the testkit.
- `rp-testkit`: the queue, the selection data and the changed-tests planner as public API, and a
  repository supplies only its classifier.

## Impact

Code: the Makefile, `tests/changed.py`, `tests/queue.py`, `tests/testmon_data.py` (deleted),
`rdf_persistence/testkit/` (three new modules, `__init__.py`), `rdf_persistence/model/technical/testkit/rp_testkit.yaml`
and its generated code, `.importlinter`, `tests/unit/tooling/` and `tests/unit/testkit/`. Docs:
`develop/testing.adoc`, the testkit's user-manual page. Release: MINOR, a new public API with
nothing broken. Consumer: MWB2 drops its copies in its own change (RISK-1, DEC-10).

## Delivered (reconciled 2026-11-26, P-0004)

Three stages, three PRs, as DEC-9 shaped them:

| Outline item | Delivered | Evidence |
|---|---|---|
| 1. The six fixes | #411: hints before reasons; no sync (`UV_NO_SYNC` reaches the fallback); the seed's clean, run and swap are one queued process, and the pytest child keeps the lock; a quiet, lazy CI worker count with `-n auto`; a bad `PYTEST_CHANGED_N` exits 2; the lock is per user | `make check-all` green before and after the fix pass; CI green; `evidence/seed-race.md`: the old recipe lost a seed to the race during the stage |
| 2. Queue and selection data in the testkit | #412: `rdf_persistence.testkit.run_queue` and `.selection_data`; `SelectionDataOutcome` and the planner's types generated from `rp_testkit.yaml`; the root does not load them; an `ast` guard on direct imports | `make check-all` green; the wheel lists both modules (PD-12 b) |
| 3. The planner in the testkit | stage-3 PR: `rdf_persistence.testkit.changed_tests` with a `Classifier` protocol and a `ChangedTestsLayout`; `tests/changed.py` is this repository's classifier; `__all__` per module; the user manual's *Test control for your project* | `make check-all` green after the full review's fix pass |

Differences from the shape, with their reasons:
- PD-7 was re-planned at the gate: `--before` on the queue became a `seed` subcommand run inside
  the queue, because `--before` left the swap outside it (gate run 1).
- The layout is a third input beside DEC-4's two callbacks (PD-3), passed as data rather than as
  a member of the protocol.
- Moving the code into the package put it under the package's lint, complexity, mypy and
  patch-marker guards. Three functions were split to keep rank B, and the moved tests gained one
  `# X3` marker each where they patch toolkit code (D-3).
- The full review (D-4) also added validation of `PYTEST_WORKER_MB`, exit 127 for a command the
  queue cannot start, NUL-separated git paths, `sys.executable -m pytest`, `__all__`, and neutral
  messages.
- Not done here: the adoption comment on MWB2 #129 waits for the release that carries stage 3
  (DEC-10). The stage-1 fixes were posted there on 2026-11-26 (RISK-1).
