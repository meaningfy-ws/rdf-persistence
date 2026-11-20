## ADDED Requirements

### Requirement: A delete refused while referenced is a problem of its own type

A generic delete refused because the aggregate's class refuses deletion while referenced SHALL be
answered 409 with a problem response whose type is `{base}problems/in-use`, distinct from the
version conflict's and the key conflict's types. Instead of a detail, it SHALL carry `referrers`
(the readable referrers, each with its IRI, class and slot, at most `max_named_referrers` of
them), `more_count` (readable referrers left out by that cap) and `hidden_count` (referrers the
caller may not read). The OpenAPI document SHALL list the type and document the delete route of
such a class with that problem.

#### Scenario: the in-use problem
- **GIVEN** `Author` annotated `refuse` and a `Book` the caller may read referring to it
- **WHEN** the client deletes the author through the generic router
- **THEN** the answer is 409 with the problem type ending `problems/in-use`, `referrers` naming
  the book by IRI, class `Book` and slot `written_by`, `more_count` 0 and `hidden_count` 0

#### Scenario: a stale delete stays a version conflict
- **GIVEN** a referenced `Author`
- **WHEN** it is deleted with `If-Match` holding an old version
- **THEN** the answer is 409 with the problem type ending `problems/conflict`

#### Scenario: the contract
- **WHEN** a client reads the OpenAPI document
- **THEN** the delete route of `Author` lists a 409 answer whose schema is the in-use problem, and
  the delete route of `Book` does not
