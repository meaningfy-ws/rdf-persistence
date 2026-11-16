# rp-events Specification

## Purpose
Aggregate events across the process boundary: the commit's activity is the outbox entry, a relay
publishes it at least once to a broker, incoming events from other deployments reach the message
bus, and a reader follows a tenant's changes over server-sent events, seeing only what it may read.
Created by archiving change aggregate-events (2026-11-16).
## Requirements
### Requirement: A committed change is pending publication atomically

Every commit that records an activity (capability `rp-messages`) SHALL mark it pending publication
in the same update, so that a refused commit leaves no pending activity and a successful one
always does. Activities recorded before this capability are never pending.

#### Scenario: a stale write records nothing
- **GIVEN** a stored book and a session holding an old version of it
- **WHEN** the session's replace is refused as stale
- **THEN** no activity is pending for that replace

#### Scenario: a restore publishes nothing again
- **GIVEN** a tenant dump holding a pending activity
- **WHEN** the dump is restored as a new tenant
- **THEN** the restored activity is not pending

### Requirement: Events reach the bus at least once, in order per aggregate

The relay SHALL publish every pending activity to the event bus at least once, as the generated
JSON of its class with an envelope naming the tenant, the origin deployment, the class and the
JSON-LD context link, in commit order for each aggregate, including activities left pending by a
crash of the service.

A commit that applied but whose caller was told `Conflict` because another writer overtook it
(atomic-commit) SHALL be published like any other, since its change happened.

#### Scenario: a crash between commit and publish
- **GIVEN** a book commit whose activity is pending
- **WHEN** the service stops and starts again
- **THEN** a subscriber receives that activity

#### Scenario: events of one aggregate arrive in order
- **GIVEN** two replaces of one book, both pending
- **WHEN** the relay publishes them
- **THEN** the replace that generated the older version arrives first

### Requirement: Incoming events reach the message bus

A message from another deployment SHALL be handed to the message bus's observers with a session on
its tenant; a message of the receiving deployment's own origin SHALL NOT be handed again.

#### Scenario: another deployment's commit
- **GIVEN** two deployments on one broker and an observer of `Replace` in the second
- **WHEN** the first deployment replaces a book
- **THEN** the second deployment's observer receives the activity once

### Requirement: Server-sent events respect access

A client following a tenant's events SHALL receive only the parts of each activity about aggregates
it may read, and no activity of which no part is left.

#### Scenario: a hidden aggregate
- **GIVEN** a reader with a Prohibition of `read` on one book, following the tenant's events
- **WHEN** that book and another are replaced
- **THEN** the reader receives the other book's event only

#### Scenario: resuming a stream
- **GIVEN** a reader whose stream ended after event A, and two later commits
- **WHEN** the reader reconnects with `Last-Event-ID` A within 7 days
- **THEN** the reader receives the two later events, each once, then live events

