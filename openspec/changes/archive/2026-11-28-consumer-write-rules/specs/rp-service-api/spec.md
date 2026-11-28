## ADDED Requirements

### Requirement: A consumer rule refuses a write with its own problem

`install_service` and `ServiceKit` SHALL take optional `refusal_problems`, generated classes that
extend `Problem`; start-up SHALL refuse one that does not, naming it. A write rule SHALL be able to
raise `RuleRefusal(problem)` with an instance of a registered class whose status is 409 or 422. The
write SHALL then be refused before anything is written, and the generic create and replace routes
SHALL answer with that problem: its status, type, title, detail and every extra field. A refusal
whose problem is not of a registered class, or whose status is neither 409 nor 422, SHALL be
answered as the 500 internal-error problem and logged once, naming the rule's problem class,
with the refusal's traceback, which names the rule (D-22); a refusal that is answered SHALL NOT
be logged as an error. In-process,
the commit SHALL raise the `RuleRefusal`.

#### Scenario: a refusal with a consumer problem type
- **GIVEN** a registered problem class `HeldKeyProblem` with an extra slot `holder`, and a write rule for `Book` that raises `RuleRefusal(HeldKeyProblem(type=T, title="Key held", status=409, detail=d, holder=h))`
- **WHEN** a client creates a `Book` the rule refuses
- **THEN** the answer is 409 with problem type `T`, detail `d` and `holder` `h`, and nothing is written

#### Scenario: a 422 refusal
- **GIVEN** the same class and a rule that refuses with status 422 and problem type `T`
- **WHEN** a client creates a `Book` the rule refuses
- **THEN** the answer is 422 with problem type `T` and the rule's detail

#### Scenario: an unregistered problem class
- **GIVEN** a rule that raises `RuleRefusal` with an instance of a `Problem` subclass not in `refusal_problems`
- **WHEN** a client creates a `Book` the rule refuses
- **THEN** the answer is the 500 internal-error problem, with none of the rule's fields, and the log names the class

#### Scenario: a status outside 409 and 422
- **GIVEN** a rule that refuses with a registered class and status 403
- **WHEN** a client creates a `Book` the rule refuses
- **THEN** the answer is the 500 internal-error problem, and nothing is written

#### Scenario: a class that is not a problem
- **GIVEN** `refusal_problems` naming a class that does not extend `Problem`
- **WHEN** the service starts
- **THEN** it refuses to start, naming the class

### Requirement: A consumer rule finds the aggregates that hold a value

The reader an aggregate validator receives SHALL give, through `find(cls, **equals)`, the IRIs of
the aggregates of `cls` in the write's tenant whose slots equal `equals`, in IRI order, with the
filters `Session.find` takes, except that a `None` value SHALL raise `TypeError` naming the slot,
and a value not of the slot's type, or a dotted slot path, SHALL raise `BadQuery`, each before any
query.
It SHALL leave out an aggregate the writer may not read, one the transaction has removed, and one
the transaction has added or replaced earlier. It SHALL read the store as committed, and no version
guard is recorded.

#### Scenario: another aggregate holds the value
- **GIVEN** a stored `Book` with isbn `v`, and a rule for `Book` calling `reader.find(Book, isbn=v)`
- **WHEN** a client creates another `Book` with isbn `v`
- **THEN** the rule receives the stored book's IRI

#### Scenario: another tenant holds the value
- **GIVEN** a `Book` with isbn `v` stored only in another tenant
- **WHEN** the rule calls `reader.find(Book, isbn=v)` during a create in this tenant
- **THEN** it receives no IRI

#### Scenario: the writer may not read the holder
- **GIVEN** a stored `Book` with isbn `v` that the writer may not read
- **WHEN** the rule calls `reader.find(Book, isbn=v)`
- **THEN** it receives no IRI

#### Scenario: the holder was removed in the same transaction
- **GIVEN** a unit of work that removes the stored `Book` with isbn `v` and then adds another with isbn `v`
- **WHEN** the second book's rule calls `reader.find(Book, isbn=v)`
- **THEN** it receives no IRI

#### Scenario: the key moved away in the same transaction
- **GIVEN** a unit of work that replaces the stored `Book` B1 at isbn `v` with isbn `w`, then adds B2 with isbn `v`
- **WHEN** B2's rule calls `reader.find(Book, isbn=v)`
- **THEN** it receives no IRI, and the commit stores both books

#### Scenario: a None value
- **WHEN** a rule calls `reader.find(Book, isbn=None)`
- **THEN** it raises `TypeError` naming `isbn`, before any query

### Requirement: A consumer registers a rule for its generated class

`aggregate_rules(cls, *rules)` and `delete_rules(cls, *rules)` SHALL be importable from
`rdf_persistence` and SHALL give the `(class name, rules)` entry of the validators mapping, typed so
that a write rule takes `cls` as its new value and `BaseModel | None` as its old value (the stored
root may be of a class `cls` does not derive from), and a delete rule takes `cls`. A rule
registered this way SHALL receive an instance of `cls` as its new value. A mapping keyed by class
name SHALL keep working.

#### Scenario: a typed rule
- **GIVEN** a rule `def check(old: BaseModel | None, new: Book, principal, reader) -> None`
- **WHEN** it is registered as `dict([aggregate_rules(Book, check)])`
- **THEN** mypy accepts it with no `cast`, and the rule receives a `Book`

#### Scenario: a rule for another class
- **GIVEN** a rule typed for `Loan`
- **WHEN** it is registered with `aggregate_rules(Book, rule)`
- **THEN** mypy reports an argument type error

### Requirement: A consumer reads a workflow state's name through the public API

`state_name(workflow, iri)` SHALL be importable from `rdf_persistence` and SHALL give the name of
the state whose IRI `state_iri(workflow, name)` builds. It SHALL raise `ValueError`, naming the IRI
and the workflow, for an IRI that is not the IRI of one of the workflow's states.

#### Scenario: the inverse of state_iri
- **WHEN** a consumer calls `state_name(w, state_iri(w, "draft"))`
- **THEN** it gets `"draft"`

#### Scenario: an IRI that is not a state
- **WHEN** a consumer calls `state_name(w, iri)` with an IRI of another workflow, or of no state of `w`
- **THEN** it raises `ValueError`
