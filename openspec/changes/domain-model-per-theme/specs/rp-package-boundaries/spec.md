## MODIFIED Requirements

### Requirement: Themes import in one order

The themes SHALL import only themes below them, in the order `core`; `iris`, `schema`;
`provenance`; `files`; `persistence`; `access`, `migrations`; `tenancy`; `collaboration`, `events`;
`messaging`; `api`, where themes named together import neither the other.

#### Scenario: a theme imports one above it
- **WHEN** a module of `rdf_persistence/collaboration/` imports from `rdf_persistence/messaging/`
- **THEN** `make check-architecture` fails and names both modules

#### Scenario: two themes of one rank
- **WHEN** a module of `rdf_persistence/events/` imports from `rdf_persistence/collaboration/`
- **THEN** `make check-architecture` fails and names both modules

#### Scenario: files above provenance
- **WHEN** a module of `rdf_persistence/files/domain/` imports from `rdf_persistence/provenance/domain/`
- **THEN** `make check-architecture` passes, and the reverse import fails naming both modules
