## ADDED Requirements

### Requirement: A session finds aggregates without a value for a slot

`Session.find(cls, slot=None)` SHALL return the aggregates of `cls` that have no value for `slot`,
combined with the other filters as any filter is. `None` inside a list, or with another value for
the same slot, SHALL raise `ValueError`.

#### Scenario: absence
- **GIVEN** two stored aggregates of a class, one with `slot` set and one without
- **WHEN** the session finds with `slot=None`
- **THEN** it returns only the second's IRI

#### Scenario: absence with another filter
- **GIVEN** the same two aggregates
- **WHEN** the session finds with `slot=None` and the second's label
- **THEN** it returns only the second's IRI

#### Scenario: absence and a value together
- **WHEN** the session finds with `slot=[None, "x"]`
- **THEN** `ValueError` is raised
