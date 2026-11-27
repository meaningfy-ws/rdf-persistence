<!-- Parents: issue #432; archive/2026-11-26-test-control-testkit PD-8 (PYTEST_N is lazy and
     quiet); found by typescript-toolkit-modules (D-8), whose post-rebase make check-all it failed. -->

# EPIC: the worker-count test reads the count once

## Appetite

**TINY.** One test in `tests/unit/tooling/test_lanes.py`. Test tooling only; no Makefile change.

## Why

`test_on_ci_pytest_runs_unqueued_with_the_workers_counted_by_make` failed once inside `make
check-all` (`-n 15` against `-n 16`) and passes alone. It asks make to print
`$(PYTEST_N)|$(PYTEST)|$(PARALLEL)`. `PYTEST_N` is a recursive variable whose value comes from
`run_queue --workers`, which counts workers from the memory free at that moment (PD-8 of
`test-control-testkit` keeps it lazy on purpose). The line expands it twice, once on its own and
once inside `PARALLEL`, so under the load of a full run the two counts can differ. A recipe expands
`PARALLEL` once, so the lanes themselves are not affected: the defect is in the test.

## Solution outline

The test prints `$(PYTEST)|$(PARALLEL)`, reads the count out of `PARALLEL` (`-n <k> --dist
loadgroup`) and checks it is a whole number within `1..workers(cpu_count, None, 1)`. The count is
computed once, so the assertion holds under any load, and it still proves that on CI the count
comes from make (an integer, not `auto` or `@workers`).

## Key decisions

- **DEC-1:** fix the test, not the Makefile. Reason: the Makefile expands the count once per
  recipe; the double expansion exists only in the test. Rejected: an eval-once idiom for
  `PYTEST_N` (`test_on_ci_the_worker_count_is_quiet_and_lazy` pins the exact `?= $(shell ...)`
  line, and nothing outside the test needs it); fixing `PYTEST_N` on the command line in the test
  (it would no longer test that make counts the workers).

## Rabbit-holes

None.

## No-gos

- Any change to the Makefile or to `run_queue`.
- Retries or a `flaky` marker.

---

## What Changes

- `tests/unit/tooling/test_lanes.py`: `test_on_ci_pytest_runs_unqueued_with_the_workers_counted_by_make`
  reads the worker count once.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `rp-developer-checks`: "The checks give the same answer on every run" gains the scenario "the
  worker count read under load".

## Impact

- Tests: one test in `tests/unit/tooling/test_lanes.py`. Code, docs: none.
