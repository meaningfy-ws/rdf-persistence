<!-- Capability: rp-testkit. Change: delivery-friction. -->

## ADDED Requirements

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
