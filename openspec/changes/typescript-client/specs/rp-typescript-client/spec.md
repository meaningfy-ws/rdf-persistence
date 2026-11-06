## ADDED Requirements

### Requirement: A typed client is generated for every served route

For a consumer schema, generation SHALL produce a TypeScript client whose calls cover every route
the generic router serves for that schema, with request and response types that are the generated
TypeScript types, and the client SHALL type-check in strict mode.

#### Scenario: the toy library's client
- **GIVEN** the toy library schema
- **WHEN** `rp-generate` runs
- **THEN** a client is written with a call for each tenant, grant and aggregate route, and `tsc --strict` accepts it

### Requirement: The client keeps the service's rules

The client SHALL send the version a read returned on every replace and delete, and SHALL surface a
problem response as a typed error carrying the problem's type and status.

#### Scenario: a stale write through the client
- **GIVEN** the served toy library and two clients that read the same book
- **WHEN** both replace it, one after the other
- **THEN** the second call fails with a typed conflict error and the book holds the first client's change
