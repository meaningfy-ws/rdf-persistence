## ADDED Requirements

### Requirement: Each domain module is generated in its theme

Each module of the toolkit's domain model SHALL be generated into the `domain/generated/` package of
its theme: `rp_core` and `rp_annotations` into `rdf_persistence.core.domain.generated`, `rp_access`
and `rp_tenancy` into `rdf_persistence.access.domain.generated`, `rp_provenance` into `provenance`,
`rp_files` into `files`, and `rp_collections`, `rp_discussion` and `rp_workflow` into
`collaboration`, each importing the classes of the modules it uses from their packages. One combined
`shapes.ttl`, `context.jsonld` and set of frames, built from all the domain modules, SHALL be
generated into `rdf_persistence.core.domain.generated`, with the model's migrations lock. The
toolkit's run SHALL write no root module that imports every theme.

#### Scenario: the access concepts
- **WHEN** the toolkit is generated
- **THEN** `Grant`, `Policy`, `RoleDefinition` and `TenantAccess` are defined in `rdf_persistence.access.domain.generated`, and no module of `rdf_persistence.core` defines or imports them

#### Scenario: the combined shapes
- **WHEN** the toolkit is generated
- **THEN** `rdf_persistence/core/domain/generated/shapes.ttl`, `context.jsonld` and the frames hold every domain module's, the same as before the split, and the migrations lock is unchanged

## MODIFIED Requirements

### Requirement: A module of another target is imported, not generated again

When a schema imports a module that declares `python_package`, and that package is not the
`python_package` of the target's root schema, `rp-generate` SHALL import that module's classes from
that package in the generated code, SHALL NOT generate them again, and SHALL record the imported
module's file as an input of the target, whether or not the module sits beside the root schema. In
the toolkit's run, such a module SHALL name the package of a toolkit target that generates it, or
the hard check SHALL fail naming the module and the package. A module beside the root schema without
`python_package`, or beside a root that declares none, SHALL be generated into the target; a
consumer's import of the metamodel SHALL still go through the metamodel's public package.

#### Scenario: one theme's technical schema uses another's
- **GIVEN** a target whose schema imports a module declaring `python_package: pkg.access.services.generated`
- **WHEN** `rp-generate` runs
- **THEN** the generated code imports that module's classes from `pkg.access.services.generated` and defines none of them

#### Scenario: a module beside the root of another target
- **GIVEN** the toolkit target rooted at `rdf_persistence/model/rp_tenancy.yaml`, which imports `rp_core.yaml` beside it, declaring `python_package: rdf_persistence.core.domain.generated`
- **WHEN** `rp-generate` runs
- **THEN** its classes import `rp_core`'s from `rdf_persistence.core.domain.generated`, and the target writes no file for `rp_core`

#### Scenario: a package no target generates
- **GIVEN** a toolkit module beside the root whose `python_package` names a package no toolkit target generates
- **WHEN** the toolkit's `rp-generate` runs
- **THEN** the hard check fails naming the module and the package

#### Scenario: a consumer's module beside its root
- **GIVEN** a consumer schema with no `python_package`, importing a module beside it
- **WHEN** `rp-generate` runs
- **THEN** that module is generated into the consumer's target, as before
