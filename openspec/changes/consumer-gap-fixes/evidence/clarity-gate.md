# Clarity gate: consumer-gap-fixes

Gate by a fresh reviewer who did not write the PLAN, after an attack against the code.

run 1, 2026-11-24, 8.2/10, fail (fresh reviewer, attack + gate; 10 counterexamples, 7 gaps: `_flag` gives None not False, broader golden diff, `Tenancy` constructor and IRI rebind, refusal order, reserved-name effect, condition split and renderer, OpenAPI built at runtime, missing rows, named files, anchors)
run 2, 2026-11-24, 9.2/10, pass (same reviewer, gaps-only re-gate; 6 closed, 1 partly: D-n are bullets, cited by name not anchor; new error `with_iris(None)` fixed after the run in D-4 and task 2.2)

No accepted gaps. Scenarios: the four issues' Acceptance lists, carried into `specs/*/spec.md`; the owner signs them off with the PR.
