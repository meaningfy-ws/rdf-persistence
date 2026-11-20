# Clarity gate: listing-contains-filter PLAN

run 1, 2026-11-20, 9.1/10, self-score (planner), pass

Rubric: actionability 9.5, specificity 9, consistency 9, structure 9.5, disambiguation 9,
reference clarity 8.5 (weakest: line references cite 4e8d1fe2 and drift as the code moves).

Attack (step 7), each counterexample and where it went:
- a multivalued slot with two matching values duplicates the row and shifts the page → PD-5
  (`FILTER EXISTS`), TC-05 row `authors~=E&limit=2`, error-matrix row.
- `EXISTS` read outside the active graph on Fuseki → RISK-2, IT-1.
- a contains condition rendered as equality by `matches` or the commit guard → PD-6, TC-08, RISK-4.
- empty text lists everything → PD-4, OPEN-1.
- `sort~`, `~`, `label~~` names → PD-1, error-matrix row.
- acceptance tests left failing across tasks would break each task gate → TC-09 moved into 1.3.

Open for the owner: OPEN-1, OPEN-2, OPEN-3 (design.md, Open Questions). Scenarios not yet signed off.

run 2 accepted at 8.8 under R-0005; gaps folded 2026-11-20
(fresh reviewer's score; owner answers in `inputs/qa.md`, PD-7, PD-10, PD-11, PD-12)
run 2, 2026-11-20, 8.8/10, fresh reviewer, fail

**Status: accepted at 8.8 under R-0005 (owner's rule: 8.8 is good enough, gaps folded, no re-run).
Ready for an epic session.**
