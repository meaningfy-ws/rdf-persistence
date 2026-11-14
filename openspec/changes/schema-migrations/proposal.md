<!-- Parents: openspec/specs/rp-generation ("LinkML is the single source of every model artefact");
     openspec/specs/rp-aggregate-store; architecture v1,
     docs/modules/ROOT/pages/architecture/index.adoc (building blocks: "schema migrations",
     deferred). Seeds: inputs/seed.md. -->

# EPIC: Migrate stored data when a schema changes

> Shaped 2026-11-06 from the v1 future list. Planned 2026-11-14 (session H): the PLAN is design.md and tasks.md. The developer's answers are in inputs/seed.md; the questions the developer delegated are answered below as the leader's choices, which the developer may overrule.
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

- **DEC-6** (developer, 2026-11-06): migrations are automatic, by rules modelled on Strapi's, run
  at start-up before serving; a tenant that is behind is refused.
- **DEC-7** (developer, 2026-11-14): the rules run in `rp-generate` against a committed lock;
  the service applies reviewed migration files. A removed slot is drafted as a drop to review,
  never dropped silently.
- **DEC-8** (developer, 2026-11-14): an instance remembers at start-up which tenants are behind.
- **DEC-9** (developer, 2026-11-14): a schema version and a migrations folder are mandatory for
  every consumer; no data exists yet, consumers adjust.
- **DEC-10** (developer, 2026-11-14): this EPIC also reaches the application database of
  `app-level-data`, as its last stage, after PR #102.
- **Leader's choices** (seed Q-1, Q-5 to Q-8; design.md PD-1, PD-2, PD-8, PD-12, PD-13): the
  version is the root schema's LinkML `version:`; it is recorded per database, in the database; a
  migrated database gets new version tokens; no down-migrations (restore a dump); the toolkit's
  metamodel is migrated by the same mechanism. Loaded graphs are not migrated.

## Rabbit-holes

- **Inferring migrations from a schema diff.** Tempting, and wrong for renames and splits.
- **Long migrations on a live service.** A big tenant migrated at start-up delays serving.
- **Version tokens.** Rewriting an aggregate's graph changes its version, so clients holding an
  `ETag` get a conflict; that may be right, but it is a choice.
- **Loaded graphs and blobs.** Loaded RDF files follow their own vocabularies; are they migrated?

## No-gos

- Automatic migrations inferred from a schema diff, beyond the drafts of DEC-7; guessing a rename.
- Down-migrations to older schemas.
- Migrating loaded graphs; validating every stored aggregate at start-up; migrations in Python.
- Migrating file contents in the bucket.
- Migrating between stores (see `second-store`).
- Any consumer term, model or code.

---

## What Changes

Reconciled with the PLAN and the code on 2026-11-14 (see "Reconciliation" below).

- `rdf_persistence/model/`: the stamp's predicate `data_schema_version` (`rp_core.yaml`);
  `Migration`, `MigrationStep` and the problem `tenant_behind` (`service/rp_service.yaml`);
  `version: "1"` on `rp.yaml`; the toolkit's own `model/migrations/` folder with its lock.
- `rdf_persistence/generation/`: the schema lock and its rules (`lock.py`, two pipeline steps), the
  hard checks for `version` and `migrations`, the `migrations` key of a target, and
  `SchemaLock`, `LockChange` in `model/rp_generation.yaml`.
- `rdf_persistence/services/migrations.py`: loading and checking a migration file, the chain, the
  guarded request, the runner per database. `services/tenancy.py`: stamps at creation, the tenants
  set aside. `services/tenant_dump.py` and `domain/tenant_move.py`: dump and restore across versions.
- `rdf_persistence/entrypoints/`: `install_service(migrations=…)`, the start-up order, the problem
  mapping.
- Docs: a new `howto/migrate.adoc`; `howto/adopt.adoc`, `howto/dump-restore.adoc`, the architecture
  pages and `questions.adoc` updated.

## Capabilities

### New Capabilities

- `rp-schema-migrations`: the schema version each database records, the lock and its rules,
  migration files, their runner.

### Modified Capabilities

- `rp-tenancy`: a restore accepts a dump of any version of the chain and migrates it (was: refuses
  a differing schema version).
- `rp-service-api`: `install_service` takes the migrations folder; the problem `tenant-behind`.

## Impact

- **Breaking for every consumer** (DEC-9): a root schema that stores data must declare a quoted
  `version:` and a `migrations` folder in its `rp-generate` target, commit the lock, and pass
  `migrations=` to `install_service`. Generation and start-up fail otherwise.
- A schema change that stored data must follow needs a new version and a reviewed migration file;
  some changes cannot be migrated and are refused at generation (below).
- Start-up runs pending migrations before serving; a tenant whose migration failed answers 503.
- A dump taken before this change (no version, no stamp) no longer restores.

## Reconciliation with the shape (2026-11-14)

The EPIC was shaped on 2026-11-06 with eight open questions. The developer's answers and the code
moved it in the places below. Each row is a recorded decision in [design.md](design.md); nothing
here is a silent edit, and the text above the line "What Changes" is left as it was shaped, apart
from DEC-6 to DEC-10, which were added on 2026-11-14. "Built" means merged or committed on the
branch; "planned" means gated in the PLAN and not built yet.

| The shape said | What is built or planned | Why | Decision | State |
|---|---|---|---|---|
| Solution outline: the consumer "writes a migration" | `rp-generate` compares the schema with a committed lock, passes additive changes, drafts the migration file (a drop for a removed slot, an unresolved step otherwise); the developer reviews and completes it | The developer asked for automatic, Strapi-style rules; the running service never has the old schema, so the comparison cannot run at start-up without storing a schema per tenant | DEC-7, PD-3 | built (stage 1) |
| Solution outline: applied "to every tenant" | To every database: the system database, the application database, then each tenant | Access records and application data follow the schema too; the sweep decodes access records before any tenant is touched | PD-9, PD-16, D-1 | planned (stage 2) |
| DEC-1: any record added is a LinkML class | The lock, the migration and a classified change are generated classes. The stamp is one statement and no class; its predicate is a LinkML slot | The stamp is written by the migration's own request, as the IRI-policy record is; a class would add a mapper round trip for one literal | PD-2, D-3 | built |
| DEC-2: version statements stay statements about the graph IRI | The stamp is about the schema's id, in a graph of its own, `{base}toolkit/schema-stamps` | DEC-2 is about an aggregate's tracking. A stamp describes a database, and a database holds two (the toolkit's metamodel and the consumer's schema) | PD-2 | planned (stage 2) |
| DEC-3: each tenant has its own `meta` graph, so a migration can run per tenant | Per database holds; the version is not in the `meta` graph | `meta` is the tenant root, an aggregate that a session rewrites; the system and application databases have none | PD-2 | planned (stage 2) |
| Why: "an aggregate stored under an older schema surfaces only when someone replaces it" | Still true for data a migration did not fix: nothing validates stored aggregates at start-up | Validating every aggregate at start-up is the rabbit-hole "long migrations on a live service" | Non-Goals | accepted |
| Solution outline: "a service never serves a tenant whose data is behind" | Per instance: each instance remembers which tenants it failed to migrate. An older instance still running does not know | The developer's choice over a stamp read on every request | DEC-8, PD-11, RISK-2 | planned (stage 2) |
| Rabbit-hole: version tokens | A migration with steps renews every version token of the database | A client cannot then overwrite migrated data with an old body; the request cannot tell which graphs a step changed | PD-8, RISK-6 | built (request), planned (runner) |
| Rabbit-hole: loaded graphs and blobs | Loaded graphs, registry graphs and the stamps graph are outside a step's reach; blobs are untouched | Loaded files follow their own vocabularies; the registry is the toolkit's bookkeeping | PD-5, PD-21 item 6 | built |
| Rabbit-hole: long migrations on a live service | One request per migration and database, at start-up; a request that outlasts the timeout sets the tenant aside until the next start | No data exists yet; a longer timeout is a setting to add when a tenant needs it | RISK-3 | accepted |
| Backlog note: migrate stored workflow states when a workflow file drops a state | A "replace a value" step on `adms:status`, carried by a new schema version; nothing detects the dropped state | A workflow file is not the schema, so the lock does not see it | PD-13 | planned (how-to, stage 3) |
| Backlog note: migrate the toolkit's own metamodel modules | Same mechanism: `rp.yaml` has a version, a lock and a migrations folder shipped with the package; its chain runs before the consumer's | One mechanism, as Strapi's internal migrations | PD-13 | built (lock), planned (runner) |
| Not in the shape | Some changes cannot be migrated and are refused at generation: a root's IRI type or path, a root's database, whether a slot's values are owned parts | A step works inside one graph and cannot change an IRI or move data between graphs | PD-3, PD-21 item 5, RISK-8 | built |
| Not in the shape | A migration step is three graph patterns checked by what the SPARQL parser understood; no raw request, no Python | Only a toolkit-built request can carry the stamp guard and the graph scope; the adversarial tests broke a text scan | PD-5, PD-6, PD-21 item 1 | built |
| Not in the shape | Dump and restore across versions: the manifest carries the tenant's own version; a restore migrates the parsed dump before it vets it | `tenant-dump-restore` left it to this EPIC (its DEC-7, PD-2) | PD-15 | planned (stage 3) |
| Impact: "consumers declare a schema version" | Mandatory, with a migrations folder and a required `install_service` argument | The developer's choice; no data exists yet | DEC-9, PD-14 | built (generation), planned (service) |
| Appetite: LARGE | Holds: three stages. The chain loader of stage 2 rides in PR 1, and the application database moved from stage 3 to stage 2 | Parallel builders; PR #102 was already merged | D-1, D-2, D-5 | in delivery |

Nothing above invalidates the bet, so this is a reconciliation and not a re-shape: the problem,
the appetite and the no-gos stand. The two shaped decisions that did not hold as worded, DEC-2 and
DEC-3, are narrowed here and in PD-2, not removed.
