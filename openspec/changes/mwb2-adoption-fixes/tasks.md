> Derives from: EPIC `mwb2-adoption-fixes` (proposal.md); design: design.md; answers in inputs/seed.md.

One stage, one PR into `develop`, closing #42, #43, #44, #45. Sections 1–4 touch disjoint code;
2.2 and 4.2 both edit `howto/adopt.adoc`, so run those two one after the other. Per task: tests
first (the `T-n` of design.md), the affected test directories, `make check-quality`,
`make clean-code`. Before each task: gitnexus impact on the symbols it changes (stop on
HIGH/CRITICAL). Before the PR: `make check-all`, `make test-containers`, `make check-docs`.

## 1. Typed package (#42)

- [ ] 1.1 PD-1: T-1 fails, then add the empty `rdf_persistence/py.typed`.
  Gate: `uv run pytest tests/unit/test_packaging.py -q`.

## 2. Tenant delete needs administer (#43) — BREAKING

- [ ] 2.1 PD-2: T-2, T-3, T-5 new and T-4 changed (`tests/unit/entrypoints/test_router.py`), then
  the route in `rdf_persistence/entrypoints/router.py`. Gate:
  `uv run pytest tests/unit/entrypoints tests/unit/services -q`.
- [ ] 2.2 PD-2 docs: `architecture/access-control.adoc` l.103, `howto/adopt.adoc` (~l.688, roles
  example ~l.738). Gate: `make check-docs`.

## 3. One tenant label (#44)

- [ ] 3.1 PD-3 rename: T-6 to T-9, then `Tenancy.rename`. Gate: `uv run pytest tests/unit/services -q`.
- [ ] 3.2 PD-3 root replacement: T-10, T-11, then the `Tenancy` check and its call in
  `Aggregates.replace`. Gate: `uv run pytest tests/unit/entrypoints tests/unit/services -q`.

## 4. Public guard API (#45)

- [ ] 4.1 PD-4 exports: T-12, T-13, then `rdf_persistence/testkit/__init__.py`. Gate:
  `uv run pytest tests/unit/testkit tests/unit/test_testkit_lazy_import.py tests/unit/generation -q`.
- [ ] 4.2 PD-4 docs: T-15, then `howto/adopt.adoc` step 6 (imports, prose at ~l.375/397, the fifth
  check), `architecture/generation.adoc` l.496/498/514, `questions.adoc` l.103. Gate:
  `make check-docs` (T-14) and T-15.

## 5. Close

- [ ] 5.1 The spec deltas (`specs/*/spec.md`) match what was built; `make check-all`,
  `make test-containers`; the durations table in `develop/index.adoc` from these runs. PR body:
  `Closes #42 #43 #44 #45`, the BREAKING change, the T-n list. Merge on green CI.

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
