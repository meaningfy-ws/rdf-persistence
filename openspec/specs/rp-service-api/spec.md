# rp-service-api Specification

## Purpose
The HTTP service a consumer installs: one generic router for every aggregate type, plain JSON with JSON-LD and RDF on request, versioned writes, filtered and paged listings, a published contract, and the hooks a consumer uses to enforce its own rules.

## Requirements

### Requirement: One generic router serves every aggregate type

The router SHALL serve `/{tenant_segment}/{t}/{rp_path}` (list, create) and
`/{tenant_segment}/{t}/{rp_path}/{id}` (read, replace, delete) for every aggregate root of the
application schema, read at run time, with no generated routes and no generated Python classes on
this path; for a service-written root (annotated `rp_writes: service`, or mixing in `StoredFile`)
it SHALL serve only the list and the read. It SHALL mint the IRI on create and refuse a client-sent
one. Bodies SHALL be validated with the generated shapes.

#### Scenario: a new class in the model
- **WHEN** the toy schema gains an aggregate root `Shelf` with `rp_path: shelves` and the
  application restarts
- **THEN** `/libraries/{t}/shelves` serves it with no code added

### Requirement: Plain JSON by default, RDF serialisations on request

Responses SHALL be plain JSON with `id` holding the IRI and a `Link` header to the generated
context. Every route that answers one aggregate (read, create, replace, and the tenant root) SHALL
also return, by `Accept`, JSON-LD (`application/ld+json`), Turtle (`text/turtle`), N-Triples
(`application/n-triples`), N-Quads (`application/n-quads`), TriG (`application/trig`) or RDF/XML
(`application/rdf+xml`); in N-Quads and TriG every triple SHALL be in the named graph the aggregate
was read from. On a tie in `Accept` the order SHALL be JSON, JSON-LD, Turtle, N-Triples, N-Quads,
TriG, RDF/XML. A listing SHALL be served as JSON or JSON-LD only. An aggregate that a serialisation
cannot express SHALL be answered 406; on a create or a replace the 406 SHALL come before anything
is written. Writes SHALL accept JSON and JSON-LD.

#### Scenario: the same book three ways
- **WHEN** a book is read with `Accept` set to `application/json`, `application/ld+json` and
  `text/turtle`
- **THEN** the three responses describe the same triples

#### Scenario: the same book in every RDF serialisation
- **WHEN** a book is read with `Accept` set to each of Turtle, N-Triples, N-Quads, TriG and RDF/XML
- **THEN** the five responses describe the same triples

#### Scenario: N-Quads name the aggregate's graph
- **WHEN** a book is read with `Accept: application/n-quads`
- **THEN** every quad is in the book's named graph, and no statement about that graph is included

#### Scenario: a listing in N-Quads
- **WHEN** books are listed with `Accept: application/n-quads`
- **THEN** the answer is 406 with a problem response

### Requirement: Writes are versioned

Every read SHALL return the aggregate's version as `ETag`; every update and delete SHALL require
`If-Match`, answering 428 without it or when it is neither `*` nor a list of entity tags, and 409
when it is stale. `If-Match` SHALL use strong comparison (RFC 9110): a weak tag SHALL never match,
`*` SHALL match any current version, and a list SHALL match when one of its tags is the current
version. Errors SHALL be RFC 9457 problem responses.

#### Scenario: a stale replace
- **WHEN** a book is replaced with `If-Match` holding an old version
- **THEN** the answer is 409 with a problem response and the book is unchanged

#### Scenario: any version
- **WHEN** a book is replaced with `If-Match: *`
- **THEN** the replace is applied to the current version

#### Scenario: a list of versions
- **WHEN** a book is deleted with `If-Match` listing an old version and the current one
- **THEN** the book is deleted

#### Scenario: a weak tag
- **WHEN** a book is replaced with `If-Match` holding its current version as a weak tag
- **THEN** the answer is 409 and the book is unchanged

### Requirement: Listings are filtered and paged

A listing SHALL accept equality filters and contains filters (`<slot>~=<text>`) on the type's
slots, `limit` from 1 to 200, `offset` from 0 to 9007199254740991 (2^53 − 1), and one sort key,
and SHALL return a page with `items`, `total`, `limit` and `offset`. A `limit` or `offset` out of
its range SHALL answer `400 bad-query`.

#### Scenario: a page of books
- **WHEN** books are listed with `limit=2&offset=2` and no sort key
- **THEN** the page holds the third and fourth books by IRI order, and the total count

#### Scenario: an offset beyond the bound
- **WHEN** books are listed with `offset=9223372036854775758`
- **THEN** the answer is 400 `bad-query`

### Requirement: Listings filter by a case-insensitive substring

A listing SHALL accept `<slot>~=<text>` on a string-ranged slot, and `Session.find` SHALL accept
`Contains(text=<text>)`, matching a case-insensitive substring, combinable with other filters,
with paging and totals unchanged; an aggregate SHALL be listed and counted once however many of
its values match. On a non-string slot, or with an empty text, it SHALL answer `400 bad-query`.
The OpenAPI document SHALL show a `<slot>~` query parameter for each string-ranged slot of a
listed type, and for no other slot.

#### Scenario: a substring in any case
- **GIVEN** books labelled "Dune", "Children of Dune" and "Emma"
- **WHEN** listing `label~=DUNE`
- **THEN** two books are returned, total 2

#### Scenario: a non-string slot
- **WHEN** listing `published~=19`
- **THEN** the answer is 400 `bad-query`

#### Scenario: combined filters
- **GIVEN** "Dune" of genre fiction and "Children of Dune" of genre nonfiction
- **WHEN** listing `label~=dune&genre=fiction`
- **THEN** only "Dune" is returned, total 1

#### Scenario: an empty text
- **WHEN** listing `label~=`
- **THEN** the answer is 400 `bad-query`

#### Scenario: an item matching on several values is listed once
- **GIVEN** books whose authors are "Herbert"; "Austen"; "Joyce" and "Herbert"; and "Morrison"
- **WHEN** listing `authors~=E&limit=2`
- **THEN** the page holds two distinct books and the total is 3

#### Scenario: the contract shows a contains parameter per string slot
- **WHEN** the OpenAPI document of the books listing is read
- **THEN** it has `label~`, `description~`, `isbn~` and `authors~` parameters, and no `published~`
  or `genre~`

### Requirement: The contract is published

The service SHALL publish an OpenAPI document generated by a hook over the schema, with LinkML
bookkeeping stripped, and the JSON-LD context at a fixed path. A contract test SHALL check that the
service's answers keep to that document: no server error, and every status, media type and JSON
body documented.

#### Scenario: the document lists the routes
- **WHEN** the OpenAPI document is fetched
- **THEN** it describes the routes of every aggregate type and their error responses

#### Scenario: the service keeps to its document
- **WHEN** the contract test sends generated requests to every operation of the toy service
- **THEN** every answer has a documented status and media type, and every JSON body is valid against its schema

### Requirement: A test can choose the ids the service draws

`install_service` SHALL take an optional `id_source`, through which every tenant and object id is
drawn. Without it, ids SHALL be drawn from a cryptographic generator.

#### Scenario: a drawn tenant id clashes
- **GIVEN** a service installed with an `id_source` that returns an existing tenant's id first and a
  fresh id second
- **WHEN** a tenant is created
- **THEN** it is created with the fresh id, and the existing tenant is unchanged

#### Scenario: no id source
- **GIVEN** a service installed without `id_source`
- **WHEN** two tenants are created
- **THEN** their ids differ and have the length the IRI policy sets

### Requirement: A consumer enforces its own rules on tenant writes

`install_service` SHALL take optional grant validators and root validators. Grant validators SHALL
run on every replacement of a tenant's grant set; root validators SHALL run when a tenant is created
(the creator, who gets the first grant, is the caller), its root is replaced or it is renamed. Each SHALL run before the write; a validator that raises
`InvalidBody` SHALL refuse the write with a 422 problem and nothing SHALL be written. Two writes at
one version SHALL NOT both succeed.

#### Scenario: the last owner is kept
- **GIVEN** a grant validator that refuses a grant set with no `owner`
- **WHEN** an administrator replaces the grants with a set that has no `owner`
- **THEN** the answer is 422, and the record keeps its grants and its version

#### Scenario: two concurrent removals of two owners
- **GIVEN** a tenant with two owners at version `v1`, and that validator
- **WHEN** two grant writes at `v1` each remove a different owner
- **THEN** one succeeds and the other gets 409, and an owner remains

#### Scenario: a root rule on create
- **GIVEN** a root validator that refuses an end date before the start date
- **WHEN** a tenant is created with such a root
- **THEN** the answer is 422, and no database, bucket or access record exists for it

### Requirement: Reads tell the caller what it may do

A read of a tenant's root or of an aggregate SHALL answer an `Allowed-Actions` header listing,
from `read, modify, delete, administer` in that order, the actions the routes on what it read
would allow the caller: on a tenant, `delete` SHALL be listed only when the caller may
`administer` (deleting a tenant needs `administer`); on an aggregate, `administer` SHALL NOT be
listed. Each item of the tenant listing SHALL carry the tenant's list in `allowed_actions`. A
refused read SHALL carry no such header.

#### Scenario: a member reads the tenant and a book
- **GIVEN** a caller whose tenant role permits `read`, `modify` and `delete`
- **WHEN** it reads the tenant and then one of its books
- **THEN** the tenant's `Allowed-Actions` is `read, modify` and the book's is `read, modify, delete`
- **AND** the tenant's item in the listing has `allowed_actions` `[read, modify]`

#### Scenario: a librarian reads the tenant
- **GIVEN** a caller whose tenant role permits all four actions
- **WHEN** it reads the tenant
- **THEN** `Allowed-Actions` is `read, modify, delete, administer`

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

### Requirement: A key clash is a problem of its own type

A write refused because it would break a unique key across aggregates SHALL be answered 409 with
a problem response whose type is `{base}problems/key-conflict`, distinct from the version
conflict's type, and, like every refusal, without a detail. The OpenAPI document SHALL list the
type.

#### Scenario: a create with a taken key
- **GIVEN** a stored book with an ISBN
- **WHEN** a client creates another book with that ISBN through the generic router
- **THEN** the answer is 409 with the problem type ending `problems/key-conflict`, and no book is
  added

#### Scenario: a stale replace stays a version conflict
- **WHEN** a book is replaced with `If-Match` holding an old version and another book's ISBN
- **THEN** the answer is 409 with the problem type ending `problems/conflict`

### Requirement: The service is installed with its migrations folder

`install_service` SHALL take the folder of the consumer's migration files as a required argument,
SHALL refuse to build the service when that folder or the toolkit's own does not form one line of
versions ending at the running schema's version, and SHALL answer a request for the data of a
tenant whose migration failed at start-up (its aggregates, files and listings, and a rename,
which writes its root) with status 503 and the problem `tenant-behind`.

#### Scenario: a chain that forks
- **GIVEN** a migrations folder with two files leaving the same version
- **WHEN** the library service is installed
- **THEN** it fails, naming both files, and serves nothing

#### Scenario: a tenant set aside
- **GIVEN** a library service that set one tenant aside at start-up
- **WHEN** a reader lists that tenant's books
- **THEN** the answer is 503 with the problem type `tenant-behind`

### Requirement: A delete refused while referenced is a problem of its own type

A generic delete refused because the aggregate's class refuses deletion while referenced SHALL be
answered 409 with a problem response whose type is `{base}problems/in-use`, distinct from the
version conflict's and the key conflict's types. Instead of a detail, it SHALL carry `referrers`
(one item per readable referrer and slot, with its IRI, class and slot, naming at most
`max_named_referrers` referrer aggregates), `more_count` (readable referrer aggregates left out
by that cap) and `hidden_count` (referrer aggregates the caller may not read). A refusal no
`readable` callable judged SHALL name no referrer and count every referrer aggregate in
`hidden_count`. The OpenAPI document SHALL list the type and document the delete route of
such a class with that problem.

#### Scenario: the in-use problem
- **GIVEN** `Author` annotated `refuse` and a `Book` the caller may read referring to it
- **WHEN** the client deletes the author through the generic router
- **THEN** the answer is 409 with the problem type ending `problems/in-use`, `referrers` naming
  the book by IRI, class `Book` and slot `written_by`, `more_count` 0 and `hidden_count` 0

#### Scenario: a stale delete stays a version conflict
- **GIVEN** a referenced `Author`
- **WHEN** it is deleted with `If-Match` holding an old version
- **THEN** the answer is 409 with the problem type ending `problems/conflict`

#### Scenario: the contract
- **WHEN** a client reads the OpenAPI document
- **THEN** the delete route of `Author` lists a 409 answer whose schema is the in-use problem, and
  the delete route of `Book` does not

### Requirement: A consumer enforces its own rules on the writes of any root

`install_service` and `ServiceKit` SHALL take optional aggregate validators: a mapping from a schema
class name to rules, each called as `(old, new, principal, reader)` and either a plain function or a
coroutine function. The rules of a class SHALL run on every guarded add and replace of a root of that
class or of a class derived from it: the generic API's writes, a unit of work's commit, a message-bus
handler and a workflow transition. They SHALL run before anything is written; a rule that raises
`InvalidBody` SHALL refuse the write with a 422 problem carrying its message, and nothing SHALL be
written. The reader SHALL give the classes of a stored aggregate by IRI, and SHALL answer an
aggregate the writer may not read as unknown. Start-up SHALL refuse a class name that is not an
aggregate root of the schema or a parent of one, naming it. Restore and migrations SHALL NOT run the
rules. With no aggregate validators, writes SHALL behave as before.

#### Scenario: a refused create
- **GIVEN** a validator for `Shelf` that refuses two members of one kind
- **WHEN** a client creates a `Shelf` with two such members
- **THEN** the answer is 422 with the validator's message, and nothing is written

#### Scenario: a refused replace
- **GIVEN** the same validator and a stored `Shelf`
- **WHEN** a client replaces it, at its version, with two members of one kind
- **THEN** the answer is 422, and the stored version is unchanged

#### Scenario: a derived class
- **GIVEN** a validator registered for a class that is a parent of the root class `Shelf`
- **WHEN** a client creates a `Shelf` the validator refuses
- **THEN** the answer is 422

#### Scenario: a write that is not the generic API
- **GIVEN** the same validator
- **WHEN** code commits a unit of work that adds a `Shelf` the validator refuses
- **THEN** the commit raises `InvalidBody`, and nothing is written

#### Scenario: an async rule reads a referenced class
- **GIVEN** an async validator that refuses a `Shelf` naming two members whose classes are equal, as the reader gives them
- **WHEN** a client creates such a `Shelf`
- **THEN** the answer is 422

#### Scenario: a reference the writer may not read
- **GIVEN** a member the writing client may not read
- **WHEN** the validator asks the reader for its classes
- **THEN** it gets none, as for an IRI that names no aggregate

#### Scenario: a class name that is not a root
- **GIVEN** aggregate validators registered for a class name that is neither a root nor a parent of one
- **WHEN** the service starts
- **THEN** it refuses to start, naming the class

#### Scenario: no validators
- **GIVEN** no aggregate validator for `Shelf`
- **WHEN** a `Shelf` is written
- **THEN** it is written as before

### Requirement: A consumer's route reads If-Match through the public API

`expected_version` and `matched_version` SHALL be importable from `rdf_persistence` and SHALL apply
the generic routes' rules: one strong tag gives its version; a missing header is the 428 problem;
a weak tag, a list or `*` is refused as the generic routes refuse it.

#### Scenario: one strong tag
- **WHEN** a consumer calls `rdf_persistence.expected_version('"v1"')`
- **THEN** it gets `v1`

#### Scenario: no If-Match
- **WHEN** a consumer calls `rdf_persistence.expected_version(None)`
- **THEN** the generic routes' 428 problem is raised
