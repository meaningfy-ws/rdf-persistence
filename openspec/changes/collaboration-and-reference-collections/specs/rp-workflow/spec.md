<!-- Capability: rp-workflow. Change: collaboration-and-reference-collections (GitHub issue #80). -->

## ADDED Requirements

### Requirement: A workflow is defined in a file and validated

The toolkit SHALL load a workflow definition from a YAML file naming its states, its initial
state and its transitions, each transition with a source state, a target state, the roles
allowed to make it and whether a comment is required. The file SHALL be validated against a model
generated from the metamodel; a definition whose initial state or a transition names an undefined
state, or whose transition names a role the role definitions do not define, SHALL be refused when
loaded, before any request is served.

#### Scenario: a review workflow
- **GIVEN** a file with states `draft`, `in_review`, `accepted`, initial `draft`, and a transition
  `draft` to `in_review` for `librarian`
- **WHEN** the service starts with it
- **THEN** the workflow is available to the classes that name it

#### Scenario: an undefined state
- **WHEN** a file has a transition to `archived`, a state it does not list
- **THEN** loading is refused and names the transition

### Requirement: The toolkit owns the current state of an aggregate under a workflow

An aggregate class whose schema names a workflow SHALL carry a current state (`adms:status`), set
to the workflow's initial state when the aggregate is first stored and readable like any slot. A
state is a `skos:Concept` whose IRI is the workflow's IRI, a slash and the state's name. A plain
write that changes the state SHALL be refused and change nothing; only a transition changes it.
An aggregate stored before its class named the workflow SHALL have no state until its first
transition, which SHALL start from the initial state.

#### Scenario: a new book starts in draft
- **WHEN** a session stores a new book whose class follows the review workflow
- **THEN** reading the book gives the state `draft` (the IRI `<review workflow IRI>/draft`)

#### Scenario: a plain write cannot skip review
- **GIVEN** a stored book in `draft`
- **WHEN** a session replaces the book with the state `accepted`
- **THEN** the replace is refused and the book stays in `draft`

### Requirement: Only defined and permitted transitions happen

`collaboration.transition(iri, to, if_version, comment)` SHALL move the aggregate to `to` only if
the workflow defines a transition from its current state to `to`, the session's principal holds
one of that transition's roles on the tenant or the aggregate, a comment is given when the
transition requires one, no Prohibition of `modify` applies to the principal on the aggregate
or the tenant, and the aggregate still has the version token `if_version` the caller read. Otherwise it SHALL be refused, with the
reason, and nothing SHALL change.

#### Scenario: an allowed transition
- **GIVEN** a book in `draft` and a principal granted `librarian`
- **WHEN** it moves the book to `in_review`
- **THEN** the book's state is `in_review`

#### Scenario: an undefined transition
- **GIVEN** a book in `draft`
- **WHEN** a `librarian` moves it to `accepted` and no transition `draft` to `accepted` exists
- **THEN** the transition is refused and the book stays in `draft`

#### Scenario: a role not on the transition
- **GIVEN** a book in `draft` and a principal granted only `reader`
- **WHEN** it moves the book to `in_review`
- **THEN** the transition is refused and the book stays in `draft`

#### Scenario: a required comment is missing
- **GIVEN** a transition `in_review` to `draft` that requires a comment
- **WHEN** a `librarian` makes it without a comment
- **THEN** the transition is refused

### Requirement: Every transition is recorded as provenance

Every transition SHALL be recorded, in the same update as the state change, as a record that is a `prov:Activity` in the metamodel
of its own naming the aggregate, the source and target states, the principal, the time and the
comment if any. A collaboration SHALL list an aggregate's transitions oldest first. A plain write of the
aggregate SHALL leave its transition records unchanged; deleting the aggregate SHALL delete them.

#### Scenario: the history of a book
- **GIVEN** a book moved from `draft` to `in_review` by p1 with comment "ready", then to
  `accepted` by p2
- **WHEN** a session lists the book's transitions
- **THEN** it gets two records in that order, with agents p1 and p2, their times and the comment
