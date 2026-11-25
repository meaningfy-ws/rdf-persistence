## MODIFIED Requirements

### Requirement: Every commit records one activity with its PROV events

Every successful commit to a tenant database or to the application database SHALL record, in the
same update request, one activity in that database's provenance graph. Its class SHALL be the
command it served; with no command it SHALL be a standard `Add`, `Replace` or `Remove` when every
change is of that kind, and a plain `Activity` otherwise. The activity SHALL carry its start, end
and principal, and for each aggregate it touched one `prov:Generation` (added, or the new version of
a replaced one) or `prov:Invalidation` (removed, or the old version of a replaced one), each naming
the aggregate, its class when it has one, and its version token. The record SHALL carry references
only, never the aggregate's content. The activity SHALL be typed with its class and every ancestor
class up to `prov:Activity`, and its IRI SHALL be the one the IRI policy's activity template mints
for that database's tenant (or the application) from the served command's UUID, or from a fresh
UUID when no command is served; under the default template it is the `urn:uuid:` IRI. A refused
commit SHALL record no activity; a commit with no change SHALL record none, and a batched commit
SHALL record one activity per batch. A commit the caller sees refused only because another writer
overwrote every graph it wrote before the confirmation (the false conflict of `rp-aggregate-store`)
SHALL keep its recorded activity. A commit to the system database SHALL record none. A session
opened with `record_activities=False` SHALL record no activity and SHALL NOT refuse a reused
activity IRI; the toolkit SHALL open such sessions only on the system database. A comment removed
with its target SHALL get no invalidation of its own.

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

#### Scenario: a command's activity under an activity template
- **GIVEN** an activity template `{tenant}/activity/{id}`
- **WHEN** a commit serves a `ShelveBooks` command with id `urn:uuid:` and UUID U
- **THEN** the recorded `ShelveBooks` activity's IRI is the tenant's IRI, `/activity/` and U, and
  the command's own statements are about that IRI
