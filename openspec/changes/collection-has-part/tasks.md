> Derives from: EPIC `collection-has-part` (proposal.md, #199). Decisions: DEC-1 to DEC-4, design.md PD-1 to PD-10.

<!-- PLAN (tasks half). One stage. Every task: the failing test first, in its tier; task gate
     `make test-fast check-quality` (the toolkit's schema and a services reader change); commit body
     `Refs: collection-has-part <task> <PD>`. Builders never commit; the lead does. -->

## 1. Stage 1: membership with dct:hasPart

- [x] 1.1 Rename (PD-1, PD-4, PD-8, PD-9, PD-10). Tests first: TC-7 and TC-8 (unit), failing.
  Then `rp_collections.yaml` per PD-1 and PD-8 (`dcmitype:Collection`), `HAS_PART` in
  `vocabulary.py`, `reference_collections.py` and `write_guards.py`, the 10 test files of the
  design's table (`had_member` → `has_part`, the referrer test renamed `..._by_has_part_...` and its
  `scenario-map.csv` row rewritten with Edit before `make refresh-map`), `make generate`, the toy
  lock per PD-9, `make refresh-snapshot`, `make refresh-served-golden`, `test_combined_artefacts`
  per PD-10. Accept: TC-7, TC-8 pass; `grep -rnI "had_member\|hadMember\|HAD_MEMBER" rdf_persistence
  rdf_persistence_generation tests docs/modules` lists only `tests/fixtures/v0_6_0/` frames (if kept)
  and `.test_durations`; `make check-freshness` passes.
- [x] 1.2 Migration (PD-2, PD-3), after 1.1. Tests first: TC-1 to TC-6 and TC-10 (unit), failing.
  Then `2__3.yaml` exactly as PD-2, `rp.yaml` `version: "3"`, `make generate` (the toolkit lock's
  `schema_version` only), and the toolkit-version tests of the design's table (`("1", "2", "3")`,
  `RP: "3"`, the feature's "version 3 of the toolkit's own schema"). Accept: the seven tests pass;
  `git status` shows no drafted file besides `2__3.yaml`; spec scenarios "stored collections are
  migrated" and "a dump at version 2 is restored" pass as TC-2 and TC-10.
- [x] 1.3 Consumer path (PD-5, RISK-5). TC-9 in `tests/generator/unit/test_lock_step.py` is a
  characterisation test: it pins today's lock behaviour, needs no production change and so passes
  on its first run (the exception to "failing test first"). Accept: TC-9 passes, and the builder
  shows it fail once by leaving the planted lock at `dcterms:hasPart`, reported.
- [x] 1.4 IT-1 (integration) in `tests/integration/store/test_migration_requests.py`, written by
  the builder, run by the lead in `make test-containers`. Accept: IT-1 passes on Fuseki.
- [x] 1.5 Docs and release note (PD-6, RISK-2). `howto/reference-collections.adoc` (slot table,
  three examples, the two lines at 251-253, one sentence: reuse `has_part` for any other
  `dct:hasPart`), `architecture/generation.adoc:73` (slot, predicate and `dcmitype:Collection`), the `CHANGELOG.md` entry exactly as PD-6
  lists. Accept: `make check-docs` passes; the entry names every item of PD-6.
- [x] 1.6 Lead: `make check-all`, `make test-containers`, `make check-generated`; one review pass
  (SMALL set); open the follow-up issue of RISK-2; PR titled `feat(collections)!: ...` with a
  `BREAKING CHANGE:` footer; tell the consumer's `v2-02` that the toolkit change landed (D-12).

## Roadmap

- [x] 1.1 · [x] 1.2 · [x] 1.3 · [x] 1.4 · [x] 1.5 · [x] 1.6 (1.3, 1.4 and 1.5 may run in parallel after 1.2)

## Verification

The spec delta's three scenarios pass as TC-7, TC-2, TC-10 (and IT-1 on Fuseki); `make check-all`,
`make test-containers`, `make check-generated` green; `openspec validate collection-has-part --strict`.
