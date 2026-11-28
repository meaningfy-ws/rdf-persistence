EPIC: dependent-aggregates (proposal.md, issue #437 A.5). Decisions: design.md PD-1 to PD-18, D-1 to D-10, DEC-1 to DEC-7.

> Derives from: EPIC `dependent-aggregates`. Three stages (MEDIUM), one pull request each.

Every task: the failing test first, in the tier named; task gate `make test-changed check-quality`;
commit body `Refs: dependent-aggregates <task> <PD>`. Builders never commit, never run `make
generate` or `uv sync`; the lead does. Toy terms: `Audit` A1, `AuditResult` R1/R2, `AuditFinding`
F1 ([PD-14](design.md#pd-14)). No existing test is moved; each new test runs in the lane of its
folder. Paths are from the repository root. **Order:** the task ids are stable references (the
attack and gate evidence cite them); the [Roadmap](#roadmap) gives the order to run them, and it
wins where the ids disagree (stage 2: 2.5a before 2.5, 2.7 before 2.6).

## 1. Stage 1: the annotation and its schema check (PR 1)

- [x] 1.1 Lead: `openspec validate dependent-aggregates --strict`; ADDED requirements only, no
  living text changed. Accept: validation passes.
- [x] 1.2 Metamodel and models ([PD-1](design.md#pd-1), [PD-2](design.md#pd-2)), lead.
  `rp_dependent_on` in `RpAnnotation` (`rdf_persistence/model/rp_core.yaml`); `DependenceLink` in
  `rdf_persistence/model/rp_core.yaml` (D-6);
  `BoundaryRule.DEPENDENCE` in `rdf_persistence_generation/model/rp_generation.yaml`; `make
  generate`, `make check-generated`. Unit first: `tests/unit/core/test_annotations.py`
  `test_rp_dependent_on_is_an_annotation_the_toolkit_reads`. Accept: passes; regenerated files in
  the same commit.
- [x] 1.3 Generator check ([PD-12](design.md#pd-12)), after 1.2. First, failing, in
  `tests/generator/unit/test_dependence_check.py`, one schema per row under
  `tests/generator/fixtures/dependence/`: refused — pointer not required, multivalued, over a
  non-root, over a toolkit-written root, over the tenant root, slot not on the class, annotation on
  a non-root, a subclass re-annotating with another slot, a concrete subclass relaxing `required`
  by `slot_usage`, A→B→A, A→A, a cycle through subclasses (X over abstract Y whose concrete Z
  depends on X), a class depending on its own abstract superclass (A-10, A-12); accepted — pointer
  over a served root, over an abstract root whose concrete subclasses are served, the annotation on
  an abstract base whose concrete subclasses are served, a two-level chain. Then
  `rdf_persistence_generation/checks/dependence.py`, called from `boundary_problems` in
  `rdf_persistence_generation/checks/boundary.py`. Accept: each refusal names class and slot
  (cycle: its classes in order) and fails when its check is removed.
- [x] 1.4 Schema structure ([PD-2](design.md#pd-2)), after 1.2.
  `tests/unit/schema/test_schema_structure_dependence.py`
  `test_dependence_links_read_the_annotation_and_subclasses`, then `dependence_links(view)` in
  `rdf_persistence/schema/services/schema_structure.py`. Accept: the test passes on the toy and on
  a fixture with an abstract annotated base (one link, its concrete subclasses as `part_classes`).
- [x] 1.5 Toy module ([PD-14](design.md#pd-14)), lead, after 1.3. `tests/fixtures/library/audits.yaml`,
  imported by `tests/fixtures/library/library.yaml`; `make generate`; goldens refreshed in one
  commit. Accept: `rp-generate` passes on the toy; `make check-generated`.
- [x] 1.6 Generation feature, after 1.3: scenarios 10–11 of
  `openspec/changes/dependent-aggregates/features/dependent_aggregates_generation.feature` into
  `tests/generator/feature/dependent_aggregates_generation.feature`, steps in
  `tests/generator/feature/test_dependent_aggregates_generation.py`, verbatim. Lane: `make
  test-generator`. Accept: both scenarios (all outline rows) pass.
- [x] 1.7 Docs ([PD-16](design.md#pd-16)): `docs/modules/ROOT/pages/user-manual/model.adoc`
  (annotation, DEC-7 rules). Accept: `make check-docs` passes.
- [ ] 1.8 Lead: `make check-all`; one review pass; PR. Accept: gates green; no Critical open.

## 2. Stage 2: write guard and cascade (PR 2), after stage 1

- [x] 2.1 Wiring ([PD-2](design.md#pd-2), [PD-6](design.md#pd-6)): `Session` and `tenant_session`
  (`rdf_persistence/persistence/services/session.py`) take `dependence: Sequence[DependenceLink]`
  and `max_roots: int | None`; the kit (`rdf_persistence/api/entrypoints/kit.py`), `Tenancy`
  (`rdf_persistence/tenancy/services/tenancy.py`) and the testkit's `fake_session`
  (`rdf_persistence/testkit/fakes.py`) pass them from `dependence_links(view)` and
  `toolkit.limits`. Unit first: `tests/unit/persistence/test_session_dependence_wiring.py`,
  including `dependence` without `max_roots` → `ValueError` (A-8). Accept: the new test passes;
  every existing `tests/unit/persistence/` and `tests/unit/tenancy/` test passes unchanged.
- [x] 2.2 Pure fragments ([PD-3](design.md#pd-3), [PD-6](design.md#pd-6), [PD-7](design.md#pd-7)):
  `rdf_persistence/persistence/services/dependence.py` — pointer of a part, whole guard, discovery
  query (selecting `?whole ?part ?type ?version`), no-late-part guard.
  `tests/unit/persistence/test_dependence.py`. Accept: the test passes; each text is filled with
  terms, never concatenated input, and each guard's variables carry its index.
- [x] 2.3 Write guard ([PD-3](design.md#pd-3), [PD-11](design.md#pd-11)), after 2.1–2.2.
  `tests/unit/persistence/test_session_dependent_write.py` on the fake store: add of R with A1
  present passes; A1 absent → `NotFound` naming A1, nothing written; A1 of another class →
  `NotFound`; whole removed by another session between the ASK and the send (fault hook) →
  `NotFound`; whole added in the same transaction, collected **before or after** its part, passes
  (G-2); whole replaced in the same transaction to a class outside `whole_classes` → `NotFound`,
  nothing sent (A-3); no or two pointer values, or the part's own IRI → `InvalidBody` (A-7).
  Accept: every row passes, asserting the exception type and its `iris` (A-5).
- [x] 2.4 Pointer fixity ([PD-4](design.md#pd-4)). Same file: replace with another `of_audit` →
  `Conflict` naming the slot; same pointer passes. Accept: both rows pass.
- [x] 2.5a Diagnosis ([PD-11](design.md#pd-11); A-5, A-18), after 2.3, before 2.5: `_wholes`,
  `_unlated`, `_versions_found` reading their graphs, `_diagnose` order (gone whole → `NotFound`;
  late part → `Conflict` naming the removed root; then `_reasons`; then `_refused_by_store`).
  `tests/unit/persistence/test_session_dependent_diagnosis.py`: a commit that also replaces a stale
  book and whose whole is gone raises `NotFound` naming the whole, not the book's conflict; a
  failed no-late-part guard raises `Conflict` with `iris == (A1,)`, not "lost a race". Accept:
  both pass.
- [x] 2.5 Cascade ([PD-5](design.md#pd-5), [PD-6](design.md#pd-6), [PD-8](design.md#pd-8),
  [PD-9](design.md#pd-9)), after 2.5a. `tests/unit/persistence/test_session_dependent_cascade.py`:
  removing A1 removes R1, R2, F1, L1 and their entries in one request; one `Remove` activity, four
  invalidations; a unit of work removing A1 and R2 removes each once and F1 too, and at exactly
  `max_roots` 4 is not refused (A-7); adding R3 while removing A1 in one transaction → `Conflict`,
  nothing sent; replacing R1 and removing A1 in one transaction → `Conflict` naming R1 and A1, no
  `ValueError`, nothing sent (G-1); adding F9 → R1 while removing A1 only (R1 reached by cascade)
  → `Conflict` naming F9 and R1, nothing sent (A-2); adding A2 `cites_finding` F1 in the commit
  that removes A1 → `InUse`, nothing sent (A-1); a #226 comment on R1 added in that commit →
  `Conflict`, nothing sent (A-1); `max_roots` 3 with A1+3 parts → `CommitTooLarge` with the limit,
  nothing written; A2 citing F1 → `InUse`, nothing removed; a part removed between discovery and
  send → `Conflict` naming A1; a part added after discovery (fault hook) → `Conflict` naming A1
  ([PD-7](design.md#pd-7)); discovery over a schema link that would revisit a root terminates
  (A-7); no `_stored` read per cascaded part (A-15: the fake store counts queries). Accept: every
  row passes, asserting type and `iris`.
- [x] 2.7 Service API (DEC-3, [PD-18](design.md#pd-18)), after 2.5: `POST /audit-results` naming a
  missing audit → 404 naming it; `PUT` changing `of_audit` → 409; listing `audit-results` filtered
  on `of_audit` A1 returns A1's results only (A-17). The OpenAPI document lists 404 on the create
  and replace routes of `AuditResult` and 413 on the delete route of `Audit`; the lead refreshes
  the OpenAPI golden in the same commit. `tests/unit/api/test_dependent_routes.py`. Accept: the
  test passes; the golden diff holds only those answers and the toy's new routes.
- [x] 2.6 Access ([PD-10](design.md#pd-10), DEC-2), after 2.7 (A-18).
  `tests/unit/api/test_dependent_delete_route.py`: a caller with delete on A1 and no right on parts
  gets 204 and the parts are gone; with a Prohibition of read on F1, the `InUse` and conflict
  answers do not name F1; a delete validator refusing F1 with a message naming F1 is answered
  naming A1 and "a dependent part" only (A-6); an SSE follower without read on R1 does not receive
  R1's invalidation. Accept: every row passes.
- [x] 2.8 Integration ([RISK-1](design.md#risk-1), A-13), after 2.5.
  `tests/integration/store/test_dependent_aggregates.py` on Fuseki: IT-D1 cascade of three levels
  with a loaded graph; IT-D2 twenty rounds of concurrent part writes and the whole's delete
  (`asyncio.gather`) leave no part without its whole; IT-D3 two parts written in parallel both
  succeed, the whole's version unchanged; IT-D4 a wrapper store pauses the delete after its
  discovery queries while another session adds R3 → the delete is a `Conflict` naming A1, nothing
  removed; IT-D5 the part's ASK passes, the whole is deleted, then the part's request is sent →
  `NotFound` naming A1, no R3 graph. Plus the conformance scenario "a guard reads a graph the
  request does not write" in `tests/integration/store/test_store_conformance.py`. Builder writes,
  lead runs `make test-containers`. Accept: all five and the conformance scenario pass on Fuseki.
- [x] 2.9 Feature, after 2.6: scenarios 1–9 of
  `openspec/changes/dependent-aggregates/features/dependent_aggregates.feature` into
  `tests/feature/dependent_aggregates.feature`, steps in `tests/feature/test_dependent_aggregates.py`,
  verbatim. Lane `make test-feature`. Accept: the nine pass.
- [x] 2.10 Docs ([PD-16](design.md#pd-16)): `docs/modules/ROOT/pages/user-manual/store-and-read.adoc`
  (incl. [D-1](design.md#d-1) validators, [RISK-8](design.md#risk-8) retry, batch mode not atomic
  across batches, [RISK-4](design.md#risk-4) cost), `docs/modules/ROOT/pages/questions.adoc`.
  Accept: `make check-docs` passes.
- [ ] 2.11 Lead: `make check-all`, `make test-containers`; review set for MEDIUM; PR. Accept: gates
  green; no Critical open.

## 3. Stage 3: converter emission (PR 3), after stage 1 and `aggregate-composition`'s converter

- [x] 3.1 Lead ([PD-17](design.md#pd-17), [D-12](design.md#d-12): not applicable yet): if `aggregate-composition` is archived, turn the
  `rp-uml-import` delta into a MODIFIED of the requirement holding the refusal. Accept: `openspec
  validate dependent-aggregates --strict` passes.
- [x] 3.2 Converter ([PD-13](design.md#pd-13)). Rewrite the refusal test as
  `tests/generator/unit/test_uml_own_graph_generated.py`: a generated «own graph» part converts to a
  root with `rp_dependent_on`, the whole-end role required single over the whole; no whole-end role
  → problem; multiplicity `0..1` or `*` → problem; a part-end role → report line, no slot on the
  whole; `rp-generate` accepts the output. Then `rdf_persistence_generation/uml/links.py`,
  `rdf_persistence_generation/uml/classes.py`. Accept: every row passes; the refusal test is gone.
- [x] 3.3 Feature: scenario 12 of
  `openspec/changes/dependent-aggregates/features/dependent_aggregates_generation.feature` into
  `tests/generator/feature/dependent_aggregates_generation.feature`, verbatim. Lane `make
  test-generator`. Accept: it passes.
- [x] 3.4 Docs: `docs/modules/ROOT/pages/howto/uml-to-linkml.adoc` («own graph» generated part,
  snippet and LinkML). Accept: `make check-docs` passes.
- [ ] 3.5 Lead: `make check-all`; review; PR; the consumer told the change id (D-12). Accept: gates
  green; no Critical open.

## Roadmap

1.1 · 1.2 · (1.3 ∥ 1.4) · 1.5 · 1.6 · 1.7 · 1.8 → 2.1 · 2.2 · 2.3 · 2.4 · 2.5a · 2.5 · (2.7 ∥ 2.8) ·
2.6 · 2.9 · 2.10 · 2.11 → 3.1 · 3.2 · 3.3 · 3.4 · 3.5

## Verification

`make check-all`, `make test-containers` (stage 2), `make check-generated`, `openspec validate
dependent-aggregates --strict`; the clarity gate in `evidence/clarity-gate.md`; each spec scenario
shown in `evidence/acceptance.md`.
