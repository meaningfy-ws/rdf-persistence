# Clarity gate: slot-uri-clash PLAN

EPIC readiness check (lightweight), 2026-11-25: pass. Appetite, why, outline, DEC-1 to DEC-4,
rabbit-holes and no-gos present; no key decision open.

Attack (lead, step 7), counterexamples folded in:
- a toolkit pair reported by every consumer target → PD-3;
- #278's same-name case reported twice → PD-2 (distinct names only);
- a module without a default prefix expanding a junk IRI → error-matrix row, no false clash;
- toolkit schemas clashing today → re-probed: the 30 toolkit schemas have none;
- the UML golden stages → stage 1 none, stage 2 only the exempt pair;
- test schemas written inline → RISK-3.

run 1, 2026-11-25, 9.2/10, pass (lead self-score, TINY)

Scores (6-criterion rubric): actionability 9.5 (one task names its first failing rows, files and
functions), specificity 9 (rule value, message, order, element fixed; the fault anchors are left to
the builder, who must read the fixture), consistency 9.5 (DEC↔PD↔spec scenarios agree; scenario 2
proved by an existing test, named), structure 9, disambiguation 9 (exemption by `identifier: true`,
grouping by distinct names, reporting by own schemas), reference clarity 9 (paths and symbols;
`generation.adoc` cited by line, to be checked by the builder).

run 2, 2026-11-25, 8.85/10, fail (fresh reviewer; 5 gaps: two scenarios only partly tested,
fault anchors left to the builder, the `Fault` field names, missing deep links, the CHANGELOG
section)

All five gaps fixed in the PLAN; no third run (the cap is two). Accepted by the owner: D-2
(design.md), with D-1 for the CHANGELOG section.

Scenarios: signed off by the owner, 2026-11-25.
