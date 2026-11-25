# Clarity gate: consumer-friction PLAN

EPIC readiness check (lightweight), 2026-11-25, planner: pass. Appetite, why, outline, DEC-1 to
DEC-6, rabbit-holes and no-gos are present, and no key decision is open (the owner answered one round,
`inputs/qa.md`).

Attack and gate by a fresh reviewer (subagent), 2026-11-25. These counterexamples were folded into the PLAN:
- `make generate` cannot leave the toolkit's trees untouched, because every generator file and template is
  a manifest input → RISK-3 and the task 1.1 Accept allow the `rp-manifest.json` hashes and the
  `rp_generation` artefacts to change; 1.1 commits the two toy manifests;
- freshness does not see a change to the owner's `typescript` (`pyproject.toml` is not an input) →
  error-matrix row, accepted (`make check-generated` catches it);
- the description edit would land on the shared slot `module` → PD-4 puts it on `TsImport`'s
  `slot_usage`;
- the root-without-package row mis-cited `generated_schemas` → the row states the difference;
- the time of the specifier rewrite was not stated → PD-3 sets the order (drop, rewrite, then
  `_with_served`) and PD-4 sets the sort order;
- TC-2 needs one run per target → stated;
- TC-6 had no fixed tier → generator integration;
- TC-3's failure modes were not stated → `TS2307`/`TS2305`, Node needed.

run 1, 2026-11-25, 8.7/10, fail (fresh reviewer; the 7 gaps above)
run 2, 2026-11-25, 9.3/10, pass (same reviewer, gaps only; actionability 9.5, specificity 9,
consistency 9.5, structure 9.5, disambiguation 9, reference clarity 9)

Nits from run 2: the anti-pattern's wording about `generated_schemas` was fixed. The lead must
confirm the CI "types" job (TC-3, needs Node) is green before the merge, because the local task gate
may skip it.

Scenarios: signed off by the owner, 2026-11-25 (spec scenarios 1 to 4, design.md TC-1 to TC-8).
