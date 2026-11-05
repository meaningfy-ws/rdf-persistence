Capability: rp-generation. Source: EPIC `toolkit-v1-foundation`; architecture `generation.adoc`
(O-1, D-2, D-6, D-8, D-9).

## ADDED Requirements

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
