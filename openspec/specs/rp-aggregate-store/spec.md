# rp-aggregate-store Specification

## Purpose
TBD - created by archiving change toolkit-v1-foundation. Update Purpose after archive.
## Requirements
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

### Requirement: A loaded graph can be read back

A session SHALL return, through `loaded_graph(iri, graph_iri)`, the triples of a graph loaded for
the aggregate `iri`, read from the store. A graph IRI that is not loaded for that aggregate SHALL
be reported as not found. The read SHALL be gated like any read of the aggregate: the session
checks no permission, and a consumer route checks `read` with `require_aggregate` before opening it.

#### Scenario: the loaded triples come back
- **GIVEN** an aggregate with a graph loaded from Turtle and committed with it
- **WHEN** the session reads that loaded graph
- **THEN** it holds exactly the triples that were loaded

#### Scenario: a graph of another aggregate
- **GIVEN** two aggregates, each with a loaded graph
- **WHEN** the session reads the first aggregate with the second one's graph IRI
- **THEN** it raises not found

#### Scenario: a caller without read
- **GIVEN** a principal with no `read` on the aggregate
- **WHEN** a consumer route checks `read` on the aggregate with `require_aggregate` before reading its loaded graph
- **THEN** the caller is refused and no session is opened

### Requirement: A session finds aggregates by slot values

A session SHALL return, through `find(cls, **equals)`, the IRIs of the tenant's aggregates of class
`cls` whose slots equal the given values; for a multivalued slot every given value SHALL be
present. It SHALL never return aggregates of another tenant or another class, and SHALL raise a
clear error for a name that is not a slot of `cls`.

#### Scenario: one match
- **GIVEN** two `Scan` aggregates in a tenant, one with `file_name` "a" and one with "b"
- **WHEN** the session finds scans with `file_name="a"`
- **THEN** it returns exactly the first scan's IRI

#### Scenario: other tenants and classes stay out
- **GIVEN** a `Scan` with `file_name` "a" in another tenant, and a `Book` with a slot valued "a"
- **WHEN** the session finds scans with `file_name="a"`
- **THEN** neither is returned

#### Scenario: an unknown slot
- **WHEN** the session finds scans with `colour="red"`
- **THEN** it raises an error naming `colour` and `Scan`

### Requirement: An aggregate's loaded graphs can be listed

A session SHALL return, through `loaded_graphs(iri)`, the IRIs of the graphs registered as loaded
for the aggregate `iri`, sorted by IRI, read from the store's registry. An aggregate with no loaded
graph SHALL give an empty list; an aggregate that does not exist SHALL be reported as not found; an
IRI the IRI policy does not mint for the tenant SHALL be refused as invalid. The session SHALL check
no permission; a consumer route checks `read` with `require_aggregate` before opening it.

#### Scenario: a later session finds the loaded graph
- **GIVEN** an aggregate committed with one loaded graph
- **WHEN** a new session lists the aggregate's loaded graphs
- **THEN** it gets exactly that graph's IRI, and `loaded_graph` reads it with that IRI

#### Scenario: the graph was replaced
- **GIVEN** an aggregate with a loaded graph, replaced with a list naming only a new loaded graph
- **WHEN** the session lists its loaded graphs
- **THEN** only the new graph's IRI is listed

#### Scenario: no loaded graph
- **GIVEN** an aggregate committed without loaded graphs
- **WHEN** the session lists its loaded graphs
- **THEN** the list is empty

#### Scenario: the aggregate was removed
- **GIVEN** an aggregate with a loaded graph that was then removed
- **WHEN** the session lists its loaded graphs
- **THEN** it raises not found

#### Scenario: an IRI the policy does not mint
- **WHEN** the session lists the loaded graphs of an IRI outside the tenant's policy
- **THEN** it raises invalid IRI and sends no query

