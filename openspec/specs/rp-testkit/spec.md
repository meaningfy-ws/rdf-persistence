# rp-testkit Specification

## Purpose
TBD - created by archiving change toolkit-v1-foundation. Update Purpose after archive.
## Requirements
### Requirement: Consumers test without servers

`rdf_persistence.testkit` SHALL provide in-memory fakes of the store, file store and identity
ports, a fake session, and a token signer whose tokens a `JwksTokenVerifier` given the testkit's in-memory
JWKS accepts, so a consumer's unit tests need no running server.

#### Scenario: a unit test of a domain service
- **WHEN** a consumer's domain service is tested with the fakes
- **THEN** the test runs with no network access

### Requirement: Adapters are tested against real containers

The toolkit SHALL ship container fixtures (Fuseki, Garage, Zitadel) in `rdf_persistence.testkit`,
behind the extra `rdf-persistence[testkit]`, and run each adapter's
integration tests against them, and one end-to-end test that serves the toy library over the API.

#### Scenario: the end-to-end proof
- **WHEN** the end-to-end suite runs
- **THEN** a librarian creates, reads, replaces and deletes a book over the API, a reader is
  refused the write, and an outsider gets 404

### Requirement: Tests wait on a condition with a deadline through the public test module

`rdf_persistence.testkit` SHALL export `wait_until`, which calls a probe until it returns a truthy
value and returns that value, and `wait_until_async`, which does the same for a probe that returns
an awaitable. Both SHALL take the thing waited for (`what`), a `timeout`, the errors that mean "not
ready yet" (`retry_on`), and an injected sleep and clock, and SHALL raise `TimeoutError` naming
`what` when the deadline passes. Any other error of the probe SHALL propagate.

#### Scenario: the import an application test makes
- **WHEN** an application test module runs `from rdf_persistence.testkit import wait_until, wait_until_async`
- **THEN** the import succeeds and `assert_public_imports` accepts the module

#### Scenario: a probe that never succeeds
- **GIVEN** a probe that always returns `None` and an injected clock that advances past the timeout
- **WHEN** `wait_until` or `wait_until_async` runs with `what="the file listing"`
- **THEN** it raises `TimeoutError` whose message names "the file listing"

#### Scenario: an async probe that succeeds on the third call
- **GIVEN** an async probe that returns `None` twice, then `["a.csv"]`, and an injected async sleep
- **WHEN** `wait_until_async` awaits it
- **THEN** it returns `["a.csv"]` and slept twice, never really sleeping

#### Scenario: an error that is not "not ready yet"
- **GIVEN** a probe that raises `ValueError` and `retry_on=(OSError,)`
- **WHEN** either helper runs
- **THEN** the `ValueError` propagates on the first call

#### Scenario: the checklist names only public helpers
- **WHEN** a reader follows rule 11 of `develop/testing.adoc`
- **THEN** every helper it names is importable from `rdf_persistence.testkit`

### Requirement: A waiting helper can bound one probe call

`wait_until` and `wait_until_async` SHALL take an optional `probe_timeout` (seconds, default none).
When it is set, a probe call that has not returned within it SHALL count as "not ready yet", and the
wait SHALL go on until the overall `timeout`, then raise `TimeoutError` naming `what`. When it is
not set, the helpers SHALL behave as before. A `probe_timeout` that is not positive SHALL raise
`ValueError`. `wait_until` SHALL NOT start a second call while an earlier one is still running: it
waits for that call again on the next poll, so at most one hung call is left behind.

#### Scenario: a probe that never returns
- **GIVEN** a probe that blocks forever, `probe_timeout=0.05` and `timeout=0.2`
- **WHEN** `wait_until` or `wait_until_async` runs with `what="the bucket"`
- **THEN** it raises `TimeoutError` whose message names "the bucket", within about the timeout

#### Scenario: a slow call, then an answer
- **GIVEN** a probe whose first call blocks longer than `probe_timeout` and whose second call
  returns `["a.csv"]`
- **WHEN** `wait_until_async` runs
- **THEN** it cancels the first call and returns `["a.csv"]`

#### Scenario: a slow sync call is waited for, not repeated
- **GIVEN** a probe whose first call blocks longer than `probe_timeout`, then returns
- **WHEN** `wait_until` runs
- **THEN** it starts no second call while the first runs; it returns the first call's value when
  that is truthy, and otherwise calls the probe again

#### Scenario: a probe timeout that is not positive
- **GIVEN** `probe_timeout=0` or a negative value
- **WHEN** either helper runs
- **THEN** it raises `ValueError` before calling the probe

#### Scenario: an error inside the bounded call
- **GIVEN** `probe_timeout=1.0`, `retry_on=(OSError,)` and a probe that raises `ValueError` at once
- **WHEN** either helper runs
- **THEN** the `ValueError` propagates on the first call

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

### Requirement: The guards catch a required-flag mismatch

The model guards SHALL fail when a generated Python field and the class's generated JSON Schema
disagree on whether the slot is required, naming the class and the slot.

#### Scenario: Python requires what the JSON Schema does not
- **GIVEN** generated output where a class's Python field is required and its JSON Schema leaves the slot optional
- **WHEN** the model guards run
- **THEN** they fail and name the class and the slot

### Requirement: A test signer can start from a given key

`TokenSigner` SHALL accept an optional keyword `key` (an RSA private key) and sign with it under its
first key id. Without `key`, it SHALL generate a fresh key, as before. `rotate` SHALL always generate
a fresh key. `rdf_persistence.testkit` SHALL export `new_key()`, which generates such a key, so a
consumer can share one without importing a private module.

#### Scenario: two signers from one key
- **GIVEN** one RSA key and two `TokenSigner(key=that_key)`
- **WHEN** each issues a token
- **THEN** each signer's JWKS verifies the other's token

#### Scenario: no key given
- **GIVEN** two `TokenSigner()` with no key
- **WHEN** the first issues a token
- **THEN** the second's JWKS does not verify it

#### Scenario: rotation after a given key
- **GIVEN** a `TokenSigner(key=k)`
- **WHEN** it rotates to a new key id
- **THEN** the new key is not `k`, and `k` stays in its JWKS

