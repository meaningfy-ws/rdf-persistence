# Clarity gate: test-debt-paydown PLAN

run 1, 2026-11-17, 8.4/10, fail (10 gaps, all fixed; plus 13 fixes from the adversarial review)
run 2, 2026-11-17, 9.2/10, pass (5 one-line consistency fixes applied after the run)

2026-11-20, no run: the gate is void. The thematic restructure left the PLAN's paths stale, and
the owner deferred the re-plan and a full re-gate until wave 2 merges (`inputs/handover.md`).

Re-plan (develop 030f580f; wave 2 merged):
run 1, 2026-11-21, 8.9/10, fail (10 gaps, all fixed; plus 21 fixes from the adversarial attack,
4 of them blockers). Not re-run: accepted as DEC-5 (design.md) under R-0005.

Scenarios signed off by the owner, 2026-11-17 ("signed off"); CI wait kept ("keep CI wait").
