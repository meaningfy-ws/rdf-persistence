## ADDED Requirements

### Requirement: Unique keys hold across the aggregates of a tenant

When a schema declares a unique key across the aggregates of one type, a commit SHALL be refused if,
once applied, two aggregates of that type in the same tenant would hold equal values for the key,
and the refusal SHALL happen inside the same guarded update as the version check, so that of two
concurrent writes with the same key at most one succeeds.

#### Scenario: two concurrent creates with the same key
- **GIVEN** the toy library declares a key on a book slot and an active library tenant
- **WHEN** two sessions create two books with the same key value at the same time
- **THEN** exactly one commit succeeds, the other is refused as a key conflict, and the tenant holds one book with that value

#### Scenario: a replace keeps its own key
- **GIVEN** a stored book holding a key value
- **WHEN** a session replaces that book without changing the key value
- **THEN** the commit succeeds

#### Scenario: a replace takes another aggregate's key
- **GIVEN** two stored books with different key values
- **WHEN** a session replaces the second book with the first book's key value
- **THEN** the commit is refused as a key conflict and both books are unchanged
