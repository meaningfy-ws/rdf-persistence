## ADDED Requirements

### Requirement: A value module generates never-stored domain values

A module annotated `module_kind: value` SHALL be generated into the domain layer (a package ending
in `domain.generated[.<group>]`). Its classes SHALL be exempt from the ownership, owned-class and
aggregate-root rules, and SHALL NOT be aggregate roots or tenant roots. A value module SHALL import
only domain, value and toolkit modules. A stored class SHALL NOT hold a class of a value module; it
MAY use an enum of one. A module of another target that imports a value module declaring
`python_package` SHALL import its classes from that package and not generate them again.

#### Scenario: a value module in the domain layer
- **GIVEN** a `module_kind: value` module with an enum and two classes that are neither roots nor owned
- **WHEN** `rp-generate` runs on a target whose package is `library.domain.generated.values`
- **THEN** the boundary and hard checks report no problem and the Python classes are generated

#### Scenario: a technical module reuses the value classes
- **GIVEN** a technical module that imports the value module
- **WHEN** both targets are generated
- **THEN** the technical module's Python imports the value classes from the value package, so both hold the same class

#### Scenario: a value module imports a technical module
- **WHEN** the boundary check runs
- **THEN** it refuses the value module with a `module_kind` problem and a hint to move the class

#### Scenario: a value class declared as a root
- **GIVEN** a value class that mixes in `AggregateRoot`
- **WHEN** the boundary check runs
- **THEN** it refuses the class: a value is never stored

### Requirement: A slot over an abstract aggregate root is a reference

A slot whose range has `AggregateRoot` among its ancestors and is not owned SHALL be generated as a
reference whether its range is abstract or concrete: `str` (or `list[str]`) in Python, `string` in
TypeScript, `sh:nodeKind sh:IRI` in the shapes.

#### Scenario: a loan lends an item
- **GIVEN** an abstract `Item` mixing in `AggregateRoot`, concrete roots below it, and a root `Loan` with `lends: {range: Item, required: true}`
- **WHEN** `rp-generate` runs
- **THEN** `Loan.lends` is `str` in Python and `string` in TypeScript, and an instance naming a book by its IRI validates and round-trips
