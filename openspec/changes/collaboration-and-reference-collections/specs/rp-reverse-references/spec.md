<!-- Capability: rp-reverse-references. Change: collaboration-and-reference-collections (GitHub issue #78). -->

## ADDED Requirements

### Requirement: A session lists the referrers of a resource

A collaboration SHALL return (a collaboration is the access-aware service the kit opens over a
session for an authorised caller), through `referrers(iri)`, every aggregate of the tenant whose stored triples refer
to `iri`, each with the referrer's IRI, its class and the slot that refers, read across the
aggregate graphs of the tenant database by the toolkit. The links that make a comment or a
transition record depend on `iri` (its target, the aggregate it was made on) SHALL NOT count:
those records are deleted with `iri`. The caller SHALL need `read` on `iri`. A referrer that refers by
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
