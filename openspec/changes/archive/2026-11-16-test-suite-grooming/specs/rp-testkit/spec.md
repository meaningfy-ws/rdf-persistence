## ADDED Requirements

### Requirement: Tests share one signing key and poll in-process fakes quickly

The testkit SHALL offer `shared_key()`, one RSA private key per process, for tests that need a
signing key but not a distinct one; `wait_until` and `wait_until_async` SHALL take
`poll_seconds` (default 1 s, positive) so a wait on an in-process fake can poll faster; a
`poll_seconds` that is not positive raises `ValueError` naming it.

#### Scenario: two calls in one process
- **WHEN** a test calls `shared_key()` twice
- **THEN** both calls return the same key object

#### Scenario: a fast poll
- **GIVEN** a condition that becomes true after three polls
- **WHEN** `wait_until_async(probe, poll_seconds=0.01)` waits for it
- **THEN** it returns before one default poll interval (1 s) has passed

#### Scenario: a poll interval that is not positive
- **WHEN** `wait_until(probe, "x", poll_seconds=0)` is called
- **THEN** it raises `ValueError` naming `poll_seconds`

## MODIFIED Requirements

### Requirement: The model guards are public names of the testkit

`rdf_persistence.testkit` SHALL export `assert_models_generated`, `Conformance`,
`conformance_problems`, `round_trip`, `assert_isomorphic`, `aggregate`, `class_shapes`,
`read_snapshot`, `write_snapshot`, `snapshot_diff` and `model_shape_diff`. Those whose modules load `hypothesis` or
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
