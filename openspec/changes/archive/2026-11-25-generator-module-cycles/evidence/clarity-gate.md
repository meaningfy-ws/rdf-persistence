# Clarity gate: generator-module-cycles PLAN

EPIC readiness check (lightweight), 2026-11-22: pass. Appetite, why, outline, DEC-1 to DEC-6,
rabbit-holes and no-gos present; the one undecided scope question (#206) is a no-go with OPEN-1.

run 1, 2026-11-22, 9.0/10, pass (planner self-score; a fresh reviewer gates later)

Scores (6-criterion rubric): actionability 9, specificity 9, consistency 9, structure 9,
disambiguation 9, reference clarity 8.5. Gaps fixed before logging: the "(if any)" row of PD-9
made a fact (no test imports `cycle_components`); PD-2 now leaves function bodies deferred
(attack counterexample: a validator naming a class of the cycle). Gaps left, below the bar:
docs targets in 1.5 and 2.5 name pages and anchors but not the exact paragraphs; RISK-1's
mitigation depends on the consumer running its model (OPEN-2).

Attack (planner, step 7), counterexamples folded in: a load cycle through `is_a` (PD-3, refusal,
test 1.4); a half-load cycle (loads; test 1.4); an imported name never used (F-2, deferred); a name
in a function body (PD-2); the root module in a cycle (error matrix); mypy's re-export rule against
attribute binding (PD-6, `setattr`); the aliased `TYPE_CHECKING` under mypy (probe, F-3); a cycle
between kinds after the merge goes (spec scenario, boundary check); two targets on one folder
(RISK-4); a LinkML template change (RISK-2); the converter's inheritance cycles (RISK-1, OPEN-2).

Scenarios: awaiting the owner's sign-off.

run 2, 2026-11-22, 8.7/10, fail (fresh reviewer; 7 gaps)

run 3, 2026-11-22, 9.1/10, pass (fresh reviewer, gaps-only re-gate; 0 gaps)
