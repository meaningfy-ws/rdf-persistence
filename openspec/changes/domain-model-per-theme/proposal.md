# EPIC: The domain model per theme

Parent: `thematic-structure` (archived 2026-11-19; DEC-1 the theme layout). Seeds and the attack on
the first PLAN: `inputs/seed.md`. Follows `target-kind-from-the-model` (split from this EPIC by the
developer).

## Appetite

MEDIUM. One capability, where the toolkit's generated domain classes live, but it reaches the
generator (which modules a target generates, imports and checks), the model's roots, the import
contracts, and about 100 modules that import the generated classes.

## Why

0.6.0 put every module in its theme, but the toolkit's domain model stayed one generation target:
`rdf_persistence/model/rp.yaml` generates all nine modules into `core/domain/generated/`. So
`access/` holds no `domain/generated/`, and its concepts (`Grant`, `Policy`, `RoleDefinition`) sit in
`core`. The developer wants the layout to say where a concept lives. Splitting also surfaces a cycle
the single target hid: `access` uses `TenantAccess`, and `rp_tenancy` builds on `rp_access`.

## Solution outline

Each theme that owns domain concepts generates them into its own `domain/generated/`, importing the
classes of the themes below it. The RDF artefacts a consumer or the service loads stay one combined
set, built from all domain modules, in `core`. The access and tenancy concepts generate together in
`access`, which removes the cycle; `schema` stops importing classes of themes above it. Consumers
that import from `rdf_persistence` see no change; deep imports of the moved modules break, with a
migration note.

## Key decisions

- **DEC-1**: one domain target per theme: `core` (`rp_core`, `rp_annotations`, root `rp.yaml`),
  `access` (`rp_access`, `rp_tenancy`), `provenance` (`rp_provenance`), `files` (`rp_files`),
  `collaboration` (`rp_collections`, `rp_discussion`, `rp_workflow`), each into
  `rdf_persistence.<theme>.domain.generated`; rejected: one target in `core` (the seed's complaint).
- **DEC-2** (developer, option (b)): one combined `shapes.ttl`, `context.jsonld` and set of frames,
  generated from all domain modules into `rdf_persistence.core.domain.generated`; each theme target
  also writes its own partial ones, unused (developer: agreed); rejected: one set per theme merged
  at load.
- **DEC-3**: `provenance` ranks below `files` in `themes-ordered`, as `rp_files` imports
  `rp_provenance`; rejected: changing the model.
- **DEC-4** (developer, option (a)): `rp_tenancy` is generated in the `access` theme — a tenant is an
  access boundary; the `tenancy` theme keeps its services. Rejected: ranking `access` above
  `tenancy` and moving every tenancy use out of `access` (larger); merging the two themes (renames a
  theme).
- **DEC-5** (developer): a new root `rdf_persistence/model/rp_collaboration.yaml` imports the three
  collaboration modules, so one target generates them; rejected: two targets in one package (they
  delete each other's output).
- **DEC-6** (developer: "do a proper fix"): `schema`'s services stop importing generated classes of
  `files` and `tenancy` (`StoredFile` in `schema_structure.py`, `TenantState` in `vocabulary.py`);
  they read what they need from the schema itself.
- **DEC-7**: the hand-written domain files stay (developer: borderline, hand-written).
- **DEC-8**: released as 0.7.0 with `target-kind-from-the-model`; the CHANGELOG names every moved
  module path.

## Rabbit-holes

- The generator decides three things per module: generate it, import it, or check it. Today one set
  (`own_schemas`, the closure in the root's folder) answers all three; all domain modules share
  `rdf_persistence/model/`, so every target would generate every module it imports. A second set,
  "the modules a target generates", is needed for the Python files, the `python_package` check and
  the migrations check; the shapes, context and frames keep the whole closure (or `core` loses
  frames). Name which step uses which set; do not swap one for the other everywhere.
- The import of a module beside the root must change only when the root declares `python_package`;
  a consumer's import of the metamodel keeps going through `rdf_persistence`.
- 38 library modules and 81 test files deep-import the moved modules, and
  `rdf_persistence/__init__.py` imports them eagerly: the regeneration and the rewrites land in one
  commit, or `import rdf_persistence` fails in between.

## No-gos

- No move of the YAML files in `rdf_persistence/model/` (a new root file is allowed, DEC-5).
- No change to any class, slot or IRI of the model; no migration of stored data.
- No change to the technical targets' layout, nor to the hand-written domain files (DEC-7).
- No per-theme shapes or context to load (DEC-2).
- No change to a name exported from `rdf_persistence`.
- No change to `target-kind-from-the-model`'s rule.

---

## What Changes

- The toolkit's domain classes generate into five packages, `rdf_persistence.<theme>.domain.generated`
  for `core`, `access`, `provenance`, `files`, `collaboration`. **BREAKING** for a deep import of a
  moved module (`rdf_persistence.core.domain.generated.rp_access` and the others).
- `rdf_persistence/model/rp_collaboration.yaml` is new.
- `themes-ordered` ranks `provenance` below `files`.
- The generator imports a module beside the root schema when the module names another package, and
  checks that package exists among the toolkit's targets.
- A consumer's generated code is unchanged; its freshness check asks it to regenerate once.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `rp-generation`: "A module of another target is imported, not generated again" (also beside the
  root); added "Each domain module is generated in its theme".
- `rp-package-boundaries`: "Themes import in one order" (`provenance` below `files`).

## Impact

- `rdf_persistence_generation/` (`extensions/pydantic_split.py`, the hard checks
  `python_package` and `stored_schema`; the mermaid diagrams stay one set, from `rp.yaml`), `rdf_persistence/model/` (annotations, the
  new root), `pyproject.toml` (four new entries), the generated packages, `.importlinter`,
  `rdf_persistence/__init__.py`, 38 library modules and 81 test files (imports), the
  theme-layout and public-surface guards, `schema/services/{schema_structure,vocabulary}.py`, docs
  ("Where a module lives", the model diagrams page), CHANGELOG.
- Consumers (MWBv2): regenerate once; rewrite any deep import of a moved module.
