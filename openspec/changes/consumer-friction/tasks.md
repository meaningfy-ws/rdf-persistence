EPIC: consumer-friction (proposal.md). Decisions: DEC-1 to DEC-6 (proposal), PD-1 to PD-8 (design.md).

> Derives from: EPIC `consumer-friction`. Issues #371, #372.

Every task: test-first; task gate `make test-changed check-quality`; commit body
`Refs: consumer-friction <task> <PD>` (`Refs: #371` / `Refs: #372` on the task that closes it).
Builders never commit; the lead does and ticks this file.

## 1. One stage — branch `change/consumer-friction`, one PR

- [x] 1.1 **unit + code (#371)** — design.md PD-1 to PD-6, spec scenarios 1, 2, 3.
  First failing tests, in `tests/generator/unit/test_typescript_imports.py` (new, beside
  `test_ext_typescript.py`): TC-1 (run `TYPESCRIPT_STEP` with `run_toy(..., target=<the technical
  target from read_targets(TOY / "pyproject.toml")>)` after PD-6's `pyproject.toml` edit), TC-4
  and TC-5 (`typescript.render(schema, folder=..., owners=...)` directly). Then PD-6's toy edit,
  `_typescript_owners` and `_write_typescript` in `steps.py`, the `folder`/`owners` parameters in
  `typescript.render` (drop, rewrite, then `_with_served`: PD-3), the template line, and
  `slot_usage.module.description` on `TsImport` in
  `rdf_persistence_generation/model/rp_generation.yaml` (not the shared slot: PD-4);
  `make generate`; commit the two new toy trees, their `rp-manifest.json` files and `TOY_TS`.
  Then TC-2 (two `run_toy` runs, one per new target, each with its own `assert_matches_toy`).
  Accept: the new tests pass; `test_ext_typescript.py` and `test_value_modules_toy.py` pass
  unchanged; `make typecheck-ts` green (TC-3); `make generate` changes nothing in the toolkit's
  trees beyond the `rp-manifest.json` input hashes and `rp_generation`'s artefacts (RISK-3; any
  other diff is reported, not fixed); task gate green.
- [x] 1.2 **integration (#371 stale copy)** — after 1.1; spec scenario 4, TC-6, in
  `tests/generator/integration/`. On a `toy_copy`: run
  `rp-generate` with the value target's `typescript` removed (the technical target writes
  `loan_checks.ts`), restore it, run again; assert `web/src/services/generated/loan_checks.ts`
  is gone. Expected green at once (the manifest's stale removal); if red, fix in `pipeline.py`
  and report it. Accept: test passes, task gate green.
- [x] 1.3 **unit + docs (#372)** — independent of 1.1; PD-7, TC-7. One test in
  `tests/unit/testkit/test_guards.py`, beside `test_exempt_folder_passes`:
  `fragment_shapes.ttl` under `area/fixtures` passes with that folder exempt, and fails naming the
  file without it. Expected green at once (it pins the documented use). Then the docstring of
  `assert_models_generated` in `rdf_persistence/testkit/guards.py` and the two docs of PD-7.
  Accept: test passes; `make check-docs` green.
- [x] 1.4 **docs (#371)** — after 1.1; PD-8: `architecture/generation.adoc` *Imports between
  targets*, `user-manual/generate.adoc` output table, `CHANGELOG.md` `[Unreleased]` *BREAKING*.
  Accept: `make check-docs` green.
- [ ] 1.5 **lead** — scenario-map rows for the new tests; `make check-all`; one review pass
  (SMALL); PR into `develop` naming MWB2 `v2-05` (D-12) and the migration line; merged on green CI;
  #371 and #372 closed; archive.

## Roadmap

- [x] 1.1 · [x] 1.2 · [x] 1.3 · [x] 1.4 · [ ] 1.5 (1.3 may run beside 1.1)

## Verification

`make test-generator`, `make check-types` and `make check-all` green; the domain target's
TypeScript and the served-types golden unchanged; the clarity gate on this PLAN ≥ 9/10 before 1.1.
