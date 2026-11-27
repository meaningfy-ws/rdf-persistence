EPIC: typescript-toolkit-modules (proposal.md). Decisions: DEC-1 to DEC-6 (proposal), PD-1 to PD-9 (design.md).

> Derives from: EPIC `typescript-toolkit-modules`. Issue #402 (split from #189).

Every task: test-first; task gate `make test-changed check-quality`; commit body
`Refs: typescript-toolkit-modules <task> <PD>` (`Refs: #402` on the task that closes it).
Builders never commit, never run `make generate` or `uv sync` (the lead does); the lead commits and
ticks this file. The generator's files are manifest inputs of both projects the freshness plugin
checks (`pytest.ini` `rp_generate_projects`: the toolkit and the toy), so after an edit to
`rdf_persistence_generation/` every test session stops as stale until `make generate` runs. So 1.2 and
1.3 each run in a worktree of their own (not shared), where the builder may run `make generate` after
its code edits and before its tests; the generated diffs it leaves are the lead's to check against
RISK-3 and to commit (RISK-5).

## 1. One stage — branch `change/typescript-toolkit-modules`, one PR

- [x] 1.1 **lead: the key** — PD-1, first half of PD-8. Add the slot `toolkit_typescript` to
  `GenerationTarget` in `rdf_persistence_generation/model/rp_generation.yaml`, and the line
  `toolkit-typescript = true` (with its comment) to the toy's domain entry in
  `tests/fixtures/library/pyproject.toml`, so the toy is valid once 1.2's check lands and every
  test built on the toy or a `toy_copy` (among them `test_stale_typescript_copy.py`, which leaves
  two or three TypeScript entries, the domain one always among them) keeps passing; `make generate`.
  Accept: `GenerationTarget.toolkit_typescript` exists with alias `toolkit-typescript`, default
  `False`; no TypeScript file changes (nothing reads the key yet); the only other diffs are
  `rp_generation`'s own artefacts and `rp-manifest.json` input hashes (RISK-3; any other diff is
  reported, not fixed).
- [x] 1.2 **unit + code: the check** — after 1.1; PD-2, TC-6. First failing tests in
  `tests/generator/unit/test_generate_config.py`: the four refusals (no owner, two owners, key
  without `typescript`, a shared folder) with their messages,
  and acceptance of one TypeScript entry with or without the key. Then `_refuse_toolkit_owner` in
  `config.py`, called from `_toml_entries`. Accept: tests pass; task gate green.
- [x] 1.3 **unit + code: render and step** — after 1.1; PD-3, PD-4, PD-5, PD-6; TC-1, TC-2, TC-5,
  TC-8. First failing tests in `tests/generator/unit/test_typescript_toolkit_owner.py` (new):
  `typescript.render(..., toolkit=...)` on the toy's technical and value schemas as importers
  (TC-1), an owner whose schema lacks a metamodel module (TC-2), `toolkit=None` unchanged and
  `_toolkit_folder` for one target and for `targets=()` (TC-5), `current_inputs` with the key
  (TC-8). Then `_shared_modules`/`_shared_names` and the `toolkit` and `owns_toolkit` parameters in
  `extensions/typescript.py`, `_toolkit_folder` and the `render` call in `steps.py`, the input rule in
  `manifest.py`; then `make generate` in this task's own worktree (tasks.md header), which rewrites
  the toy's value and technical trees (second half of PD-8); then rewrite the assertion of
  `test_a_toy_generation_writes_rp_service_ts` (`test_typescript_service_types_adversarial.py`) to
  one `rp_service.ts`, in the owner's folder (design.md, Lanes). Accept: new tests pass;
  `test_ext_typescript.py`, `test_typescript_imports.py` and the rest of
  `test_typescript_service_types_adversarial.py` pass unchanged; task gate green.
- [x] 1.4 **lead: the toy** — after 1.2 and 1.3; second half of PD-8, TC-3, TC-4. Review and commit
  the regenerated value and technical trees and their `rp-manifest.json`. Accept: the domain tree is
  byte-identical to `develop` (RISK-2: a difference is reported to the developer, not patched); the
  toolkit's own trees differ only as RISK-3 allows; TC-3 green; `make typecheck-ts` green where Node
  exists, else the CI "types" job before merge (TC-4).
- [ ] 1.5 **integration: stale copies** — after 1.4; PD-7, TC-7, in
  `tests/generator/integration/test_stale_toolkit_typescript.py` (new, beside
  `test_stale_typescript_copy.py`). Expected green at once; if red, fix in `pipeline.py` and report
  it. Accept: test passes; task gate green.
- [ ] 1.6 **docs** — after 1.4; PD-9: `architecture/generation.adoc` *Imports between targets*,
  `user-manual/generate.adoc` (keys table, output row, example), `CHANGELOG.md` `[Unreleased]`
  *BREAKING* with the migration note. Accept: `make check-docs` green.
- [ ] 1.7 **lead** — scenario-map rows for the new tests; `make check-all`; one review pass (SMALL);
  PR into `develop` naming #402 and the migration line, and the consumer (D-12); merged on green CI;
  #402 closed; #189 item (v) ticked; archive.

## Roadmap

- [x] 1.1 · [x] 1.2 · [x] 1.3 · [x] 1.4 · [ ] 1.5 · [ ] 1.6 · [ ] 1.7 (1.2 and 1.3 may run side by
  side after 1.1)

## Verification

`make test-generator`, `make check-types` and `make check-all` green; the toy's domain TypeScript tree
and `tests/fixtures/library/golden/served_typescript/` unchanged; the clarity gate on this PLAN ≥ 9/10 before 1.1 (R-0005:
8.8 accepted with the small gaps folded in).
