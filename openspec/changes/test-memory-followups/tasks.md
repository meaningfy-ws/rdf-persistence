EPIC: test-memory-followups (proposal.md). Decisions: proposal.md DEC-1 to DEC-6; design.md PD-1 to PD-7.

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
  the queue: `TEST_QUEUE_LABEL=timing uv run python -m tests.queue -- /usr/bin/time -v pytest
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
- [ ] 2.2 PD-6, after 2.1. **Pass:** a builder makes the `Makefile` change (Red first: a test in
  `tests/unit/tooling/` that `make -n test-unit` under `test` carries `--testmon` and a lone
  `make -n test-unit` does not), the lead writes the `rp-developer-checks` delta and the docs
  (`develop/testing.adoc#test-control`, `develop/agents.adoc` tools table, `AGENTS.md` test
  control: no seed after a passed `check-all` on the same commit). **Fail:** the lead writes the
  one paragraph in `develop/testing.adoc#test-control`. Either way `make check-docs`.

## 3. Close

- [ ] 3.1 The lead's `make check-all`, the PR, the merge (review set per
  `develop/agents.adoc#challenge`, SMALL: one pass). The stage report lists every full test run
  with who read its result (PD-7).
- [ ] 3.2 **Lead.** PD-5, once the sessions that were paused on 2026-11-25 (the rdf-persistence
  sessions waiting for #394) run on `develop` after #394's merge: the DEC-8 measurement in
  `evidence/measure.md`, with PD-5's filters and formulas; a missed target goes to the developer.
- [ ] 3.3 Archive the change (`spec-stewardship`).

## Roadmap

- [ ] 1.1 · [ ] 1.2 · [ ] 1.3 · [ ] 2.1 · [ ] 2.2 · [ ] 3.1 · [ ] 3.2 · [ ] 3.3

1.1, 1.2, 1.3 and 2.1 run in parallel; only 1.2's edit to `rdf_persistence/testkit/memory.py` waits
for 1.1's commit on the branch, and 2.2 waits for 2.1's verdict.

## Verification

`make check-all`; `openspec validate test-memory-followups --strict`; `evidence/timing.md`,
`evidence/measure.md`, `evidence/seed-spike.md`.
