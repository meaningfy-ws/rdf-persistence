EPIC: test-memory-followups (proposal.md). Decisions: proposal.md DEC-1 to DEC-4; design.md PD-1 to PD-5.

> Derives from: the EPIC `test-memory-followups`.

Every task: its **Red** test is written first and seen failing. Task gate
`make test-changed check-quality`; the lead seeds at stage start (`make test-seed`) and runs
`make check-all` once before the PR. One stage, branch `change/test-memory-followups` off
`develop`, one PR. Commit body `Refs: test-memory-followups <task> <PD>`.

## 1. The fixes

- [ ] 1.1 PD-1, unit. `auth.py`, `sse.py`. Red: `tests/unit/api/test_service_release.py::
  test_a_dropped_service_is_freed_without_clearing_typing`: build three `ToyService()`, drop them,
  clear only the `SchemaView` and FastAPI caches (the testkit's helpers, `typing` left alone),
  `gc.collect()`, assert no `ServiceKit` is alive (count before and after). Guard:
  `tests/unit/api/test_openapi.py`, the served-golden test, `tests/unit/api/` whole.
- [ ] 1.2 PD-2, PD-3, unit (parallel with 1.1). `service_view` and `kit.py`. Red, in
  `tests/unit/schema/test_service_view.py`: the four worked examples of design.md as one
  parametrized table plus the concurrent case (two threads, one load); in
  `tests/unit/api/test_service_view_guard.py`: PD-3's guard. Guard: `tests/unit/api/` whole,
  `tests/feature/`. Then the **Lead** times `tests/unit/api/test_allowed_actions_adversarial.py` on
  one process before and after (RISK-3), through the queue, and records it in
  `evidence/timing.md`.
- [ ] 1.3 PD-4, unit (parallel with 1.1 and 1.2). Red: a test in the same module raises the limit
  to 20000 in a fixture applied before the parser-depth test's own, and the parser-depth test
  still passes; seen failing with the pin removed (planted, then reverted).

## 2. Close

- [ ] 2.1 The lead's `make check-all`, the PR, the merge (review set per
  `develop/agents.adoc#challenge`, SMALL: one pass).
- [ ] 2.2 **Lead.** PD-5, after the paused sessions run on #394's code: the DEC-8 measurement in
  `evidence/measure.md`; a missed target goes to the developer.
- [ ] 2.3 Archive the change (`spec-stewardship`).

## Roadmap

- [ ] 1.1 · [ ] 1.2 · [ ] 1.3 · [ ] 2.1 · [ ] 2.2 · [ ] 2.3

1.1, 1.2 and 1.3 touch different files and run in parallel.

## Verification

`make check-all`; `openspec validate test-memory-followups --strict`; `evidence/timing.md`,
`evidence/measure.md`.
