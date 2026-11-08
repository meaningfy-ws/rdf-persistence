<!-- Capability: rp-testkit. Change: testkit-wait-until (GitHub issue #24). -->

## ADDED Requirements

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
