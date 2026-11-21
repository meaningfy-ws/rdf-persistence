## ADDED Requirements

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
