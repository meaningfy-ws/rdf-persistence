<!-- Capability: rp-aggregate-store. Change: cross-aggregate-unique-keys (after atomic-commit). -->

## ADDED Requirements

### Requirement: Unique keys hold across the aggregates of a tenant

When a schema declares a unique key on an aggregate root with the scope `tenant`, a commit SHALL be
refused if, once applied, two aggregates of that type in the same tenant would hold equal values
for every slot of the key. The check SHALL be part of the commit's one guarded update, so that of
two concurrent writes with the same key at most one succeeds, and a refused commit SHALL change
nothing. Values are equal when they are the same RDF term, after an `xsd:string` literal is read as the plain literal of the same text. An aggregate with a key slot absent
SHALL claim nothing and SHALL never conflict. Aggregates of other types, subclasses included, and
of other tenants SHALL never conflict. A refusal SHALL be a key conflict, told apart from a
version conflict, naming the roots of the commit whose key clashed. Like a version conflict's
roots, the kind of the refusal and its roots are a diagnosis read after the refusal: it can miss a
root or name one too many, and a clash whose holder is gone by then is reported as a lost race.

#### Scenario: two concurrent creates with the same key
- **GIVEN** the toy library declares a key on the book's ISBN and an active library tenant
- **WHEN** two sessions create two books with the same ISBN at the same time
- **THEN** exactly one commit succeeds, the other is refused as a key conflict, and the tenant
  holds one book with that ISBN

#### Scenario: a replace keeps its own key
- **GIVEN** a stored book holding an ISBN
- **WHEN** a session replaces that book without changing the ISBN
- **THEN** the commit succeeds

#### Scenario: a replace takes another aggregate's key
- **GIVEN** two stored books with different ISBNs
- **WHEN** a session replaces the second book with the first book's ISBN
- **THEN** the commit is refused as a key conflict naming the second book, and both books are
  unchanged

#### Scenario: a removed aggregate frees its key
- **GIVEN** a stored book holding an ISBN
- **WHEN** it is removed and a new book with the same ISBN is added
- **THEN** the add succeeds

#### Scenario: one commit moves a key and removes its holder
- **GIVEN** a stored book A holding an ISBN
- **WHEN** one unit of work removes A and adds a book B with A's ISBN
- **THEN** the commit succeeds

#### Scenario: two changes of one commit claim one key
- **WHEN** one unit of work adds two books with the same ISBN and commits
- **THEN** a key conflict naming both is raised before any request is sent

#### Scenario: absent keys never conflict
- **WHEN** two books without an ISBN are added
- **THEN** both commits succeed

#### Scenario: the same key in two tenants
- **GIVEN** two active library tenants
- **WHEN** each adds a book with the same ISBN
- **THEN** both commits succeed

#### Scenario: a version conflict is not a key conflict
- **GIVEN** a stored book read at a version, then changed by another session
- **WHEN** the first session replaces it with another book's ISBN
- **THEN** a version conflict is raised, not a key conflict

### Requirement: Existing key duplicates can be reported

A session SHALL report, for each declared key, the key values its tenant's aggregates already
repeat and the roots that hold each, without changing anything.

#### Scenario: a key declared over duplicates
- **GIVEN** a tenant holding two books with the same ISBN, stored before the key was declared
- **WHEN** an operator asks a session of that tenant for its key duplicates
- **THEN** the report names the key, the ISBN and both books, and the store is unchanged
