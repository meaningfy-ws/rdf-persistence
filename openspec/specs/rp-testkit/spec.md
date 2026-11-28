# rp-testkit Specification

## Purpose
What the toolkit gives a consumer's tests: in-process fakes, real containers for adapter tests, deadline-bound waiting, model guards, and a token signer with shared keys.

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

`rdf_persistence.testkit` SHALL export `assert_models_generated`, `assert_isomorphic`,
`class_shapes`, `read_snapshot`, `write_snapshot`, `snapshot_diff` and `model_shape_diff`;
`rdf_persistence_generation.testkit` SHALL export `Conformance`, `conformance_problems`,
`round_trip` and `aggregate`, which `rdf_persistence.testkit` no longer exports (#165). Those whose
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

### Requirement: The generator's test helpers live with the generator

The freshness plugin, the conformance suite, the round trip and the instance strategies SHALL live
in `rdf_persistence_generation.testkit`, which SHALL export `Conformance`, `conformance_problems`,
`round_trip` and `aggregate`. The graph comparison `assert_isomorphic`, which the round trip uses,
SHALL stay in `rdf_persistence.testkit`. Their former paths under `rdf_persistence.testkit`
(`freshness`, `conformance`, `roundtrip`, `strategies`) warned for 0.5.0 and are removed in 0.6.0
(#165). The freshness plugin SHALL be enabled only by the project's `pytest_plugins`.

#### Scenario: the old paths are gone
- **WHEN** a consumer imports `rdf_persistence.testkit.freshness`, or `conformance_problems` from
  `rdf_persistence.testkit`
- **THEN** it fails with `ModuleNotFoundError`, resp. `ImportError`; the generator's
  `rdf_persistence_generation.testkit` serves both

#### Scenario: the testkit alone
- **WHEN** a consumer imports `rdf_persistence.testkit` and uses only the fakes
- **THEN** no warning is raised and no generator module is imported

#### Scenario: the graph comparison stays in the library
- **WHEN** a consumer imports `assert_isomorphic` from `rdf_persistence.testkit`
- **THEN** no warning is raised and no generator module is imported

### Requirement: The testkit opens a tenant's event stream in-process

`rdf_persistence.testkit.open_event_stream` SHALL open the events route of an app built by
`install_service`, return its status, headers and the first `events` parsed events, then leave, and
SHALL raise `TimeoutError` naming the URL rather than hang.

#### Scenario: a reader follows the stream
- **GIVEN** a reader's token on tenant `t`
- **WHEN** a test opens `.../t/rp-events`
- **THEN** it returns 200 with a `text/event-stream` content type within the timeout

#### Scenario: one event
- **GIVEN** a commit in `t` after the stream opened
- **WHEN** the helper waits for `events=1`
- **THEN** it returns one event whose `id` is the activity's IRI

#### Scenario: a refusal
- **GIVEN** a caller with no right on `t`
- **WHEN** the helper opens the stream
- **THEN** it returns 404 without waiting for the timeout

#### Scenario: nothing arrives
- **WHEN** `events=1` and `timeout=0.5` on a silent stream
- **THEN** it raises `TimeoutError` naming the URL

#### Scenario: the server ends the stream early
- **GIVEN** a stream the server ends after one event
- **WHEN** the helper waits for `events=3`
- **THEN** it returns that one event instead of raising

#### Scenario: the lifespan runs only when it is not running
- **GIVEN** an app whose lifespan the toolkit's own lifespan has not started (`app.state.rp_lifespan_started`
  is not set)
- **WHEN** the helper opens a stream on it
- **THEN** it enters the app's lifespan for the call and leaves it once
- **AND** on an app where the flag is set it does not enter the lifespan again

#### Scenario: an app that fails after the head
- **GIVEN** an app that sends the head and one event, then raises
- **WHEN** the helper waits for more events than came
- **THEN** it returns the head and the event that came, and does not re-raise

#### Scenario: a lifespan start-up longer than the timeout
- **GIVEN** an app whose lifespan the helper enters, and whose start-up takes longer than `timeout`
- **WHEN** the helper opens a stream on it with that `timeout`
- **THEN** it returns the head without raising, because the lifespan's start-up is outside `timeout`

### Requirement: The event-bus conformance kit polls at a caller's interval

`run_case` of `rdf_persistence.testkit.event_bus_conformance` SHALL take `poll_seconds` (default
the testkit's `POLL_SECONDS`) and pass it to every wait of the case, so a bus that delivers within
milliseconds is not waited on in one-second steps; a case called without it SHALL behave as before.

#### Scenario: a fast poll on a slow-delivering bus
- **GIVEN** a bus pair that delivers 100 ms after `publish`
- **WHEN** `run_case(case, pair, poll_seconds=0.02)` runs a delivery case
- **THEN** the case passes before one default poll interval (1 s) has passed

#### Scenario: the default
- **WHEN** a case is run as `run_case(case, pair)`
- **THEN** its waits poll every `POLL_SECONDS`

### Requirement: The aggregate strategy draws what the class accepts

`aggregate(conformance, class_name)` SHALL draw each slot from the class's induced slot, its
`slot_usage` applied: `equals_string` SHALL give that exact value, `equals_string_in` one of its
values, and a slot made `multivalued` by `slot_usage` a list.

#### Scenario: a reference collection's member class
- **GIVEN** a class with `slot_usage: {member_class: {equals_string: Book}}`
- **WHEN** the strategy draws it
- **THEN** `member_class` is `Book` and the round trip passes

#### Scenario: a slot made multivalued by the class
- **GIVEN** a class with `slot_usage: {holds: {multivalued: true}}` on a single-valued slot
- **WHEN** the strategy draws it
- **THEN** `holds` is a list and the round trip passes

### Requirement: A fault test can keep the relay out

The testkit documentation SHALL show how to run a request inside `kit.relay.paused()`, so that a
fault armed with `FakeStore.on` is taken by the request's own store call and not by the relay's.

#### Scenario: the request takes the armed fault
- **GIVEN** a service over `FakeStore` with its relay running, an activity pending and the relay woken
- **WHEN** inside `kit.relay.paused()` the test arms `on("update", StoreUnavailable(...))` and calls a write route that awaits a thread before writing
- **THEN** the route answers 503 on every run, and after the block the pending activity is relayed

### Requirement: A test can hold concurrent writes

`FakeStore.hold(operation, until, timeout)` SHALL make the first `until` calls of `operation`
inside its block wait until `until` of them are waiting, then release them in arrival order. A
hold that does not fill within `timeout` SHALL release its waiters and fail when its block exits.

#### Scenario: two writers at one version
- **GIVEN** a service over `FakeStore`, the relay paused, and `hold("update", until=2)`
- **WHEN** two requests replace the same root at the same version at once
- **THEN** one commits and the other is answered 409 `conflict`

#### Scenario: a hold that never fills
- **GIVEN** `hold("update", until=2, timeout=0.1)`
- **WHEN** only one `update` arrives
- **THEN** it completes after the timeout, and leaving the block raises `AssertionError` naming the operation and the count seen

#### Scenario: a hold left by an exception
- **GIVEN** `hold("update", until=2)` with one `update` waiting
- **WHEN** the block's body raises
- **THEN** the waiting call is released and completes, and the body's exception propagates, not an `AssertionError`

#### Scenario: a mistaken hold
- **GIVEN** an unknown operation, `until` below 1, or a hold already open on the operation
- **WHEN** `hold` is entered
- **THEN** it raises (`ValueError`, `ValueError`, `RuntimeError`) and no call waits

### Requirement: A project queues and selects its tests with the testkit

The testkit SHALL ship the test queue (`rdf_persistence.testkit.run_queue`), the selection data
(`rdf_persistence.testkit.selection_data`) and the changed-tests planner
(`rdf_persistence.testkit.changed_tests`) as public modules run with `python -m` from the
installed package. A project SHALL supply only a classifier (what a changed path selects, and
which paths testmon sees) and a layout; the planning, the pytest runs, the exit codes and the
locks SHALL be the testkit's. The modules SHALL NOT be loaded by importing the testkit's root, and
SHALL directly import nothing of the library but the testkit's generated types (and, for the
planner, the selection data).

#### Scenario: run from outside the repository
- **GIVEN** an environment with the toolkit installed and a working directory outside its repository
- **WHEN** `python -I -m rdf_persistence.testkit.run_queue --workers` runs
- **THEN** it prints a positive worker count and exits 0

#### Scenario: a project's own classifier
- **GIVEN** a classifier that maps `src/app/x.py` to `tests/unit/app/`
- **WHEN** the planner runs with `src/app/x.py` changed and no selection data
- **THEN** it runs pytest on `tests/unit/app/` with the layout's ignores and markers, and hints
  that the lead runs `make test-seed`

#### Scenario: the root stays light
- **WHEN** a test imports `rdf_persistence.testkit`
- **THEN** none of the three modules is loaded

### Requirement: A fallback path counts only if it changed since the seed

The testkit's seed SHALL record, beside the selection data it swaps in, the commit it ran on, and
SHALL remove that record when it swaps in data whose commit it cannot read or whose tracked files
differed from that commit when the seed started. When the selection
data is sound and a seed commit is recorded and readable, the changed-tests planner SHALL keep a
changed path's fallback reasons only if that path differs between the seed's commit and the
working tree, and SHALL name every path it set aside in a hint; a path that differs from the
seed's commit but not from the base SHALL still be classified, and its fallback reasons SHALL
count. Otherwise the planner SHALL plan
as it did without the record.

#### Scenario: a shared file changed before the seed
- **GIVEN** a branch whose `Makefile` changed, and a sound seed taken after that change
- **WHEN** a task changes one source file and runs the planner
- **THEN** the planner runs testmon's selection, does not fall back, and hints that `Makefile`
  is unchanged since the seed

#### Scenario: a shared file changed after the seed
- **GIVEN** a sound seed, then a change to `Makefile`
- **WHEN** the planner runs
- **THEN** it falls back, as it does without a seed commit

#### Scenario: a shared file reverted after the seed
- **GIVEN** a branch that changed `Makefile`, a sound seed taken then, and `Makefile` since
  reverted to the base's content
- **WHEN** the planner runs
- **THEN** it falls back, because the data was recorded under a `Makefile` the worktree no longer
  has

#### Scenario: no seed commit
- **GIVEN** selection data with no recorded commit, or a commit git cannot read
- **WHEN** the planner runs
- **THEN** it plans exactly as it does without the record

#### Scenario: a seed on a dirty tree
- **GIVEN** a tracked file with uncommitted changes
- **WHEN** a seed runs and finishes
- **THEN** its data is swapped in with no recorded commit, so the planner plans as it does without
  the record

#### Scenario: a seed that did not finish
- **GIVEN** a recorded seed commit C
- **WHEN** a later seed is interrupted before its run finishes
- **THEN** the selection data and the recorded commit C both stay as they were

### Requirement: A rule is unit-tested with the testkit's reader

`rdf_persistence.testkit` SHALL offer `FakeAggregateReader`, an in-memory `AggregateReader` seeded
with generated aggregates and the IRIs the writer may not read. It SHALL answer `classes_of`,
`aggregate` and `find` as the real reader does for the aggregates seeded, leave out the unreadable
ones, and record each call with its arguments in order. `rdf_persistence.testkit.reader_conformance`
SHALL hold the cases of that contract, each taking a reader seeded the same way, so that one test
runs them against the fake and the real reader.

#### Scenario: a rule under unit test
- **GIVEN** a validator under unit test and a `FakeAggregateReader` seeded with two books, one unreadable by the writer
- **WHEN** the validator is called with it
- **THEN** the rule sees only the readable book, and the test asserts the reader calls the rule made, with no consumer-side stub

#### Scenario: the fake and the real reader agree
- **GIVEN** the reader conformance cases
- **WHEN** they run against the fake and against the real reader over the same seeded aggregates
- **THEN** every case passes for both
