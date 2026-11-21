# Clarity gate: aggregate-validators PLAN

EPIC readiness check (lightweight), 2026-11-21, planner: pass (appetite, DEC-1 to DEC-5, rabbit-holes,
no-gos present; the owner answered one round, inputs/qa.md).

run 1, 2026-11-21, 8.1/10, fresh reviewer (attack + gate), fail
run 2, 2026-11-21, 8.9/10, fresh reviewer (run 1's gaps only), accepted under R-0005

Run 1 attack, twelve counterexamples, all folded into the PLAN: the tenant root is not in
`aggregate_roots` (PD-2, F-8); mixin and toolkit-class keys would run on the toolkit's writes (PD-2);
a root with several root types (PD-3); `from_graph` needs the graph IRI (PD-6); an `old` that no
longer decodes, a non-aggregate IRI, store errors and the unit-of-work visibility (error matrix,
PD-5, PD-7); `may_read` threaded through `DocumentApi`, `kit.collaboration` and the rename path,
with `Readable` rejected (PD-4); the reader moved to the collaboration layer (PD-1); a rule's name
for a partial (PD-7); the docs page named (task 1.7). Also corrected by the planner before the
attack: PD-9 (a stale PUT a rule refuses answers 422; the version is compared at commit).

Run 2 found four small gaps (the rename method's name, how a toolkit class is told apart, how the
stored class is chosen, a member removed earlier in the same unit of work); all four were folded in
without a third run (R-0005).

Scenarios (specs/rp-service-api/spec.md, design.md T-1 to T-11, A-1 to A-7): sign-off by the owner
pending.
