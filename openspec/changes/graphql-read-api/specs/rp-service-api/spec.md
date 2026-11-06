## ADDED Requirements

### Requirement: A read-only GraphQL endpoint serves the schema's aggregates

The service SHALL serve, per tenant, a GraphQL endpoint whose types and fields are derived from the
LinkML schema with names that follow the JSON-LD context, that answers queries for aggregates with
their owned parts and referenced aggregates, and that accepts no mutation.

#### Scenario: a nested read in one query
- **GIVEN** a library tenant with a book that has chapters and a scan
- **WHEN** a reader queries the book with its chapters and its scan's file name
- **THEN** the response holds the book, its chapters and the scan's file name, equal to what the REST routes return for them

#### Scenario: a mutation is refused
- **GIVEN** the GraphQL endpoint of a library tenant
- **WHEN** a librarian sends a mutation
- **THEN** the endpoint refuses it and no aggregate changes

### Requirement: GraphQL reads pass the same access check

Every aggregate in a GraphQL response SHALL have passed the per-tenant and per-aggregate check, and
an aggregate the caller may not read SHALL be answered as absent.

#### Scenario: a prohibited book
- **GIVEN** a reader with a Prohibition of `read` on one book
- **WHEN** the reader queries all books of the tenant
- **THEN** the response omits that book, and querying it by IRI answers as for a book that does not exist
