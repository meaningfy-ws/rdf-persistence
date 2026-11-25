# Clarity gate: activity-iri-policy PLAN

EPIC readiness (lightweight), 2026-11-22: pass. Problem, appetite, DEC-1 to DEC-6 and no-gos
stated; OPEN-1 to OPEN-4 recorded with recommendations (`inputs/qa.md`).

Adversarial attack (planner, before the gate), folded in: the default aggregate template's
`{rp_path}` reads any segment, so `{tenant}/activity/{id}` read as an aggregate (DEC-4 reshaped,
PD-3b, PD-3c); `{base}{tenant_segment}/{id}` reads as a tenant under UUID tenant ids (PD-3a); a
`Served` reused after a refused-before-send commit in another tenant (PD-5: no mutation); a later
command or aggregate holding the provisional id (RISK-2); a flat part type equal to the activity
segment (RISK-6); `is_loaded_graph(None, …)` (PD-2 takes `None`); no Fuseki proof of the taken-IRI
guard under the policy (task 1.7a).

run 1, 2026-11-22, 9.0/10, pass (planner self-score; a fresh reviewer gates later). Weakest
criterion: specificity of task 1.3's adversarial rows and of 1.7's feature steps (Gherkin still to
be written and signed off).

run 2, 2026-11-22, 8.6/10, fail (fresh reviewer; 5 gaps)

run 3, 2026-11-22, 8.8/10, pass (fresh reviewer, gaps-only re-gate; 2 gaps)
Accepted at 8.8 under R-0005; two small gaps folded in after the run (PD-2 tenant_id resolution, 1.3 row list).

Re-plan on develop 12d84873, 2026-11-25. The five run-2 gaps (from the reviewer's report: the
`{tenant_segment}` row, the tenant-less template, eager placement in PD-5, the part ordering in
PD-5, the `Served` docstring) checked closed in the text. Drift: `Iris.aggregate_id_of` joins PD-3b.
Adversarial attack (fresh subagent), folded in: `is_activity` compiled with `application=True`
(PD-2); PD-3a made syntactic, the default skipped (a random probe refused at random), glued
templates refused at build, and the schema-free `{tenant}/{id}` clash caught in every `Iris`
(PD-3a (iii), (iv)); `Session.activity_iri` checks the tenant first (PD-6); two tests that could
not fail first rewritten (1.2, 1.6); RISK-7 (bare `Tenancy` skips PD-3c), RISK-8 (rewrite of a
UUID group equal to the old tenant id). The owner asked for ≥ 9 on this PLAN, so R-0005's 8.8 is
not used.

run 4, 2026-11-25, 8.9/10, fail (fresh reviewer, full gate on develop 12d84873)
run 5, 2026-11-25, 9.2/10, pass (same reviewer, gaps-only re-gate)
