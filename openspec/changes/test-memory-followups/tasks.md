EPIC: test-memory-followups (proposal.md). Decisions: proposal.md DEC-1 to DEC-7; design.md PD-1 to PD-8.

> Derives from: the EPIC `test-memory-followups`.

Every task: its **Red** test is written first and seen failing. Task gate
`make test-changed check-quality`; the lead seeds at stage start (`make test-seed`), because
stage 1 has builders, and runs `make check-all` once before the PR and once after the fix pass,
never its lanes by hand beside it (PD-7, P-0022). The close seeds nothing. One stage, branch `change/test-memory-followups` off
`develop`, one PR. Commit body `Refs: test-memory-followups <task> <PD>`.

## 1. The fixes

- [ ] 1.1 PD-1, unit. `auth.py`, `sse.py`, `rdf_persistence/testkit/memory.py` (the `typing`
  keyword and `_clear_typing`'s docstring). Red, in `tests/unit/api/test_service_release.py`:
  `test_a_dropped_service_is_freed_without_clearing_typing` builds three `ToyService()`, drops
  them, calls `clear_caches(typing=False)`, runs `gc.collect()`, and asserts the number of live
  `ServiceKit` objects is back to its value before the three; in
  `tests/unit/testkit/test_memory.py`, `clear_caches(typing=False)` reports 0 for `typing` and at
  least 1 for the other two. Guard: `tests/unit/api/test_openapi.py`,
  `tests/unit/api/test_openapi_served.py`, `tests/unit/api/` whole.
- [ ] 1.2 PD-2, PD-3, unit (parallel with 1.1, except its edit to `memory.py`: the
  `service_views` count in `release_memory` is made after 1.1's commit is on the branch).
  `service_view`, `clear_service_views`, `kit.py`, `ServiceKit.view`'s docstring,
  `release_memory`. Red, in `tests/unit/schema/test_service_view.py`: the eight worked examples of
  design.md's *Algorithm / approach* as one parametrized table, plus the concurrent case (two
  threads started together on one file; a counting loader passed as `service_view(path, load=...)`, called once);
  in `tests/unit/api/test_service_view_guard.py`: PD-3's guard over the named scene. Before the
  change, scan the tests for a modification of a kit's view (`ast-grep` for `$K.view.$M(...)`
  with `add_slot`, `add_class`, `set_modified`, and `.slots.append` on a view taken from a kit);
  report each, and switch it to its own `load_schema` if any. Guard: `tests/unit/api/` whole,
  `tests/feature/`. Then the **Lead** times the module on one process before and after, through
  the queue: `TEST_QUEUE_LABEL=timing uv run python -m rdf_persistence.testkit.run_queue -- /usr/bin/time -v pytest
  tests/unit/api/test_allowed_actions_adversarial.py -n 0 --no-cov -p no:randomly`, and records
  wall time and maximum RSS in `evidence/timing.md`; more than 10 % slower goes to the developer
  (RISK-3).
- [ ] 1.3 PD-4, unit (parallel with 1.1 and 1.2). Red, in the module itself:
  `test_the_module_runs_at_the_default_recursion_limit` sets `sys.setrecursionlimit(20000)`,
  enters `with default_recursion_limit_pinned():`, asserts the limit is `DEFAULT_RECURSION_LIMIT`
  inside, and asserts 20000 is restored after the block (the context manager, not the fixture,
  which pytest forbids calling directly). The planted
  check: with the autouse removed, running the parser-depth test after
  `sys.setrecursionlimit(20000)` makes it fail (seen once, then reverted).

## 2. The seed spike

- [ ] 2.1 **Lead**, PD-6 (parallel with 1.1 to 1.3; it touches no file they touch). In a
  throwaway worktree, the three runs on `tests/unit/schema/` and one feature folder, through the
  queue; `evidence/seed-spike.md` records commands, times, coverage totals, the selected test ids
  for the three sample changes, and the verdict against PD-6's three pass criteria. Timebox: half
  a day.
- [ ] 2.2 PD-6, after 2.1. **Pass:** a builder makes PD-6's *mechanism under test* the
  `Makefile`'s local `test` recipe, its command held in a variable `RECORD_SEED` (empty under
  `CI`). Red first, in `tests/unit/tooling/test_lanes.py`. Never `make -n test`: its recipe holds
  `$(MAKE)`, which GNU make runs even under `-n`, so it would start a real seed. Instead, print
  the variable with `make --no-print-directory --eval='print-%: ; @echo $($*)' print-RECORD_SEED`
  (a probe target added on the command line, running nothing else): with `CI` unset `RECORD_SEED` names `selection_data seed` once,
  with `TEST_QUEUE=off`, `RECORD_SELECTION=1` and `TESTMON_DATAFILE=.testmondata.seed`; with
  `CI=1` it is empty. `make -n test-unit RECORD_SELECTION=1` (no `$(MAKE)` in that recipe, so it
  only prints) carries `--testmon --testmon-forceselect -p no:randomly`; a lone
  `make -n test-unit` carries none of them.
  The lead keeps the drafted `rp-developer-checks` delta and writes the docs
  (`develop/testing.adoc#test-control`, `develop/agents.adoc` tools table, `AGENTS.md` test
  control: no seed after a passed `check-all` on the same commit). **Fail:** the lead deletes
  `specs/rp-developer-checks/` from this change and writes the one paragraph in
  `develop/testing.adoc#test-control`. Either way `make check-docs`.

## 4. The seed's commit (DEC-7)

- [ ] 4.1 PD-8 recording, unit (parallel with 1.1 to 1.3). `selection_data.py`: `SEED_COMMIT`,
  `seed()` reads the sha before the run, `swap(..., commit=...)` writes or deletes the file under
  its lock. Red, in `tests/unit/testkit/test_selection_data.py`: design.md's five cases of *The
  seed's commit* as one parametrized table over a temporary git repository (`git init`, one
  commit; the non-git case uses a plain `tmp_path`) with a fake `run` that writes
  `.testmondata.seed` and exits as the case says; git itself runs for real, outside the seam.
- [ ] 4.2 PD-8 reading and use, unit (after 4.1's commit, since it imports `SEED_COMMIT`).
  `changed_tests.py`: `seed_commit`, `changed_since`, `select`/`plan`'s `since_seed`, `main`
  taking the check and the commit under one shared lock, `__all__`. Red, in
  `tests/unit/testkit/test_changed_tests.py`: design.md's eight `plan` cases as one table with a
  stub classifier; `seed_commit` on a missing, empty, garbage, upper-case and valid file; one
  `main` test in a temporary git repository: commit a `Makefile` and `src/x.py` on `develop`,
  branch off, commit a `Makefile` change on the branch, write that commit's sha to
  `.testmondata.commit`, then change `src/x.py`; `monkeypatch.chdir` into the repository,
  `monkeypatch.setenv("BASE", "develop")`, a stub classifier with `Makefile` as a fallback path,
  `data_state` returning `SOUND`, a recording `run` and a null `lock`; assert exit 0, one
  testmon run and the hint `Makefile: unchanged since the seed`; the same with a further
  `Makefile` change after the recorded commit asserts `FALLBACK_EXIT`. In
  `tests/unit/tooling/test_changed.py`: this repository's classifier through `plan` with
  `changed = ["Makefile", "rdf_persistence/model/x.yaml"]` and
  `since_seed = ["rdf_persistence/model/x.yaml"]`: falls back for the schema only, hints for
  `Makefile`. Guard: `tests/unit/testkit/` and `tests/unit/tooling/` whole.
- [ ] 4.3 **Lead**, after 4.2: the docs. User manual *Test control for your project* (what the seed
  records and when a shared file no longer falls back), `develop/testing.adoc#test-control` (the
  same, one paragraph, and the hint text), CHANGELOG `Added`; the `rp-testkit` delta is already in
  this change. `make check-docs`.

## 3. Close

- [ ] 3.1 The lead's `make check-all`, the PR, the merge (review set per
  `develop/agents.adoc#challenge`, MEDIUM in one stage: one L2+L3 pass and the full review, both
  on the same PR, P-0005; the fixes in one pass). The stage report lists every full test run
  with who read its result (PD-7).
- [ ] 3.2 **Lead.** PD-5, once the sessions that were paused on 2026-11-25 (the rdf-persistence
  sessions waiting for #394) run on `develop` after #394's merge: the DEC-8 measurement in
  `evidence/measure.md`, with PD-5's filters and formulas; a missed target goes to the developer.
- [ ] 3.3 Archive the change (`spec-stewardship`).

## Roadmap

- [ ] 1.1 · [ ] 1.2 · [ ] 1.3 · [ ] 2.1 · [ ] 4.1 · [ ] 4.2 · [ ] 2.2 · [ ] 4.3 · [ ] 3.1 · [ ] 3.2 · [ ] 3.3

1.1, 1.2, 1.3, 2.1 and 4.1 run in parallel; only 1.2's edit to `rdf_persistence/testkit/memory.py`
waits for 1.1's commit on the branch, 4.2 waits for 4.1, 2.2 waits for 2.1's verdict (on a pass,
its `Makefile` change swaps through `selection_data seed`, so it records the commit too), 4.3 waits
for 4.2. Section 4 (added 2026-11-26) keeps its number so the close stays section 3, as design.md cites it;
it sits and runs before the close.

## Verification

`make check-all`; `openspec validate test-memory-followups --strict`; `evidence/timing.md`,
`evidence/measure.md`, `evidence/seed-spike.md`.
