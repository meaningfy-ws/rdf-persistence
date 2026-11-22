# Clarity gate: review-floors PLAN

EPIC readiness check (lightweight), 2026-11-22: pass. Appetite, why, no-gos and DEC-1 to DEC-5
present; every seed item classed in `inputs/triage.md`; each out-of-scope item has a home and an
OPEN question.

Attack of the PLAN (planner, before the gate), folded in: the collect-only proof of 1.4 collects
nothing before the move (replaced by `make refresh-map`); the wake test could pass on the relay's
first look (two commits, design.md error matrix); `relay_interval_seconds` has a real seam
(`ToyService(toolkit=...)`), no patch; two readers of `python_package` may disagree (error-matrix
row); parallel tasks editing one test file (roadmap sequenced); 2.1's "modules its target
generates" had no source (now `generated_schemas` via `read_targets`).

run 1, 2026-11-22, 8.8/10, fail (planner self-score). Scores: actionability 9, specificity 8,
consistency 9, structure 9, disambiguation 9, reference clarity 9. Gaps: 2.3's planted mutation
left to the builder; 3.7's "sample output" and "defined" undecided. Both fixed.
run 2, 2026-11-22, 9.1/10, pass (planner self-score, re-reading only run 1's gaps). Weakest:
specificity of the refactor tasks, whose proof is "Red: none (DEC-3)" plus named guard tests
rather than a red test of their own; accepted by design (DEC-3).

A fresh reviewer gates the PLAN before delivery; the owner signs off the two spec-delta scenarios
and answers OPEN-1 to OPEN-9 (`inputs/qa.md`).
run 3, 2026-11-22, 8.3/10, fail (fresh reviewer; 9 gaps)
run 4, 2026-11-22, 8.9/10, pass (fresh reviewer, gaps-only re-gate; 3 gaps)
Accepted at 8.9 under R-0005; three small slips folded in after the run (1.9 line, 235-m example, 2.3 test count).
