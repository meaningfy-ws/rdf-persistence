<!-- Capability: rp-aggregate-store. Change: collaboration-and-reference-collections (consumer need, inputs/consumer-needs.md). -->

## ADDED Requirements

### Requirement: The object-level read exposes an aggregate's version token

A unit of work SHALL return, through `version(iri)`, the version token of an aggregate it read or
committed: the token read by `get`, and after a commit the new token. Asking for an aggregate the
unit of work has not read or committed SHALL raise a lookup error naming it.

#### Scenario: record the version that was used
- **GIVEN** a stored book
- **WHEN** a unit of work gets the book and asks for its version
- **THEN** it gets the same token `Session.get_graph` returns and the generic API sends as `ETag`

#### Scenario: after a commit
- **GIVEN** a unit of work that got a book, changed it and committed
- **WHEN** it asks for the book's version
- **THEN** it gets the new token, different from the one it read
