## ADDED Requirements

### Requirement: A dependent part is written only while its whole exists

An add or a replace of a dependent part SHALL check, in the same update request as the write, that
its whole exists and is of the class the pointer ranges over (or a subclass). Otherwise the write
SHALL raise `NotFound` naming the whole, and nothing SHALL be written; this holds also when the
whole is removed after the check and before the write's request is applied. A whole added or
replaced in the same transaction SHALL be judged by the triples collected for it. A part SHALL
hold exactly one pointer value, other than its own IRI (`InvalidBody` otherwise). A replace that changes the pointer SHALL raise `Conflict` naming the slot, and nothing
SHALL be written. A part write SHALL NOT read, guard or change the whole's version token.

#### Scenario: the whole is there
- **GIVEN** a stored audit A1
- **WHEN** a session adds result R1 pointing at A1
- **THEN** R1 is stored and A1 keeps its version

#### Scenario: the whole is gone
- **GIVEN** audit A1 deleted
- **WHEN** a session adds result R1 pointing at A1
- **THEN** `NotFound` names A1 and R1 has no graph

#### Scenario: the whole is deleted while the part is being written
- **GIVEN** a session that has checked A1 exists and is about to send R1's add
- **WHEN** another session deletes A1 before R1's request is applied
- **THEN** `NotFound` names A1 and R1 has no graph

#### Scenario: a pointer to an aggregate of another class
- **WHEN** a session adds result R1 pointing at a book
- **THEN** `NotFound` names the book and nothing is written

#### Scenario: the pointer is fixed
- **GIVEN** stored result R1 pointing at A1, and audit A2
- **WHEN** R1 is replaced pointing at A2
- **THEN** `Conflict` names `of_audit` and R1 is unchanged

#### Scenario: parallel parts
- **GIVEN** a stored audit A1
- **WHEN** two sessions add results R1 and R2 of A1 at the same time
- **THEN** both are stored and neither is a conflict

### Requirement: Deleting a whole deletes its dependent parts

Removing an aggregate SHALL remove, in the same update request, every dependent part that points at
it, transitively, each with its loaded graphs, registry entries and dependent records, all or
nothing, whatever path removes it (session, transaction, unit of work). The parts SHALL be counted
before anything is written, each aggregate once: when the transaction's roots and the parts exceed
`max_roots`, it SHALL raise `CommitTooLarge` whose message gives the limit and not the number of
parts. A part added or replaced in the same transaction as the removal of its whole, whether the
caller removes that whole or the cascade reaches it, SHALL raise `Conflict` naming both, nothing
sent; the checks a commit makes of its own links to removed roots SHALL include the cascaded ones.
A part written, changed or removed after the parts were read and before the removal is applied
SHALL make the removal a `Conflict` naming the whole; a caller retries it. A part of a class annotated `rp_on_referenced_delete: refuse`
that an aggregate outside the cascade refers to SHALL refuse the whole removal with `InUse`; the
pointers of the cascade's own parts SHALL NOT count. The commit SHALL record one activity with one
invalidation per removed aggregate. An error SHALL name a cascaded part only when the caller may
read it.

#### Scenario: a whole with parts on two levels
- **GIVEN** audit A1 with results R1 and R2, R1 with finding F1 and a loaded graph L1
- **WHEN** A1 is removed
- **THEN** A1, R1, R2, F1 and L1 are gone, in one request, and one `Remove` activity holds four
  invalidations

#### Scenario: above the limit
- **GIVEN** `max_roots` 3 and audit A1 with three results
- **WHEN** A1 is removed
- **THEN** `CommitTooLarge` gives the limit 3 and nothing is removed

#### Scenario: a refusing part referred to from outside
- **GIVEN** finding F1 of A1, `AuditFinding` annotated `refuse`, and audit A2 citing F1
- **WHEN** A1 is removed
- **THEN** `InUse` is raised and A1, its results and F1 remain

#### Scenario: a part written during the delete
- **GIVEN** the removal of A1 has read its parts
- **WHEN** another session adds R3 of A1 before the removal is applied
- **THEN** the removal is a `Conflict` naming A1 and nothing is removed

#### Scenario: a unit of work that removes a whole and one of its parts
- **GIVEN** `max_roots` 4
- **WHEN** a unit of work removes A1 and R2 and commits
- **THEN** A1, R1, R2 and F1 are removed once each, and the commit is not too large

#### Scenario: a part added under a whole the cascade reaches
- **WHEN** a transaction removes A1 and adds finding F9 of R1
- **THEN** `Conflict` names F9 and R1, and nothing is sent

#### Scenario: a link to a part the cascade removes
- **GIVEN** `AuditFinding` annotated `refuse`
- **WHEN** a transaction removes A1 and adds audit A2 citing F1
- **THEN** `InUse` is raised and nothing is sent
