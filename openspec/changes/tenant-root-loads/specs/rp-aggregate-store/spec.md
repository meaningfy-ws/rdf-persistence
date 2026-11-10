<!-- Type: Reference. Capability: rp-aggregate-store. Change: tenant-root-loads (DEC-1, DEC-2). -->

## ADDED Requirements

### Requirement: The tenant root's loaded graphs are registered

A graph loaded for the tenant root and named in a commit of the root SHALL be registered like a
graph loaded for any aggregate: `loaded_graph(T, g)` SHALL read it, `loaded_graphs(T)` SHALL list
it, a later write of the root that does not name the loaded graphs SHALL keep them, and a replace
that lists other loaded graphs SHALL empty the ones it drops. The tenant root SHALL get no
`Aggregate` registry entry and SHALL appear in no listing.

#### Scenario: a root load comes back
- **GIVEN** a tenant whose root was committed with a graph loaded from Turtle
- **WHEN** a new session lists and reads the root's loaded graphs
- **THEN** it gets exactly that graph's IRI and exactly the loaded triples

#### Scenario: a rename keeps the root's loaded graph
- **GIVEN** a tenant root committed with one loaded graph
- **WHEN** the tenant is renamed
- **THEN** the root still lists that loaded graph and it still holds its triples

#### Scenario: a replace that drops a root load empties it
- **GIVEN** a tenant root committed with one loaded graph
- **WHEN** the root is replaced with an empty list of loaded graphs
- **THEN** the root lists no loaded graph and the graph holds no triple
