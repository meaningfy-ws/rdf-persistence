## ADDED Requirements

### Requirement: The generator's test helpers live with the generator

The freshness plugin, the conformance suite, the round trip and the instance strategies SHALL live
in `rdf_persistence_generation.testkit`, which SHALL export `Conformance`, `conformance_problems`,
`round_trip` and `aggregate`. The graph comparison `assert_isomorphic`, which the round trip uses,
SHALL stay in `rdf_persistence.testkit`. For one minor release, their former paths under
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

#### Scenario: the graph comparison stays in the library
- **WHEN** a consumer imports `assert_isomorphic` from `rdf_persistence.testkit`
- **THEN** no warning is raised and no generator module is imported

## MODIFIED Requirements

### Requirement: The model guards are public names of the testkit

`rdf_persistence.testkit` SHALL export `assert_models_generated`, `assert_isomorphic`,
`class_shapes`, `read_snapshot`, `write_snapshot`, `snapshot_diff` and `model_shape_diff`, and,
for one minor release, `Conformance`, `conformance_problems`, `round_trip` and `aggregate` through
the deprecation shims; `rdf_persistence_generation.testkit` SHALL export those four. Those whose
modules load `hypothesis` or `pyshacl` SHALL load on first use, so `import rdf_persistence.testkit`
loads neither library. The adoption guide SHALL import the four from
`rdf_persistence_generation.testkit` and the others from `rdf_persistence.testkit`.

#### Scenario: the guide's model guards pass the public-imports check
- **GIVEN** a consumer test written as the adoption guide's step 6 shows
- **WHEN** `assert_public_imports` checks it
- **THEN** it passes

#### Scenario: an undocumented testkit module is still refused
- **GIVEN** a test that imports `rdf_persistence.testkit.strategies`
- **WHEN** `assert_public_imports` checks it
- **THEN** it is refused, naming the file, the line and the module

#### Scenario: importing the testkit stays light
- **WHEN** a process imports `rdf_persistence.testkit` and nothing else
- **THEN** neither `hypothesis` nor `pyshacl` is loaded
