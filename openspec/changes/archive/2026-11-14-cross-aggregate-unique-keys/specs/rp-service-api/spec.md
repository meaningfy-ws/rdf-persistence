<!-- Capability: rp-service-api. Change: cross-aggregate-unique-keys. -->

## ADDED Requirements

### Requirement: A key clash is a problem of its own type

A write refused because it would break a unique key across aggregates SHALL be answered 409 with
a problem response whose type is `{base}problems/key-conflict`, distinct from the version
conflict's type, and, like every refusal, without a detail. The OpenAPI document SHALL list the
type.

#### Scenario: a create with a taken key
- **GIVEN** a stored book with an ISBN
- **WHEN** a client creates another book with that ISBN through the generic router
- **THEN** the answer is 409 with the problem type ending `problems/key-conflict`, and no book is
  added

#### Scenario: a stale replace stays a version conflict
- **WHEN** a book is replaced with `If-Match` holding an old version and another book's ISBN
- **THEN** the answer is 409 with the problem type ending `problems/conflict`
