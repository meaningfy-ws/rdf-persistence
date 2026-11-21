# rp-reverse-references Specification

## Purpose
Listing the aggregates of a tenant that reference a given one, where what the caller may not read
is counted and never named.

## Requirements

### Requirement: A session lists the referrers of a resource

A collaboration SHALL return (a collaboration is the access-aware service the kit opens over a
session for an authorised caller), through `referrers(iri)`, every aggregate of the tenant whose stored triples refer
to `iri`, each with the referrer's IRI, its class and the slot that refers, read across the
aggregate graphs of the tenant database by the toolkit. The link that makes a comment depend on
`iri` (its target) SHALL NOT count: a comment is deleted with `iri`. Activity records, a
transition's among them, are not aggregates and SHALL NOT be listed; a transition record stored
before this change (`rp:TransitionRecord`) is an ordinary aggregate and SHALL be listed like any
other. The caller SHALL need `read` on `iri`. A referrer that refers by
several slots SHALL be listed once per slot. The call SHALL accept an optional class and an
optional slot that narrow the result. An IRI the IRI policy does not mint for the tenant SHALL be
refused as invalid; an IRI nothing refers to SHALL give an empty result.

#### Scenario: two books on the same shelf
- **GIVEN** two books whose `shelf` slot refers to shelf s, and a third book on another shelf
- **WHEN** a session lists the referrers of s
- **THEN** it gets exactly the two books, each with class `Book` and slot `shelf`

#### Scenario: narrowed by slot
- **GIVEN** a book whose `sequel_of` refers to book b and a note whose `about` refers to book b
- **WHEN** a session lists the referrers of b with slot `sequel_of`
- **THEN** it gets only the book

#### Scenario: an unused resource
- **WHEN** a session lists the referrers of a shelf that no aggregate refers to
- **THEN** it gets an empty list and a hidden count of zero

### Requirement: Referrers the caller may not read are counted, not listed

The result SHALL list only referrers the caller may `read`, as the access check decides for the
session's principal, and SHALL report the number of the other referring aggregates (each counted
once, whatever its slots) as a hidden count, without their IRIs, classes or slots. The hidden
count SHALL be the same whatever class or slot the call narrows by, so that narrowing cannot
reveal the class or slot of a hidden referrer. A comment is
readable as a referrer only when the caller may read its target and would see it in the
target's thread.

#### Scenario: a hidden referrer
- **GIVEN** two books on shelf s, and a principal holding `read` on only one of them
- **WHEN** that principal lists the referrers of s
- **THEN** it gets the one book it may read and a hidden count of one

#### Scenario: narrowing does not change the hidden count
- **GIVEN** two books on shelf s, and a principal holding `read` on only one of them
- **WHEN** that principal lists the referrers of s narrowed to a class or slot the hidden book does not have
- **THEN** it gets no hidden book's class or slot, and the hidden count is still one

### Requirement: A class may refuse deletion while referenced

A class annotated `rp_on_referenced_delete: refuse` SHALL have the generic delete and
`session.remove` refuse to delete an aggregate that other aggregates reference, inside the delete's
transaction, with `409` problem `in-use` (`InUse` in-process) naming the readable referrers and
counting the unreadable ones. A class without the annotation SHALL behave as before.

#### Scenario: a referenced aggregate
- **GIVEN** `Author` annotated `refuse` and a `Book` referring to it
- **WHEN** a caller deletes the author
- **THEN** the answer is 409 `in-use` naming the book, and the author remains

#### Scenario: only an unreadable referrer
- **GIVEN** the only referrer is unreadable to the caller
- **WHEN** the caller deletes
- **THEN** the answer is 409 with `hidden_count: 1` and no referrer named

#### Scenario: no referrer
- **WHEN** an unreferenced author is deleted
- **THEN** the answer is 204

#### Scenario: a cascade over a referenced member
- **GIVEN** a collection of `Author`s naming an author that a `Book` refers to
- **WHEN** a caller deletes the collection with its members (`delete_cascade`)
- **THEN** `InUse` names the author and the book, and neither the collection nor any member is deleted

#### Scenario: a cascade whose only referrers go with it
- **GIVEN** a collection of `Author`s naming an author that nothing else refers to
- **WHEN** a caller deletes the collection with its members
- **THEN** the collection and the author are deleted

#### Scenario: opt-in only
- **GIVEN** a class without the annotation and a referrer
- **WHEN** it is deleted
- **THEN** it is deleted as before
