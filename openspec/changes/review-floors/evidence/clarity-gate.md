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

## Re-plan of 2026-11-25

Rebased on `develop` 12d84873 (248 commits). Re-triage: no item fixed (`inputs/triage.md`,
last section); line references refreshed. Round 2 with the owner: OPEN-1 to OPEN-9 accepted;
#272 (all six), #273, #275 folded in (DEC-6, PD-17 to PD-22, tasks 1.9-1.11, 3.8-3.10). The
owner asked for a gate ≥ 9 this time (R-0005's acceptance below 9 not applied).

Attack of the PLAN (fresh reviewer, 2026-11-25), folded in: PD-8 would have bypassed the
`METAMODEL_DIR` seam two `# X1` tests use (now `METAMODEL_DIR = vocabulary.METAMODEL.parent`);
PD-20 judged the wrong line of a multi-line call (now first or last, via `tokenize`; instances
out of scope); PD-6's `None` default clashed with `None` as an answer (now a sentinel); PD-17's
`TIMEOUT`/`BIBO`/`TITLE` values and types undecided (now stated, four exceptions listed); task
1.11's guard pattern and the local integration/perf lanes; `BOOK_JSON`'s rewrite forms; 3.8's
process-wide warm-up state (fresh content per test); PD-18's three missed references; rule 11
exceptions for PD-13 and 3.1 recorded; nits (DEC-6, ten readers, yaml `:210`, `async`, RISK order).

run 5, 2026-11-25, 8.6/10, fail (fresh reviewer; actionability 8.5, specificity 8.5, consistency
8.0, structure 9.5, disambiguation 8.5, reference clarity 9.0). Gaps: the findings above.
run 6, 2026-11-25, 9.4/10, pass (same fresh reviewer, gaps-only re-gate; actionability 9.5,
specificity 9.5, consistency 9.0, structure 9.5, disambiguation 9.5, reference clarity 9.5).
Two nits folded in after the run: `test_changed.py:58`'s rule-5 example (`tests/e2e/world.py`),
the `BOOK_JSON` use count (33).

The owner signs off the two spec-delta scenarios (`rp-generation`, `rp-testkit`) at the PR.

EPIC readiness check (lightweight), 2026-11-25, after the fold-in: pass. Every template
section is present. The Why and the solution outline now name the ten issues and their stages.
Every key decision has a `DEC-` id (DEC-6 added); DEC-5 now follows the merge rules in force
(P-0013, P-0021). The no-gos name #371 and #372 as `consumer-friction`'s. The only item whose
DEC-1 status was unsettled, 272-c, is decided by DEC-6.
