<!-- Capability: rp-messages. Change: message-bus. -->

## ADDED Requirements

### Requirement: Commands have one handler, events have any number

The message bus SHALL dispatch a command to exactly one handler and raise that handler's error to
the caller, and SHALL dispatch an event to every handler registered for its class, logging a
handler's error and still running the others. A bus whose command map gives a command class no
handler or more than one SHALL be refused when it is built.

#### Scenario: a failing event handler
- **GIVEN** two handlers registered for an event, the first of which raises an error
- **WHEN** the event is handled
- **THEN** the error is logged and the second handler still runs

#### Scenario: a failing command handler
- **WHEN** a command whose handler raises an error is handled
- **THEN** the caller receives that error

### Requirement: Events leave the unit of work only after a successful commit

A unit of work SHALL collect the events raised through it and one change event per root it
added, replaced or removed, naming the root, its class, its new version and the committer. The bus
SHALL receive them only after the commit succeeded; a refused commit SHALL hand over none.

#### Scenario: a refused commit
- **GIVEN** a handler that replaces a book, raises an event and commits, while the book changed
  meanwhile
- **WHEN** the commit is refused as a conflict
- **THEN** no event, neither the raised one nor a change event, reaches any handler

#### Scenario: a committed replace
- **GIVEN** a handler that replaces a book and commits
- **WHEN** the command is handled
- **THEN** the handlers of the replace change event receive one event naming the book and its new
  version

### Requirement: Events raised while handling are handled in the same call

Events raised by handlers SHALL be handled in the same `handle` call, after the message that raised
them, up to a limit of messages per call; past the limit the call SHALL stop with an error naming it.

#### Scenario: an event loop
- **GIVEN** a handler that raises the event it handles
- **WHEN** that event is handled
- **THEN** the call stops with an error naming the limit
