# Hand-over: aggregate-composition, after stage 3

## Done
Stage 1, PR #448; stage 2, PR #449 (both merged). Stage 3 (conventions page, guide, questions, the
adopted rules P-0025 to P-0040, the changelog), this PR (merged by the watch-and-merge command after
this note). Every build task is ticked.

## Decided since the PLAN
D-1 to D-16 (design.md, Delivery decisions); DEC-4 re-shaped and DEC-2 amended (inputs/qa.md).

## Open
- Acceptance is deferred to the developer (`evidence/acceptance.md`): the scenarios, the EPIC
  changes, D-1 to D-16, the rules P-0025 to P-0040, and RISK-9's EA probe. No release before that.
- Under the floor: D-13 (S5 to S7) and D-15 (S3 to S6).
- The first consumer may retire its copies of the rules and its check script once this is released
  (RISK-3); #437 is told.
- After acceptance: archive the change (`openspec archive aggregate-composition --yes`), per
  spec-stewardship.

## Next
Acceptance by the developer, then the archive. Read first: evidence/acceptance.md.

## Prompt
Act as the team lead. Run the acceptance of openspec/changes/aggregate-composition with me from
evidence/acceptance.md, then archive it.
