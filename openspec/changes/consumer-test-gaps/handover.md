# Hand-over: consumer-test-gaps, after stage 1

## Done
Stage 1 (testkit: `FakeStore.hold`, the `relay.paused()` docs and feature test), PR #355 (merged
on a passing local `make check-all`, P-0021, after this note).

## Decided since the PLAN
D-9, D-10, D-11, D-12 (design.md, Delivery decisions).

## Open
Stages 2 and 3 are already built in `.worktrees/ctg-2` and `.worktrees/ctg-3` (D-9); each still
needs its review pass, fix pass, gates and PR, in that order. The scenario map lacks rows for 84
tests that predate this change (D-10): a follow-up, not this EPIC.

## Next
Stage 2, task 2.5 (review and PR of `feat/referrer-location`). Read first: tasks.md §2,
design.md D-4 to D-6, specs/rp-service-api.

## Prompt
Act as the team lead. Deliver stage 2 of openspec/changes/consumer-test-gaps from handover.md.
