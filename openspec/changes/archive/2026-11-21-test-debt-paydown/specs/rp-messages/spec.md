## MODIFIED Requirements

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
