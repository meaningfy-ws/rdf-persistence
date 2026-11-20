## ADDED Requirements

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

#### Scenario: opt-in only
- **GIVEN** a class without the annotation and a referrer
- **WHEN** it is deleted
- **THEN** it is deleted as before
