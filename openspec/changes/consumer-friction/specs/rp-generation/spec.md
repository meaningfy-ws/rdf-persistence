## ADDED Requirements

### Requirement: A module another target writes as TypeScript is imported, not copied

When a target writes TypeScript and its schema's import closure holds a module whose
`python_package` is the package of another target of the same project, and that target sets
`typescript`, `rp-generate` SHALL NOT write that module into the importing target's folder. The
importing target's modules SHALL import its types from the owner's folder by a relative path, and
the importing target's `index.ts` SHALL NOT export it. When the owner is not a target of the
project, or sets no `typescript`, the module SHALL be written into the importing target's folder,
as before.

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
