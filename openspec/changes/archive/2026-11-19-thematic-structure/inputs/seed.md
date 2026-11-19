<!-- SECONDARY INPUT: preserved, never groomed. The EPIC (../proposal.md) is the shaped truth. -->

# Seed: thematic structure (from the manual-revision-notes initiative)

This change was sliced out of the `manual-revision-notes` initiative on 2026-11-17. Its seeds live
there and are not copied:

- [`../../manual-revision-notes/inputs/seed.md`](../../manual-revision-notes/inputs/seed.md): the
  developer's notes, verbatim; the paragraph "inside the model folder I am surprised to see models
  that are under /adapters and under /services ..." is this change's seed.
- [`../../manual-revision-notes/inputs/answers-2026-11-17.md`](../../manual-revision-notes/inputs/answers-2026-11-17.md):
  Q-2 ("we must separate the technical and the domain models") and the slicing: this change is
  5th of 5, VERY LARGE, staged.
- [`../../manual-revision-notes/inputs/improvements.md`](../../manual-revision-notes/inputs/improvements.md):
  the ids this change owns, **E-1 to E-6**, and **Q-2 at the package level**.
- [`../../manual-revision-notes/inputs/analysis.md`](../../manual-revision-notes/inputs/analysis.md)
  §2.1 (FusekiStore), §2.3 (the IRI wrappers), §5.3 (the thematic map and its constraints).
- [`../../manual-revision-notes/inputs/keep.md`](../../manual-revision-notes/inputs/keep.md):
  "Structure and generation that stay".

## What the shaping checked against the code (2026-11-17, `docs/manual-revision-notes`)

| Claim of the seeds | Found | Where it went |
|---|---|---|
| The theme graph of the hand-written modules is acyclic | Holds for the 61 modules (computed with grimp over the import graph). There are 13 themes with the kernel, not 12 | DEC-1 |
| The generated code can mirror the themes | Not for the metamodel: `rp_tenancy.py` imports `rp_access.py`, `rp_files.py` imports `rp_provenance.py`, and `services.vocabulary` (schema), `services.access` (access) and `services.schema_structure` (schema) use `TenantState`, `TenantAccess` and `StoredFile`. Placed by theme, they make the cycles access↔tenancy, schema↔tenancy and schema→files→provenance→schema | DEC-2 |
| The consumer imports 5 modules | It imports 3 in hand-written code (`rdf_persistence` 33 times, `.testkit` 8, `.testkit.fakes` 1). The 5 `domain.base` imports are its **generated** files (the template emits them); the one `adapters.fuseki` line is a string planted in its own test of `assert_public_imports` | DEC-5 |
| The `iris.py` wrappers only delegate to `DEFAULT_IRIS` | 11 of the 23 functions at `iris.py:57-205` do; no runtime module calls them, only `__init__` re-exports `mint_aggregate_iri`. The other 12 are policy-free layout functions used by 7 runtime modules | DEC-8 |
| The 141-name re-export | Holds (`len(rdf_persistence.__all__) == 141`) | DEC-5 |
