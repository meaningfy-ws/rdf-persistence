Capability: rp-testkit. Source: EPIC `toolkit-v1-foundation`; architecture `index.adoc` (N-10),
DEC-4 of the EPIC.

## ADDED Requirements

### Requirement: Consumers test without servers

`rdf_persistence.testkit` SHALL provide in-memory fakes of the store, file store and identity
ports, a fake session, and a token signer whose tokens the service kit accepts in test mode, so a
consumer's unit tests need no running server.

#### Scenario: a unit test of a domain service
- **WHEN** a consumer's domain service is tested with the fakes
- **THEN** the test runs with no network access

### Requirement: Adapters are tested against real containers

The toolkit SHALL ship container fixtures (Fuseki, Garage, Zitadel) and run each adapter's
integration tests against them, and one end-to-end test that serves the toy library over the API.

#### Scenario: the end-to-end proof
- **WHEN** the end-to-end suite runs
- **THEN** a librarian creates, reads, replaces and deletes a book over the API, a reader is
  refused the write, and an outsider gets 404
