## ADDED Requirements

### Requirement: A second store passes the same contract

The GraphDB store adapter SHALL pass every case of the `Store` conformance suite, and the toy
library's end-to-end test SHALL pass with that adapter wired in place of Fuseki, with each tenant in
a repository of its own.

#### Scenario: the conformance suite on GraphDB
- **GIVEN** GraphDB running in its test container
- **WHEN** the `Store` conformance suite runs against its adapter
- **THEN** every case passes with the same outcome as on Fuseki

#### Scenario: the toy library end to end
- **GIVEN** the toy library service wired to GraphDB
- **WHEN** the end-to-end test runs through the permission matrix
- **THEN** it passes as it does on Fuseki

#### Scenario: tenants stay apart
- **GIVEN** two tenants on GraphDB
- **WHEN** each stores books, a loaded graph and registry entries
- **THEN** neither tenant's session reads the other's aggregates, loaded graphs or registry

### Requirement: A store declares what it can do

Each store adapter SHALL declare a capability descriptor stating `datasets`,
`atomic_update_request`, `graph_store_put` and `dataset_quads`. The conformance suite SHALL prove
every capability an adapter declares. The service SHALL refuse to start, naming the store and the
missing capability, when a wired store's descriptor lacks any of the four.

#### Scenario: a missing capability
- **GIVEN** a store whose descriptor states `atomic_update_request` false
- **WHEN** the service starts
- **THEN** it refuses to serve and names the store and `atomic_update_request`

#### Scenario: atomicity is proven, not trusted
- **GIVEN** an adapter that declares `atomic_update_request`
- **WHEN** one update request inserts a triple and then runs an operation that fails
- **THEN** the store raises an error and the triple is not stored
