## ADDED Requirements

### Requirement: Orphans inside a live tenant are removed

A sweep of an `active` tenant SHALL find every loaded graph that no registry entry owns and every
blob that no graph of the tenant names in `rp:fileKey`, each older than a grace period (default one
hour). It SHALL remove the loaded graphs only when asked to remove them, and the blobs only when
asked, separately, to remove blobs; by default it is a dry run. It SHALL never remove a loaded
graph or blob that a committed aggregate names, nor one younger than the grace period, and SHALL
never touch the tenant's `meta`, `registry`, access or aggregate graphs, a loaded graph of the
tenant root, nor another tenant. It SHALL return a report listing what it found and what it removed.

#### Scenario: an uncommitted loaded graph is swept
- **GIVEN** an active library tenant with a graph loaded for a book two hours ago and never named by a commit
- **WHEN** the live-tenant sweep runs with removal of loaded graphs
- **THEN** the loaded graph no longer exists, the report lists it, and every committed book and its loaded graphs are unchanged

#### Scenario: a blob of a removed aggregate is swept
- **GIVEN** an active library tenant where a scan was stored two hours ago and its aggregate then removed through the session
- **WHEN** the live-tenant sweep runs with removal of blobs
- **THEN** the scan's blob no longer exists and the blobs of every stored scan are byte for byte unchanged

#### Scenario: blobs stay unless their removal is asked for
- **GIVEN** an active tenant with an old orphan loaded graph and an old orphan blob
- **WHEN** the live-tenant sweep runs with removal of loaded graphs only
- **THEN** the loaded graph is gone, the blob still exists, and the report says the blob was not removed

#### Scenario: work in flight is kept
- **GIVEN** a graph loaded for a book five minutes ago whose commit has not yet run
- **WHEN** the live-tenant sweep runs with removal
- **THEN** the graph is kept and the commit that names it succeeds

#### Scenario: a dry run changes nothing
- **GIVEN** an active tenant with an old orphan loaded graph and an old orphan blob
- **WHEN** the live-tenant sweep runs without removal
- **THEN** the report lists both as not removed, and both still exist

#### Scenario: a tenant being deleted is not swept
- **GIVEN** a tenant in the deleting state
- **WHEN** the live-tenant sweep runs on it
- **THEN** it is refused as a conflict and nothing is removed

### Requirement: A file aggregate can be removed with its blobs

The service kit SHALL offer a removal of an aggregate at a version that, after the aggregate is
removed, deletes from the tenant's bucket every blob the aggregate named in `rp:fileKey` that no
other graph of the tenant still names. A stale version SHALL be refused with nothing changed. A blob
that cannot be deleted SHALL be logged and left for the live-tenant sweep; the removal of the
aggregate SHALL still succeed.

#### Scenario: a scan's blob goes with it
- **GIVEN** a stored scan whose file key names a blob
- **WHEN** the consumer's delete route removes the scan with its files
- **THEN** the scan and its blob no longer exist

#### Scenario: a shared blob stays
- **GIVEN** two scans whose file keys name the same blob
- **WHEN** one scan is removed with its files
- **THEN** the blob still exists

#### Scenario: the object store fails
- **GIVEN** a stored scan and an object store that fails on delete
- **WHEN** the scan is removed with its files
- **THEN** the scan no longer exists, the blob remains, and the failure is logged
