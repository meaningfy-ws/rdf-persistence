# Clarity gate: uml-roles-and-workflows PLAN

EPIC readiness check (lightweight), 2026-11-21, planner: pass (appetite, DEC-1 to DEC-8, rabbit-holes,
no-gos present; the owner answered one round, inputs/qa.md; probe in inputs/probe.md).

run 1, 2026-11-21, 8.0/10, fresh reviewer (attack + gate, against the code and the real model), fail
run 2, 2026-11-21, 9.0/10, fresh reviewer (run 1's gaps only), pass

Run 1 attack, nine counterexamples, all folded into the PLAN: a class's `workflow` tag checked only
when a Statechart diagram is converted, so models that convert today still do (PD-5; the owner may
overrule this reading of DEC-3); stale files reported only when that kind is drawn, moved file by
file into `workflows/` (PD-4, PD-6); the columns and tables needed to refuse names, guards,
triggers, substates and state behaviours (PD-1); empty `actions` refused (PD-3); two diagrams with
one name (PD-5); the exact `safe_dump` call, the example regenerated from it and checked byte for
byte (PD-6); the data path through `convert`, `write` and `cli.py` (PD-8); IRI stability on a
diagram rename (RISK-2).

Run 2 found five small defects (a stale `safe_dump` line in PD-3, F-1 on `Stereotype`, the tasks
header, a mutable default, the stale roles-file glob); all fixed after the run.

Scenarios (specs/rp-uml-import/spec.md, the design's error matrix, tasks 1.4 and 2.4): sign-off by
the owner pending.
