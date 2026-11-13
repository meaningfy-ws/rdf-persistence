## ADDED Requirements

### Requirement: The application keeps its own aggregates outside any tenant

The service kit SHALL store the aggregates of every class the schema annotates `database:
application` in one application database, created at start-up when the schema has such a class, and
SHALL offer a session on it with the same reads, versioned writes and loaded graphs as a tenant
session. It SHALL never store such an aggregate in a tenant database, nor a tenant class in the
application database, and SHALL never write an access record through an application session.

#### Scenario: an application aggregate is not in any tenant
- **GIVEN** an application aggregate and a tenant
- **WHEN** the tenant's aggregates are listed and the application's aggregate is read through an application session
- **THEN** the listing does not include it and the read returns it

#### Scenario: application writes are versioned
- **GIVEN** an application aggregate at version v1
- **WHEN** two application sessions replace it at v1
- **THEN** the first succeeds and the second is refused as a conflict

#### Scenario: a class in the wrong space
- **GIVEN** `Book` is a tenant class and `Template` an application class
- **WHEN** a `Book` is committed through an application session, or a `Template` through a tenant session
- **THEN** the session raises `InvalidIri` and nothing is written

#### Scenario: the sweep leaves the application database alone
- **GIVEN** an application database with aggregates and no access record naming it
- **WHEN** the start-up sweep runs
- **THEN** the application database and its aggregates are unchanged

#### Scenario: a schema without application classes
- **GIVEN** a schema with no class annotated `database: application`
- **WHEN** the service starts
- **THEN** no application database is created
