## ADDED Requirements

### Requirement: A consumer schema imports the toolkit's technical modules

A consumer schema SHALL be able to import each schema module under
`rdf_persistence/model/technical/` by the path `rdf_persistence/model/technical/<theme>/<module>`,
as it imports a metamodel module by `rdf_persistence/model/<module>`. The imports a consumer could
write before SHALL resolve as before.

#### Scenario: the problem module
- **GIVEN** a consumer technical schema whose `imports` hold `rdf_persistence/model/technical/api/rp_api_entrypoints`
- **WHEN** `rp-generate` runs
- **THEN** the import resolves to the installed package's module, and no file is looked up under the consumer's folder

### Requirement: A consumer class extends a toolkit technical class the package exports

When a class of a consumer schema is `is_a` a class of a toolkit technical module, the generated
Python class SHALL inherit that class, imported from `rdf_persistence`, and the generated
TypeScript interface SHALL hold every field of the toolkit class, so that it is assignable to it.
When `rdf_persistence` does not export the toolkit class, generation SHALL fail, naming the
consumer class and the toolkit class.

#### Scenario: a consumer problem
- **GIVEN** a consumer technical module that imports the problem module and declares `HeldKeyProblem` with `is_a: Problem` and one extra slot
- **WHEN** `rp-generate` runs
- **THEN** the generated Pydantic class inherits `Problem` imported from `rdf_persistence`, and `tsc --strict` accepts assigning a `HeldKeyProblem` to a `Problem`

#### Scenario: a class the package does not export
- **GIVEN** a consumer class `is_a` a technical class that `rdf_persistence` does not export
- **WHEN** `rp-generate` runs
- **THEN** it fails, naming both classes, and writes nothing

## MODIFIED Requirements

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
- **THEN** it resolves as before
- **AND** a consumer schema that imports a technical module by its path under `model/` (`rdf_persistence/model/technical/<theme>/<module>`) resolves too
- **AND** a path under `rdf_persistence/model/migrations/` does not resolve: that folder holds migrations, not schemas

#### Scenario: a setting used by an adapter and by the service kit
- **GIVEN** the HTTP settings, read by the HTTP adapter base and composed into the toolkit settings the kit takes
- **WHEN** the toolkit is generated
- **THEN** their class is in `rdf_persistence.core.services.generated`, and no entrypoint imports an adapters package

#### Scenario: a wire record
- **GIVEN** the record of an identity provider's answer, used only by the identity adapter
- **WHEN** the toolkit is generated
- **THEN** its class is in `rdf_persistence.access.adapters.generated` and in no `domain` package
