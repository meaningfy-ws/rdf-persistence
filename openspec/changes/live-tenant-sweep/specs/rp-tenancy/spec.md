## ADDED Requirements

### Requirement: Orphans inside a live tenant are removed

A sweep of an `active` tenant SHALL remove every loaded graph that no registry entry owns and every
blob that no stored aggregate names, and SHALL never remove a loaded graph or blob that a committed
aggregate names, nor one that a commit in progress is about to name.

#### Scenario: an uncommitted loaded graph is swept
- **GIVEN** an active library tenant with a graph loaded for a book and never named by a commit
- **WHEN** the live-tenant sweep runs after that graph has become eligible
- **THEN** the loaded graph no longer exists and every committed book and its loaded graphs are unchanged

#### Scenario: a blob of a removed aggregate is swept
- **GIVEN** an active library tenant where a scan was stored and its aggregate then removed
- **WHEN** the live-tenant sweep runs
- **THEN** the scan's blob no longer exists and the blobs of every stored scan are byte for byte unchanged

#### Scenario: work in flight is kept
- **GIVEN** a graph loaded for a book whose commit has not yet run
- **WHEN** the live-tenant sweep runs before that graph is eligible
- **THEN** the graph is kept and the commit that names it succeeds
