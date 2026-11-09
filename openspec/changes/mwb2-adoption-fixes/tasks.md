> Derives from: EPIC `mwb2-adoption-fixes` (proposal.md, re-shaped 2026-11-09); design: design.md; answers in inputs/seed.md.

Four stages, **one PR per stage** into `develop`, each merged on green CI before the next starts.
Within a stage, tests come first (the `T-n` of design.md). Per task: the affected test
directories, `make check-quality`, `make clean-code`. Before each task: gitnexus impact on the
symbols it changes (stop on HIGH/CRITICAL). Before each PR: `make check-all`,
`make test-containers`, `make check-docs`. Tasks touching `howto/adopt.adoc` run one after the other.

# Stage 1 — v1-05 blockers and small fixes (#42, #43, #44, #45, #46, #50)

## 1. Typed package (#42)

- [x] 1.1 PD-1: T-1 fails, then `uv add --dev "uv_build>=0.10,<0.11"` and the empty
  `rdf_persistence/py.typed`. Gate: `uv run pytest tests/unit/test_packaging.py -q`.

## 2. Tenant delete needs administer (#43) — BREAKING

- [x] 2.1 PD-2: T-2, T-3, T-5 new and T-4 changed (`tests/unit/entrypoints/test_router.py`), then
  the route in `rdf_persistence/entrypoints/router.py`. Gate:
  `uv run pytest tests/unit/entrypoints tests/unit/services -q`.
- [x] 2.2 PD-2 docs: `architecture/access-control.adoc` l.103, `howto/adopt.adoc` (~l.688, roles
  example ~l.738). Gate: `make check-docs`.

## 3. One tenant label (#44) and its version (#50)

- [x] 3.1 PD-3 rename: T-6 to T-9, then `Tenancy.rename`. Gate: `uv run pytest tests/unit/services -q`.
- [x] 3.2 PD-3 root replacement: T-10, T-11, then the `Tenancy` check and its call in
  `Aggregates.replace`. Gate: `uv run pytest tests/unit/entrypoints tests/unit/services -q`.
- [x] 3.3 PD-6: T-18, T-19, then `Record-ETag` on `read_root`, its OpenAPI text and the guide
  (incl. the CORS note). Gate: `uv run pytest tests/unit/entrypoints -q`, `make check-docs`.

## 4. Public guard API (#45)

- [x] 4.1 PD-4 exports: T-12, T-13, then `rdf_persistence/testkit/__init__.py`. Gate:
  `uv run pytest tests/unit/testkit tests/unit/test_testkit_lazy_import.py tests/unit/generation -q`.
- [x] 4.2 PD-4 docs: T-15, then `howto/adopt.adoc` step 6 (imports, prose at ~l.375/397, the fifth
  check), `architecture/generation.adoc` l.496/498/514, `questions.adoc` l.103. Gate:
  `make check-docs` (T-14) and T-15.

## 5. Id source (#46)

- [x] 5.1 PD-5: T-16, T-17, then `install_service`, `ServiceKit`, and export `IdSource` from `rdf_persistence`. Gate:
  `uv run pytest tests/unit/entrypoints tests/unit/domain -q`.

## 6. Close stage 1

- [ ] 6.1 Stage gates; the durations table in `develop/index.adoc`. PR: `Closes #42 #43 #44 #45
  #46 #50`, the BREAKING change, the T-n list. Merge on green CI.

# Stage 2 — consumer rules on tenant writes (#49)

## 7. Validators

- [ ] 7.1 PD-7 grants: T-20, T-21, T-23, then the types, `install_service`/`ServiceKit` wiring and
  `Tenancy.set_grants`. Gate: `uv run pytest tests/unit/services tests/unit/entrypoints -q`.
- [ ] 7.2 PD-7 roots: T-22, then `Tenancy.create`, `rename` and `vet_root` (with the PD-3 check).
  Gate: same; T-24 (the whole unit suite unchanged).
- [ ] 7.3 PD-7 docs: `howto/adopt.adoc` "Enforce your own rules on tenant writes",
  `architecture/access-control.adoc`. Gate: `make check-docs`.
- [ ] 7.4 Close stage 2: stage gates; PR `Closes #49`. Merge on green CI.

# Stage 3 — API shapes (#47, #48)

## 8. Generation

- [ ] 8.1 PD-9: T-27, T-28, then `_ownership_problems`; the guide's `module_kind` paragraph.
  Gate: `uv run pytest tests/unit/generation -q`.
- [ ] 8.2 PD-8: T-25, then `linkml:Any` → `unknown` in `range()` and `typescript.render`; `make generate` (the toy gains `rp_service.ts`);
  T-26. Gate: `uv run pytest tests/unit/generation -q`, `make check-generated`, `make typecheck-ts`.
- [ ] 8.3 Close stage 3: stage gates; PR `Closes #47 #48`. Merge on green CI.

# Stage 4 — permitted actions (#51)

## 9. Allowed actions

- [ ] 9.1 PD-10 model: `allowed_actions` in `rp_service.yaml`, `make generate`,
  `make refresh-snapshot` (review: one added slot); T-32. Gate: `make check-generated`.
- [ ] 9.2 PD-10 behaviour: T-29, T-30, T-31, then the header on both reads, the listing, the
  OpenAPI text; the guide's CORS note names `Allowed-Actions`. Gate:
  `uv run pytest tests/unit/entrypoints tests/unit/services -q`, `make check-docs`.
- [ ] 9.3 Close the EPIC: stage gates; the spec deltas (`specs/*/spec.md`) match what was built;
  PR `Closes #51`; merge on green CI; then archive the change (`/opsx:archive`).

## Clarity gate

- **Round 1** (independent reviewer, 2026-11-09): **8.4 / 10, fail.** Gaps: the testkit's lightness
  claim was false (`linkml_runtime` and `rdflib` already load through `testkit.fakes`); stale
  `If-Match` is 409, not 412; `test_router.py:138–156` breaks under PD-2 and was not named;
  "What Changes" said the toy roles change; three error-matrix rows missing; conditional "if"s in
  PD-1 and PD-2; the guide's snapshot check underspecified; too few anti-patterns; tests without ids.
- **Revision** (same day): all of the above fixed in design.md (PD-1 to PD-4, T-1 to T-15, the
  anti-pattern table, the error matrix), tasks.md and the spec deltas.
- **Round 2** (same reviewer, 2026-11-09): **9.1 / 10, pass.** Four residual gaps, all folded in
  the same day: `uv_build` must be added to `dev` (PD-1); T-5 defined; T-8/T-9 injection through
  `FakeStore.on("update", …, after=1)`; the guide's model-shape snippet filters to the schema's own
  classes (probed: `[]`). The eager/lazy reasons in PD-4 corrected; `shape_snapshot` made eager.
- **Re-shape** (2026-11-09, Q-5): #46–#51 added as PD-5 to PD-10 and stages 2–4; PD-3's refusal
  corrected from 400 to 422 (`InvalidBody` → 422, `entrypoints/problems.py:36`).
- **Round 3** (same reviewer, whole re-shaped PLAN, 2026-11-09): **8.8 / 10, fail.** Gaps: PD-8 would
  ship `linkml:Any` as `string` (probed: renders and passes tsc, but `root: string`,
  `items: string[]`); PD-9 named the wrong helper and a toy technical module that does not exist;
  PD-5 cited the wrong line and left the `IdSource` export as an "if"; PD-7's rename order
  contradicted itself; a validator's pydantic `ValidationError` gives 422, not 500.
- **Revision** (same day): all five fixed (PD-5, PD-7 table and T-23, PD-8 `Any` → `unknown` with
  T-25, PD-9 and T-27, error matrix).
- **Round 4** (same reviewer, 2026-11-09): **9.25 / 10, pass.** Two minor gaps folded in: PD-7's
  "Types" paragraph now matches the 422/500 rule; PD-8 states that only the toy target renders
  TypeScript (`rp_wire.yaml` uses `linkml:Any` but has no TS target).
