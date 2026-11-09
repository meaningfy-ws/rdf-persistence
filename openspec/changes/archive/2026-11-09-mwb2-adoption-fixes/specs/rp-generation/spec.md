<!-- Capability: rp-generation. Change: mwb2-adoption-fixes (#47 DEC-8, #48 DEC-9). -->

## ADDED Requirements

### Requirement: A technical module may hold shapes that are never stored

The ownership rule SHALL NOT apply to classes of a module annotated `module_kind: technical`; they
SHALL be generated in Python and TypeScript. A class of a domain or access module that is neither a
root nor owned SHALL still be refused.

#### Scenario: an API shape in a technical module
- **GIVEN** a technical module with a class that is neither a root nor owned
- **WHEN** `rp-generate` runs
- **THEN** it succeeds and generates the class in Python and TypeScript

#### Scenario: the same class in a domain module
- **GIVEN** a domain module with a class that is neither a root nor owned
- **WHEN** `rp-generate` runs
- **THEN** it fails with an ownership problem naming the class

### Requirement: TypeScript targets get the service's types

When a target sets `typescript`, `rp-generate` SHALL also write the classes of the toolkit's
`rp_service.yaml`, among them the service's wire types, as `rp_service.ts`, exported from
`index.ts`. For such a target, the module name `rp_service` and the names of the classes and enums
of `rp_service.yaml` SHALL be reserved, and the service schema SHALL be an input of the target's
manifest.

#### Scenario: a consumer with a web app
- **GIVEN** a consumer with `typescript` set in `[tool.rp-generate]`
- **WHEN** `rp-generate` runs
- **THEN** its TypeScript folder holds `AccountSummary`, `TenantSummary`, `Page`, `Problem` and
  `GrantSet`, and `tsc --strict` accepts them

#### Scenario: a consumer class named like a service type
- **GIVEN** a consumer with `typescript` set and a class named `Page`
- **WHEN** `rp-generate` runs
- **THEN** it fails with a problem naming `Page` as reserved by `rp_service.ts`

#### Scenario: the service schema changes
- **GIVEN** a consumer with `typescript` set and a fresh manifest
- **WHEN** the toolkit's `rp_service.yaml` changes
- **THEN** the freshness check reports the service schema as a stale input
