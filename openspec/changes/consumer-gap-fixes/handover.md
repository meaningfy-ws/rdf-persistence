# Hand-over: consumer-gap-fixes, after stage 3

## Done
Stage 1 (#304), PR #330. Stage 2 (#306), PR #335. Stage 3 (#311), this PR (merged by the
watch-and-merge command after this note).

## Decided since the PLAN
D-6, D-7, D-8 (design.md, Delivery decisions).

## Open
#332: narrowed minimum/maximum cardinality is still inherited (follow-up, outside the No-gos).
#331: generator e2e tests fail on develop (pre-existing; `make test-containers` is red there).

## Next
Stage 4 (#312), task 4.5: built on `fix/absent-filter`, reviewed; rebase, `make check-all`,
`make test-containers`, PR flagging DEC-5, merge. Then 5.2.
Read first: tasks.md §4, design.md D-1 to D-3, D-9, D-10.

## Prompt
Act as the team lead. Deliver stage 4 of openspec/changes/consumer-gap-fixes from handover.md.
