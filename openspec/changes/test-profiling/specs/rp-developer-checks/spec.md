## ADDED Requirements

### Requirement: Check timings come from a repeatable profile

The timings table in `docs/modules/ROOT/pages/develop/index.adoc` SHALL give, for `make check-all`
and `make test-containers`, times measured by a documented, repeatable command, with the date and
commit of the measurement, and SHALL name the slowest tests and check steps.

#### Scenario: a developer refreshes the table
- **GIVEN** the documented profiling command
- **WHEN** a developer runs it on the current `develop`
- **THEN** it reports the total time and the slowest tests and steps in the form the table uses

#### Scenario: the table names where the time goes
- **GIVEN** the timings table after this change
- **WHEN** a reader looks up `make check-all`
- **THEN** the row gives a measured time, its date and commit, and the slowest tests or steps that make it up
