<!-- Capability: rp-testkit. Change: mwb2-adoption-fixes (#45, DEC-3). -->

## ADDED Requirements

### Requirement: The model guards are public names of the testkit

`rdf_persistence.testkit` SHALL export `assert_models_generated`, `Conformance`,
`conformance_problems`, `round_trip`, `aggregate`, `class_shapes`, `read_snapshot`,
`write_snapshot`, `snapshot_diff` and `model_shape_diff`. Those whose modules load `hypothesis` or
`pyshacl` SHALL load on first use, so `import rdf_persistence.testkit` loads neither library. The adoption guide SHALL import them only from
`rdf_persistence.testkit`.

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
