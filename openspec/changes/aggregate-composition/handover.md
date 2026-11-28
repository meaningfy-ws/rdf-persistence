# Hand-over: aggregate-composition, after stage 1

## Done
Stage 1 (compositions, derived roots, «own graph», pointers, Realisation), PR #448 (merged by the
watch-and-merge command after this note).

## Decided since the PLAN
D-1 to D-13 (design.md, Delivery decisions); DEC-4 re-shaped and DEC-2 amended (inputs/qa.md).

## Open
- The developer validates D-1 to D-13, the DEC-4 re-shape, the DEC-2 amendment and the scenarios
  (`evidence/scenario-signoff.md`).
- RISK-9: the developer's EA probe (`@manual` "An EA-drawn composition reads the same either way")
  before any release; the official Sparx docs refused automated fetches (`evidence/ea-connectors.md`).
- Under the floor (D-13): a doubled problem for a generalisation inside an own graph; constants
  re-declared in `aggregates.py`; `_Pass` to split before stage 2 adds passes; caching; an order
  test for `_adopt`. Stage 2 is the natural place for the first three.
- The two-roots boundary row lands in task 2.4 (A-23).
- `evidence/acceptance.md` is written after the last build stage (stage 3), with the demo or its
  skip.
- No release before stage 3 merges (PD-17). Task 1.12's comment on #343 and the note to the
  consumer (D-12 of AGENTS.md) are posted with this merge.

## Next
Stage 2, task 2.1. Read first: tasks.md §2, design.md PD-12, PD-13, PD-14, PD-15, D-7, D-13, the
C-1..C-12 classification, specs/rp-uml-import/spec.md (the `--check` requirement).

## Prompt
Act as the team lead. Deliver stage 2 of openspec/changes/aggregate-composition from handover.md.
