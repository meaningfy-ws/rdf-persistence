<!-- Capability: rp-aggregate-store. Change: sparql-control-escape (GitHub issue #270). -->

## MODIFIED Requirements

### Requirement: SPARQL is never built by concatenating input

Every value that reaches a SPARQL query or update SHALL pass through one escaping or binding
function. A literal SHALL be read back by the store as exactly the string it was given, whatever
characters it holds.

#### Scenario: an injection attempt
- **WHEN** a filter value contains `"} ; DROP ALL ; #`
- **THEN** the query matches no book and the store is unchanged

#### Scenario: a control character followed by hex digits
- **WHEN** a literal holds a control character followed by hex digits, such as `"\x1f0000"`
- **THEN** it is stored and read back unchanged
