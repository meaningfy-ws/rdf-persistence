<!-- Parents: issue #199 (inputs/seed.md); openspec/specs/rp-reference-collections;
     rp-schema-migrations ("A schema change that stored data must follow needs a new version and a
     migration"). Serves: MWB2 v2-02 task 2.1b, v2-03 and v2-05 collections (D-12).
     Seeds: inputs/seed.md, inputs/qa.md. -->

# EPIC: Reference collections state their members with dct:hasPart

## Appetite

**SMALL.** One capability (reference collections) touched in a few places: the model slot, the
vocabulary constant, the services that read it, and one schema migration.

## Why

Collections state membership with `prov:hadMember`. Applications that keep PROV for provenance and
model part-whole with DCT cannot use the toolkit's collections. The first consumer's five
collection classes wait for this, so it comes right after the UML converter and can run in
parallel with it.

## Solution outline

Membership is `dct:hasPart` everywhere, for every application. The `rp_collections` slot becomes
`has_part` (`slot_uri: dcterms:hasPart`). Every reader follows from the model through
`vocabulary.predicate`: `members`, `collections_of`, `delete_cascade`, `referrers`, the write
guards and access counting. Stored data moves with a schema migration (version 2 → 3) that rewrites
`prov:hadMember` to `dcterms:hasPart` in collection graphs. The tutorial and how-to follow.

## Key decisions

- **DEC-1:** one membership property, `dct:hasPart`, for all applications, with no per-class
  choice. Source: owner, 2026-11-20 ("always and everywhere"). Rejected: a `member_property`
  annotation (the generated JSON-LD context and types would disagree with the stored triples), and
  an app-declared sub-slot (two membership slots on one class).
- **DEC-2:** the slot is renamed `had_member` → `has_part`, so the Python, JSON and TypeScript names
  match the predicate. **BREAKING** for callers that use `had_member=`. The toolkit is pre-1.0 and
  the release notes state it. Rejected: keeping the old name over a new IRI.
- **DEC-3:** stored data is migrated through the existing schema-migration mechanism, not left
  behind. Rejected: "no data moved" (as in `1__2`), because collections are live data that the
  services read.
- **DEC-4:** the collection class (the `ReferenceCollection` mixin's `class_uri`) is
  `dcmitype:Collection`, not `prov:Collection`; decided by the owner 2026-11-20 (OQ-1, raised as
  OPEN-1 in the PLAN; `inputs/qa.md` item 2). No stored graph carries the mixin's type, so no data
  moves for it (design.md F-6). Rejected: keeping `prov:Collection`.

## Rabbit-holes

- OQ-1, the class type `prov:Collection`: settled by DEC-4 (2026-11-20).
- Generated artefacts carry the old name in many places (shapes, context, frames, TS, OpenAPI):
  `make generate` regenerates them, never a hand edit.

## No-gos

- No per-class or per-application choice of membership property.
- No change to membership rules, nesting (`nested-collections`) or cascade semantics.
- No dual reading of both predicates after the migration.

---

## What Changes

- **BREAKING** `rp_collections.yaml`: `had_member` → `has_part`, `slot_uri: dcterms:hasPart`.
- `vocabulary.HAD_MEMBER` → `HAS_PART`; `reference_collections.py` and `write_guards.py` follow.
- Migration `2__3.yaml` with a step that rewrites the predicate in collection graphs.
- Docs: `howto/reference-collections.adoc`, the tutorial, release notes.

## Capabilities

### Modified Capabilities

- `rp-reference-collections`: members are stated with `dct:hasPart`; the class is
  `dcmitype:Collection` (DEC-4).

`rp-schema-migrations` was listed here at shaping and removed on 2026-11-20 at the PLAN review: its
mechanism is unchanged and version 3 is an instance of its requirements, so it has no delta
(design.md PD-7).

## Impact

Library model, collaboration services, generated artefacts, the consumer's lock (`v2-02` regenerates
against the new slot name).
