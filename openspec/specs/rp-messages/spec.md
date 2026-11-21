# rp-messages Specification

## Purpose
What a commit records of itself and who hears of it: one PROV activity per commit, kept as the
audit trail, and an in-process message bus that sends a command to the handler of its nearest
class and hands each committed activity to the observers of its class and every ancestor.

## Requirements

### Requirement: Every commit records one activity with its PROV events

Every successful commit to a tenant database or to the application database SHALL record, in the
same update request, one activity in that database's provenance graph. Its class SHALL be the
command it served; with no command it SHALL be a standard `Add`, `Replace` or `Remove` when every
change is of that kind, and a plain `Activity` otherwise. The activity SHALL carry its start, end
and principal, and for each aggregate it touched one `prov:Generation` (added, or the new version of
a replaced one) or `prov:Invalidation` (removed, or the old version of a replaced one), each naming
the aggregate, its class when it has one, and its version token. The record SHALL carry references
only, never the aggregate's content. The activity SHALL be typed with its class and every ancestor
class up to `prov:Activity`, and its IRI SHALL be a `urn:uuid:` IRI. A refused commit SHALL record
no activity; a commit with no change SHALL record none, and a batched commit SHALL record one
activity per batch. A commit the caller sees refused only because another writer overwrote every
graph it wrote before the confirmation (the false conflict of `rp-aggregate-store`) SHALL keep its
recorded activity. A commit to the system database SHALL record none. A session opened with
`record_activities=False` SHALL record no activity and SHALL NOT refuse a reused activity IRI; the
toolkit SHALL open such sessions only on the system database. A comment removed with its target
SHALL get no invalidation of its own.

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
carry it, and a restore SHALL keep the activity IRIs of the dump. An activity's IRI SHALL identify one record: a commit serving a command whose IRI is
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

After a commit whose confirmation held the bus SHALL hand the completed activity, with its
generations and invalidations, as one message to every observer registered for the activity's class
or an ancestor of it, the nearest class first. A commit reported as a false conflict is recorded
and SHALL NOT be handed over. A session opened with a hook that does not record SHALL hand over an
activity that is stored nowhere. A session opened with a hook SHALL await it after each commit
whose confirmation held, with the completed activity and the session, and an error of the hook
SHALL be logged and SHALL NOT fail the commit. An observer's error SHALL be logged and the other observers SHALL
still run; it SHALL NOT undo or fail the commit. With no bus the activity SHALL still be recorded.

#### Scenario: a specialised transition
- **GIVEN** an observer registered for `Transition` and a consumer class `ApproveBook is_a: Transition`
- **WHEN** an `ApproveBook` command commits
- **THEN** the observer receives one message: the `ApproveBook` activity with its generations

#### Scenario: a failing observer
- **GIVEN** two observers of `Activity`, the first of which raises an error
- **WHEN** any command commits
- **THEN** the error is logged and the second observer still runs

#### Scenario: a false conflict
- **GIVEN** a commit that applied, and an observer of `Activity`
- **WHEN** another writer overwrote every graph it wrote before the confirmation, so the caller sees a conflict
- **THEN** the activity is recorded and the observer receives nothing

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

A command carrying a value for a slot the toolkit fills SHALL be refused before anything is
written. Those slots are its start, end and principal, its generations and invalidations, and for a
transition its two states and its comment. The generator SHALL refuse a consumer class that redefines such a slot,
and a consumer class other than an activity whose slot ranges over a consumer activity class that is
no aggregate root.

#### Scenario: a forged principal
- **WHEN** a command naming another principal as its agent is handled
- **THEN** it is refused and nothing is written

### Requirement: A command's record carries only its own statements

A command's record (a `Served`) SHALL carry only statements about its own activity or about blank
nodes, and SHALL be refused when it carries a statement about another subject that is not a blank
node, a type, a slot the session fills, an IRI that is not a `urn:uuid:` UUID, or a class the schema
does not have. A `Served` SHALL serve one commit: it SHALL be spent when its commit's request is
sent, whether the store accepts or refuses it, and a second commit serving it SHALL be refused. A
commit that sends nothing (an empty one) SHALL NOT spend it, so a helper that commits before there is
anything to write does not use up its command. A unit of work in batch mode SHALL record one
activity per batch.

#### Scenario: a statement about another resource
- **GIVEN** a `ShelveBooks` record that also states a title for a book that is not a blank node
- **WHEN** a commit serves it
- **THEN** it is refused and nothing is written

#### Scenario: a spent record
- **GIVEN** a `ShelveBooks` record that ada's commit served and that was refused as a conflict
- **WHEN** a second commit serves the same record
- **THEN** it is refused

#### Scenario: an empty commit spends nothing
- **GIVEN** a `ShelveBooks` handler whose unit of work commits once with nothing to write
- **WHEN** it then adds a book and commits again
- **THEN** the second commit is recorded as the command, once

#### Scenario: a batched unit of work
- **GIVEN** a unit of work in batch mode that adds two batches of books, with no command
- **WHEN** it commits
- **THEN** two activities are recorded, one per batch

### Requirement: Messages raised while handling stay bounded

Commands sent by observers SHALL be handled in the same `handle` call, after the current message,
up to a limit of commands per call; past the limit the call SHALL stop with an error naming it. An
observer of a commit made outside a `handle` call SHALL NOT be able to send a command.

#### Scenario: a loop
- **GIVEN** an observer of `ShelveBooks` that sends a `ShelveBooks` command
- **WHEN** a `ShelveBooks` command is handled
- **THEN** the call stops with an error naming the limit
