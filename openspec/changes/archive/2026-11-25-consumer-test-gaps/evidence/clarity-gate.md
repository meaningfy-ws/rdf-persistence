# Clarity gate: consumer-test-gaps

Gate by a fresh reviewer who did not write the PLAN, after an attack against the code at `1f2687bc`.

run 1, 2026-11-24, 8.45/10, fail (fresh reviewer, attack + gate; 9 counterexamples, 11 gaps: `Event` release order lets the last caller write first, ancestor bound read from the stored not the derived maximum, wrong problem slug, the toy client skips the lifespan, exit with waiters unspecified, E1's pending activity could be relayed before the block, `parents` key type, 0..0, open options in D-6/D-7, no anti-pattern table, line drift)
run 2, 2026-11-24, 9.2/10, pass (same reviewer, gaps-only re-gate; 11 closed; one new gap, the lineage map missing a class without attributes, plus E4b's cancellation nuance and the spec wording, all folded in after the run: D-8, E23, E4b, `specs/rp-uml-import`)

No accepted gaps. Scenarios: `specs/*/spec.md` and the `design.md` error matrix (E1 to E23); the owner signs them off with the PR.
