<!-- Capability: rp-workflow. Change: message-bus (DEC-13; design.md PD-11). -->

## MODIFIED Requirements

### Requirement: Every transition is recorded as provenance

Every transition SHALL be recorded, in the same update as the state change, as a `Transition`
activity (a `prov:Activity`) in the tenant's provenance graph, naming the aggregate, the source and
target states, the principal, the time and the comment if any. A collaboration SHALL list an
aggregate's transitions oldest first. A plain write of the aggregate SHALL leave its transition
records unchanged. A listed transition SHALL be an activity that used the aggregate and generated a
version of it, and SHALL carry only the generations and invalidations of that aggregate; a record
of a consumer's subclass SHALL be returned as a `Transition`. Deleting the aggregate SHALL keep them
in the provenance graph; no collaboration call SHALL return the transitions of an aggregate that is
no longer stored, while a session, which checks no access, MAY read every activity of the
provenance graph with `activities`.

#### Scenario: the history of a book
- **GIVEN** a book moved from `draft` to `in_review` by p1 with comment "ready", then to
  `accepted` by p2
- **WHEN** a session lists the book's transitions
- **THEN** it gets two records in that order, with agents p1 and p2, their times and the comment

#### Scenario: the history outlives the book
- **GIVEN** a book with two transitions
- **WHEN** the book is deleted
- **THEN** the provenance graph still holds the two transition activities, and its comments are gone
