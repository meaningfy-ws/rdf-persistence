## MODIFIED Requirements

### Requirement: The toolkit's TypeScript has one owner in a project

When two or more entries of a project's `[tool.rp-generate]` set `typescript`, exactly one of them
SHALL set `toolkit-typescript = true`. That entry, the owner, SHALL write the TypeScript of the
toolkit's shared modules: every module of the metamodel's closure that has classes or enums, and
the served types as `rp_service.ts` with the modules it imports. Every other entry that sets
`typescript` SHALL write none of those modules: its modules SHALL import their types from the
owner's folder by a relative path, and its `index.ts` SHALL NOT export them. A toolkit module
outside the shared set SHALL be written by each entry whose schema imports it, as before. When one
entry sets `typescript`, the key SHALL change nothing in the files written. An entry that sets both
`typescript` and `toolkit-typescript = true` SHALL list the metamodel's schema files among its
freshness inputs, since it writes their modules. `rp-generate` SHALL refuse the configuration
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

#### Scenario: the owner's freshness inputs
- **GIVEN** an entry that sets `typescript` and `toolkit-typescript = true`
- **WHEN** a metamodel schema file changes, one that entry's own schema does not import
- **THEN** `rp-generate --check` reports that entry as stale

#### Scenario: a toolkit module outside the shared set
- **GIVEN** a project with an owner and an importer whose schema imports a toolkit module that is not a metamodel module nor a served one
- **WHEN** the developer regenerates
- **THEN** the importer's folder holds that module's file and its `index.ts` exports it
