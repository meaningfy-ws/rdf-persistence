## ADDED Requirements

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
