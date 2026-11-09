## ADDED Requirements

### Requirement: Some roots are written only through a session

The router SHALL NOT serve the generic create, replace and delete of an aggregate root annotated
`rp_writes: service` or mixing in `StoredFile`, and the OpenAPI document SHALL NOT describe them; the read of one aggregate and the listing SHALL be served as for
any root. The consumer SHALL be able to write such a root through a session in its own routes.

#### Scenario: a stored file cannot be rewritten by a client
- **GIVEN** the served toy library and a `Scan` stored by a session
- **WHEN** a caller with `modify` sends `PUT`, `POST` or `DELETE` to the generic scan routes
- **THEN** the answer is 405 and the scan is unchanged
- **AND** `GET` of the scan and the scan listing still answer 200

#### Scenario: any root can opt in
- **GIVEN** a root without `StoredFile` annotated `rp_writes: service`
- **WHEN** the OpenAPI document is fetched
- **THEN** it describes the root's read and listing and no create, replace or delete

#### Scenario: the consumer's route writes it
- **GIVEN** a root annotated `rp_writes: service`
- **WHEN** the consumer's own route opens `kit.session(...)` and adds, replaces and removes an aggregate of it
- **THEN** each write is committed and versioned as for any root

### Requirement: Listing filters type their values inline

In the OpenAPI document, the schema of a listing's filter parameter SHALL be the slot's item schema
written inline, or a reference to an enum's component schema, and SHALL NOT point into a property
of another schema; TypeScript generated from the document by `openapi-typescript` SHALL type-check
in strict mode.

#### Scenario: a multivalued slot's filter
- **GIVEN** the toy `Book` with the multivalued string slot `authors`
- **WHEN** the OpenAPI document is generated
- **THEN** the `authors` filter's schema is `{"type": "string"}`
- **AND** no parameter schema in the document holds a `$ref` containing `/properties/`

#### Scenario: the consumer's TypeScript compiles
- **WHEN** `openapi-typescript` runs on the toy service's OpenAPI document
- **THEN** `tsc --noEmit --strict` accepts its output
