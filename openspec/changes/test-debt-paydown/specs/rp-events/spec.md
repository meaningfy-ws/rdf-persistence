## ADDED Requirements

### Requirement: The relay can be held still

`Relay.paused()` SHALL be an async context manager during which the relay runs no publication
round, so a caller can hold committed activities pending; a round that was due while it was held
SHALL run after the block ends, and leaving the block by an exception SHALL release the relay too.

#### Scenario: commits stay pending while the relay is held
- **GIVEN** a running relay and a book commit made inside `async with relay.paused()`
- **WHEN** the block is still open
- **THEN** the commit's activity is still pending

#### Scenario: the relay resumes after the block
- **GIVEN** an activity committed while the relay was held
- **WHEN** the block ends
- **THEN** a subscriber receives that activity

#### Scenario: a block that raises releases the relay
- **GIVEN** a held relay whose block raises an error
- **WHEN** a book is committed after the block
- **THEN** a subscriber receives that activity
