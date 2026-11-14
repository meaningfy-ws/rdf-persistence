<!-- Parents: openspec/specs/rp-generation ("LinkML is the single source of every model artefact");
     openspec/specs/rp-aggregate-store; architecture v1,
     docs/modules/ROOT/pages/architecture/index.adoc (building blocks: "schema migrations",
     deferred). Seeds: inputs/seed.md. -->

# EPIC: Migrate stored data when a schema changes

> Shaped 2026-11-06 from the v1 future list. Planned 2026-11-14 (session H): the PLAN is design.md and tasks.md. The developer's answers are in inputs/seed.md; the questions the developer delegated are answered below as the leader's choices, which the developer may overrule. Delivered in three stages (#109, #112, stage 3); the text above "What Changes" is the bet as shaped, and the table "Reconciliation with the shape" at the end records every place the delivery left it.
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

As delivered, in three stages: stage 1 (#109) the lock, the rules and migration files; stage 2
(#112) the stamps, the runner, start-up and the tenants set aside; stage 3 (branch
`feature/schema-migrations-stage-3`) dump and restore across versions, the Fuseki proof and the docs.

- `rdf_persistence/model/` (stage 1): the stamp's predicate `data_schema_version` (`rp_core.yaml`);
  `Migration`, `MigrationStep` and the problem `tenant_behind` (`service/rp_service.yaml`);
  `version: "1"` on `rp.yaml`; the toolkit's own `model/migrations/` folder with its lock and no
  migration yet. The slot `schema_id` now has the IRI `rp:schemaId` (was `rp:dumpSchemaId`).
- `rdf_persistence/generation/` (stage 1): the lock, its rules and drafts (`lock.py`), the check and
  write steps (`lock_step.py`), the hard rules `migrations_folder` and `quoted_version`
  (`checks/hard.py`), the `migrations` key of a target, and `SchemaLock`, `LockChange`, `LockRule`
  in `model/rp_generation.yaml`.
- `rdf_persistence/domain/` (stages 1, 2): `stamps_graph_iri`; `sparql.py` `checked_group`, the one
  check of a step's pattern on the parser's tree; the exceptions `InvalidMigration`,
  `MigrationFailed`, `TenantBehind`; `tenant_move.py` accepts and copies the stamps graph.
- `rdf_persistence/services/`: `migrations.py` (stage 1, 2: the file, the chain, the guarded
  request, the stamps and the stamps rule `stamp_problems`); `migration_runner.py` (stage 2:
  `migrate_database`, `migrate_shared`, `migrate_tenants`; stage 3: `migrate_dataset`);
  `yaml_files.py` (stage 1: one YAML reader, shared with the workflow loader); `tenancy.py`
  (stage 2: stamps at creation, `behind`, `set_aside`, the refusal in `tenant_session`);
  `tenant_dump.py` (stage 3: `dump` writes the tenant's stamp, `restore` migrates the dump).
- `rdf_persistence/entrypoints/` (stage 2): `install_service(migrations=…)`, `ServiceKit.chains`,
  the start-up order, the mapping of the three exceptions. `.importlinter` (stage 3): the runner
  stays above `migrations.py` and `tenancy.py`.
- Docs (stage 3): a new `howto/migrate.adoc`; `howto/adopt.adoc`, `howto/dump-restore.adoc`,
  `architecture/index.adoc`, `data-flows.adoc`, `api.adoc`, `generation.adoc`, `questions.adoc`.

## Capabilities

### New Capabilities

- `rp-schema-migrations`: the schema version each database records, the lock and its rules,
  migration files, their runner, and a dump's version and its migration on restore.

### Modified Capabilities

- `rp-tenancy`: a restore accepts a dump of any version of the chain and migrates it (was: refuses
  a differing schema version).
- `rp-service-api`: `install_service` takes the migrations folder; the problem `tenant-behind`.

## Impact

**BREAKING** for every consumer (DEC-9), and nothing else needs a data change, since no data exists
yet:

- `rp-generate`: a target whose own modules define a root class needs a `migrations` key, and its
  root schema a quoted `version:`; the lock is committed. Generation fails otherwise.
- `install_service(migrations=...)` and `ServiceKit(migrations=...)` are required; a chain that is
  not one line ending at the schema's version, or a schema with no version, stops the service.
- A restore refuses a dump with no stamps, with a stamp that is not a plain string at a version of
  the chain, or whose manifest version differs from its stamp. So a dump made before this change
  no longer restores.
- `load_workflow` refuses a workflow file with a key given twice and lists at most five problems.
- The slot IRI of `schema_id` is `rp:schemaId`: the generated shapes and JSON-LD context change; a
  dump manifest is JSON, so nothing stored changes.

Behaviour: start-up runs pending migrations before serving; a tenant whose migration failed answers
503 `tenant-behind` for its data. Public API added: `InvalidMigration`, `MigrationFailed`,
`TenantBehind`; `ServiceKit.chains`; `Tenancy(stamps=...)`, `.behind`, `.set_aside`,
`.stamps_graph`; `stamps_graph_iri`; in `services/migrations.py` `load_migration`, `load_chain`,
`chain_of`, `migration_file_name`, `migration_request`, `stamps`, `stamp_if_none`,
`stamp_problems`, `versions`, `first_version`, `current_version`, `pending_from`; in
`services/migration_runner.py` `migrate_database`, `migrate_shared`, `migrate_tenants`,
`migrate_dataset`; `tenant_dump.restore(chains=...)` (required).

## Delivered

The EPIC delivers a recorded schema version per database, Strapi-style rules run by `rp-generate`
against a committed lock, reviewed migration files applied at start-up once, in order and
atomically per migration and database, tenants set aside on failure, and dump and restore across
versions; the bet held. PRs: #109 (stage 1), #112 (stage 2), stage 3 on its branch. Challenge:
PLAN attacked (PD-18), gated 9.1/10 (PD-19); adversarial testers broke stage 1 (PD-21), the runner
(PD-23) and restore across versions (PD-26); four reviewers per stage, no blocker (PD-22, PD-24,
PD-25); fresh checkers on stages 1 and 2; a cold read of the how-to (its writer found RISK-11).
The developer decided: the blast-radius answers of PD-20 and the four answers of 2026-11-14
(`inputs/seed.md`). Left to the developer: accepting and archiving the EPIC; the upstream report
to rdflib (PD-26); issue #108.

## Reconciliation with the shape (2026-11-15)

The EPIC was shaped on 2026-11-06 with eight open questions. The developer's answers and the code
moved it in the places below. Each row is a recorded decision in [design.md](design.md); nothing
here is a silent edit, and the text above the line "What Changes" is left as it was shaped, apart
from DEC-6 to DEC-10, added on 2026-11-14, and the header note. "Stage 3" is committed on
`feature/schema-migrations-stage-3`, not yet merged.

| The shape said | What was built | Why | Decision | State |
|---|---|---|---|---|
| Solution outline: the consumer "writes a migration" | `rp-generate` compares the schema with a committed lock, passes additive changes, drafts the migration file (a drop for a removed slot, an unresolved step otherwise); the developer reviews and completes it | The developer asked for automatic, Strapi-style rules; the running service never has the old schema, so the comparison cannot run at start-up without storing a schema per tenant | DEC-7, PD-3 | built (stage 1, #109) |
| Solution outline: applied "to every tenant" | To every database: the system database, the application database (when the schema has an application class), then each tenant not being deleted, in order of IRI | Access records and application data follow the schema too; the sweep decodes access records, so the shared databases are migrated before it | PD-9, PD-16, D-1 | built (stage 2, #112) |
| Solution outline: "a failed migration leaves the tenant usable at its previous version" | Atomic per migration and database, not per run: with a chain `1, 2, 3` a tenant can stop at `2`. The failed tenant keeps its data and stamp but is set aside by the release that failed; only the previous release can serve it, and that release will not start once the new one has moved the shared databases' stamps | One request per migration keeps the stamp guard simple; the toolkit has no dump of the shared databases, so a rollback needs a backup of the store itself (how-to) or a fix forward | PD-7, PD-12 narrowed by RISK-11 | built (stage 2, #112); rollback of shared databases not built |
| Solution outline: "a service never serves a tenant whose data is behind" | Per instance: each instance remembers which tenants it failed to migrate; an older instance still running does not know. A tenant set aside answers `503` `tenant-behind` for its data and for a rename; its record, its grants, its deletion, a dump and the live sweep still work | The developer's choice over a stamp read on every request; the operator rescues the tenant through what still works | DEC-8, PD-11 (as amended in stage 2), RISK-2 | built (stage 2, #112) |
| DEC-1: any record added is a LinkML class | The lock, the migration and a classified change are generated classes. The stamp is one statement and no class; its predicate is the LinkML slot `data_schema_version` | The stamp is written by the migration's own request, as the IRI-policy record is; a class would add a mapper round trip for one literal | PD-2, D-3 | built (stage 1, #109) |
| DEC-2: version statements stay statements about the graph IRI | Tracking statements are unchanged. The stamp is about the schema's id, in a graph of its own, `{base}toolkit/schema-stamps`, one per schema per database | DEC-2 is about an aggregate's tracking. A stamp describes a database, and a database holds two (the toolkit's metamodel and the consumer's schema) | PD-2 | built (stage 2, #112) |
| DEC-3: each tenant has its own `meta` graph, so a migration can run per tenant | Per database holds; the version is in the stamps graph, not in `meta` | `meta` is the tenant root, an aggregate that a session rewrites; the system and application databases have none | PD-2 | built (stage 2, #112) |
| Not in the shape: what a stamp is | A stamp is a plain string literal; a stamp with a language tag or a datatype is "not a stamp". One rule, `stamp_problems`, judges a dump's stamps graph: one stamp per schema of the service, at a version the caller accepts, and nothing else | A typed stamp passed every check and could never match the runner's guard again | PD-24 item 1, PD-25 items 1, 8 | built (stages 2 and 3) |
| Why: "an aggregate stored under an older schema surfaces only when someone replaces it" | Still true for data a migration did not fix: nothing validates stored aggregates at start-up | Validating every aggregate at start-up is a No-go and the rabbit-hole "long migrations on a live service" | Non-Goals | accepted |
| Rabbit-hole: version tokens | A migration with steps renews every version token of the database; `dcterms:modified` and contributors stay | A client cannot then overwrite migrated data with an old body; the request cannot tell which graphs a step changed | PD-8, RISK-6 | built (stage 2, #112) |
| Rabbit-hole: loaded graphs and blobs | Loaded graphs, registry graphs and the stamps graph are outside a step's reach; blobs are untouched. A step with a variable predicate can still delete a graph's own token or registry statement; the how-to says how to avoid it | Loaded files follow their own vocabularies; the registry is the toolkit's bookkeeping | PD-5, PD-21 item 6, RISK-10 | built (stages 1, 2) |
| Rabbit-hole: long migrations on a live service | One request per migration and database, at start-up; a request that outlasts the timeout sets the tenant aside until the next start; no longer timeout for the runner | No data exists yet; a longer timeout is a setting to add when a tenant needs it | RISK-3 | accepted, not built |
| Backlog note: migrate stored workflow states when a workflow file drops a state | A recipe in the how-to: a "replace a value" step on `adms:status`, carried by a new schema version. Nothing detects the dropped state | A workflow file is not the schema, so the lock does not see it | PD-13 | built as docs (stage 3); detection not built |
| Backlog note: migrate the toolkit's own metamodel modules | Same mechanism: `rp.yaml` has `version: "1"`, a lock of its own root classes (the access record, the workflow, discussion and provenance records) and a migrations folder shipped with the package, with no migration yet; its chain runs before the consumer's in every database | One mechanism, as Strapi's internal migrations | PD-13 | built (stages 1, 2) |
| Not in the shape | Some changes cannot be migrated and are refused at generation: a root's IRI type or path, a root's database, whether a slot's values are owned parts | A step works inside one graph and cannot change an IRI or move data between graphs | PD-3, PD-21 item 5, RISK-8 | built (stage 1, #109) |
| Not in the shape | A migration step is three graph patterns checked by what the SPARQL parser understood (`checked_group`); no raw request, no Python, no toolkit predicate in a template, no key given twice | Only a toolkit-built request can carry the stamp guard and the graph scope; the adversarial tests broke a text scan | PD-5, PD-6, PD-21, PD-22 | built (stage 1, #109) |
| Not in the shape | Dump and restore across versions: `dump` writes the tenant's own stamp as the manifest's version, or none; a restore accepts any version of the chain, checks the manifest agrees with the stamp, and migrates the parsed dump in memory, with the store's request text, before the IRI rewrite and the root's vetting | `tenant-dump-restore` left it to this EPIC (its DEC-7, PD-2); `Tenancy` cannot call the runner without an import cycle, so `tenant_dump.restore` does | PD-15, PD-25 items 5, 7, 9 | built (stage 3) |
| Not in the shape: the cost of a restore across versions | The migration runs in a worker thread. Its cost is bounded only by the steps; on rdflib a large dump is slow. The loaded-graph exclusion is written with `MINUS` for the store and the dump alike | An unbound `FILTER NOT EXISTS` made rdflib walk every graph per row (400 graphs: 122 s, about 11 s after the fix). No size guard: a restore's caller is trusted | PD-25 item 4, PD-26, RISK-12 | built (stage 3) |
| Not in the shape: rdflib's row hash | Not fixed: a solution row's hash collides when a subject equals its graph IRI, which slows its join. The toolkit does not patch an external library | An upstream report is recommended, for the developer to file | PD-26 | not built |
| Not in the shape: a dump of the shared databases | Not built: rolling back a release that migrated the system and application databases needs a backup of the store | Found by the docs writer; a later change | RISK-11 | not built |
| Leader's choices: "a migrated database gets new version tokens", "no down-migrations", "loaded graphs are not migrated" | As chosen; no automatic backup before a migration; the how-to says to dump, or back up the store, before deploying a migration with steps | The developer did not overrule them | PD-8, PD-12, PD-5, RISK-1 | built (stages 1, 2), docs (stage 3) |
| Impact: "consumers declare a schema version" | Mandatory, with a migrations folder, a quoted `version:` and a required `install_service` argument | The developer's choice; no data exists yet | DEC-9, PD-1, PD-14 | built (stage 1, #109; stage 2, #112) |
| Appetite: LARGE | Held: three stages. The chain loader of stage 2 rode in PR 1, and the application database moved from stage 3 to stage 2 | Parallel builders; PR #102 was already merged | D-1, D-2, D-5 | built (#109, #112, stage 3) |

Nothing above invalidates the bet, so this is a reconciliation and not a re-shape: the problem,
the appetite and the no-gos stand. The shaped decisions that did not hold as worded, DEC-2 and
DEC-3, are narrowed here and in PD-2, not removed; the Solution outline's "usable at its previous
version" is narrowed by RISK-11. Not built, as the No-gos say: migrations inferred beyond the
drafts, down-migrations, migrating loaded graphs or file contents, validating every aggregate at
start-up, migrations in Python.
