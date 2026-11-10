<!-- Capability: rp-aggregate-store. Change: loaded-graphs-listing (GitHub issue #70). -->

## ADDED Requirements

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
