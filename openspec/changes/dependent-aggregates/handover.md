# Hand-over: dependent-aggregates, after stage 2

## Done
Stage 1, PR #446 (merged). Stage 2 (write guard and cascade delete), PR #450 (merged by the
watch-and-merge command after this note).

## Decided since the PLAN
D-1 to D-11 (design.md, Delivery decisions).

## Open
- The developer validates D-1 to D-11 and the scenarios (`evidence/scenario-signoff.md`).
- Under the floor (D-11): batch-mode rows untested (the mapper's); a `Cascade` helper out of
  `session.py`; `is_whole` per class in the OpenAPI build; the class the validators see for a doubly
  typed part.
- Stage 3 can start now: `aggregate-composition`'s converter is merged (PRs #448, #449, #451).

## Next
Stage 3, task 3.1. Read first: tasks.md §3, design.md PD-13, PD-17, the converter's
`uml/aggregates.py` refusal of a generated «own graph» part (aggregate-composition DEC-7).

## Prompt
Act as the team lead. Deliver stage 3 of openspec/changes/dependent-aggregates from handover.md.
