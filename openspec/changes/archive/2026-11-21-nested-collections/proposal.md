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
- Delivered as well: the member class of a collection a nesting collection holds cannot change
  (review C-1).
- Delivered as well: the persistence port. `WriteGuard.prepare` takes a keyword-only
  `context: GuardContext` (the triples collected earlier in the transaction, and `rely_on`, which
  adds a version guard to the commit). `graphs_with` takes a literal object.

## Capabilities

### Modified Capabilities

- `rp-reference-collections`: a collection may nest collections of its own kind.

## Impact

Library model and collaboration services; generated artefacts; how-to page. As delivered, also:
the persistence port (`WriteGuard`, `Transaction`), which is internal (not exported, no public
surface change); and the architecture pages (`data-flows.adoc`, `index.adoc`).

## Delivery reconciliation

What was delivered against this shape (rule P-0004), added after the archive because it was missed
before the last merge. The decisions are in [design.md](design.md#delivery-decisions); this table
only names them.

| Shaped | Delivered | Why | Decision | PR |
|---|---|---|---|---|
| One SPARQL property path for the transitive walk (Rabbit-holes, preferred) | A breadth-first read for `members(deep=True)`, and one read of the tenant's nesting collections walked in memory for the cycle check | Each collection's membership is in its own named graph and the store has no union default graph, so a path stops at the first graph | PD-11 | #234 |
| `members(..., transitive=True)` | `members(..., deep=True)`, the existing flag | No caller breaks (owner, OPEN-2) | PD-6 | #234 |
| A cycle refused "with `InvalidBody` naming the cycle" | The refusal names the saved collection and the member that closes the cycle, and counts the others | The collections between may be hidden from the saver | PD-7 | #234 |
| The cycle check in the save's transaction (DEC-2) | As shaped. Every collection the walk reached is also guarded at the version it was read, through a new port argument (`GuardContext.rely_on`). A racing save gets a `Conflict` naming the collection that changed | Without the guards, two racing saves could together store a cycle | PD-4, PD-5, PD-9, D-3 (T-1) | #234 |
| Not shaped | The member class of a collection a nesting collection holds cannot change. A nesting collection that changes its own member class has its nested members checked again | A guarded save could otherwise break the parent's deep reads and later saves | D-4 (C-1), D-5 | #234 |
| No stored cycle, racing or not (G-2) | Holds for cycles. One race is not closed: a member-class change of a collection, racing a save that makes a nesting collection hold it, can commit both when the holder commits first | Version guards cannot state that a holder is absent | D-5 | #235 |
| `delete_cascade` on a tree (Rabbit-holes, the owner's question) | Direct members only; a sub-collection is deleted as a member and its own members are kept | Owner, OPEN-1 | PD-8 | #234 |
