## ADDED Requirements

### Requirement: A module of another target is imported, not generated again

When a schema imports a module that declares `python_package`, `rp-generate` SHALL import that
module's classes from that package in the generated code, SHALL NOT generate them again, and SHALL
record the imported module's file as an input of the target.

#### Scenario: one theme's technical schema uses another's
- **GIVEN** a target whose schema imports a module declaring `python_package: pkg.access.services.generated`
- **WHEN** `rp-generate` runs
- **THEN** the generated code imports that module's classes from `pkg.access.services.generated` and defines none of them

### Requirement: Generated consumer code imports the toolkit from its public package

The Python classes `rp-generate` writes for an application SHALL import every toolkit name,
`RpModel` included, from `rdf_persistence` and from no deeper module.

#### Scenario: the toy library
- **WHEN** the toy library is generated
- **THEN** each generated module imports `RpModel` from `rdf_persistence`, and `testkit.assert_public_imports` finds no deep import in it

## MODIFIED Requirements

### Requirement: LinkML is the single source of every model artefact

Every model artefact SHALL be generated from the LinkML schema: domain classes, shapes, the JSON-LD
context and frames, TypeScript types, OpenAPI component schemas and diagrams.
No such artefact SHALL be written or edited by hand. A gap in a stock generator SHALL be closed by
a toolkit extension with its own test, and a rule the schema declares SHALL be enforced by the
generated classes as well as by the shapes.

#### Scenario: a hand-written domain class
- **WHEN** a module of `rdf_persistence.<theme>.domain` outside `generated/` defines a pydantic class
- **THEN** the model guard fails and names the class

#### Scenario: a consumer's class derived from the public base
- **GIVEN** a consumer module with `from rdf_persistence import RpModel` and `class Book(RpModel)` outside `generated/`
- **WHEN** the model guard runs on the consumer
- **THEN** it fails and names `Book`

#### Scenario: classes and shapes agree on a declared rule
- **WHEN** a `Grant` instance has both a role and an action, which `exactly_one_of` forbids
- **THEN** both the generated class and the generated shape refuse it

### Requirement: Technical models are generated apart from domain models

Each technical schema of the toolkit SHALL live under `rdf_persistence/model/technical/<theme>/`
as `rp_<theme>_<layer>.yaml` (settings, wire records, template variables, request and response
bodies), or as `rp_<theme>_settings.yaml` or `rp_<theme>_templates.yaml` for a non-served group
(D-15 (1)), or under `rdf_persistence/model/technical/testkit/` for the testkit records, annotated
`module_kind: technical`, and SHALL be generated into the `generated/` package of the lowest layer
that every user of its classes may import, in the lowest theme that uses them
(`<theme>/<layer>/generated/`, `<layer>` being `services`, `adapters` or `entrypoints`, and
`services` when both an adapter and an entrypoint use them; a `settings` or `templates` group into
`<theme>/<layer>/generated/settings/` or `<theme>/<layer>/generated/templates/`; a testkit record
into `testkit`),
apart from the domain models, which SHALL sit only in a `<theme>/domain/generated/` package. No
module of a domain layer, generated or hand-written, SHALL import a technical model; a technical
model MAY import a domain model. The domain schemas SHALL stay at their paths.

#### Scenario: a domain model imports a technical one
- **GIVEN** a copy of the toolkit where a generated domain module imports a technical model
- **WHEN** `make check-architecture` runs
- **THEN** it fails and names both modules

#### Scenario: a hand-written domain module imports a technical one
- **GIVEN** a copy of the toolkit where the IRI layout module of the `iris` theme's domain layer imports the service settings
- **WHEN** `make check-architecture` runs
- **THEN** it fails and names both modules

#### Scenario: the schemas a consumer imports
- **WHEN** a consumer schema imports `rdf_persistence/model/rp_core`
- **THEN** it resolves as before, and no technical schema can be imported that way

#### Scenario: a setting used by an adapter and by the service kit
- **GIVEN** the HTTP settings, read by the HTTP adapter base and composed into the toolkit settings the kit takes
- **WHEN** the toolkit is generated
- **THEN** their class is in `rdf_persistence.core.services.generated`, and no entrypoint imports an adapters package

#### Scenario: a wire record
- **GIVEN** the record of an identity provider's answer, used only by the identity adapter
- **WHEN** the toolkit is generated
- **THEN** its class is in `rdf_persistence.access.adapters.generated` and in no `domain` package

### Requirement: A target declares the kind of model it generates

`rp-generate` SHALL check the `kind` an entry declares (`domain` or `technical`, optional) and
SHALL fail, naming the target and the module, when a technical target holds a module not annotated
`module_kind: technical`, or a domain target holds a module annotated `technical`. An entry without
`kind` SHALL generate as before. In the toolkit's own run, a target that declares
`kind = "domain"` SHALL generate into a package whose segment before `generated` is `domain`, and
one that declares `kind = "technical"` into a package whose segment before `generated` is
`services`, `adapters` or `entrypoints`, and the segment before that is a theme of the library
(the package is `rdf_persistence.<theme>.<layer>.generated`); the packages outside the themes,
`rdf_persistence.testkit` and `rdf_persistence_generation`, are exempt. `rp-generate` SHALL fail, naming the target and the
package, otherwise. A consumer's targets SHALL NOT be checked for their folder.

#### Scenario: a domain module in a technical target
- **GIVEN** a target declaring `kind = "technical"` whose folder holds a module annotated `module_kind: domain`
- **WHEN** `rp-generate` runs
- **THEN** it fails naming that module, and no output file changes

#### Scenario: a target without a kind
- **GIVEN** the toy library's table, which declares no `kind`
- **WHEN** `rp-generate` runs
- **THEN** it writes the same files as before

#### Scenario: a technical target pointed at a domain folder
- **GIVEN** a toolkit target with `kind = "technical"` and a package ending in `.domain.generated`
- **WHEN** `rp-generate` runs on the toolkit
- **THEN** it fails, naming the target and its package, and writes nothing

#### Scenario: a technical target under no theme
- **GIVEN** a toolkit target with `kind = "technical"` and `package = "rdf_persistence.services.generated"`
- **WHEN** `rp-generate` runs on the toolkit
- **THEN** it fails naming the target and the package, which has no theme before its layer

#### Scenario: a domain target in an adapters folder
- **GIVEN** a toolkit target with `kind = "domain"` and `package = "rdf_persistence.files.adapters.generated"`
- **WHEN** `rp-generate` runs on the toolkit
- **THEN** it fails naming the target and the package

#### Scenario: a consumer's own layout
- **GIVEN** a consumer target with `kind = "technical"` and `package = "app.generated"`
- **WHEN** `rp-generate` runs on the consumer
- **THEN** no folder problem is reported

### Requirement: TypeScript targets get the service's types

When a target sets `typescript`, `rp-generate` SHALL also write the classes of the schemas the HTTP
API serves, among them the service's wire types, which are in
`rdf_persistence/model/technical/api/rp_api_entrypoints.yaml`, as one module `rp_service.ts`,
exported from `index.ts`. For such a target, the module name `rp_service`, the names of the served
schemas' modules and the names of their classes and enums SHALL be reserved, and every served schema
SHALL be an input of the target's manifest. A technical class that is not served SHALL add nothing
to `rp_service.ts`.

#### Scenario: a consumer with a web app
- **GIVEN** a consumer with `typescript` set in `[tool.rp-generate]`
- **WHEN** `rp-generate` runs
- **THEN** its TypeScript folder holds `AccountSummary`, `TenantSummary`, `Page`, `Problem` and
  `GrantSet`, all in `rp_service.ts`, and `tsc --strict` accepts them

#### Scenario: a consumer class named like a service type
- **GIVEN** a consumer with `typescript` set and a class named `Page`
- **WHEN** `rp-generate` runs
- **THEN** it fails with a problem naming `Page` as reserved by `rp_service.ts`

#### Scenario: the service schema changes
- **GIVEN** a consumer with `typescript` set and a fresh manifest
- **WHEN** the toolkit's `rp_api_entrypoints.yaml` or another served schema changes
- **THEN** the freshness check reports that schema as a stale input
