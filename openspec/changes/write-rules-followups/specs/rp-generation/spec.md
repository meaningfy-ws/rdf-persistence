## MODIFIED Requirements

### Requirement: A consumer class extends a toolkit technical class the package exports

When a class of a consumer schema is `is_a` a class of a toolkit technical module, the generated
Python class SHALL inherit that class, imported from `rdf_persistence`, and the generated
TypeScript interface SHALL hold every field of the toolkit class, so that it is assignable to it.
When `rdf_persistence` does not export the toolkit class, or a consumer slot is ranged to an enum
of a toolkit technical module that `rdf_persistence` does not export, generation SHALL fail,
naming the consumer class and the toolkit class or enum.

#### Scenario: a consumer problem
- **GIVEN** a consumer technical module that imports the problem module and declares `HeldKeyProblem` with `is_a: Problem` and one extra slot
- **WHEN** `rp-generate` runs
- **THEN** the generated Pydantic class inherits `Problem` imported from `rdf_persistence`, and `tsc --strict` accepts assigning a `HeldKeyProblem` to a `Problem`

#### Scenario: a class the package does not export
- **GIVEN** a consumer class `is_a` a technical class that `rdf_persistence` does not export
- **WHEN** `rp-generate` runs
- **THEN** it fails, naming both classes, and writes nothing

#### Scenario: an enum the package does not export (S6)
- **GIVEN** a consumer class with a slot ranged to a technical enum that `rdf_persistence` does not export
- **WHEN** `rp-generate` runs
- **THEN** it fails, naming the consumer class and the enum, and writes nothing
