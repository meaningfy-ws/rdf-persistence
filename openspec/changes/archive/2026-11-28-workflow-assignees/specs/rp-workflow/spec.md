## ADDED Requirements

### Requirement: An assignable workflow gives its aggregates assignees

A workflow file MAY say `assignable: true` (absent: false), and an edge MAY say
`clears_assignees: true` (absent: false). A file whose edge clears the assignees of a workflow
that is not assignable SHALL be refused when loaded, naming the file and the edge. An aggregate
under an assignable workflow SHALL hold zero or more assignees (`rp:assignedTo`, the IRIs of
principals), readable like any slot; a new aggregate SHALL hold none. The toolkit SHALL own them as
it owns the state: a plain write that adds, removes or changes an assignee SHALL be refused and
change nothing; a replace that names no assignee SHALL keep the stored ones; an add that names one
SHALL be refused. Under a workflow that is not assignable, a plain write that adds an assignee
SHALL be refused; assignees stored while the workflow was assignable SHALL be kept and readable
until an assignment to the empty set or a release removes them.

#### Scenario: a new book has no assignee
- **GIVEN** the review workflow with `assignable: true`
- **WHEN** a session stores a new book
- **THEN** reading the book gives no assignee

#### Scenario: a plain write cannot reassign
- **GIVEN** a book assigned to p1
- **WHEN** a session replaces the book naming p2 as its assignee
- **THEN** the replace is refused and the book is still assigned to p1

#### Scenario: a replace that omits the assignees keeps them
- **GIVEN** a book assigned to p1
- **WHEN** a session replaces the book's title with triples that name no assignee
- **THEN** the title changes and the book is still assigned to p1

#### Scenario: a clearing edge on a workflow that is not assignable
- **WHEN** a workflow file without `assignable: true` has an edge with `clears_assignees: true`
- **THEN** loading is refused and names the edge

### Requirement: Whoever may modify an aggregate sets its assignees; a mover takes it for itself

`collaboration.assign(iri, principals, if_version)` SHALL replace the assignees of `iri` with the
set `principals` (an empty set unassigns everyone) and return the new version, only if: the
aggregate is under a workflow that is assignable, or under a workflow and `principals` is
empty; the caller may read it and
no Prohibition of `modify` applies to the caller on the aggregate or the tenant; it still has the
version token `if_version` the caller read (checked next, a conflict that hides every refusal
below, as for a transition); and either the caller may `modify` the aggregate, or the set differs
from the stored one only by the caller itself and either removes it or the caller holds a role
on an edge leaving the aggregate's current state. Otherwise it SHALL be refused, with the
reason, and nothing SHALL change. A set equal to the stored one SHALL change nothing, record
nothing and return the version held.

#### Scenario: an editor assigns two people
- **GIVEN** a book in `draft` and a caller who may modify it
- **WHEN** it assigns the book to p1 and p2
- **THEN** reading the book gives the assignees p1 and p2

#### Scenario: a reviewer takes the work
- **GIVEN** a book in `in_review`, an edge from `in_review` to `accepted` for `reviewer`, and a
  caller granted `reviewer` that may read and annotate but not modify
- **WHEN** it adds itself to the book's assignees, and later removes itself
- **THEN** the book is assigned to it, and then no longer

#### Scenario: an assignee drops finished work
- **GIVEN** a book in `accepted`, from which no edge leaves, assigned to a reviewer without `modify`
- **WHEN** the reviewer removes itself from the book's assignees
- **THEN** the book is no longer assigned to it

#### Scenario: a reviewer cannot assign someone else
- **GIVEN** the same reviewer
- **WHEN** it assigns the book to p2
- **THEN** the assignment is refused and the assignees are unchanged

#### Scenario: a reader without a role on the edges
- **GIVEN** a caller granted only `reader`
- **WHEN** it adds itself to the book's assignees
- **THEN** the assignment is refused

#### Scenario: a stale version
- **GIVEN** a book whose version changed after the caller read it
- **WHEN** the caller assigns it at the version it read
- **THEN** the assignment is refused as a conflict and nothing changes

#### Scenario: a workflow that is not assignable
- **WHEN** a caller who may modify a book under a workflow without `assignable: true` assigns it
  to p1
- **THEN** the assignment is refused and nothing changes

### Requirement: An assignee may read the aggregate

Every principal that an assignment adds SHALL be one who may `read` the aggregate by the tenant's
stored grants and prohibitions (a tenant grant, a grant on the aggregate, no Prohibition of
`read`); a token role of another principal SHALL NOT count, since the toolkit cannot see it,
while a caller that adds itself is checked with its own token roles. An
assignment that adds any other principal SHALL be refused, naming it, and nothing SHALL change.
A principal already assigned SHALL NOT be checked again by an assignment that keeps it.

#### Scenario: an outsider
- **GIVEN** p9 with no grant in the library
- **WHEN** an editor assigns a book to p1 and p9
- **THEN** the assignment is refused, names p9, and the assignees are unchanged

### Requirement: An edge may clear the assignees

A transition along an edge with `clears_assignees: true` SHALL remove every assignee of the
aggregate in the same update that changes its state, and its `Transition` record SHALL name the
principals it released. Any other transition SHALL leave the assignees unchanged.

#### Scenario: acceptance releases the reviewer
- **GIVEN** a book in `in_review` assigned to p1, and an edge to `accepted` with
  `clears_assignees: true`
- **WHEN** a reviewer moves the book to `accepted`
- **THEN** the book has no assignee, and its last transition names p1 as released

### Requirement: Every assignment change is recorded as provenance

Every assignment that changes the assignees SHALL be recorded, in the same update as the change,
as an `Assignment` activity (a `prov:Activity`) in the tenant's provenance graph, naming the
aggregate, the principals added, the principals removed, the agent and the time.
`collaboration.assignments(iri)` SHALL list them oldest first to a caller who may read `iri`, as
`transitions` lists moves; they SHALL be kept when the aggregate is deleted, and no collaboration
call SHALL return them for an aggregate no longer stored.

#### Scenario: the history of an assignment
- **GIVEN** a book assigned to p1 by e1, then to p1 and p2 by e2
- **WHEN** a session lists the book's assignments
- **THEN** it gets two records in that order: e1 added p1; e2 added p2

### Requirement: Losing read access releases an assignment

After the grants of a tenant are replaced through the toolkit's grants route, the toolkit SHALL
remove, from each aggregate of the tenant, every assignee who may no longer read it by the new
grants, and SHALL record each such change as an `Assignment` whose agent is the caller who
replaced the grants. The release SHALL follow the grant change and SHALL NOT undo it when it fails;
a root whose release is refused SHALL be logged and SHALL NOT stop the release of the others; it
SHALL consider every assignment of a root under a workflow in the tenant, so a release a failure
interrupted is completed by the next grant change. Assignees of a root under no workflow are the
application's and SHALL NOT be touched.

#### Scenario: a member leaves
- **GIVEN** a book assigned to p1 and p2, and p1 reads the library only through its tenant grant
- **WHEN** an administrator replaces the grants without p1's
- **THEN** the book is assigned to p2 only, and its last assignment, by the administrator, removed p1

#### Scenario: access kept another way
- **GIVEN** a book assigned to p1, who holds a tenant grant and a grant on the book
- **WHEN** an administrator removes p1's tenant grant only
- **THEN** the book is still assigned to p1

### Requirement: A person's queue is one listing

The generic listing of a type under an assignable workflow SHALL filter on the assignees:
`?assigned_to=<principal IRI>` SHALL return the aggregates that the principal is one of the
assignees of, and only those the caller may read.

#### Scenario: my work
- **GIVEN** book b1 assigned to p1 and p2, b2 assigned to p2, b3 assigned to no one
- **WHEN** a caller lists books with `assigned_to=<p2>`
- **THEN** the page holds b1 and b2, and the total is 2
