EPIC: flaky-worker-count-test (proposal.md, #432). Decisions: DEC-1, design.md PD-1.

## 1. One stage — branch `change/flaky-worker-count-test`, one PR

- [x] 1.1 **unit: the test** — PD-1, TC-1, TC-2. Rewrite
  `test_on_ci_pytest_runs_unqueued_with_the_workers_counted_by_make` in
  `tests/unit/tooling/test_lanes.py`. Accept: it passes; the TC-2 mutation makes it fail; task gate
  green.
- [x] 1.2 **lead** (PR #436, merged as 72d50540; #432 closed) — `make check-all`; one review pass (TINY); PR into `develop` naming #432; merged
  on green CI; #432 closed; archive.

## Roadmap

- [x] 1.1 · [x] 1.2

## Verification

The test passes alone and inside `make check-all`; `make check-quality` green.
