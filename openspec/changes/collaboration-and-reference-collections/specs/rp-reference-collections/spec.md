<!-- Capability: rp-reference-collections. Change: collaboration-and-reference-collections (GitHub issue #79). -->

## ADDED Requirements

### Requirement: A reference collection holds typed references it does not own

The metamodel SHALL provide a reference collection class (a `prov:Collection`) that an
application uses as an aggregate root or mixes into one. A collection SHALL name the class of its
members and SHALL hold references (`prov:hadMember`) to aggregates of the same tenant, never their
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
also delete every member as resolved at that moment (explicit and by rule; a nested collection is
deleted as a member, its own members kept), and only if the caller may `delete` every one of them
and none changed since it was resolved; otherwise nothing SHALL be deleted and the refusal SHALL
name the members that caused it which the caller may read, and count the others.

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
