## ADDED Requirements

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
