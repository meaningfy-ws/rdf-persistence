## ADDED Requirements

### Requirement: A consumer builds a workflow state IRI through the public API

`state_iri` SHALL be importable from `rdf_persistence` and listed in its `__all__`, and the
workflow how-to SHALL import it from there.

#### Scenario: the top-level import
- **WHEN** a consumer runs `from rdf_persistence import state_iri`
- **THEN** it gets the function the collaboration services use

### Requirement: A listing filters on an absent slot

A listing SHALL accept the repeatable parameter `absent=<slot>` and SHALL return only the
aggregates with no value for that slot, combined with every other filter, paged and counted like
any listing. `absent` SHALL be a reserved parameter name, as `sort`, `limit` and `offset` are.

#### Scenario: one absent, one present
- **GIVEN** two books, one with an optional slot set and one without
- **WHEN** a caller lists books with `absent=<that slot>`
- **THEN** only the second is returned and the total is 1

#### Scenario: a multivalued slot
- **GIVEN** a book with one value of a multivalued slot and a book with none
- **WHEN** a caller lists with `absent=<that slot>`
- **THEN** only the book with none is returned

#### Scenario: an unknown slot
- **WHEN** a caller lists with `absent=nosuch`
- **THEN** the answer is the 400 bad-query problem naming the slot
