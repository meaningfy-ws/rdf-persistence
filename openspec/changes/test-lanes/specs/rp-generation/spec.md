## ADDED Requirements

### Requirement: The freshness check runs once per parallel session

Under `pytest-xdist`, the freshness plugin SHALL check the generated code once, in the controller,
before any worker starts, and SHALL NOT check again in the workers. A stale tree SHALL stop the
session once, with one message.

#### Scenario: a fresh tree on several workers
- **GIVEN** fresh generated code
- **WHEN** pytest runs with `-n 2`
- **THEN** the check runs in the controller only

#### Scenario: a stale tree on several workers
- **GIVEN** a stale generated target
- **WHEN** pytest runs with `-n 2`
- **THEN** the session stops before any test runs, with one message naming the target and the
  regenerating command
