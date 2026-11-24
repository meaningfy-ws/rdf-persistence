# Hand-over: aggregate-guards, after stage 1

## Done
Stage 1 (#305, the reader hands over a referenced aggregate), PR feat/reader-aggregate (merged by
the watch-and-merge command after this note).

## Decided since the PLAN
D-9, D-10, D-11 (design.md, Delivery decisions).

## Open
- `make test-containers` fails 6 generator e2e tests and errors 1 router test on `develop` too
  (#331); the fix is its own PR, `fix/generator-e2e-331` (change `generator-e2e-fixtures`).
- Stage 2 is being built in `.worktrees/aggregate-guards-309` on top of this stage; it rebases on
  `develop` once this PR merges.

## Next
Stage 2, task 2.1. Read first: tasks.md §2, design.md D-5 to D-8, specs/rp-service-api.

## Prompt
Act as the team lead. Deliver stage 2 of openspec/changes/aggregate-guards from handover.md.
