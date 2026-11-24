## ADDED Requirements

### Requirement: Start-up reports grants that name undefined roles

Once the shared databases are migrated, start-up SHALL log a warning for each tenant whose grants
name a role that the role definitions do not define at the grant's level, naming the tenant and
the roles, and for each tenant where no grant gives the `administer` action. It SHALL NOT stop
start-up, also when the report cannot read the store or a record does not decode.

#### Scenario: a stale grant
- **GIVEN** a tenant whose grants name `reader`, which the role definitions no longer define
- **WHEN** the service starts
- **THEN** a warning names the tenant and `reader`, and the service serves requests

#### Scenario: a tenant nobody administers
- **GIVEN** a tenant whose grants give no one the `administer` action
- **WHEN** the service starts
- **THEN** a warning names the tenant

### Requirement: A caller learns the roles it holds on an aggregate

`Collaboration.roles_held(iri)` SHALL return the role names the caller holds on the aggregate
`iri` by the same rule the comment audience and the workflow transitions use: its role grants in
scope and its token roles defined at system level. A caller who may not read `iri` SHALL be
refused as reading the thread is. Every generic read that sends `Allowed-Actions` SHALL send
`Held-Roles`, the same names sorted and comma-separated, empty when none is held.

#### Scenario: roles held decide the audience
- **GIVEN** a caller and a comment on an aggregate with audience `R`
- **WHEN** the caller asks for its roles held on that aggregate
- **THEN** the comment is in the caller's thread exactly when `R` and those roles share a name

#### Scenario: the header
- **GIVEN** a caller granted `editor` on the tenant and `reader` on one book
- **WHEN** the caller reads that book
- **THEN** the response carries `Held-Roles: editor,reader`
