## MODIFIED Requirements

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
