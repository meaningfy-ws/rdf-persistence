EPIC: flaky-worker-count-test (proposal.md, #432). Decisions: DEC-1, design.md PD-1.

## 1. One stage — branch `change/flaky-worker-count-test`, one PR

- [ ] 1.1 **unit: the test** — PD-1, TC-1, TC-2. Rewrite
  `test_on_ci_pytest_runs_unqueued_with_the_workers_counted_by_make` in
  `tests/unit/tooling/test_lanes.py`. Accept: it passes; the TC-2 mutation makes it fail; task gate
  green.
- [ ] 1.2 **lead** — `make check-all`; one review pass (TINY); PR into `develop` naming #432; merged
  on green CI; #432 closed; archive.

## Roadmap

- [ ] 1.1 · [ ] 1.2

## Verification

The test passes alone and inside `make check-all`; `make check-quality` green.
