## ADDED Requirements

### Requirement: A migration renames or drops a role in the stored grants

A migration file MAY carry `grant_roles` with `rename` (old name to new name) and `drop` (names).
On the system database, the migration's request SHALL rename the role of every grant naming an
old name, deleting a grant whose renamed form the same assignee already holds on the same target,
and SHALL delete every grant naming a dropped name. It SHALL do this in the same stamp-guarded
request as the migration's steps, rotating the version tokens. Other databases SHALL get no grant
changes. Renames SHALL apply in file order, each completing before the next, and the drops
after them, so that two names renamed to one leave no duplicate grant. A rename SHALL apply to
grants at every level. A file that drops a name it also renames from or to, renames a name to
a renamed name or to itself, renames one name twice, renames a name to one that holds a comma,
or holds an empty name SHALL be refused when it is loaded, naming the file.

#### Scenario: two roles merged into one
- **GIVEN** an assignee holding both `reader` and `viewer` on the same target
- **WHEN** a migration renames `reader` to `member` and `viewer` to `member`
- **THEN** one `member` grant remains for them on that target, and the access record decodes

#### Scenario: a role renamed
- **GIVEN** a tenant whose grants name `reader`, and a pending migration with `rename: {reader: member}`
- **WHEN** start-up migrates the system database
- **THEN** those grants name `member`, the access record decodes, and its version changed

#### Scenario: a rename that meets an existing grant
- **GIVEN** an assignee holding both `reader` and `member` on the same target
- **WHEN** the migration renames `reader` to `member`
- **THEN** one `member` grant remains for them on that target

#### Scenario: a role dropped
- **GIVEN** a tenant whose grants name `guest`, and a migration with `drop: [guest]`
- **WHEN** start-up migrates
- **THEN** no grant names `guest`, and the other grants are unchanged

#### Scenario: a second run
- **WHEN** the same migration is sent again after the stamp moved
- **THEN** nothing changes

#### Scenario: a contradictory file
- **WHEN** a migration file names `guest` in both `rename` and `drop`
- **THEN** loading it is refused, naming the file
