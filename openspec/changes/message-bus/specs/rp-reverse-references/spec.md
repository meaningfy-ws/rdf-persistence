<!-- Capability: rp-reverse-references. Change: message-bus (DEC-13; design.md PD-11). -->

## MODIFIED Requirements

### Requirement: A session lists the referrers of a resource

A collaboration SHALL return (a collaboration is the access-aware service the kit opens over a
session for an authorised caller), through `referrers(iri)`, every aggregate of the tenant whose stored triples refer
to `iri`, each with the referrer's IRI, its class and the slot that refers, read across the
aggregate graphs of the tenant database by the toolkit. The link that makes a comment depend on
`iri` (its target) SHALL NOT count: a comment is deleted with `iri`. Activity records, a
transition's among them, are not aggregates and SHALL NOT be listed. The caller SHALL need `read` on `iri`. A referrer that refers by
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
