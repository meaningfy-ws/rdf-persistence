## ADDED Requirements

### Requirement: A second store passes the same contract

A second store adapter SHALL pass every case of the `Store` conformance suite, and the toy library's
end-to-end test SHALL pass with that adapter wired in place of Fuseki.

#### Scenario: the conformance suite on the second store
- **GIVEN** the second store running in its test container
- **WHEN** the `Store` conformance suite runs against its adapter
- **THEN** every case passes with the same outcome as on Fuseki

#### Scenario: the toy library end to end
- **GIVEN** the toy library service wired to the second store
- **WHEN** the end-to-end test runs through the permission matrix
- **THEN** it passes as it does on Fuseki

### Requirement: A store declares what it can do

Each store adapter SHALL publish a capability descriptor, and the service SHALL refuse to start, with
a message naming the missing capability, when the descriptor lacks something the configured use
requires, rather than weaken tenant isolation or atomic guarded commits.

#### Scenario: a missing capability
- **GIVEN** a store whose descriptor lacks a capability the service requires
- **WHEN** the service starts
- **THEN** it refuses to serve and names the capability
