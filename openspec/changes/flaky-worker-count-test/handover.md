# Hand-over: flaky-worker-count-test, after stage 1

## Done
Stage 1, task 1.1 (98e1670a): the test reads the worker count once, from `PARALLEL`. TC-2 probe:
with `PYTEST_N=""` make prints `-n auto --dist loadgroup` and the test fails with "make did not
count the workers". `make check-all` green at 98e1670a (1090 s; unit 8653 passed, feature 102,
generator 1837).

## Decided since the PLAN
none.

## Open
none.

## Next
1.2, the close: one review pass, merge on green CI, close #432, archive.

## Prompt
Act as the team lead. Close openspec/changes/flaky-worker-count-test from handover.md.
