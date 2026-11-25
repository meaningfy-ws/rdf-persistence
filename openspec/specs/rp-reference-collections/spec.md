# rp-reference-collections Specification

## Purpose
An aggregate that groups other aggregates of one class without owning them, by name or by a rule:
how its members are checked on write, listed for a caller, and deleted with it on request.

## Requirements

### Requirement: A reference collection holds typed references it does not own

The metamodel SHALL provide a reference collection class (a `dcmitype:Collection`) that an
application uses as an aggregate root or mixes into one. A collection SHALL name the class of its
members and SHALL hold references (`dct:hasPart`) to aggregates of the same tenant, never their
triples. Saving a collection with a member of another class, or with an IRI the IRI policy does
not mint for the tenant, SHALL be refused and nothing SHALL be stored.

#### Scenario: a shelf of books
- **WHEN** a session saves a collection of class `Book` naming two stored books
- **THEN** reading the collection returns both IRIs, and each book's graph is unchanged

#### Scenario: a member of the wrong class
- **WHEN** a session saves a collection of class `Book` naming a shelf
- **THEN** the save is refused as invalid and the collection is not stored

### Requirement: Membership can be given by a stored rule

A collection SHALL accept, instead of or beside explicit members, a stored rule made of a class
and slot equalities, the same shape `session.find` takes. Its members SHALL be computed on every
read as the aggregates of the tenant that match the rule, together with the explicit members.
A member the caller may not `read` SHALL NOT be listed: one named explicitly SHALL be counted as
hidden; one that only matches the rule SHALL NOT be counted either, so that a rule cannot be used
to count the aggregates hidden from its author.

#### Scenario: a rule does not count what its author may not read
- **GIVEN** a collection whose rule matches two books, and a principal holding `read` on only one of them
- **WHEN** that principal reads the members of the collection
- **THEN** it gets the one book it may read and a hidden count of zero

#### Scenario: a new matching book appears
- **GIVEN** a collection whose rule is class `Book` with `genre` equal to `poetry`
- **WHEN** a poetry book is saved and the collection is read again
- **THEN** the new book is among its members

### Requirement: Collections can contain collections

A collection SHALL accept other collections as members when its member class is the collection
class. A deep read SHALL return the members of the nested collections as well, visiting each
collection once, so that a cycle ends the walk instead of repeating it.

#### Scenario: nested shelves
- **GIVEN** collection A containing collection B, and B containing book b
- **WHEN** a session reads A deeply
- **THEN** b is among the members

#### Scenario: a cycle
- **GIVEN** collection A containing B and B containing A
- **WHEN** a session reads A deeply
- **THEN** the read ends and lists A's and B's own members once each

### Requirement: Deleting a collection keeps its members unless a cascade is asked for

Deleting a collection SHALL delete only the collection. A delete with an explicit cascade SHALL
also delete every member as resolved at that moment (explicit, and by rule those the caller may
`read`; a nested collection is deleted as a member, its own members kept), and only if the caller
may `delete` every one of them,
none was replaced after its version was read for the cascade (one that another writer removed
meanwhile is skipped or refuses the cascade, and is gone either way), and each member that only matches the
rule still matches it when the delete is applied; otherwise nothing SHALL be deleted. A refusal
for the right to delete SHALL name the members that caused it which the caller may read and count
the other named members. An aggregate that only matches the rule and that the caller may not
`read` SHALL NOT be deleted and SHALL NOT cause a refusal, so that a refusal cannot tell the
author of a rule that something hidden matches it. A refusal because a member changed SHALL name it; one because a member stopped matching the rule
MAY name no member. A cascade SHALL delete only stored aggregates of the collection's member
class, and SHALL refuse the tenant root.

#### Scenario: a plain delete
- **GIVEN** a collection with two books
- **WHEN** a session deletes the collection
- **THEN** the collection is gone and both books still exist

#### Scenario: a cascade refused for one member
- **GIVEN** a collection with books b1 and b2, and a caller who may delete b1 but not b2
- **WHEN** the caller deletes the collection with cascade
- **THEN** nothing is deleted and the refusal names b2

### Requirement: A collaboration lists the collections a resource belongs to

A collaboration SHALL return, through `collections_of(iri)`, the collections of the tenant that hold
`iri` explicitly or by their rule, filtered by the caller's `read` access with the others counted
as hidden, as for referrers.

#### Scenario: by list and by rule
- **GIVEN** a poetry book listed in collection A and matched by the rule of collection B
- **WHEN** a session lists the collections of the book
- **THEN** it gets A and B

### Requirement: Collections state their members with dct:hasPart

A reference collection SHALL state each member it names with `dct:hasPart` (slot `has_part`), and
SHALL NOT state `prov:hadMember`. Every collection service (`members`, `collections_of`,
`delete_cascade`, `referrers`) and access counting SHALL read membership through `dct:hasPart`.

#### Scenario: members are stated with dct:hasPart
- **GIVEN** a collection class
- **WHEN** a collection is saved with two members
- **THEN** its graph states `dct:hasPart` twice and no `prov:hadMember`, and `members`,
  `collections_of`, `delete_cascade` and `referrers` find both

#### Scenario: stored collections are migrated
- **GIVEN** a tenant at schema version 2 holding a collection stated with `prov:hadMember`
- **WHEN** the migration to version 3 runs
- **THEN** the collection states `dct:hasPart` for the same members and the services find them

#### Scenario: a dump at version 2 is restored
- **GIVEN** a dump of a tenant taken at the toolkit's schema version 2, holding a collection stated with `prov:hadMember`
- **WHEN** it is restored into a service at version 3
- **THEN** the new tenant's collection states `dct:hasPart` for the same members and `members` lists them

### Requirement: A collection may nest collections of its own kind

A collection with `nests: true` SHALL accept as members collections of exactly the same collection
class and `member_class`, which may themselves have `nests` false. It SHALL refuse a cycle with
`InvalidBody` naming the saved collection and the member that closes the cycle, and counting the
collections between without naming them; a save that loses a race which would otherwise store a
cycle SHALL be refused with a conflict. The member class of a collection that a nesting collection
of its class holds SHALL NOT change. `members(deep=True)` SHALL list the items of the whole tree, without the
nested collections themselves. (The issue's `transitive=True` is written `deep=True`: the existing
flag is kept so that no caller breaks.) A collection whose member class is itself a collection
class SHALL NOT set `nests`. A collection without `nests` SHALL behave as before.

#### Scenario: a nested collection
- **GIVEN** a nesting collection of `Book` holding a book and a nested collection of `Book`
- **WHEN** it is saved
- **THEN** it is accepted, and `members(deep=True)` lists the books of both

#### Scenario: a deep read lists no sub-collections
- **GIVEN** a nesting collection of `Book` holding book b1 and a nested collection S holding book b2
- **WHEN** a session reads its members with `deep=True`
- **THEN** it gets b1 and b2, and not S

#### Scenario: a cycle
- **GIVEN** a collection that would contain itself through a nested one
- **WHEN** it is saved
- **THEN** it is refused with `InvalidBody` naming the collection and the member that closes the
  cycle, and counting the collections between without naming them

#### Scenario: a held collection's member class
- **GIVEN** a collection of `Book` that a nesting collection of `Book` holds
- **WHEN** it is saved with another member class
- **THEN** it is refused with `InvalidBody` that does not name the holder

#### Scenario: racing saves
- **GIVEN** two saves read before either commits, one adding collection B to A and one adding A to B
- **WHEN** both commit
- **THEN** one succeeds and the other is refused with a conflict, and no cycle is stored

#### Scenario: a leaf race
- **GIVEN** a save adding collection N, which does not nest, to C, and a racing save that makes N nest and adds C to it, read before either commits
- **WHEN** the racing save commits first and then the other
- **THEN** the second is refused with a conflict naming N, and no cycle is stored

#### Scenario: a hidden level
- **GIVEN** a nesting collection holding a nested collection the reader may not read
- **WHEN** the reader lists the members with `deep=True`
- **THEN** the nested collection is counted once in the hidden count and its members are neither listed nor counted

#### Scenario: another member class
- **GIVEN** a nested collection whose member class is not `Book`
- **WHEN** it is saved
- **THEN** it is refused as a member of the wrong class

#### Scenario: nesting over a collection member class
- **GIVEN** a collection whose member class is itself a collection class
- **WHEN** it is saved with `nests: true`
- **THEN** it is refused with `InvalidBody`

### Requirement: A membership rule names slots of the member class only

A membership rule's equality SHALL name a slot of the member class itself. An equality whose slot
is a path through references (`<reference>.<slot>`) SHALL be refused when the collection is
written, and a stored rule holding one SHALL be reported as invalid stored data, so that no path
condition reaches `matches` or the commit guard.

#### Scenario: a rule through a reference
- **WHEN** a caller writes a collection whose membership rule has the equality `written_by.label = Frank Herbert`
- **THEN** the write is refused as an invalid body and nothing is stored
