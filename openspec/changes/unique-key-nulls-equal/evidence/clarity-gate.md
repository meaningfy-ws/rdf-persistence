# Clarity gate: unique-key-nulls-equal (design.md + tasks.md)

run 1, 2026-11-20, 9/10, self-score (planner), pass

| Criterion (weight) | Score | Note |
|---|---|---|
| Actionability (25 %) | 9.5 | Each PD names the file, function and rendered pattern |
| Specificity (20 %) | 9 | Marker IRI, slot name and query text given; task 1.5 names its cases by error-matrix row, not by TC id |
| Consistency (15 %) | 9 | OPEN-1: the living `rp-generation` spec still says SHALL refuse until task 1.1 adds its delta |
| Structure (15 %) | 9.5 | Worked-example table, error matrix, one-stage roadmap |
| Disambiguation (15 %) | 9.5 | Six anti-patterns; blank node, `""`, marker-valued, every-slot-absent and multi-valued cases mapped |
| Reference clarity (10 %) | 8 | Weakest: docs and spec lines cited as `~216` / `~194`, not anchors |

Weighted: 9.2 → 9/10.

Attack (step 7), each folded in: blank-node value (PD-3 `!isBlank`, matrix row); application value
equal to the marker (PD-4); `""` versus absence (example, row); every slot absent (OPEN-3,
RISK-2); swap present/absent in one transaction (example); fake store versus Fuseki on nested
`NOT EXISTS` (RISK-1, task 1.6); query text of keys without the option (G-4, test in 1.5); living
spec contradiction (OPEN-1, task 1.1).

run 2 input: an independent gate scored 8.7/10, fail (2026-11-20). Its six gaps are fixed: MODIFIED
store and generation deltas (PD-9, task 1.1), the "without the option" scenario, PD-4/PD-4a
placement, PD-10's wording, symbol and anchor references. Owner answers in `inputs/qa.md`
(PD-9 to PD-11). Run 2 is the gate's to log.
run 2, 2026-11-20, 8.7/10, fresh reviewer, fail
run 3, 2026-11-20, 9.2/10, fresh reviewer (gaps only), pass
