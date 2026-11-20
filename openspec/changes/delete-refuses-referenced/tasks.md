EPIC: delete-refuses-referenced (proposal.md, #201). Decisions: design.md PD-1 to PD-13, DEC-1 to DEC-3.

Every task: the failing test first (its ID in design.md *Test cases*), then the code; task gate
`make test-changed check-quality` (`make test-fast check-quality` for 2.1 and 2.2, which change
`domain` and a port); commit body `Refs: delete-refuses-referenced <task> <PD>`. Builders never
commit and never run `make generate`; the lead does, then `make check-generated`.

## 1. Stage 1: model

- [x] 1.1 Metamodel and settings (PD-1, PD-10, PD-11): in `rp_core.yaml` the `RpAnnotation` entry
  and `OnReferencedDelete`; in `rp_persistence_settings.yaml` `max_named_referrers`; in
  `rp_api_entrypoints.yaml` `ProblemSlug.in_use`, the new slot `more_count`, the import of
  `../collaboration/rp_collaboration_services`, and `InUseProblem` (`is_a: Problem`) with the
  optional slots `referrers` (range `Referrer`, inlined as list), `hidden_count` and `more_count`; the
  `ALLOWED_ANNOTATIONS` row in `hard.py`. Tests first: TC-1 (generator unit). Lead: `make generate`.
  Accept: TC-1 passes; `ToolkitSettings().limits.max_named_referrers == 20`.
- [x] 1.2 Toy (PD-13): `Author` and `Book.written_by` in `tests/fixtures/library/books.yaml`;
  `schema_structure.refusing_classes` (PD-2). Tests first: TC-2 (unit). Lead: `make generate`,
  `make refresh-golden`, `make refresh-served-golden`, `make refresh-snapshot`. Accept: TC-2
  passes; `make test-fast` passes.

## 2. Stage 2: the refusal

- [x] 2.1 `InUse` (PD-6) in `core/domain/exceptions.py`, exported from `rdf_persistence`
  (`make refresh-surface`); the naming move (PD-8) to `collaboration/services/referrer_naming.py`.
  Tests first: TC-0 (unit); TC-7 must stay green. Accept: TC-0 passes; TC-7 unchanged and passing.
- [x] 2.2 Session (PD-3, PD-4, PD-5, PD-7, PD-9): the `RemovalRefusal` protocol, `removals` on
  `Session`, `open_session`, `Tenancy`; the shared referrer fragment; the guard; the diagnosis
  step; the same-commit check; `readable` on `transaction` and `remove`. Tests first: TC-3, TC-4,
  TC-5 with a stub `RemovalRefusal` (unit, fake store). Accept: they pass; existing
  `tests/unit/persistence/` passes unchanged.
- [ ] 2.3 Schema side and HTTP (PD-7, PD-9, PD-10, PD-11; the `rp-service-api` delta):
  `ReferencedRemovals`; `Collaboration.readable_referrers` (moved out of `referrers`); kit wiring;
  `Aggregates.remove(…, readable)`; the route opening `kit.collaboration(checked)`; the `InUse`
  problem row and handler branch; the `DELETE` docs. Tests first: TC-6, TC-9, TC-10 (unit).
  Accept: they pass; E1 to E4, E8 (OPEN-2 as decided, `inputs/qa.md`) and E9 hold through the toy
  app; TC-7 still passes.
- [ ] 2.4 Cascade (PD-12, OPEN-1 as decided): `Collaboration.delete_cascade` passes
  `readable_referrers` to `ReferenceCollections.delete_cascade`. Tests first: TC-8 (unit).
  Accept: E6, E7 hold.
- [ ] 2.5 Integration (RISK-2): IT-1, IT-2, IT-3 on Fuseki. Accept: all three pass in
  `make test-containers` (lead).

## 3. Stage 3: docs and close

- [ ] 3.1 Docs: `user-manual/store-and-read.adoc` new `[#refuse-referenced]` section (the
  annotation, E1/E2/E5, matrix rows 4 and 6, RISK-1); `user-manual/model.adoc` annotation list;
  `architecture/api.adoc` the `in-use` problem; `questions.adoc` the question it answers; lead runs
  `make docs-reference`. Accept: `make check-docs` passes.
- [ ] 3.2 Lead: `make refresh-map` (spec scenarios to TC-3, TC-8, TC-9, TC-10), `make check-all`,
  `make test-containers`, the MEDIUM review set, fixes, PR into `develop`.

## Roadmap

1.1 → 1.2 → 2.1 → 2.2 → (2.3 ∥ 2.4) → 2.5 → 3.1 → 3.2

## Verification

`make check-all` and `make test-containers` pass, `openspec validate delete-refuses-referenced
--strict` passes, every scenario of the spec delta has a row in `tests/audit/scenario-map.csv`, and
the PR's CI is green.
