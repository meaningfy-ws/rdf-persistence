## ADDED Requirements

### Requirement: The generator's test helpers live with the generator

The freshness plugin, the conformance suite, the round trip and the instance strategies SHALL live
in `rdf_persistence_generation.testkit`, which SHALL export `Conformance`, `conformance_problems`,
`round_trip` and `aggregate`. For one minor release, their former paths under
`rdf_persistence.testkit` SHALL still work and SHALL raise a `DeprecationWarning` naming the new
path; the release after SHALL remove them. The freshness plugin SHALL be enabled only by the
project's `pytest_plugins`.

#### Scenario: the old plugin path
- **GIVEN** a consumer whose root conftest has `pytest_plugins = ["rdf_persistence.testkit.freshness"]`
- **WHEN** its generated code is stale and a test session starts
- **THEN** the session stops with the stale message and the regenerate command, and a
  `DeprecationWarning` names `rdf_persistence_generation.testkit.freshness`

#### Scenario: the old conformance import
- **WHEN** a consumer imports `conformance_problems` from `rdf_persistence.testkit`
- **THEN** it gets the generator's function and a `DeprecationWarning` naming the new path

#### Scenario: the testkit alone
- **WHEN** a consumer imports `rdf_persistence.testkit` and uses only the fakes
- **THEN** no warning is raised and no generator module is imported
