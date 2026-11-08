<!-- Capability: rp-testkit. Change: delivery-friction. -->

## ADDED Requirements

### Requirement: A waiting helper can bound one probe call

`wait_until` and `wait_until_async` SHALL take an optional `probe_timeout` (seconds, default none).
When it is set, a probe call that has not returned within it SHALL count as "not ready yet", and the
wait SHALL go on until the overall `timeout`, then raise `TimeoutError` naming `what`. When it is
not set, the helpers SHALL behave as before.

#### Scenario: a probe that never returns
- **GIVEN** a probe that blocks forever, `probe_timeout=0.05` and `timeout=0.2`
- **WHEN** `wait_until` or `wait_until_async` runs with `what="the bucket"`
- **THEN** it raises `TimeoutError` whose message names "the bucket", within about the timeout

#### Scenario: a slow call, then an answer
- **GIVEN** a probe whose first call blocks longer than `probe_timeout` and whose second call
  returns `["a.csv"]`
- **WHEN** either helper runs
- **THEN** it returns `["a.csv"]`
