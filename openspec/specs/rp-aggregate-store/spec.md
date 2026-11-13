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

A commit SHALL write in one guarded update that succeeds only if the stored version token of
every aggregate it replaces or removes equals the one the caller read, and SHALL confirm the
outcome with an `ASK` for the new tokens. A guard that does not match SHALL raise a conflict and
change nothing.

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

### Requirement: A store exports and imports a whole database as N-Quads

The `Store` port SHALL export every named graph of a database as N-Quads in one read, and SHALL
import N-Quads into an existing database, adding the quads to their named graphs. Both SHALL raise
`DatabaseGone` for a database that does not exist. The store conformance suite SHALL prove both on
every adapter and on the fake.

#### Scenario: a round trip between two databases
- **GIVEN** a database with triples in two named graphs, one object a literal with a language tag and one a typed literal
- **WHEN** it is exported and the N-Quads are imported into an empty database
- **THEN** both graphs in the second database hold exactly the same triples

#### Scenario: a database that does not exist
- **WHEN** a dropped database is exported
- **THEN** the store raises `DatabaseGone`

### Requirement: Several aggregates of one tenant commit atomically

A session SHALL offer a transaction that collects adds, replaces and removes of aggregates of its
tenant and sends them as one update request. The request SHALL apply every change only if every
guard holds (each replaced or removed aggregate still has the version token given, each added
aggregate has no graph), and otherwise SHALL change nothing. The outcome SHALL be confirmed by one
`ASK`. A refused transaction SHALL raise a conflict that lists, sorted, the root IRIs found
conflicting by one read after the refusal; the list is a diagnosis and MAY be incomplete or empty.
The conflict's message SHALL name roots in words and SHALL NOT contain a graph IRI or a version
token. A transaction of removes only, whose aggregates another writer already removed, SHALL
succeed. A transaction SHALL refuse the same aggregate twice before sending anything, and SHALL
refuse any change after its block has ended. A store SHALL apply one update request of several
operations entirely or not at all; the store conformance suite SHALL prove it on every adapter.

#### Scenario: one root changed meanwhile
- **GIVEN** stored books A and B read by one unit of work
- **WHEN** A is changed by the unit of work, B is changed by another session meanwhile, and the
  unit of work commits A and B
- **THEN** a conflict naming B is raised and neither A nor B is changed in the store

#### Scenario: adds and a remove together
- **GIVEN** a unit of work adding three new books and removing a stored one
- **WHEN** it commits
- **THEN** the store holds the three books with new version tokens and not the removed one

#### Scenario: an add over an existing root
- **GIVEN** a transaction that replaces book A and adds book B, which already exists
- **WHEN** it is sent
- **THEN** a conflict naming B is raised and A keeps its old version

#### Scenario: the store fails during the request
- **GIVEN** a transaction of several changes
- **WHEN** the store fails before answering the update
- **THEN** the store error is raised and no change is visible (one request, one store transaction)

#### Scenario: a root twice
- **WHEN** a transaction is given book A twice
- **THEN** it is refused before any request is sent

#### Scenario: a conflict a person can read
- **GIVEN** a transaction that replaces book B, which another session changed meanwhile
- **WHEN** it is sent
- **THEN** the conflict lists B's IRI, and its message says B was changed by someone else since it
  was read, with no graph IRI and no version token

#### Scenario: removing what is already removed
- **GIVEN** a transaction that only removes book B, which another session removed meanwhile
- **WHEN** it is sent
- **THEN** it succeeds and nothing is written

#### Scenario: a request that fails part-way
- **GIVEN** an update request of two operations whose second fails when the store runs it
- **WHEN** it is sent to the fake store or to Fuseki
- **THEN** the request fails and the first operation is not applied

### Requirement: The unit of work removes roots and exposes version tokens

A unit of work SHALL remove a root it read, in the same atomic commit as its other changes. It
SHALL return, through `version(iri)`, the version token of a root it read or committed: the token
read, and after a commit the new one. Asking for a root it has neither read nor committed SHALL
raise a lookup error naming it.

#### Scenario: record the version that was used
- **GIVEN** a stored book
- **WHEN** a unit of work gets the book and asks for its version
- **THEN** it gets the token `Session.get_graph` returns and the generic API sends as `ETag`

#### Scenario: after a commit
- **GIVEN** a unit of work that got a book, changed it and committed
- **WHEN** it asks for the book's version
- **THEN** it gets the new token, different from the one it read

#### Scenario: remove with the others
- **GIVEN** a unit of work that read books A and B, changed A and removed B
- **WHEN** it commits and A had changed meanwhile
- **THEN** a conflict names A, and B is still stored

### Requirement: A commit has a size limit and an explicit batch mode

A unit of work SHALL refuse, before reading or writing, a commit of more roots than its limit
(500 by default), and SHALL refuse a limit below 1 when it is created. An HTTP route that meets
the limit SHALL answer 413 `payload-too-large`. With batch mode it SHALL commit in batches of at
most the limit, each batch atomic, and SHALL state that the whole is not atomic. A batch that
fails SHALL raise its error with its type and fields unchanged, saying how many batches were
committed, and the roots not yet committed SHALL stay pending so the same unit of work can retry.
Re-running the same changes in batch mode after an interruption SHALL end in the same stored state
for added roots whose own IRI and whose parts' IRIs are the same on every run: an added root that
already exists with the same triples, bookkeeping excluded, counts as committed.

#### Scenario: over the limit
- **GIVEN** a unit of work with a limit of 2 and three new books
- **WHEN** it commits without batch mode
- **THEN** it is refused with an error naming the limit, and nothing is written

#### Scenario: a batch fails and the same unit of work retries
- **GIVEN** a limit of 2 and a batch holding a book already stored as it would be written and a
  book that clashes with a stored one
- **WHEN** the batch-mode commit raises a conflict, the clashing stored book is removed, and the
  same unit of work commits in batch mode again
- **THEN** the conflict said how many batches were committed, and the retry writes only the book
  that clashed

#### Scenario: batches re-run after an interruption
- **GIVEN** three new books, a limit of 2, and a first batch-mode commit interrupted after its
  first batch
- **WHEN** a new unit of work adds the same three books and commits in batch mode
- **THEN** the store holds the three books once each

### Requirement: The tenant root is recognised whatever the IRI's type

A session SHALL treat an IRI as its tenant root when its text equals the tenant IRI, whether
either is given as a string or as an rdflib `URIRef`.

#### Scenario: URIRef tenant, string IRI
- **GIVEN** a session opened with the tenant IRI as a `URIRef`
- **WHEN** the tenant root is written and read with the IRI as a `str`
- **THEN** it is stored in the tenant's `meta` graph and the registry holds no `Aggregate` entry
  for it (and the same with the types swapped)

