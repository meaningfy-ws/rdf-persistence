## ADDED Requirements

### Requirement: The toolkit's TypeScript has one owner in a project

When two or more entries of a project's `[tool.rp-generate]` set `typescript`, exactly one of them
SHALL set `toolkit-typescript = true`. That entry, the owner, SHALL write the TypeScript of the
toolkit's shared modules: every module of the metamodel's closure that has classes or enums, and
the served types as `rp_service.ts` with the modules it imports. Every other entry that sets
`typescript` SHALL write none of those modules: its modules SHALL import their types from the
owner's folder by a relative path, and its `index.ts` SHALL NOT export them. A toolkit module
outside the shared set SHALL be written by each entry whose schema imports it, as before. When one
entry sets `typescript`, the key SHALL change nothing. `rp-generate` SHALL refuse the configuration
before any step runs, naming the entries and the key, when several entries set `typescript` and
none or more than one sets `toolkit-typescript = true`, or when an entry sets
`toolkit-typescript = true` without `typescript`, or when two entries set the same `typescript`
folder.

#### Scenario: two TypeScript targets and an owner
- **GIVEN** a project whose entry with `typescript = "web/src/domain/generated"` sets `toolkit-typescript = true` and whose entry with `typescript = "web/src/services/generated"` does not
- **WHEN** the developer regenerates
- **THEN** `web/src/domain/generated/` holds `rp_core.ts` and `rp_service.ts`, `web/src/services/generated/` holds neither, its modules import the toolkit types `from "../../domain/generated/<module>"`, its `index.ts` exports no toolkit module, and `tsc --strict` compiles both folders

#### Scenario: the old copies are removed
- **GIVEN** a project whose second TypeScript target wrote copies of the toolkit modules on an earlier run
- **WHEN** an owner is named and the developer regenerates
- **THEN** the copies are removed from the second target's folder as stale outputs

#### Scenario: one TypeScript target
- **GIVEN** a project with one entry that sets `typescript`, with or without `toolkit-typescript`
- **WHEN** the developer regenerates
- **THEN** its TypeScript folder holds the same files as before this change

#### Scenario: several TypeScript targets and no owner
- **GIVEN** a project with two entries that set `typescript` and none that sets `toolkit-typescript = true`
- **WHEN** the developer runs `rp-generate`
- **THEN** it fails before writing anything, naming both entries and telling the developer to set `toolkit-typescript = true` on the one whose folder holds the toolkit's types

#### Scenario: the key on an entry without TypeScript
- **GIVEN** a project with an entry that sets `toolkit-typescript = true` and no `typescript`
- **WHEN** the developer runs `rp-generate`
- **THEN** it fails before writing anything, naming that entry and saying the key needs `typescript` on the same entry

#### Scenario: two entries share a TypeScript folder
- **GIVEN** a project with two entries that set the same `typescript` folder
- **WHEN** the developer runs `rp-generate`
- **THEN** it fails before writing anything, naming both entries and the folder

#### Scenario: two owners
- **GIVEN** a project with two entries that set `typescript` and `toolkit-typescript = true`
- **WHEN** the developer runs `rp-generate`
- **THEN** it fails before writing anything, naming both entries and saying only one may set the key

## MODIFIED Requirements

### Requirement: TypeScript targets get the service's types

When a target sets `typescript`, `rp-generate` SHALL also write the classes of the schemas the HTTP
API serves, among them the service's wire types, which are in
`rdf_persistence/model/technical/api/rp_api_entrypoints.yaml`, as one module `rp_service.ts`,
exported from `index.ts`; in a project with several TypeScript targets, only the owner of the
toolkit's TypeScript writes it, and the others import its types from the owner's folder. For such a
target, the module name `rp_service`, the names of the served schemas' modules and the names of
their classes and enums SHALL be reserved, and every served schema SHALL be an input of the
target's manifest. A technical class that is not served SHALL add nothing to `rp_service.ts`.

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

### Requirement: A module another target writes as TypeScript is imported, not copied

When a target writes TypeScript and its schema's import closure holds a module whose
`python_package` is the package of another target of the same project, and that target sets
`typescript`, `rp-generate` SHALL NOT write that module into the importing target's folder. The
importing target's modules SHALL import its types from the owner's folder by a relative path, and
the importing target's `index.ts` SHALL NOT export it. When the owner is not a target of the
project, or sets no `typescript`, the module SHALL be written into the importing target's folder,
as before, unless it is one of the toolkit's shared modules and the project names an owner of the
toolkit's TypeScript.

#### Scenario: the owner writes TypeScript
- **GIVEN** a technical target with `typescript = "web/src/services/generated"` whose schema imports a value module of a target with `typescript = "web/src/domain/generated/values"`
- **WHEN** the developer regenerates
- **THEN** `web/src/services/generated/` holds no file for the value module, its module imports the value types `from "../../domain/generated/values/<module>"`, its `index.ts` does not export the value module, and `tsc --strict` compiles both folders

#### Scenario: the owner's folder is under the importer's
- **GIVEN** an importing target with `typescript = "web/src/domain/generated"` and an owner with `typescript = "web/src/domain/generated/values"`
- **WHEN** the developer regenerates
- **THEN** the importer imports the owner's types `from "./values/<module>"`

#### Scenario: the owner writes no TypeScript
- **GIVEN** a technical target with `typescript` set whose schema imports a value module of a target without `typescript`
- **WHEN** the developer regenerates
- **THEN** the technical target's folder holds the value module's file and its `index.ts` exports it, as before

#### Scenario: the old copy is removed
- **GIVEN** a project whose importing target wrote a copy of the owner's module on an earlier run
- **WHEN** the owner sets `typescript` and the developer regenerates
- **THEN** the copy is removed from the importing target's folder as a stale output
