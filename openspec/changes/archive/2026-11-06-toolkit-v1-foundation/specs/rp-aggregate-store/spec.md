Capability: rp-aggregate-store. Source: EPIC `toolkit-v1-foundation`; architecture `index.adoc`
(N-1, N-2, N-5), DEC-29.

## ADDED Requirements

### Requirement: One named graph per aggregate, at a derived IRI

The session SHALL store each aggregate (its root and owned parts) in one named graph whose IRI is
`graph_iri(root)`, derived from the root's IRI by one function, and SHALL never use the root's IRI
as a graph name. A tenant's root object SHALL live in the tenant's designated `meta` graph.

#### Scenario: graph name
- **WHEN** a book with IRI `<b>` is committed
- **THEN** its triples are in the graph `graph_iri(<b>)` and no graph is named `<b>`

### Requirement: Stale writes are refused

A commit SHALL replace the aggregate's graph in one guarded update that succeeds only if the
stored version token equals the one the caller read, and SHALL confirm the outcome with an `ASK`
for the new token. A guard that does not match SHALL raise a conflict and change nothing.

#### Scenario: two editors
- **WHEN** two sessions read version v7 of a book and both commit
- **THEN** the first commit stores a new version token and the second raises a conflict, and the
  stored book is the first one's

### Requirement: SPARQL is never built by concatenating input

Every value that reaches a SPARQL query or update SHALL pass through one escaping or binding
function.

#### Scenario: an injection attempt
- **WHEN** a filter value contains `"} ; DROP ALL ; #`
- **THEN** the query matches no book and the store is unchanged

### Requirement: RDF files load into a graph of their own

Graph loading SHALL parse a Turtle, RDF/XML, N-Triples or JSON-LD file, refuse it with the parser's
message if it does not parse, and otherwise put it into a new named graph owned by an aggregate.

#### Scenario: a broken file
- **WHEN** a Turtle file with a syntax error is loaded
- **THEN** loading fails with the parser's message and no graph is created
