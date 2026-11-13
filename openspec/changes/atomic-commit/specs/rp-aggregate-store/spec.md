<!-- Capability: rp-aggregate-store. Change: atomic-commit (issue #83). -->

## ADDED Requirements

### Requirement: Several aggregates of one tenant commit atomically

A session SHALL offer a transaction that collects adds, replaces and removes of aggregates of its
tenant and sends them as one update request. The request SHALL apply every change only if every
guard holds (each replaced or removed aggregate still has the version token given, each added
aggregate has no graph), and otherwise SHALL change nothing. The outcome SHALL be confirmed by one
`ASK`. A refused transaction SHALL raise a conflict that names every aggregate whose guard did not
hold. A transaction SHALL refuse the same aggregate twice before sending anything.

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

A unit of work SHALL refuse, before writing, a commit of more roots than its limit. With batch
mode it SHALL commit in batches of at most the limit, each batch atomic, and SHALL state that the
whole is not atomic. Re-running the same changes in batch mode after an interruption SHALL end in
the same stored state for added roots whose parts carry no randomly minted IRIs (design PD-9): an added root that already exists with the same triples, bookkeeping
excluded, counts as committed.

#### Scenario: over the limit
- **GIVEN** a unit of work with a limit of 2 and three new books
- **WHEN** it commits without batch mode
- **THEN** it is refused with an error naming the limit, and nothing is written

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

## MODIFIED Requirements

### Requirement: Stale writes are refused

A commit SHALL write in one guarded update that succeeds only if the stored version token of
every aggregate it replaces or removes equals the one the caller read, and SHALL confirm the
outcome with an `ASK` for the new tokens. A guard that does not match SHALL raise a conflict and
change nothing.

#### Scenario: two editors
- **WHEN** two sessions read version v7 of a book and both commit
- **THEN** the first commit stores a new version token and the second raises a conflict, and the
  stored book is the first one's
