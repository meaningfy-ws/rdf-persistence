> Derives from: EPIC `mwb2-file-resources` (proposal.md, shaped 2026-11-09); design: design.md; answers in inputs/seed.md.

Two stages, **one PR per stage** into `develop`, each merged on green CI before the next starts.
Within a task, tests come first (the `T-n` of design.md). Per task: the affected test directories
with `-n auto`, `make check-quality`, `make clean-code`. Before each task: gitnexus impact on the
symbols it changes (stop on HIGH/CRITICAL). Before each PR: `make check-all`,
`make test-containers`, `make check-docs`. Tasks touching `howto/adopt.adoc` run one after the
other. Review: MEDIUM — five lenses (L4+L5 one pass) and a checker per stage.

# Stage 1 — buildable, trustworthy file records (#59, #55, #54)

## 1. Description optional (#59)

- [x] 1.1 PD-1: T-1, T-2, T-3 fail, then remove the root half of `apply_defaults`, fix the
  `class_shapes` docstring, `make generate`, rewrite `tests/fixtures/model-shape.yaml`, update the
  tests that asserted the old default. Gate: `uv run pytest -n auto tests/unit/generation
  tests/unit/testkit tests/unit/services -q`.
- [x] 1.2 PD-2: T-4, T-5, then `model_schema_diff` in `testkit/model_shape.py`, its export, its call
  in the toolkit's generated-artefact test, `howto/adopt.adoc` step 6 and
  `architecture/generation.adoc` (descriptions optional; the guard). Gate: `uv run pytest -n auto
  tests/unit/testkit tests/unit/generation -q`, `make check-docs`.

## 2. Service-written roots (#55) — BREAKING for generic writes on StoredFile roots

- [x] 2.1 PD-3 model and rule: T-9, then `rp_writes` and `WritesKind` in `model/rp_core.yaml`,
  `make generate`, the hard check, `is_service_written`. Gate: `uv run pytest -n auto
  tests/unit/generation tests/unit/services -q`.
- [x] 2.2 PD-3 routes: T-6, T-7, T-8, then `add_aggregate_routes`; change every scan-writing test as PD-3's
  table says (incl. the e2e toy app's own scan route). The report says which
  way each of PD-3's open branches went (l.107's 422 test, the service-level stripping tests). Gate: `uv run pytest -n auto
  tests/unit/entrypoints tests/unit/services tests/integration/api -q`.
- [x] 2.3 PD-3 docs: `howto/adopt.adoc` step 10 (file roots are written through a session; the
  annotation), `architecture/api.adoc` (which routes a root gets), `questions.adoc` ("Why does my
  file root answer 405 on PUT?"). Gate: `make check-docs`.

## 3. Inline filter schemas (#54)

- [x] 3.1 PD-4: T-10, T-11, then `_inline_property_refs` in `install_openapi`. Gate:
  `uv run pytest -n auto tests/unit/entrypoints -q`.
- [x] 3.2 PD-4 toolchain: `tests/dump_openapi.py`, the `typecheck-openapi-ts` target under
  `check-types`. Gate: `make typecheck-openapi-ts` (T-12).

Stage 1 close: five-lens review, decisions recorded below, fixes, checker, durations in
`develop/index.adoc`, PR, merge on green CI. Then: comment on and close #59, #55, #54
naming the PR, so MWB2 can refresh its lock (EPIC, Solution outline). #54's comment says it is
fixed for any consumer generating a client from the OpenAPI document, and that MWB2 no longer
needs it.

# Stage 2 — read without SPARQL (#56, #60)

## 4. Loaded graphs read back (#56)

- [ ] 4.1 PD-5, PD-7: T-13, T-14, T-15, then `Session.loaded_graph` (the delta spec
  already carries PD-7). Gate: `uv run pytest -n auto tests/unit/services
  tests/integration/store -q`, `openspec validate mwb2-file-resources --strict`.

## 5. Finding aggregates (#60)

- [ ] 5.1 PD-6: T-16 to T-21, then `Session.find`, the `listings` keyword on `Session`, `open_session`,
  `fake_session` and `Tenancy`, and the `ServiceKit` wiring (PD-6). The
  report says whether T-16 to T-20 run on `FakeStore` or Fuseki. Gate: `uv run pytest -n auto tests/unit/services tests/unit/entrypoints
  tests/integration/store -q`.
- [ ] 5.2 Docs: `howto/adopt.adoc` (reading a loaded graph, with the `require_aggregate`
  check first; finding aggregates, and that `find` ignores Prohibitions), `questions.adoc`. Gate: `make check-docs`.

Stage 2 close: five-lens review, checker, PR, merge on green CI. Then: comment on and close #56, #60
naming the PR; archive the change.

# Roadmap

| Stage | Issues | Unblocks in MWB2 |
|---|---|---|
| 1 | #59, #55, #54 | v1-06's critical path: #59 unblocks tasks 1.3–1.5, 1.8, 2.1, 2.2 (and 1.6, 1.7, 3.6, 4.6 through them); #55 unblocks 1.6. #54 is moot for MWB2 (it drops openapi-typescript in `rp-adoption-refresh`) and is fixed for other consumers |
| 2 | #56, #60 | #56 unblocks v1-06 tasks 2.3, 2.4, 3.7 (counts, browsing, "replace leaves one graph"); #60 unblocks 1.7 (the 409 `duplicate-name`) |
