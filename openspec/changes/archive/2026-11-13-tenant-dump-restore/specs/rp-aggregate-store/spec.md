## ADDED Requirements

### Requirement: A store exports and imports a whole database as N-Quads

The `Store` port SHALL export every named graph of a database as N-Quads in one read, and SHALL
import N-Quads into an existing database, adding the quads to their named graphs. Both SHALL raise
`DatabaseGone` for a database that does not exist. The store conformance suite SHALL prove both on
every adapter and on the fake.

#### Scenario: a round trip between two databases
- **GIVEN** a database with triples in two named graphs, one object a literal with a language tag and one a typed literal
- **WHEN** it is exported and the N-Quads are imported into an empty database
- **THEN** both graphs in the second database hold exactly the same triples

#### Scenario: a database that does not exist
- **WHEN** a dropped database is exported
- **THEN** the store raises `DatabaseGone`
