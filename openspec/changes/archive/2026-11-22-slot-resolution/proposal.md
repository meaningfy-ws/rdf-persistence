<!-- Parents: issues #277, #278 (inputs/seed.md); openspec/specs/rp-generation,
     rp-schema-migrations. Serves: MWB2 v2-02 phase B, mapping-workbench-v2 PR #101 (D-12).
     Recorded after delivery (PR #289): the work ran as a bug fix outside an EPIC. -->

# EPIC: Resolve slots by owner and IRI

## Appetite

**SMALL.** Two defects in how a slot or a property is resolved to the toolkit's own slots: a
generator extension, the lock diff, the schema loader and one hard rule. One PR, one commit per
issue.

Recorded after delivery on the owner's request (2026-11-22). The work ran as a bug fix outside an
EPIC, with its decisions in PR #289. This EPIC and its PLAN record what was shaped and built, so the
change has its place in the spine.

## Why

Two slots of the toolkit got in the way of the application's own:

- The toolkit's identifier slot `id` has `slot_uri: dcterms:identifier`. A business identifier on
  the same property (a string) was refused as "not an IRI" (#277).
- The toolkit's internal `version` shares one LinkML namespace of slot names with the application.
  A module's own `version` resolved to the toolkit's by import order: the value was dropped
  silently, or every write was refused because the context and the shapes disagreed (#278).

Both block MWB2's `v2-02` phase B. Its projects, packages and source elements carry a business
`identifier`, and its packages carry a `version`.

## Solution outline

- **The identifier is never a property.** Its value is the node's IRI, never a statement. No
  shape, lock entry or referrer name treats it as one.
- **A slot name resolves to its owner's slot.** Where an application slot takes the name of a
  toolkit slot that no toolkit class carries, the application's slot wins in every view: the
  runtime, the shapes, the context and the components, whatever the import order.
- **A true clash is refused.** Where a toolkit class carries the toolkit slot, the generator
  refuses the application slot with a hard rule naming both definitions. Data is never dropped
  silently.

## Key decisions

- **DEC-1:** the identifier slot takes no part in resolving a property (the issue's first option,
  and the converter's DEC-4). Rejected: refusing a business slot on `dcterms:identifier`, which a
  consumer's model needs.
- **DEC-2:** an uncarried toolkit slot gives way to the application's slot of the same name; a
  carried one is a hard-check refusal (`toolkit_slot_name`). Rejected: renaming the toolkit's
  internal slots, which changes the public metamodel and only moves the clash.
- **DEC-3:** the resolution happens once, in the schema loader every reader goes through
  (`load_schema`, and `apply_defaults` for the stock generators' views). Rejected: patching each
  generator and the mapper apart, which is how the context and the shapes came to disagree.

## Rabbit-holes

- Stock generators build their own views and merge imports their own way; each must resolve as
  the runtime does.
- A slot shared by two definitions in the lock: the diff must not read a second slot on one IRI as
  a range change.

## No-gos

- No rename of a toolkit slot.
- No change to how a toolkit class carries its slots.
- No resolution of class names (only slots).

---

## What Changes

- Shapes: the identifier slot's property shape goes; the node stays `sh:nodeKind sh:IRI`.
- Lock: slots that share an IRI are paired, not collapsed.
- Referrer naming: the identifier slot never names a predicate.
- Schema loading: `prefer_application_slots` in `load_schema` and `apply_defaults`.
- Hard check: the rule `toolkit_slot_name`.
- Closed shapes ignore the session's predicates by IRI.
- The toy's `Template` carries a business `identifier` and its own `version`.

## Capabilities

### Modified Capabilities

- `rp-generation`: the identifier is never a property; a slot name resolves to the application's
  slot; a clash with a carried toolkit slot is refused.
- `rp-schema-migrations`: slots that share an IRI are locked apart.

## Impact

Generator (shapes extension, lock, hard check), library (schema loader, referrer naming), the toy,
`architecture/generation.adoc`. For a consumer: after the bump, `rp-generate` changes its shapes,
context and lock, and a slot that clashes with a carried toolkit slot is now refused.

## As built

Delivered in PR #289, merged as `13af7af2` on 2026-11-22: commit `55932696` (#277) and commit
`d8fbd245` (#278). The delivery decisions are D-1 to D-7 in `design.md`.

- Every outline item was built as shaped.
- The identifier's property shape is found by its `sh:order` (D-4), a coupling to the stock
  generator that the #277 test guards.
- The review's minor points were left as they are and are listed in `design.md`.
- Found on the way, fixed apart: `make refresh-map` collected no node ids since pytest.ini's
  addopts gained `-q` (PR from `fix/refresh-map-collect`).
