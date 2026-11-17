# Hand-over: manual-revision-notes, after stage 1

## Done
Stage 1 (defects, tasks 1.1–1.6), PR #141 (merged by the watch-and-merge command after this note).
It unblocks `technical-models` (A-3/A-4, `jwks.py`) and `otel-observability` (A-7). The EPIC is
reconciled for stage 1 (proposal.md "As built"); stages 2 and 3 add their rows.

## Decided since the PLAN
D-1 to D-7 (agreed by the developer), F-1, F-2, and the stage 1 findings under the floor
(design.md, Delivery decisions).

## Open
- The full review (L1, L2, L3, L4+L5) runs once after stage 3 (D-1, P-0005); it weighs the findings
  under the floor, first the `RpModel.replaced` naming (L3 W1).
- #142: `test_heads_of_hundreds_of_iris_is_one_query` is quarantined (CI timeout, D-7); task 2.5's
  pyoxigraph `FakeStore` may make it fast enough to lift the quarantine.
- Fresh worktrees need `make install` (all extras) before a builder's gate, or `tests/unit/generation`
  and mypy fail on missing extras.
- GitNexus `analyze` must run outside the sandbox (`~/.gitnexus` is not writable inside it).

## Next
Stage 2, task 2.1. Read first: tasks.md §Stage 2, design.md PD-5, PD-6, PD-10, PD-11, PD-13 and the
stage 1 findings, `inputs/keep.md`. The tester runs after task 2.5.

## Prompt
Act as the team lead (epic-delivery). Deliver stage 2 of openspec/changes/manual-revision-notes
from handover.md: one PR into develop from branch change/manual-revision-notes-s2.
