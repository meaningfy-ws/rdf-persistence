# rp-generation Specification

## Purpose
TBD - created by archiving change toolkit-v1-foundation. Update Purpose after archive.
## Requirements
### Requirement: Generation fails on missing IRIs, labels or definitions

`rp-generate` SHALL fail, naming each offending element, when an element of the application schema
has no IRI (no declared `default_prefix` and no explicit `class_uri`/`slot_uri`), when a class, slot,
enum or permissible value has no `title` or no `description`, or when a permissible value has no
`meaning`.

#### Scenario: a slot without a description
- **WHEN** the toy schema declares a slot `isbn` without a `description`
- **THEN** `rp-generate` exits with an error naming `isbn`, and no output file changes

### Requirement: Generation fails on boundary violations

`rp-generate` SHALL fail when a class is reachable through a non-owned slot without being an
aggregate root, when a class is owned by nothing, or when a module annotated `module_kind: domain`
imports one annotated `technical` or `access`.

#### Scenario: a domain module imports the access module
- **WHEN** a domain module of the toy schema imports the toy access module
- **THEN** `rp-generate` fails and names both modules

### Requirement: Each artefact goes to its declared place

`rp-generate` SHALL write Python classes, shapes and the JSON-LD context to the backend path,
TypeScript types to the frontend path, and one Mermaid class diagram per schema module to the docs
path, as declared in the application's `[tool.rp-generate]` table; command-line flags SHALL override
the table. A failed run SHALL leave every previous output unchanged.

#### Scenario: placement from the table
- **WHEN** the toy application's table declares `typescript = "web/src/domain/generated"`
- **THEN** the TypeScript types are written there and nowhere else

### Requirement: Generated output is reproducible

Running `rp-generate` twice on the same schema with the same pinned `linkml` version SHALL produce
byte-identical output.

#### Scenario: regeneration in CI
- **WHEN** CI regenerates the toy library
- **THEN** the result equals the committed output

### Requirement: LinkML is the single source of every model artefact

Every model artefact SHALL be generated from the LinkML schema: domain classes, shapes, the JSON-LD
context and frames, TypeScript types, OpenAPI component schemas and diagrams.
No such artefact SHALL be written or edited by hand. A gap in a stock generator SHALL be closed by
a toolkit extension with its own test, and a rule the schema declares SHALL be enforced by the
generated classes as well as by the shapes.

#### Scenario: a hand-written domain class
- **WHEN** a module of `rdf_persistence.domain` outside `generated/` defines a pydantic class
- **THEN** the model guard fails and names the class

#### Scenario: classes and shapes agree on a declared rule
- **WHEN** a `Grant` instance has both a role and an action, which `exactly_one_of` forbids
- **THEN** both the generated class and the generated shape refuse it

### Requirement: Stale or edited generated output is detected

`rp-generate --check` SHALL fail, naming the files, when an input of the last generation (the
schema closure, a template or an extension) has changed since, or when a generated file differs
from what was generated. The check SHALL run in `make check-quality`, at the start of every test
session and in CI. Its message SHALL end with a hint naming the command that regenerates: the
`regenerate-command` of each stale `[tool.rp-generate]` entry, or `rp-generate` for an entry that
sets none.

#### Scenario: a schema changed without regenerating
- **WHEN** a slot is added to the toy schema and `rp-generate` is not run
- **THEN** the test session stops before any test runs, naming the schema and the regenerating command

#### Scenario: a generated file edited by hand
- **WHEN** a line of a generated class file is changed by hand
- **THEN** `make check-quality` fails and names that file

#### Scenario: a model change is acknowledged
- **WHEN** a slot is added to the toy schema and the code is regenerated
- **THEN** the model-shape snapshot test fails until `make refresh-snapshot` is run

#### Scenario: an application that sets no command
- **GIVEN** a `[tool.rp-generate]` entry without `regenerate-command`
- **WHEN** its generated code is stale and the check runs through the CLI or the pytest plugin
- **THEN** the hint reads "run `rp-generate` to regenerate, then commit the result"

#### Scenario: an application that names its own command
- **GIVEN** a `[tool.rp-generate]` entry with `regenerate-command = "make generate-models"`
- **WHEN** its generated code is stale and the check runs through the CLI or the pytest plugin
- **THEN** the hint reads "run `make generate-models` to regenerate, then commit the result"

#### Scenario: a configuration error
- **GIVEN** a `[tool.rp-generate]` entry with an unknown key
- **WHEN** the pytest plugin runs
- **THEN** the session stops naming the key, and no regenerating command is suggested

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

### Requirement: The freshness check runs once per parallel session

Under `pytest-xdist`, the freshness plugin SHALL check the generated code once, in the controller,
before any worker starts, and SHALL NOT check again in the workers. A stale tree SHALL stop the
session once, with one message.

#### Scenario: a fresh tree on several workers
- **GIVEN** fresh generated code
- **WHEN** pytest runs with `-n 2`
- **THEN** the check runs in the controller only

#### Scenario: a stale tree on several workers
- **GIVEN** a stale generated target
- **WHEN** pytest runs with `-n 2`
- **THEN** the session stops before any test runs, with one message naming the target and the
  regenerating command

### Requirement: The REFERENCE problem names its fixes

The problem `rp-generate` reports SHALL, when a non-owned slot ranges over a class that is
neither an aggregate root nor a reference class, name the slot, its class and its range, and SHALL
name two fixes: annotating the slot `owned: true`, or making the range an aggregate root or pointing the slot at a root, `Principal` or `Activity`.

#### Scenario: a nested response class without owned
- **GIVEN** a technical module with class `Terms` whose slot `items` ranges over `Term`, not owned
- **WHEN** `rp-generate` runs
- **THEN** it fails with a REFERENCE problem whose text contains `owned: true` and names `Term`

#### Scenario: with owned
- **GIVEN** the same module with `annotations: {owned: true}` on `items`
- **WHEN** `rp-generate` runs
- **THEN** it reports no REFERENCE problem

### Requirement: A unique key across aggregates is declared with its scope

A `unique_keys` entry annotated `rp_unique_scope` SHALL be a key across aggregates; any other
`unique_keys` entry SHALL keep its in-aggregate meaning and its generated validators and shapes.
`rp-generate` SHALL fail, naming the class and the key, when a scoped key: has a scope other than
`tenant`; is declared on a class that is neither a tenant-database aggregate root nor an ancestor
of one; names a slot that is not a slot of every such root, or is multivalued, an identifier,
bookkeeping, or holds an owned part; or sets `consider_nulls_inequal: false`. It SHALL also fail
when a `unique_keys` entry on a tenant-database aggregate root has no `rp_unique_scope`. No
validator or shape SHALL be generated for a scoped key.

#### Scenario: a key on an owned part's slot
- **WHEN** the toy schema declares on `Book` a key `isbn_key` with `rp_unique_scope: tenant` over
  the slot `chapters`
- **THEN** `rp-generate` exits with an error naming `Book`, `isbn_key` and `chapters`, and no
  output file changes

#### Scenario: a key slot that is not a slot of the root
- **WHEN** the toy schema declares on `Book` a scoped key over a slot `binding` that `Book` lacks
- **THEN** `rp-generate` exits with an error naming `Book` and `binding`

#### Scenario: a root key without a scope
- **WHEN** the toy schema declares on `Book` a `unique_keys` entry without `rp_unique_scope`
- **THEN** `rp-generate` exits with an error naming `Book` and the key

#### Scenario: in-aggregate keys are unchanged
- **WHEN** the toolkit's own schemas are generated after this change
- **THEN** the validator and the shape of `Grant`'s key are as before

