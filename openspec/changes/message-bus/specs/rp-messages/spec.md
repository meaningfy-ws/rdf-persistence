<!-- Capability: rp-messages. Change: message-bus. -->

## ADDED Requirements

### Requirement: Every commit records one activity with its PROV events

Every successful commit SHALL record, in the same transaction, one activity whose class is the
command it served (a standard `Add`, `Replace` or `Remove` when no other command was given),
carrying its start, end and principal, and for each aggregate it touched one `prov:Generation`
(added, or the new version of a replaced one) or `prov:Invalidation` (removed, or the old version of
a replaced one). A refused commit SHALL record no activity.

#### Scenario: a generic replace
- **GIVEN** a stored book
- **WHEN** it is replaced through the generic HTTP API
- **THEN** one `Replace` activity is recorded, associated with the caller, with a generation of the
  new version and an invalidation of the old one

#### Scenario: a refused commit
- **GIVEN** a unit of work holding an old version of a book
- **WHEN** its commit is refused as a conflict
- **THEN** no activity, generation or invalidation is recorded

### Requirement: One message per commit reaches observers along the class hierarchy

After a successful commit the bus SHALL hand the completed activity, with its generations and
invalidations, as one message to every observer registered for the activity's class or an ancestor
of it. An observer's error SHALL be logged and the other observers SHALL still run.

#### Scenario: a specialised transition
- **GIVEN** an observer registered for `Transition` and a consumer class `ApproveMapping is_a: Transition`
- **WHEN** an `ApproveMapping` command commits
- **THEN** the observer receives one message: the `ApproveMapping` activity with its generations

#### Scenario: a failing observer
- **GIVEN** two observers of `Activity`, the first of which raises an error
- **WHEN** any command commits
- **THEN** the error is logged and the second observer still runs

### Requirement: A command goes to the nearest handler

The bus SHALL hand a command to the handler of its nearest class that has one and SHALL raise that
handler's error to the caller. A command with no handler along its class hierarchy SHALL be refused
with an error naming its class.

#### Scenario: an extension without its own handler
- **GIVEN** `ApproveMapping is_a: Transition` and no handler registered for `ApproveMapping`
- **WHEN** an `ApproveMapping` command is handled
- **THEN** the toolkit's `Transition` handler runs it

### Requirement: The toolkit fills the provenance of a command

A command carrying a value for a slot the toolkit fills (start, end, principal) SHALL be refused
before anything is written.

#### Scenario: a forged principal
- **WHEN** a command naming another principal as its agent is handled
- **THEN** it is refused and nothing is written

### Requirement: Messages raised while handling stay bounded

Commands sent by observers SHALL be handled in the same `handle` call, after the current message,
up to a limit of messages per call; past the limit the call SHALL stop with an error naming it.

#### Scenario: a loop
- **GIVEN** an observer of `PublishRelease` that sends a `PublishRelease` command
- **WHEN** a `PublishRelease` command is handled
- **THEN** the call stops with an error naming the limit
