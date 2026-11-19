## RENAMED Requirements

- FROM: `### Requirement: A target declares the kind of model it generates`
- TO: `### Requirement: A target's kind is derived from its modules`

## MODIFIED Requirements

### Requirement: A target's kind is derived from its modules

`rp-generate` SHALL derive a target's kind from the modules it generates (the modules of its import
closure in its root schema's folder): `technical` when every one is annotated
`module_kind: technical`, `domain` when none is; a target whose modules are some technical and some
not SHALL fail, naming the target and its technical modules. A `[tool.rp-generate]` entry SHALL NOT declare `kind`;
an entry that does SHALL be refused, naming the key. Every target, the toolkit's and a consumer's,
SHALL generate into a package with a `generated` segment, whose segment before `generated` is
`domain` for a domain target, and `services`, `adapters` or `entrypoints` for a technical one; in the
toolkit's own run the segment before that SHALL be a theme of the library (the package is
`rdf_persistence.<theme>.<layer>.generated`). The packages `rdf_persistence.testkit` and
`rdf_persistence_generation`, and those inside them, SHALL be exempt. `rp-generate` SHALL fail,
naming the target, the package and the derived kind, otherwise, and write nothing; when the derived
kind is `domain` and the layer is a technical one, the message SHALL name the `module_kind: technical`
annotation as a fix.

#### Scenario: a domain module in a technical target
- **GIVEN** a toolkit target whose package ends in `.services.generated` and whose root schema generates a module annotated `module_kind: domain`
- **WHEN** `rp-generate` runs
- **THEN** it fails naming the target, its package and the derived kind `domain`, and no output file changes

#### Scenario: a target without a kind
- **GIVEN** the toy library's table, which declares no `kind` and generates into a `domain` package
- **WHEN** `rp-generate` runs
- **THEN** the kind `domain` is derived from its modules and it writes the same files as before

#### Scenario: a technical target pointed at a domain folder
- **GIVEN** a toolkit target of technical modules with a package ending in `.domain.generated`
- **WHEN** `rp-generate` runs on the toolkit
- **THEN** it fails, naming the target and its package, and writes nothing

#### Scenario: an entry that still declares its kind
- **GIVEN** a consumer entry with `kind = "domain"`
- **WHEN** `rp-generate` runs
- **THEN** it fails naming the unknown key `kind`

#### Scenario: a technical target under no theme
- **GIVEN** a toolkit target of technical modules with `package = "rdf_persistence.services.generated"`
- **WHEN** `rp-generate` runs on the toolkit
- **THEN** it fails naming the target and the package, which has no theme before its layer

#### Scenario: a domain target in an adapters folder
- **GIVEN** a toolkit target of domain modules with `package = "rdf_persistence.files.adapters.generated"`
- **WHEN** `rp-generate` runs on the toolkit
- **THEN** it fails naming the target and the package

#### Scenario: a consumer's own layout
- **GIVEN** a consumer target of domain modules with `package = "app.generated"`
- **WHEN** `rp-generate` runs on the consumer
- **THEN** it fails naming the target and the package, which has no layer before `generated`

#### Scenario: a consumer's own themes
- **GIVEN** a consumer target of domain modules with `package = "app.catalogue.domain.generated"`
- **WHEN** `rp-generate` runs on the consumer
- **THEN** no folder problem is reported

#### Scenario: a target of both kinds
- **GIVEN** a target whose root schema generates one module annotated `module_kind: technical` and one not
- **WHEN** `rp-generate` runs
- **THEN** it fails naming the target and the technical module

#### Scenario: a package with no layer at all
- **GIVEN** a consumer target with `package = "generated"`
- **WHEN** `rp-generate` runs on the consumer
- **THEN** it fails naming the target and the package, which has no layer before `generated`

#### Scenario: a consumer's settings without the annotation
- **GIVEN** a consumer target of settings modules not annotated `module_kind: technical`, with `package = "app.services.generated"`
- **WHEN** `rp-generate` runs on the consumer
- **THEN** it fails with the derived kind `domain`, and the message names the `module_kind: technical` annotation
