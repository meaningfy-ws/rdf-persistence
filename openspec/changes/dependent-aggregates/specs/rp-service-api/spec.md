## ADDED Requirements

### Requirement: A whole's delete removes its dependent parts

The generic delete of an aggregate SHALL remove its dependent parts (capability
`rp-aggregate-store`) with the caller's delete right on that aggregate only, whatever the caller's
rights on the parts. A cascade above `max_roots` SHALL answer 413 `payload-too-large`; a refusing
part referred to from outside SHALL answer 409 `in-use`, naming no aggregate the caller may not
read. A create or replace of a dependent part whose whole does not exist SHALL answer 404 naming
the whole; a replace that changes the pointer SHALL answer 409 `conflict`. Any refusal SHALL name
a part only when the caller may read it, and otherwise the whole. The OpenAPI document SHALL list
the 404 on the create and replace routes of a dependent class and the 413 on the delete route of a
whole's class. A whole's parts are listed through the existing listing filter on the pointer
slot; no new route is added.

#### Scenario: the caller holds delete on the whole only
- **GIVEN** a caller with delete on audit A1 and no grant on its results
- **WHEN** it deletes A1 through the generic router
- **THEN** the answer is 204 and A1's results are gone

#### Scenario: a part posted for a deleted whole
- **GIVEN** audit A1 deleted
- **WHEN** a client posts a result with `of_audit` A1
- **THEN** the answer is 404 naming A1

#### Scenario: a part moved to another whole
- **WHEN** a client replaces result R1 with `of_audit` changed
- **THEN** the answer is 409 with the problem type ending `problems/conflict`

#### Scenario: a whole's parts listed
- **WHEN** a client lists `audit-results` filtered on `of_audit` A1
- **THEN** it receives A1's results only
