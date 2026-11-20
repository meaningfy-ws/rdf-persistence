## MODIFIED Requirements

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
- **THEN** `rdf_persistence/core/domain/generated/` holds one `shapes.ttl`, one `context.jsonld` and the frames, built from every domain module, with the same set of frames as before the split, the migrations lock sits beside the metamodel, and the committed files equal a regeneration
