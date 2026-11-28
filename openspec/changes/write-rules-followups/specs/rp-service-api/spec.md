## MODIFIED Requirements

### Requirement: A consumer rule refuses a write with its own problem

`install_service` and `ServiceKit` SHALL take optional `refusal_problems`, any iterable of
generated classes that extend `Problem`, a generator included, and SHALL register every class it
yields; start-up SHALL refuse one that does not extend `Problem`, naming it. A write rule SHALL be
able to raise `RuleRefusal(problem)` with an instance of a registered class whose status is the
integer 409 or 422. The write SHALL then be refused before anything is written, and every write
that runs the rules SHALL answer with that problem: its status, type, title, detail and every
extra field. A refusal whose problem is not of a registered class, or whose status is not the
integer 409 or 422 (a float or a boolean included), SHALL be answered as the 500 internal-error
problem and logged once, naming the rule's problem class or its status, with the refusal's
traceback, which names the rule (D-22); a refusal that is answered SHALL NOT be logged as an
error. In-process, the commit SHALL raise the `RuleRefusal`.

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

#### Scenario: a status equal to 409 but not an integer (S2)
- **GIVEN** a rule that refuses with a registered class built with `model_construct` and status `409.0`, or `True`
- **WHEN** a client creates a `Book` the rule refuses
- **THEN** the answer is the 500 internal-error problem, and exactly one error record names the status

#### Scenario: registered through a generator (S1)
- **GIVEN** `refusal_problems` given as a generator of registered classes
- **WHEN** the service starts and a rule refuses with one of them at 409
- **THEN** the answer is that problem; and a generator yielding a class that does not extend `Problem` stops the start-up, naming it

#### Scenario: a class that is not a problem
- **GIVEN** `refusal_problems` naming a class that does not extend `Problem`
- **WHEN** the service starts
- **THEN** it refuses to start, naming the class

### Requirement: A consumer rule finds the aggregates that hold a value

The reader an aggregate validator receives SHALL give, through `find(cls, **equals)`, the IRIs of
the aggregates of `cls` in the write's tenant whose slots equal `equals`, in IRI order, with the
filters `Session.find` takes, except that, each before any query and in this order, no keyword at
all SHALL raise `ValueError`, a dotted slot path SHALL raise `BadQuery`, a `None` value SHALL raise
`TypeError` naming the slot, an empty list SHALL raise `ValueError`, and a value not of the slot's
type SHALL raise `BadQuery`, before the class is checked to be a root, whose
message names the slot and the class and quotes the value bounded in length.
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

#### Scenario: no slot at all (S3)
- **WHEN** a rule calls `reader.find(Book)`
- **THEN** it raises `ValueError`, before any query, in the real reader and in the testkit's fake

#### Scenario: a long value of the wrong type (S5)
- **WHEN** a rule calls `reader.find(Book, pages="x" * 10000)` on an integer slot
- **THEN** it raises `BadQuery` naming `pages` and `Book`, whose message is under 300 characters
