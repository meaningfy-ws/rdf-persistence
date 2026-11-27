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
