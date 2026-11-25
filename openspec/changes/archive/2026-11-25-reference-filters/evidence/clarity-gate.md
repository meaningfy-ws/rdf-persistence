# Clarity gate: reference-filters

Gated by a fresh reviewer who did not write the PLAN, after an attack against the code (the D-2
query shape was run on rdflib: S1, S4 and S10 hold).

run 1, 2026-11-24, 8/10, fail (fresh reviewer, attack + gate; 12 counterexamples: S2 impossible under the ISBN key, `_hop` accepting the tenant root and non-root classes, no OpenAPI description plumbing, hops miscounted and no 3-hop test, `hidden` consumed once, S4 fixture, E7 rationale, `skos:prefLabel` not `rdfs:label`, E11 construction and message, E9 check order, E14 too narrow, spec wider than DEC-5)
run 2, 2026-11-24, 9/10, pass (same reviewer, gaps-only re-gate; 11 closed, S4 set-up partly; three small defects (S4 author helper, E16 non-root case, a stale S3 reference in RISK-2) fixed after the run, R-0005)

No accepted gaps. Scenarios: `specs/*/spec.md` and the design's error matrix; the owner signs them off with the PR.
