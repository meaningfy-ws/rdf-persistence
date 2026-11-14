<!-- Capability: rp-messages. Change: message-bus. Reconciled with design.md on 2026-11-14
     (proposal.md, "Where the PLAN and the code differ from the shape"). -->

## ADDED Requirements

### Requirement: Every commit records one activity with its PROV events

Every successful commit to a tenant database or to the application database SHALL record, in the
same update request, one activity in that database's provenance graph. Its class SHALL be the
command it served; with no command it SHALL be a standard `Add`, `Replace` or `Remove` when every
change is of that kind, and a plain `Activity` otherwise. The activity SHALL carry its start, end
and principal, and for each aggregate it touched one `prov:Generation` (added, or the new version of
a replaced one) or `prov:Invalidation` (removed, or the old version of a replaced one), each naming
the aggregate, its class when it has one, and its version token. The record SHALL carry references
only, never the aggregate's content. A refused commit SHALL record no activity. A commit to the
system database SHALL record none.

#### Scenario: a generic replace
- **GIVEN** a stored book
- **WHEN** it is replaced through the generic HTTP API
- **THEN** one `Replace` activity is recorded, associated with the caller, with a generation of the
  new version and an invalidation of the old one

#### Scenario: a refused commit
- **GIVEN** a unit of work holding an old version of a book
- **WHEN** its commit is refused as a conflict
- **THEN** no activity, generation or invalidation is recorded

#### Scenario: a commit of mixed changes
- **GIVEN** a transaction that adds one book and removes another, serving no command
- **WHEN** it commits
- **THEN** one plain `Activity` is recorded, with a generation of the first and an invalidation of
  the second

### Requirement: Activity records are kept

An activity record SHALL stay in the provenance graph when an aggregate it names is removed. The
provenance graph SHALL NOT be listed, counted as a referrer or swept, and a dump and a restore SHALL
carry it. An activity's IRI SHALL identify one record: a commit serving a command whose IRI is
already recorded SHALL be refused and write nothing.

#### Scenario: a removed book
- **GIVEN** a book with one recorded `Add`
- **WHEN** the book is removed
- **THEN** the provenance graph holds the `Add` and a `Remove` naming the book

#### Scenario: a reused activity IRI
- **GIVEN** a recorded activity
- **WHEN** a commit serves a command with the same IRI
- **THEN** the commit is refused as a conflict naming that IRI and nothing is written

### Requirement: One message per commit reaches observers along the class hierarchy

After a successful commit the bus SHALL hand the completed activity, with its generations and
invalidations, as one message to every observer registered for the activity's class or an ancestor
of it, the nearest class first. An observer's error SHALL be logged and the other observers SHALL
still run; it SHALL NOT undo or fail the commit. With no bus the activity SHALL still be recorded.

#### Scenario: a specialised transition
- **GIVEN** an observer registered for `Transition` and a consumer class `ApproveBook is_a: Transition`
- **WHEN** an `ApproveBook` command commits
- **THEN** the observer receives one message: the `ApproveBook` activity with its generations

#### Scenario: a failing observer
- **GIVEN** two observers of `Activity`, the first of which raises an error
- **WHEN** any command commits
- **THEN** the error is logged and the second observer still runs

### Requirement: A command goes to the nearest handler

The bus SHALL hand a command to the handler of its nearest class that has one and SHALL raise that
handler's error to the caller. A command with no handler along its class hierarchy SHALL be refused
with an error naming its class. The toolkit SHALL provide the handlers of `Transition`,
`PostComment` and `PostReply`; a consumer MAY replace them. A command SHALL be recorded by one
commit: a second commit serving the same command SHALL be refused.

#### Scenario: an extension without its own handler
- **GIVEN** `ApproveBook is_a: Transition` and no handler registered for `ApproveBook`
- **WHEN** an `ApproveBook` command is handled
- **THEN** the toolkit's `Transition` handler runs it, and the stored activity is an `ApproveBook`

#### Scenario: a standard command without a handler
- **WHEN** a `DeleteFile` command is handled by a bus with the toolkit's handlers only
- **THEN** it is refused with an error naming `DeleteFile`

### Requirement: The toolkit fills the provenance of a command

A command carrying a value for a slot the toolkit fills (its start, end and principal, its
generations and invalidations, and for a transition its two states and its comment) SHALL be refused
before anything is written. The generator SHALL refuse a consumer class that redefines such a slot,
and a consumer class other than an activity whose slot ranges over a consumer activity class that is
no aggregate root.

#### Scenario: a forged principal
- **WHEN** a command naming another principal as its agent is handled
- **THEN** it is refused and nothing is written

### Requirement: Messages raised while handling stay bounded

Commands sent by observers SHALL be handled in the same `handle` call, after the current message,
up to a limit of commands per call; past the limit the call SHALL stop with an error naming it. An
observer of a commit made outside a `handle` call SHALL NOT be able to send a command.

#### Scenario: a loop
- **GIVEN** an observer of `ShelveBooks` that sends a `ShelveBooks` command
- **WHEN** a `ShelveBooks` command is handled
- **THEN** the call stops with an error naming the limit
