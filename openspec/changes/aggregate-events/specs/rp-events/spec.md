## ADDED Requirements

### Requirement: A committed change records its event atomically

Every commit that adds, replaces or removes an aggregate SHALL record one event naming the
aggregate, the kind of change and the new version, in the same update as the change, so that a
refused commit records no event and a successful one always does.

#### Scenario: a stale write records nothing
- **GIVEN** a stored book and a session holding an old version of it
- **WHEN** the session's replace is refused as stale
- **THEN** no event is recorded for that replace

### Requirement: Events reach subscribers at least once, in order per aggregate

The relay SHALL deliver every recorded event to the bus at least once, in commit order for each
aggregate, including events recorded before a crash of the service.

#### Scenario: a crash between commit and publish
- **GIVEN** a book commit whose event was recorded but not yet published
- **WHEN** the service stops and starts again
- **THEN** a subscriber receives that event

### Requirement: Server-sent events respect access

A client following a tenant's events SHALL receive only events about aggregates it may read.

#### Scenario: a hidden aggregate
- **GIVEN** a reader with a Prohibition of `read` on one book, following the tenant's events
- **WHEN** that book and another are replaced
- **THEN** the reader receives the other book's event only
