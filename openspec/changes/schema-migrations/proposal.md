<!-- Parents: openspec/specs/rp-generation ("LinkML is the single source of every model artefact");
     openspec/specs/rp-aggregate-store; architecture v1,
     docs/modules/ROOT/pages/architecture/index.adoc (building blocks: "schema migrations",
     deferred). Seeds: inputs/seed.md. -->

# EPIC: Migrate stored data when a schema changes

> Candidate EPIC, shaped 2026-11-06 from the v1 future list. Not planned: the PLAN (design.md, tasks.md) waits for the developer's answers in inputs/seed.md.
>
> **Backlog position (2026-11-12):** after the tenant-governance EPICs (`tenant-dump-restore` records the schema version in its manifest, which this EPIC then reads). It must migrate the toolkit's own new metamodel modules (`rp_collections`, `rp_workflow`, `rp_discussion`) and stored workflow states when a workflow file drops a state (No-go of the collaboration EPIC). See `openspec/changes/README.md`.

**Golden-thread parent:** capabilities `rp-generation` and `rp-aggregate-store`, and the deferred
building block "schema migrations" of `docs/modules/ROOT/pages/architecture/index.adoc`.

## Appetite

**LARGE.** Several related capabilities: recording which schema version stored data follows,
describing a migration, running it per tenant safely, and detecting data that no longer fits. It
touches generation, the session, tenancy and the start-up path.

## Why

In v1 the LinkML schema changes freely: `rp-generate` regenerates classes, shapes and context, and
the freshness check (`generation/manifest.py`, PD-26) guards the generated code. Stored data is not
guarded. No schema version is recorded with a tenant or an aggregate (`model/rp.yaml` and the toy
schemas carry none). Bodies are validated with the shapes on write (PD-14), so an aggregate stored
under an older schema surfaces only when someone replaces it and the shapes refuse it; reads return
the old graph as it is.

## Solution outline

When a consumer changes its schema in a way that stored data must follow (a renamed slot, a split
class, a new required slot), it writes a migration, and the toolkit applies it to every tenant once,
in order, recording which version each tenant's data follows. A service never serves a tenant whose
data is behind the schema it runs, and a failed migration leaves the tenant usable at its previous
version. The toolkit's own metamodel changes are migrated the same way.

## Key decisions

- **DEC-1**: LinkML is the single source; any record this EPIC adds (a schema version, a migration
  record) is a LinkML class, generated, and handled through generated models, not dicts (D-13;
  PD-24; AGENTS.md).
- **DEC-2**: Tracking and version statements stay statements about the graph IRI (D-7, PD-5, PD-7).
- **DEC-3**: Each tenant has its own database and its own `meta` graph (PD-6a), so a migration can run
  per tenant.
- **DEC-4**: SPARQL is built only through `domain/sparql.py` (PD-3).
- **DEC-5**: `linkml` and `linkml-runtime` stay pinned together; a bump regenerates the toy library
  and reviews the diff (archived DEC-5). A generator bump is not a data migration.

## Rabbit-holes

- **Inferring migrations from a schema diff.** Tempting, and wrong for renames and splits.
- **Long migrations on a live service.** A big tenant migrated at start-up delays serving.
- **Version tokens.** Rewriting an aggregate's graph changes its version, so clients holding an
  `ETag` get a conflict; that may be right, but it is a choice.
- **Loaded graphs and blobs.** Loaded RDF files follow their own vocabularies; are they migrated?

## No-gos

- Automatic migrations inferred from a schema diff, beyond what the developer chooses in Q-2.
- Down-migrations to older schemas, unless chosen in Q-5.
- Migrating file contents in the bucket.
- Migrating between stores (see `second-store`).
- Any consumer term, model or code.

---

## What Changes

- `rdf_persistence/model/`: a schema-version record (in `rp_tenancy` or a new module).
- `rdf_persistence/services/`: a migration runner, per tenant; tenancy records the version.
- `rdf_persistence/entrypoints/service.py`: the start-up path checks (and maybe runs) migrations.
- `rdf_persistence/generation/`: what a migration needs from the schema (a declared version).
- `docs/modules/ROOT/pages/howto/adopt.adoc`: a step for changing a schema with stored data.

## Capabilities

### New Capabilities

- `rp-schema-migrations`: the stored schema version, migrations and their runner.

### Modified Capabilities

None.

## Impact

- Consumers declare a schema version; changing a schema with stored data needs a migration.
- Start-up may take longer or refuse to serve a tenant that is behind.
