## ADDED Requirements

### Requirement: Technical models are generated apart from domain models

Each technical schema of the toolkit SHALL live under `rdf_persistence/model/technical/<group>/`
(settings, wire records, template variables, request and response bodies, testkit records), annotated
`module_kind: technical`, and SHALL be generated into the `generated/` package of the lowest
layer that every user of its classes may import (a wire record used only by adapters into
`adapters`, a model a service, an adapter or an entrypoint uses into `services`, a testkit record
into `testkit`), apart from the domain models generated from `rdf_persistence/model/rp_*.yaml`
into `domain/generated/`. No module of the domain layer, generated or hand-written, SHALL import a
technical model; a technical model MAY import a domain model. The domain schemas SHALL stay at
their paths.

#### Scenario: a domain model imports a technical one
- **GIVEN** a copy of the toolkit where a generated domain module imports a technical model
- **WHEN** `make check-architecture` runs
- **THEN** it fails and names both modules

#### Scenario: a hand-written domain module imports a technical one
- **GIVEN** a copy of the toolkit where the IRI layout module of the domain layer imports the service settings
- **WHEN** `make check-architecture` runs
- **THEN** it fails and names both modules

#### Scenario: the schemas a consumer imports
- **WHEN** a consumer schema imports `rdf_persistence/model/rp_core`
- **THEN** it resolves as before, and no technical schema can be imported that way

### Requirement: A target declares the kind of model it generates

`rp-generate` SHALL check the `kind` an entry declares (`domain` or `technical`, optional) and
SHALL fail, naming the target and the module, when a technical target holds a module not annotated
`module_kind: technical`, or a domain target holds a module annotated `technical`. An entry without
`kind` SHALL generate as before.

#### Scenario: a domain module in a technical target
- **GIVEN** a target declaring `kind = "technical"` whose folder holds a module annotated `module_kind: domain`
- **WHEN** `rp-generate` runs
- **THEN** it fails naming that module, and no output file changes

#### Scenario: a target without a kind
- **GIVEN** the toy library's table, which declares no `kind`
- **WHEN** `rp-generate` runs
- **THEN** it writes the same files as before

### Requirement: A generated field can hold a toolkit type

The generator SHALL generate a LinkML type whose `repr` names a Python class, annotated
`python_import` with that class's module, as a field of that class, with its import. A SPARQL term field
SHALL accept only text that `term()` produced.

#### Scenario: a raw string in a SPARQL term field
- **GIVEN** a generated term model whose fields range over `sparql_term`
- **WHEN** it is built with a plain string
- **THEN** it is refused before any query text is made

### Requirement: A slot can default to an instance of its class

A slot annotated `default_instance: true` SHALL be generated so that, when no value is given, it
holds a new instance of its range class, a distinct instance for each object built. `rp-generate`
SHALL refuse the annotation, naming the slot and writing nothing, when the slot's range is not a
class, when the range class has a required slot without `ifabsent`, when the slot is multivalued,
or when the range class is declared after the class that holds the slot in the same module. A
multivalued slot whose `ifabsent` is `string(a, b, ...)` SHALL default to the list of those
values; any other `ifabsent` on a multivalued slot SHALL be refused, naming the slot.

#### Scenario: a group defaults to its own defaults
- **GIVEN** a class whose slot ranges over a class whose every slot has a default, annotated `default_instance`
- **WHEN** two objects of the class are built with no value for the slot
- **THEN** each holds an instance of the range class with its defaults, and the two instances are distinct

#### Scenario: a slot that cannot default to an instance
- **GIVEN** a slot annotated `default_instance` whose range is a type, or a class with a required slot without a default, or a class declared after its holder, or a multivalued slot
- **WHEN** `rp-generate` runs
- **THEN** it fails naming the slot, and no output file changes

#### Scenario: a list default
- **GIVEN** a multivalued slot whose `ifabsent` is `string(RS256, ES256)`
- **WHEN** an object is built with no value for the slot
- **THEN** the slot holds the list `RS256`, `ES256`, a distinct list for each object

#### Scenario: a list default in another form
- **GIVEN** a multivalued slot whose `ifabsent` is `int(3)`
- **WHEN** `rp-generate` runs
- **THEN** it fails naming the slot
