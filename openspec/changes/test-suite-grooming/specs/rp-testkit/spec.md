## ADDED Requirements

### Requirement: Tests share one signing key and poll in-process fakes quickly

The testkit SHALL offer `shared_key()`, one RSA private key per process, for tests that need a
signing key but not a distinct one; `wait_until` and `wait_until_async` SHALL take
`poll_seconds` (default 1 s) so a wait on an in-process fake can poll faster.

#### Scenario: two calls in one process
- **WHEN** a test calls `shared_key()` twice
- **THEN** both calls return the same key object

#### Scenario: a fast poll
- **GIVEN** a condition that becomes true after three polls
- **WHEN** `wait_until_async(probe, poll_seconds=0.01)` waits for it
- **THEN** it returns before one default poll interval (1 s) has passed
