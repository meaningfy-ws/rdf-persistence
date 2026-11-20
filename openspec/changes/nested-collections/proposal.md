<!-- Parents: issue #198 (inputs/seed.md); openspec/specs/rp-reference-collections ("Collections
     can contain collections"). Depends on: collection-has-part (the membership slot it extends).
     Serves: MWB2 v2-03-project-and-resources task 7.2 (D-12). Seeds: inputs/seed.md;
     owner's answer of 2026-11-20 (option A). -->

# EPIC: Collections that nest sub-collections of the same kind

## Appetite

**SMALL.** One flag on the existing collection, plus a cycle check and a transitive walk in the
existing services.

## Why

A collection cannot hold both items and sub-collections of the same kind (a folder tree). The
consumer's hierarchical resource collections need this before `v2-03`'s last stage. Flat
collections work without it.

## Solution outline

An optional slot `nests` (boolean, default false) on `ReferenceCollection`. When it is true, a
member may also be a collection of the same collection class with the same `member_class`. Saving
refuses a cycle (a collection that contains itself directly or through nested ones) with
`InvalidBody` naming the cycle. It refuses a nested collection of another member class, as it does
today for any member of the wrong class. `members(deep=True)` lists the items of the whole
tree (the existing flag keeps its name; owner, 2026-11-20, `inputs/qa.md`). `collections_of` and `delete_cascade` treat a nested collection as a member.

## Key decisions

- **DEC-1:** nesting of the same collection class and member class only (option A of the issue).
  Source: owner, 2026-11-20. Rejected: a list of member classes (option B), which touches
  membership rules and access counting more.
- **DEC-2:** the cycle check runs in the save's transaction. Rejected: a check after the commit.
- **DEC-3:** built on `collection-has-part`'s `has_part` slot and delivered after it.

## Rabbit-holes

- How deep a transitive walk can go: one SPARQL property path is preferred over a walk in Python.
  `hidden_count` must still count unreadable members at every level.
- `delete_cascade` on a tree: whether it descends into nested collections is the PLAN's question for
  the owner (default: it deletes only the direct members, as today).

## No-gos

- No mixed member classes, no nesting across collection classes.
- No ordering of members, no "move" operation.
- No change to flat collections' behaviour.

---

## What Changes

- `rp_collections.yaml`: `nests` slot.
- Collection services: the nested-member check, the cycle check, `members(deep=…)` over nested collections.

## Capabilities

### Modified Capabilities

- `rp-reference-collections`: a collection may nest collections of its own kind.

## Impact

Library model and collaboration services; generated artefacts; how-to page.
