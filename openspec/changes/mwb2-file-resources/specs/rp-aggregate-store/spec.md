## ADDED Requirements

### Requirement: A loaded graph can be read back

A session SHALL return, through `loaded_graph(iri, graph_iri)`, the triples of a graph loaded for
the aggregate `iri`, read from the store. A graph IRI that is not loaded for that aggregate SHALL
be reported as not found. The read SHALL be gated like any read of the aggregate: the session
checks no permission, and a consumer route checks `read` with `require_aggregate` before opening it.

#### Scenario: the loaded triples come back
- **GIVEN** an aggregate with a graph loaded from Turtle and committed with it
- **WHEN** the session reads that loaded graph
- **THEN** it holds exactly the triples that were loaded

#### Scenario: a graph of another aggregate
- **GIVEN** two aggregates, each with a loaded graph
- **WHEN** the session reads the first aggregate with the second one's graph IRI
- **THEN** it raises not found

#### Scenario: a caller without read
- **GIVEN** a principal with no `read` on the aggregate
- **WHEN** a consumer route checks `read` on the aggregate with `require_aggregate` before reading its loaded graph
- **THEN** the caller is refused and no session is opened

### Requirement: A session finds aggregates by slot values

A session SHALL return, through `find(cls, **equals)`, the IRIs of the tenant's aggregates of class
`cls` whose slots equal the given values; for a multivalued slot every given value SHALL be
present. It SHALL never return aggregates of another tenant or another class, and SHALL raise a
clear error for a name that is not a slot of `cls`.

#### Scenario: one match
- **GIVEN** two `Scan` aggregates in a tenant, one with `file_name` "a" and one with "b"
- **WHEN** the session finds scans with `file_name="a"`
- **THEN** it returns exactly the first scan's IRI

#### Scenario: other tenants and classes stay out
- **GIVEN** a `Scan` with `file_name` "a" in another tenant, and a `Book` with a slot valued "a"
- **WHEN** the session finds scans with `file_name="a"`
- **THEN** neither is returned

#### Scenario: an unknown slot
- **WHEN** the session finds scans with `colour="red"`
- **THEN** it raises an error naming `colour` and `Scan`
