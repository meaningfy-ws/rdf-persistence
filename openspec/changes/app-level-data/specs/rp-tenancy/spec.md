## ADDED Requirements

### Requirement: The application keeps its own aggregates outside any tenant

The service kit SHALL store the aggregates of every class the schema annotates `database:
application` in one application database, created at start-up when the schema has such a class, and
SHALL offer a session on it with the same reads, versioned writes and loaded graphs as a tenant
session, and SHALL mint the IRI of a new application aggregate for its class. A class SHALL be
application-level when it, or a class it descends from by `is_a`, carries the annotation; a
mixin's annotation SHALL not count. A session SHALL never store such an aggregate in a tenant
database, nor a tenant class in the application database, and SHALL never write an access record
through an application session: a tenant session SHALL refuse a root typed as an application
class, and an application session SHALL refuse a root not typed as one, with `InvalidIri` and
before anything is sent. The application session SHALL also refuse the application IRI itself and
the IRI of an access record as the IRI of an aggregate. Restoring a tenant dump SHALL refuse, with
`InvalidBody` and before anything is created, a dump that holds an object typed as an application
class. Generation SHALL fail for an application class that is the tenant root, is
owned, is not an aggregate root, is a stored file, or shares its class IRI with a root of another
database, and for a mixin that carries the annotation.

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

#### Scenario: a subclass of an application class
- **GIVEN** `ReportTemplate` is a `Template` and carries no annotation of its own
- **WHEN** a `ReportTemplate` is committed through an application session
- **THEN** it is stored in the application database

#### Scenario: a root with no class
- **GIVEN** triples that give their root no type
- **WHEN** they are added through an application session
- **THEN** the session raises `InvalidIri` and nothing is written

#### Scenario: a class moved to the application after it had data
- **GIVEN** a `Template` stored in a tenant database before the class was annotated `database: application`
- **WHEN** a tenant session reads it, replaces it, and removes it
- **THEN** the read returns it, the replace raises `InvalidIri`, and the remove succeeds

#### Scenario: the sweep leaves the application database alone
- **GIVEN** an application database with aggregates and no access record naming it
- **WHEN** the start-up sweep runs
- **THEN** the application database and its aggregates are unchanged

#### Scenario: a schema without application classes
- **GIVEN** a schema with no class annotated `database: application`
- **WHEN** the start-up step that ensures the application database runs
- **THEN** no application database is created

#### Scenario: a dump that carries an application class
- **GIVEN** a tenant dump in which an aggregate is typed as the application class `Template`
- **WHEN** it is restored
- **THEN** the restore is refused with `InvalidBody` and no tenant is created

#### Scenario: the application IRI is not an aggregate
- **GIVEN** an application session
- **WHEN** a `Template` is added at the application IRI itself, or at the IRI an access record would have
- **THEN** the session raises `InvalidIri` and nothing is written
