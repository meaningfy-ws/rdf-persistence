<!-- Secondary input, never groomed: GitHub issue #198 (meaningfy-ws/rdf-persistence), fetched 2026-11-20. The EPIC (../proposal.md) supersedes it. -->

# #198 Reference collections that nest sub-collections of the same kind

## Summary

A reference collection collects aggregates of exactly one `member_class` (or classes derived from
it). A collection that holds **items and sub-collections of the same kind together** (a folder-like
tree: files and folders of files) cannot be expressed: a collection of collections must have the
collection class as its member class, and then it cannot also name items.

## Context

- Consumer: Mapping Workbench 2, change `v2-02-model-from-ea` (generating LinkML from its UML model)
  and `v2-03-project-and-resources` (collections of resources); toolkit read at `origin/develop`
  `c671fefb` (`rdf_persistence/model/rp_collections.yaml`, `howto/reference-collections.adoc`).
- The consumer's users organise items in collections that are flat, few, hierarchical and
  overlapping (a collection of items that also contains sub-collections of the same kind of item).

## Current behaviour

```python
collab.create(Shelf, member_class="Book", had_member=[b1, sub_shelf])
# InvalidBody: sub_shelf is stored and is not of the member class
```

`member_class` is one required string; a member of another class is refused (`InvalidBody`), and a
membership rule matches exactly the member class.

## Proposed capability

Let a collection also hold sub-collections of its own class (or name several member classes):

```yaml
# option A (recommended): nesting of the same collection class
member_class: Book
nests: true                 # had_member may also name collections of this class whose member_class is Book

# option B: several member classes
member_classes: [Book, Shelf]
```

`members` / `collections_of` / `delete_cascade` treat a nested collection as a member; a cycle (a
collection that contains itself, directly or through nested ones) is refused, naming the cycle.

```python
poetry = collab.create(Shelf, member_class="Book", nests=True, had_member=[b1, b2])
library = collab.create(Shelf, member_class="Book", nests=True, had_member=[b3, poetry.id])
collab.members(library, transitive=True)   # b3, b1, b2
```

## Why it belongs in rdf-persistence

Reference collections are the toolkit's; any application organising items in folders needs nesting,
and the cycle check, cascade and access counting (`hidden_count`) must be the toolkit's to stay
consistent.

## Acceptance

- **Given** a nesting collection of `Book` with a book and a nested collection of `Book`, **when** it
  is saved, **then** it is accepted, and `members(transitive=True)` lists the books of both.
- **Given** a collection that would contain itself through a nested one, **when** it is saved,
  **then** it is refused with `InvalidBody` naming the cycle.
- **Given** a nested collection of another member class, **when** it is saved, **then** it is refused,
  as today for a member of the wrong class.
- **Given** a collection without nesting, **then** the behaviour is unchanged.

## Impact on the consumer

Flat collections work today; hierarchical collections (a resource collection with sub-collections)
wait for this. The consumer does not nest collections by its own means meanwhile.


## Comments

