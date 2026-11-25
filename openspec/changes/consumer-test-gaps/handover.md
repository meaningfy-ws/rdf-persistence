# Hand-over: consumer-test-gaps, after stage 2

## Done
Stage 2 (API: `referrer_rp_path` and `referrer_id` on `Referrer`), PR #360 (merged on a passing
local `make check-all`, P-0021, after this note). Stage 1 is PR #355.

## Decided since the PLAN
D-9 to D-14 (design.md, Delivery decisions).

## Open
Stage 3 is built and committed in `.worktrees/ctg-3` (D-9). It still needs its rebase, gates,
review pass and PR. Follow-ups, not this EPIC:
- The scenario map lacks rows for 84 tests that predate this change (D-10).
- `located` takes the path from the class, not from the IRI, so the class path can differ from the
  path inside the IRI (stage-2 review S3).

## Next
Stage 3, task 3.5 (gates, review and PR of `fix/narrowed-cardinality`). Read first: tasks.md §3,
design.md D-7 and D-8, specs/rp-uml-import.

## Prompt
Act as the team lead. Deliver stage 3 of openspec/changes/consumer-test-gaps from handover.md.
