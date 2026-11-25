EPIC: test-memory-followups (proposal.md). Decisions: proposal.md DEC-1 to DEC-4; design.md PD-1 to PD-5.

> Derives from: the EPIC `test-memory-followups`.

Every task: its **Red** test is written first and seen failing. Task gate
`make test-changed check-quality`; the lead seeds at stage start (`make test-seed`) and runs
`make check-all` once before the PR. One stage, branch `change/test-memory-followups` off
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
- [ ] 1.2 PD-2, PD-3, unit (parallel with 1.1; 1.1 and 1.2 both touch `memory.py`: 1.2 adds the
  `service_views` count to `release_memory` after 1.1 merges, or the lead merges them in order).
  `service_view`, `clear_service_views`, `kit.py`, `ServiceKit.view`'s docstring,
  `release_memory`. Red, in `tests/unit/schema/test_service_view.py`: the eight worked examples of
  design.md's *Algorithm / approach* as one parametrized table, plus the concurrent case (two
  threads started together on one file; `load_schema` counted by an injected loader, called once);
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
  drives the `default_recursion_limit` fixture's generator by hand (`next`), asserts the limit is
  `DEFAULT_RECURSION_LIMIT`, finishes the generator, and asserts 20000 is restored. The planted
  check: with the autouse removed, running the parser-depth test after
  `sys.setrecursionlimit(20000)` makes it fail (seen once, then reverted).

## 2. Close

- [ ] 2.1 The lead's `make check-all`, the PR, the merge (review set per
  `develop/agents.adoc#challenge`, SMALL: one pass).
- [ ] 2.2 **Lead.** PD-5, once the sessions that were paused on 2026-11-25 (the rdf-persistence
  sessions waiting for #394) run on `develop` after #394's merge: the DEC-8 measurement in
  `evidence/measure.md`, with PD-5's filters and formulas; a missed target goes to the developer.
- [ ] 2.3 Archive the change (`spec-stewardship`).

## Roadmap

- [ ] 1.1 · [ ] 1.2 · [ ] 1.3 · [ ] 2.1 · [ ] 2.2 · [ ] 2.3

1.1, 1.2 and 1.3 touch different files and run in parallel.

## Verification

`make check-all`; `openspec validate test-memory-followups --strict`; `evidence/timing.md`,
`evidence/measure.md`.
