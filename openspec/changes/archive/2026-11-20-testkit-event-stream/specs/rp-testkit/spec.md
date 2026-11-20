## ADDED Requirements

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
