## ADDED Requirements

### Requirement: A consumer rule reads an aggregate its root references

The reader an aggregate validator receives SHALL give, through `aggregate(iri)`, the aggregate at
`iri` decoded as its generated class, as the write's transaction leaves it. It SHALL give None
for an IRI that is not a readable aggregate of the tenant for the writer, or that the transaction
has removed. When the aggregate is read from the store, the commit SHALL fail with a conflict
naming it if its version changes before the commit is applied. The reader's `classes_of` SHALL
behave as before, except that it answers empty for an aggregate the transaction has removed.

#### Scenario: a rule compares a referenced value
- **GIVEN** a validator for `Loan` that refuses a loan naming a book whose title is "forbidden"
- **WHEN** a client creates a loan naming such a book
- **THEN** the answer is 422 with the validator's message, and nothing is written

#### Scenario: an unreadable reference
- **GIVEN** the writer may not read the book a loan names
- **WHEN** the validator asks the reader for that book
- **THEN** it gets None

#### Scenario: a reference in the same transaction
- **GIVEN** a unit of work that adds a book and then a loan naming it
- **WHEN** the loan's validator asks for the book
- **THEN** it gets the book as added, and no version guard is recorded for it

#### Scenario: a reference removed in the same transaction
- **GIVEN** a unit of work that removes a book and then writes a loan naming it
- **WHEN** the loan's validator asks for the book
- **THEN** it gets None

#### Scenario: the reference changes before the commit
- **GIVEN** a validator read a stored book at one version
- **WHEN** the book is replaced before the loan's commit is applied
- **THEN** the commit fails with a conflict naming the book, and the loan is not written

### Requirement: A consumer refuses the delete of a root

`install_service` and `ServiceKit` SHALL take optional delete validators: a mapping from a schema
class name to rules, each called as `(old, principal, reader)`, either a plain function or a
coroutine function, checked at start-up as aggregate validators are. The rules of a class SHALL
run on every removal of a root of that class, or of a class derived from it, through a
transaction, cascades included, before anything is removed. A rule that raises `Conflict` SHALL
refuse the removal: the generic route answers 409 with its message, nothing in the transaction is
removed or written, and any other exception from the rule is an error of the rule. Restore,
migrations and tenant deletion SHALL NOT run them. With no delete validators, removals SHALL
behave as before.

#### Scenario: a refused delete
- **GIVEN** a delete validator for `Book` that refuses while the book is on loan
- **WHEN** a client deletes a book on loan, at its version
- **THEN** the answer is 409 with the validator's message, and the book is still stored at that version

#### Scenario: an allowed delete
- **GIVEN** the same validator
- **WHEN** a client deletes a book that is not on loan
- **THEN** the book is removed

#### Scenario: a refusal inside a cascade
- **GIVEN** a delete validator that refuses one member of a cascade
- **WHEN** the cascade's transaction is committed
- **THEN** it is refused, and nothing is removed

#### Scenario: a bad key
- **WHEN** a service starts with a delete validator keyed by a name that is not an application class a root derives from
- **THEN** start-up fails, naming the key
