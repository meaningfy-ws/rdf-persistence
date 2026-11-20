# Clarity gate: uml-to-linkml PLAN

run 1, 2026-11-20, 9.0/10, self-score (planner), pass

| Criterion | Weight | Score | Note |
|---|---|---|---|
| Actionability | 25 % | 9 | Every PD names its module, rule and test; the spikes have pass/fail criteria |
| Specificity | 20 % | 9 | Exact maps (XSD, multiplicity, plural, names), exact messages for every error row; the `no_rule` message is a template whose "<what it is>" part is left to the builder |
| Consistency | 15 % | 8.5 | The spec delta's activity-root scenario contradicts the existing `rp-generation` toolkit-filled requirement; PLAN follows OPEN-1's default until the owner approves the amended scenario (task 2.6) |
| Structure | 15 % | 9.5 | Rule table, PD list, test table, error matrix, roadmap |
| Disambiguation | 15 % | 9 | 10 anti-patterns; boundary edge cases (edge, straddle, twice placed, two diagrams, 0/2 roots) and nine OPENs with defaults |
| Reference clarity | 10 % | 8.5 | Code references are file + symbol (some with lines); no anchors into code files exist |

Attack (step 7) done by the planner, not a fresh subagent: 8 RISK entries and 5 matrix rows came
from it (cycles, missing notes, foreign parents, column drift, twice-placed class, home-module
imports, toolkit-filled narrowing, toy ripple). A fresh reviewer gates the PLAN next.

run 2 accepted at 8.8 under R-0005; gaps folded 2026-11-20; OPEN-1..9 decided by the owner (accept all)

Gaps folded: one rule name for boundary ambiguity (`no_rule`); the 24 `UmlRule` values listed
exactly (PD-2, task 1.1); module of the root package (`<root>_main`) and nested separator `__`
(PD-5); `--not-generated` in PD-1's command line; task 1.7 reordered (tests, `Review`, generate,
run); PD-20 renames only `_segment_pattern`. F-3: the reviewer asked to add `generated_at_time`
to the toolkit-filled slots; the metamodel does not annotate it (`rp_provenance.yaml`
`generated_at_time`), so F-3 now lists the eight annotated slots and says `generated_at_time` is
not one.
run 2, 2026-11-20, 8.8/10, fresh reviewer, fail

**Status: accepted at 8.8 under R-0005 (owner's rule: 8.8 is good enough, gaps folded, no re-run).
Ready for an epic session.**
