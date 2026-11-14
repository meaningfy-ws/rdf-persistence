> Derives from: EPIC `schema-migrations` (proposal.md). Three stages, one PR each into `develop`.
> Type: Implementation.

## Context

Checked in the code on 2026-11-14 (develop at `4be90eb`):

- **No version, no old schema.** No schema declares `version:`. The service loads only the current
  schema (`ServiceKit`, `entrypoints/kit.py:81`) and imports only the current generated code. The
  generated code of an older version exists nowhere, so a migration cannot be "read with the old
  model, write with the new".
- **One request is one transaction.** `Transaction.commit` (`services/session.py`) sends one SPARQL
  update request of several operations and relies on the store applying it atomically; the fake
  store does the same on a copy (`testkit/fakes.py`). Operations of one request run in order. A
  database (dataset) is the unit: one request can rewrite every graph of a tenant.
- **A first-writer-wins record exists.** `services/iri_policy_guard.py` keeps the IRI policy in the
  system database, in the graph `{base}toolkit/iri-policy`, written with a conditional insert and
  read back. It is the only start-up coordination between instances.
- **Start-up** (`entrypoints/service.py` `_run_at_startup`): `ensure_system_database`,
  `guard_iri_policy`, `sweep`. Any exception stops the service. `sweep` and `Tenancy.tenants()`
  decode every access record with the current model (`tenancy.py` `_records`, `_decoded`).
- **Version tokens** are random UUIDs, `<graph> rp:version "<uuid>"` inside the aggregate's graph,
  one per graph, read and written only by `services/session.py` (and read by `listing.py`).
- **Blank nodes** are skolemised because an insert template runs once per matched row.
- **Loaded graphs** are registered as `<graph> rp:kind <loaded-graph>` in a registry graph; the
  system database has one registry graph per tenant.
- **IRIs depend on the schema.** An aggregate's and a part's IRI embed `{type}` (`rp_iri_type`, or
  the class name in kebab case) and `rp_path`; `Session` refuses an IRI whose type is not a current
  root type (`InvalidIri`). An owned part lives in its root's graph, a referenced object in its own.
- **Dump and restore** (`services/tenant_dump.py`, `Tenancy.restore`): the manifest carries
  `schema_id` and `schema_version` from the running view; restore requires both equal to the running
  view's, parses `graphs.nq` into an rdflib `Dataset`, rewrites the tenant's IRIs, accepts only
  graphs the IRI policy mints for the tenant (`check_graphs`, `domain/tenant_move.py`), decodes the
  root with the current model (`_vet_restored_root`), then creates a new tenant.
- **Generation** (`generation/pipeline.py`): steps stage files; every staged file becomes a manifest
  output; an output no longer staged is removed as stale; `--check` runs only steps that do not
  write. `own_schemas(view, folder)` and `root_classes` (`services/schema_structure.py`) tell a
  target's own modules and its stored root classes. linkml-runtime reads `version: 1.10` as `"1.1"`.
- **The application database** (`app-level-data`, PR #102, open): one database `{prefix}-app`,
  created by `Tenancy.ensure_application_database()` at start-up when the schema has an application
  class; no access record, no root.
- **Strapi's rules** (its documentation and source, read 2026-11-14): per boot it runs the user's
  migrations, then its own, then syncs the schema. Added types and attributes are applied on their
  own. Removed ones are dropped silently. A rename is not detected and loses data unless a
  hand-written migration copies it first. Migrations are files, run once in name order, each in a
  transaction, recorded in a table; there are no down migrations and no lock between instances.

## Goals / Non-Goals

**Goals:** a recorded schema version per database; the Strapi-style rules applied when the schema
changes; reviewed migration files applied automatically at start-up, once, in order, atomically per
database; a tenant that is behind refused; dump and restore and the application database covered;
the toolkit's own metamodel migrated the same way.

**Non-Goals:** the proposal's No-gos; validating every stored aggregate at start-up; a migration
written in Python; an automatic backup before a migration; a lock between instances beyond the
guard of PD-7; guessing a rename from a diff; a migration that changes an IRI or moves data between
graphs (PD-3's "not migratable" row).

## Decisions

The developer's answers of 2026-11-06 and 2026-11-14 are in `inputs/seed.md`. "Leader's choice"
marks an answer the developer delegated (seed, 2026-11-06) and may overrule.

- **PD-1 The version is the schema's `version:` (seed Q-8, leader's choice).** The LinkML `version`
  of the root schema, the same value the dump manifest records. It must be written as a quoted
  string (`version: "1.10"`): a hard check reads the YAML source and refuses a number. Versions are
  not compared as numbers: their order is the migration chain (PD-4).
- **PD-2 A stamp per database (seed Q-1, leader's choice).** Every database (system, application,
  each tenant) records the version its data follows, per schema id, as one statement
  `<schema id> rp:dataSchemaVersion "<version>"` in the graph `{base}toolkit/schema-stamps`
  (`stamps_graph_iri(base)` in `domain/iris.py`, beside `policy_record_iri`). In the database, so
  one update request changes data and stamp together. Not in the access record (another database:
  no atomicity). Not per aggregate (no lazy migration, PD-9). A database holds two stamps: the
  toolkit's metamodel (`rp.yaml`'s id) and the consumer's root schema. As the IRI-policy record, a
  stamp is one statement and no class; its predicate is the slot `data_schema_version`
  (`slot_uri: rp:dataSchemaVersion`, `bookkeeping: true`) declared in `rp_core.yaml` beside
  `version`, so the vocabulary still comes from LinkML (EPIC DEC-1). EPIC DEC-2 is about an
  aggregate's tracking; a stamp describes a database, so it is about the schema id, in a graph of
  its own.
- **PD-3 The rules run in `rp-generate`, against a committed lock (developer, 2026-11-14).** A
  target with a `migrations` folder keeps `<migrations>/schema.lock.json` (a generated `SchemaLock`):
  the schema id, the version, and the RDF-facing summary of what the target stores. Per stored
  class (a root class of the target's own modules, `own_schemas` and `root_classes`, or a class
  reachable from one through inlined slots; never a mixin or an abstract class): its class IRI, its
  IRI type, `rp_path` and database when it is a root (classes that share one class IRI are one
  entry with the union of their slots, PD-21 item 5), and per induced slot its IRI, its range as an IRI (for
  an enum: the enum's name), `required`, `multivalued`, `inlined`. Per enum used as a range: the
  `meaning` IRI of each value (its text when it has none). `rp-generate` compares lock and schema:

  | Change (old lock to schema) | Rule | What `rp-generate` does |
  |---|---|---|
  | none (also a LinkML rename that changes nothing above), version unchanged | — | nothing |
  | none, version raised | safe | rewrites the lock; writes a migration with no steps |
  | no lock yet | bootstrap | writes the lock; no migration |
  | class added; slot added, not required; `required` dropped; single to multivalued; enum value added | safe | rewrites the lock; with a new version, writes a migration with no steps |
  | slot IRI gone from a class | destructive | needs a new version; drafts a `drop` step (PD-5) |
  | class IRI gone; slot added `required`; `required` set; multivalued to single; range changed; enum value gone | needs a step | needs a new version; drafts an `unresolved` step naming the change |
  | a root's IRI type, `rp_path` or database changed; a slot's `inlined` changed | not migratable | fails: a step cannot change an IRI or move data between graphs |
  | any change not "safe", version unchanged | refused | fails, naming the changes: "set a new `version:`" |
  | the lock's schema id differs; the new version is one the chain already left (the `from_version` of an existing migration file); lock unreadable | refused | fails |

  A rename shows as "gone" plus "added": the draft drops, and the how-to says to turn the drop into a
  rename. Nothing guesses a rename (EPIC Rabbit-holes, No-gos). Mechanics, forced by the pipeline:
  the comparison is a check step (it does not write, so `--check` runs it too); the lock is staged by
  a write step and is a manifest output, so the freshness check covers it; a draft is written
  straight into the migrations folder, only when the file is absent, and is never staged nor a
  manifest output (it is the developer's file from then on). The run that drafts succeeds and prints
  what it drafted; the migration files that existed before the run are loaded and checked (PD-6),
  so an `unresolved` step fails the next run and `--check`. To rework a version not yet merged: put
  the lock back from `develop` (`git checkout develop -- <lock>`), delete the draft, regenerate.
- **PD-4 A migration is a reviewed file; the chain is the order (seed Q-2, developer 2026-11-06).**
  `<migrations>/<from>__<to>.yaml`, one per version step, validated into the generated `Migration`
  (`schema_id`, `from_version`, `to_version`, `description`, `steps`), declared with `MigrationStep`
  in `rp_service.yaml` (they are file formats, not stored). The files of one schema must form one
  line ending at the running schema's version: no fork, no gap, no cycle, no duplicate. With no file
  the chain is the current version alone. A version in a file name is the version with every
  character outside `[A-Za-z0-9.-]` written as `_`; the fields inside the file are the truth.
- **PD-5 One step form.** A `MigrationStep` has `title` and three group graph patterns as text:
  `where_pattern` (required unless `unresolved`), `delete_pattern`, `insert_pattern` (at least one
  of the two). The toolkit builds, through `domain/sparql.py` (EPIC DEC-4):

  ```sparql
  DELETE { GRAPH ?rp_graph { <delete_pattern> } } INSERT { GRAPH ?rp_graph { <insert_pattern> } }
  WHERE { GRAPH <stamps> { <schema id> rp:dataSchemaVersion "<from>" }
          GRAPH ?rp_graph { <where_pattern> }
          FILTER (?rp_graph != <stamps>)
          FILTER NOT EXISTS { GRAPH ?rp_registry { ?rp_graph rp:kind <loaded-graph kind> } }
          FILTER NOT EXISTS { GRAPH ?rp_graph { ?rp_entry rp:kind ?rp_kind } } }
  ```

  So a step works inside one graph at a time, never moves data between graphs, never touches a
  loaded graph (EPIC Rabbit-holes: loaded files follow their own vocabularies; leader's choice) or
  a registry graph (the third filter, PD-21 item 6), and does nothing once the stamp has moved. A pattern may use `?rp_graph` (the graph's IRI, the subject
  of its tracking statements). A step with `unresolved` (text) is a draft: loading it fails. One
  form covers the recipes of the how-to: rename a slot, retype (a changed class IRI), drop a slot,
  give a new required slot a value, replace a value (an enum value, a workflow state). No Python
  hook and no raw request: neither could carry the guard.
- **PD-6 A step is checked when it is loaded,** by `rp-generate` and at start-up
  (`load_migration`; as amended by PD-21 and PD-22, the check of one pattern is
  `domain/sparql.py` `checked_group` and reads the parser's tree, never the text). Each pattern
  must parse alone as a group (`ASK { p }` for the where, `INSERT { p } WHERE {}` for the other
  two, rdflib); its tree must hold no graph or service pattern, no variable starting `rp_` other
  than `rp_graph`, no prefixed name; the text must hold no codepoint escape (`\u`, `\U`); a
  delete or insert template must hold no blank node or collection and none of the toolkit's own
  predicates (`rp:version`, `rp:kind`, the stamp's). A pattern too long for the parser is refused
  as too long to check. The file is refused when a YAML key is given twice, and when the request
  built from the migration does not parse into exactly the expected number of operations (one per
  step, plus the token rotation when there is a step, plus the stamp move). A failure is
  `InvalidMigration`, naming the file and the step.
- **PD-7 One request per migration and database; the stamp is the guard.** The request is: every
  step in order; if the migration has a step, the rotation of every version token (PD-8); last, the
  stamp moved from `from` to `to`, itself matching only the `from` stamp. Applied atomically (the
  store's property the session already relies on; proven for this request in the container test),
  so a failure leaves data and stamp as they were. After the request the runner reads the stamp
  back: `to`, or any later version of the chain, means done, whoever did it, and the runner goes on
  from the stamp it read. A second instance sending the same request after the first matches
  nothing. No lock is needed and none is added.
- **PD-8 A migrated database gets new version tokens (seed Q-6, leader's choice).** A migration with
  at least one step replaces `rp:version` of every graph that has one with `STRUUID()`. A client
  holding an older `ETag` gets a conflict and reads again, so it cannot overwrite migrated data with
  an old body. Every token, not only those of changed graphs: one operation, and the request cannot
  tell which graphs a step changed. `dcterms:modified` and the contributors stay: a migration is not
  a user's edit.
- **PD-9 Eager, at start-up, the system database before anything decodes it (seed Q-3, developer
  2026-11-06).** Order in the lifespan: `ensure_system_database`, `guard_iri_policy`,
  `ensure_application_database` (with #102), **`migrate_shared`** (the system database, then the
  application database), `sweep`, **`migrate_tenants`**. The kit loads both chains when it is built
  (a bad chain stops the service: `InvalidMigration`). For each database, the toolkit's chain first
  and the consumer's second: stamp it if it has none (PD-10), apply each pending migration (PD-7).
  Tenants in order of IRI, skipping tenants in state `deleting`.
- **PD-10 Whoever creates a database stamps it current; a database found with no stamp follows
  the first version of the chain.** `ensure_system_database` (when it created the database),
  `Tenancy.create` (right after `create_dataset`, before the root is written) and
  `ensure_application_database` (when it created the database) write both stamps at the current
  versions. The runner, meeting a database with no stamp for a schema (one from before this change,
  or one filled by a script or a test fake), stamps it with the first version of that chain and
  then migrates it. Every stamp is written with the conditional insert of the IRI-policy guard, per
  schema id, so two writers leave one stamp. `Tenancy` takes `stamps: Sequence[tuple[str, str]]`
  (schema id, current version), which the kit builds from the two chains.
- **PD-11 Failure: the shared databases stop start-up; a tenant is set aside (seed Q-4, developer
  2026-11-06 and 2026-11-14).** A failed migration of the system or application database raises
  `MigrationFailed`. A failed tenant is logged (`log.error`, `extra={"step": "migrate-tenant", "tenant", "schema", "migration", "cause"}`;
  a failed shared database the same with step `migrate-shared` and `database` in place of `tenant`;
  each applied migration `log.info`, step `migrate`, with database, schema and migration; the
  `migration` field is `<from>__<to> of <schema id>`, or empty when the stamp itself failed), and
  the next tenant runs. At the end of `migrate_tenants` the failed tenants become
  `Tenancy.behind` (a set in memory of this instance, read-only, replaced by
  `Tenancy.set_aside`; the set of the previous run stays in force while a run is in flight,
  PD-24 item 4). A stamp unknown to the chain (data newer than the
  service) is the same failure. `Tenancy.tenant_session`, the one door of every tenant read and
  write, raises `TenantBehind` for a tenant in the set; the service answers `503` with the new
  problem `tenant-behind`, title "Tenant behind its schema" (a `503` carries no detail,
  `entrypoints/problems.py` `_EXPLAINED`; the exception's message names the tenant, for the log).
  `MigrationFailed`'s message names the database, the migration (`<from>__<to>` of which schema)
  and the cause. Other tenants are served. Dump and the live sweep use the store
  directly and stay available for a tenant set aside (that is how an operator rescues it); its
  record can be read, its grants changed and the tenant deleted (the system database); a rename
  answers `503`, because it writes the tenant's root. A
  successful migration at a later start is the only way out, also when the failure was transient
  or another instance has migrated the tenant meanwhile (RISK-2).
- **PD-12 No down-migrations (seed Q-5, leader's choice).** Rollback is: the failed tenant stays at
  its previous data and stamp, so the previous release serves it; for a migration that succeeded and
  was wrong, restore a dump taken before it. The how-to says to dump before deploying a migration
  with steps.
- **PD-13 The toolkit's metamodel uses the same mechanism (seed Q-7, leader's choice).** `rp.yaml`
  declares `version: "1"`; its target sets `migrations = "rdf_persistence/model/migrations"`; the
  folder ships in the wheel, with a lock and no migration yet. A later change to an `rp_*` module
  that stored data must follow adds a file there, in the same PR. A workflow file that drops a state
  is migrated by the consumer with a "replace a value" step on `adms:status`, carried by a new
  schema version; nothing detects it (as today: a transition from the dropped state conflicts).
- **PD-14 Mandatory (developer, 2026-11-14).** `rp-generate` fails for a target whose own modules
  define a root class (`root_classes` over `own_schemas`) and that has no `migrations` folder, and
  for a target with `migrations` whose root schema has no `version`. Of the toolkit's four targets
  only `rp.yaml` has own root classes. `install_service` and `ServiceKit` take a required
  `migrations: Path`. Consumers adjust when they upgrade; no data exists yet anywhere (developer,
  2026-11-14).
- **PD-15 Dump and restore read the stamp.** `check_graphs` accepts the stamps graph (stage 2, with
  the first stamp, or no stamped tenant could be restored). `dump` writes the tenant's consumer
  stamp as the manifest's `schema_version` (PD-2 of `openspec/changes/archive/2026-11-13-tenant-dump-restore/design.md`). Restore accepts a manifest
  whose schema id is the service's and whose version is in the chain; then, on the parsed `Dataset`
  in memory and before the IRI rewrite, the graph check and the root's vetting, it applies the
  pending migrations of both chains with the same request text (`migrate_dataset`, rdflib's
  `Dataset.update`), so the rest of restore sees current data and stamps. A manifest with no
  version, a version or a stamp unknown to a chain, or a dump with no stamps graph is refused
  (`InvalidBody`) before anything is created.
- **PD-16 The application database is one more shared database (app-level-data).** Delivered in
  stage 3, after PR #102 is in `develop` (developer, 2026-11-14: this session brings #102 in).
- **PD-17 Layers (as amended by PD-22 and PD-24 item 2).** `domain`: `stamps_graph_iri`, the
  exceptions; `domain/sparql.py` builds SPARQL text and holds the one check of a step's pattern
  (`checked_group`). `services/migrations.py`: `load_migration`, `load_chain`, `chain_of`,
  `migration_file_name`, the request text, the stamp's read and conditional write (`stamps`,
  `stamp_if_none`), the `SchemaChain` alias and the helpers `versions`, `first_version`,
  `current_version`, `pending_from`; it imports neither `tenancy` nor the runner.
  `services/vocabulary.py`: `TOOLKIT_MIGRATIONS`, beside the metamodel's path.
  `services/migration_runner.py`: the runner on the `Store` port (`migrate_database`,
  `migrate_shared`, `migrate_tenants`) and, in stage 3, `migrate_dataset`. `services/yaml_files.py`: reading a YAML file into a mapping,
  shared with the workflow loader. `generation/lock.py` and `lock_step.py`: the summary, the diff,
  the drafts, the two pipeline steps; `generation` imports `load_migration` and
  `migration_file_name` from `services/migrations.py` (`.importlinter` forbids the
  runtime layers to import `generation`, not the reverse). A new file under `generation/` changes
  the inputs of every consumer's manifest, so every consumer regenerates on upgrade (as PD-14 asks
  anyway). No report class: the runner logs each migration and answers the set of tenants set
  aside.

## Algorithm / approach

Worked example. The toy library is at version `"1"`. The developer changes the slot IRI
`lib:shelf` to `lib:shelfMark` on `Book` and sets `version: "2"`.

1. `make generate`: the lock says `Book` had `lib:shelf`; the schema has `lib:shelfMark` instead.
   "Slot gone" is destructive and the version is new, so `migrations/1__2.yaml` is drafted:

   ```yaml
   schema_id: https://example.org/ns/library
   from_version: "1"
   to_version: "2"
   description: Drafted by rp-generate from the schema change. Review every step.
   steps:
     - title: DROP <https://example.org/ns/library#shelf> of <https://example.org/ns/library#Book> (deletes data)
       where_pattern: "?s a <https://example.org/ns/library#Book> ; <https://example.org/ns/library#shelf> ?o"
       delete_pattern: "?s <https://example.org/ns/library#shelf> ?o"
   ```

   and the lock is rewritten. The added slot is safe and drafts nothing.
2. The developer turns the drop into a rename by adding
   `insert_pattern: "?s <https://example.org/ns/library#shelfMark> ?o"`, and commits schema,
   generated code, lock and migration together.
3. At start-up each database holds `<…/library> rp:dataSchemaVersion "1"`. For each, one request:
   the step, the token rotation, the stamp to `"2"`. Read back: `"2"`.
4. A second start, or a second instance: the stamp is `"2"`, nothing is pending, nothing is sent.

Idempotency: every operation of the request matches only under the `from` stamp, and the request
is atomic, so sending it twice, or from two instances, applies it once. The conditional first
stamp is first-writer-wins. `rp-generate` run twice writes the same lock and never overwrites a
migration file.

### Anti-patterns

| Don't | Do instead | Why |
|---|---|---|
| Write a migration as a raw update request or a Python function | The step form of PD-5 | Only the toolkit-built request carries the stamp guard and the graph scope |
| Insert a blank node in a step | Insert IRIs and literals | The template runs once per matched row; parts are skolem IRIs |
| Move the stamp in its own request | The last operation of the migration's request | Otherwise a crash leaves migrated data with the old stamp |
| Hand-edit `schema.lock.json` | Change the schema and run `make generate` | It is generated (EPIC DEC-1; rule P-0003, `docs/rules/P-0003 first read the diff on both.md`) |
| Stage a draft or record it in the manifest | Write it once, outside the manifest | The pipeline would remove it as stale or report the developer's edit |
| Edit a migration that has been deployed | Add a new version and a new migration | A stamped database never runs it again |
| Decode access records before the system database is migrated | The order of PD-9 | The current model cannot read the old shape |
| Keep the behind tenants in the store or check per request | The in-memory set of PD-11 | The developer's choice of 2026-11-14 |
| Hold migrations or the lock as dicts | The generated `Migration`, `SchemaLock` | EPIC DEC-1 |

## Error matrix

| Failure mode | How it is detected | Expected handling |
|---|---|---|
| Non-safe schema change, same version | lock diff in `rp-generate` (also `--check`) | generation fails naming each change; nothing written |
| A root's IRI type, `rp_path` or database, or a slot's `inlined`, changed | lock diff | generation fails: not migratable |
| Root schema without `version`, or with an unquoted one; own root class without `migrations` | hard check | generation fails (PD-1, PD-14) |
| Migration file with an `unresolved` step, a pattern that does not parse or escapes its group, a blank node, `GRAPH`, `SERVICE`, a reserved variable, a prefixed name, a codepoint escape, a toolkit predicate in a template, a step too long to check, a key given twice | `load_migration` (PD-6) | `rp-generate` fails; the kit raises `InvalidMigration` naming file and step |
| Chain forks, has a gap, a cycle, or does not end at the running version | `load_chain` | `InvalidMigration`; the service does not start |
| File's `schema_id` is not the chain's | `load_chain` | `InvalidMigration` |
| The store refuses or times out a tenant's request | exception from `Store.update`, or the stamp read back is before `to` | tenant set aside (PD-11); data and stamp unchanged; next tenant runs |
| The request timed out for the client but the store finished it | next start reads the stamp `to` | nothing pending; the tenant is served |
| Same for the system or application database | as above | `MigrationFailed`; start-up stops |
| Stamp not in the chain (data newer than the service) | stamp lookup | as a failed migration of that database |
| Two stamps for one schema id in a database | stamp read returns two rows | as a failed migration of that database, naming both |
| Two instances start at once, one or several migrations pending | a request matches nothing; the stamp read back is `to` or later | both serve; each migration applied once |
| Tenant database gone (`DatabaseGone`) | exception | tenant set aside; the sweep or an operator deals with it |
| Request for a tenant set aside | `Tenancy.tenant_session` | `TenantBehind`, `503` `tenant-behind` |
| Restore, as stage 2 ships it: a manifest version other than the running one, or a stamps graph that is not exactly the running versions and nothing else | `_check_manifest`, `Tenancy._refuse_other_stamps` (PD-24 item 1) | `InvalidBody` before anything is created |
| Restore, from stage 3: a dump with no version, an unknown version or stamp, or no stamps graph | `_check_manifest`, `migrate_dataset` | `InvalidBody` before anything is created |
| Restore whose migration fails on the parsed dataset | exception from `Dataset.update` | `InvalidBody` naming the migration; nothing created |
| The live tenant sweep meets the stamps graph | — | it is not a policy-minted loaded graph and is left alone (TC-27) |

## Risks / Trade-offs

- **RISK-1 A wrong step damages data in one clean transaction.** Likelihood medium (hand-written
  patterns), impact high. Mitigation: the draft's title says "deletes data"; the migration is
  reviewed with the schema change in one PR; the how-to says to dump before deploying a migration
  with steps and to try it by restoring that dump into the new release (PD-15 migrates it).
  Accepted: no automatic backup.
- **RISK-2 The in-memory set is per instance.** An old instance writes old-shaped data during a
  rolling deployment; an instance whose migration of a tenant failed for a passing reason answers
  `503` for it until it restarts. Likelihood medium where deployments roll, impact medium. Accepted
  with the developer (2026-11-14): the how-to says to stop old instances first and to restart an
  instance that set a tenant aside. Upgrade path: read the stamp per session.
- **RISK-3 A large tenant's request outlasts the HTTP timeout.** Likelihood low today (no data
  anywhere), impact low: the store finishes or rolls back; the tenant is set aside until the next
  start (error matrix). Accepted; a longer timeout for the runner is a setting to add when a tenant
  needs it.
- **RISK-4 Fuseki does not apply this request atomically.** Likelihood low (the session relies on
  the same property), impact high. Mitigation: the container test TC-40 fails a late operation and
  asserts nothing changed; if it shows otherwise, stop and re-plan.
- **RISK-5 A toolkit slot removed from a mixin shows up in the consumer's diff too** (the lock holds
  induced slots). Likelihood low, impact low: the consumer gets a second, harmless drop draft.
  Accepted.
- **RISK-6 Rotating every token makes every open editor re-read after a migration with steps.**
  Accepted: correct, rare, and cheaper than tracking changed graphs.
- **RISK-7 PR #102 changes before it merges.** Stage 3 starts from `develop` after the merge; the
  application database is one entry in the shared list, so the exposure is one task.
- **RISK-8 Renaming a root class, or changing whether a slot is inlined, cannot be migrated.**
  Likelihood medium over a product's life, impact medium: the developer keeps the IRI type
  (`rp_iri_type`) and path when renaming, which PD-3 enforces. A migration that changes IRIs is a
  later EPIC. Accepted.
- **RISK-9 Two instances starting at once are still exposed to the start-up sweep** (it can drop a
  database another instance is creating; found by the attack, older than this change). Not made
  worse here; noted for the backlog.

## Open Questions

None.

## Attack and gate

- **PD-18 The attack (fresh reviewer, 2026-11-14)** found one blocker and seven major holes, each
  checked against the code and folded in: restore refused every stamped dump (`check_graphs`; now
  PD-15, and the fix moved to stage 2); drafts could not be manifest outputs (PD-3 mechanics); the
  sweep decoded access records before their migration (PD-9 order); restore vetted the root before
  migrating it (PD-15 `migrate_dataset`); the read-back failed a healthy tenant with two instances
  and two pending migrations (PD-7); "own classes" broke the toolkit's other targets (PD-3, PD-14
  use `own_schemas`, `root_classes`); IRIs that embed the type were outside the lock (PD-3 "not
  migratable", RISK-8); a user's `?g` joined the template's (PD-5 `?rp_` variables). Minor ones:
  patterns parsed alone (PD-6), enum meanings and unquoted versions (PD-1, PD-3), a database
  found with no stamp (PD-10), no report class and no stamp class (PD-2, PD-17).
- **PD-19 The gate (fresh reviewer, 2026-11-14), first run 8.7/10.** Eight gaps, all closed in the
  text: "empty" could never be true after the IRI-policy record and the first stamp (PD-10 now
  stamps at creation); a raised version with no change, and what "left" means (PD-3 table); the
  spec scenarios mapped to test cases and the old-token conflict tested (tasks 2.3, TC-26); TC-32
  rewritten to what the fake's hook can do; how `Tenancy` learns the stamps (PD-10); log steps and
  the problem's title (PD-11); the operation count (PD-6); paths for the cited rules and pages. **Second run, same reviewer:
  9.1/10, pass**, no new gap.
- **PD-20 Blast radius (GitNexus, 2026-11-14).** `Tenancy.tenant_session` is rated CRITICAL and
  `check_graphs` HIGH; both edits only add a branch. The developer answered "Go ahead" (2026-11-14).

## Delivery decisions

- **D-1 The application database moves to stage 2 (lead, 2026-11-14).** PR #102 was already
  merged when delivery started (14:12; `develop` at `5ba0d49`), and the branch is rebased on it. So
  `migrate_shared`, the lifespan order of PD-9 and the stamp of a new application database (task
  3.2, TC-54) are built in tasks 2.2 and 2.3; task 3.2 is closed by them. RISK-7 no longer applies.
- **D-2 Task 1.3 is cut in two so builders can run in parallel (developer, 2026-11-14: "if any
  activities can be run in parallel then start subagents").** 1.3a: `stamps_graph_iri`,
  `InvalidMigration`, the request text and `load_migration` (files in `domain`, `services`, their
  tests), beside task 1.2 (`generation/lock.py`), on disjoint files. 1.3b: the pipeline steps, the
  hard checks and the wiring, after both. The lead runs the task gates once both have reported.
- **D-3 Names as built in task 1.1.** `SchemaLock.locked_classes`, `.locked_enums`;
  `LockedClass.class_uri`, `.iri_type`, `.root_path`, `.locked_slots`; `LockedSlot.slot_uri`,
  `.range`, `.required`, `.multivalued`, `.inlined`; `LockedEnum.name`, `.enum_values`.
- **D-4 Details the how-to draft asked for (lead).** A pattern holds full IRIs in angle brackets;
  the request has no `PREFIX`, so a prefixed name does not parse. A `FILTER`, `FILTER NOT EXISTS`,
  `OPTIONAL` or `BIND` inside `where_pattern` is allowed (it parses as a group). The draft of a drop
  uses the class's and slot's IRIs from the lock (the toy `Book` is `bibo:Book`,
  `http://purl.org/ontology/bibo/Book`; the worked example's `lib:Book` stands for it).
  `Tenancy`'s `stamps` argument is optional and empty by default (about twenty tests build a
  `Tenancy`); only the kit passes it, and with none `create` stamps nothing.
- **D-5 Task 2.1 rides in PR 1 (lead, 2026-11-14).** The chain loader and the exceptions
  `MigrationFailed` and `TenantBehind` were built beside task 1.3b, on disjoint files, to use the
  waiting time. They are pure code with no caller yet, so PR 1 carries them. Task 2.2 starts only
  after stage 1's full gates have run, so that PR 1's check results describe what it contains.
- **D-6 The shape is reconciled in `proposal.md` (developer, 2026-11-14: "reconcile the deviations
  of epic implementation and epic shape").** Its "Reconciliation with the shape" table lists every
  place where the PLAN or the code left the shaped text, with the decision behind it. Two living
  requirements change and now have spec deltas: `rp-tenancy` (a restore across versions) and
  `rp-service-api` (the migrations folder, the problem `tenant-behind`).

## Accepted findings

- **PD-21 The adversarial tester's findings on stage 1 (2026-11-14), each accepted unless said.**
  1. *A step could hide `GRAPH`, `SERVICE`, a reserved variable or a blank node from the text scan*
     (a `\u` escape, which SPARQL expands before it parses; or `FILTER(?o<3)…(?o>1)` read as an
     IRI), and then delete from a loaded graph or write into graphs it did not match. PD-6 changes:
     the checks read what the parser understood, not the text. Each pattern is parsed alone and its
     algebra walked: no graph or service pattern; no variable starting `rp_` other than `rp_graph`;
     in a delete or insert template no blank node. A pattern, a version or a schema id containing a
     codepoint escape (`\u`, `\U`) is refused outright. The text scan stays only for prefixed names.
  2. *A version holding `"` is stored as another text by rdflib.* Closed by the refusal of 1.
  3. *A YAML key given twice was accepted, the last winning.* Refused: a reviewer must read what
     runs.
  4. *A where pattern of more than about a hundred triple patterns was refused as "does not
     parse"* (rdflib's recursion limit). Still refused; the message says the step is too long to
     check and to split it.
  5. *The lock missed or misordered some changes.* A root's database (`tenant`, `application`,
     `system`) is recorded, and its change is "not migratable". Slots are sorted by all their
     fields, so two slots sharing an IRI give one lock in either order. Classes sharing one class
     IRI (a subclass keeping its parent's) are recorded as one class with the union of their
     slots: stored data cannot tell them apart. **Not accepted:** recording the IRI type of an
     owned part; it matters only under a part template that writes `{type}`, a runtime setting
     `rp-generate` does not know. RISK-8 covers it and the how-to says so.
  6. *A step's `?s ?p ?o` also matches a registry graph* (the tester's "not checked"). PD-5 gains
     a third filter: a graph that holds registry statements (`?x rp:kind ?k`) is not a step's to
     change, as the stamps graph and loaded graphs are not.
- **PD-22 The review of stage 1 (four reviewers, 2026-11-14: L1, L2, L3, and L4 with L5 as one
  pass, as `develop/agents.adoc` says for this repository).** No blocker. Accepted:
  1. *The prefixed-name check still scanned text and could be passed* (`FILTER(?o<rdf:x||?p>1)`
     read as an IRI; rdflib resolves `rdf:` by default, a store would refuse it at start-up). The
     check reads the parse tree for prefixed names; no text scan is left (L1).
  2. *Turning untrusted pattern text into SPARQL had no single home.* The pattern checks move to
     `domain/sparql.py` as one function that answers a `SparqlTerm` or raises; `load_migration`
     calls it, and nothing else makes a `SparqlTerm` from a file's text. This narrows PD-17's
     "`domain/sparql.py` only builds text" (L3). The parse and the walk get separate `try` blocks,
     so a defect in the walk is not reported as the developer's syntax error (L4).
  3. *A step could delete or write the toolkit's own predicates* (`rp:version`, `rp:kind`, the
     stamp's) in a data graph and so break the token rotation or hide a graph from later steps.
     A delete or insert template that names one is refused (L1).
  4. *The file-name rule of PD-4 was written twice.* One `migration_file_name` in
     `services/migrations.py`, imported by the generation step (L1, L3, L4).
  5. *Reading a YAML file into a model was copied from the workflow loader.* One shared helper in
     `services`, with the duplicate-key refusal, used by both loaders (L4).
  6. *The drafted drop built SPARQL with f-strings.* It uses `term(URIRef(...))` (L1).
  7. *The new hard checks had no rule id.* They get `HardRule` values and a row in the rule
     catalogue, and name the target (L2, L3).
  8. *`Migration.schema_id` reused the dump's slot and its IRI.* The slot becomes a neutral
     `rp:schemaId`; a dump is a JSON file, so nothing stored changes (L3).
  9. *The generation docs contradict what PR 1 ships.* The `adopt.adoc` example and its
     required keys, and the keys and pipeline table of `architecture/generation.adoc`, change in
     PR 1; the how-to stays in stage 3 (L2).
  10. Smaller ones, all accepted: a lock that is not UTF-8 and a schema with no source file give a
      problem, not a traceback; the draft is created exclusively (no race, no symlink followed);
      messages are cut to a bounded length; the stored classes are computed once per summary; the
      renamed-root case runs through `rp-generate` and asserts "not migratable"; tests that
      accepted two outcomes or any exception assert one; the non-adversarial new tests follow the
      checklist's one-idea-per-assert rule; the hard-check function is renamed for what it checks.
  **Not accepted:** an enum for `root_database` (the lock's schema is technical and does not
  import `rp_core`); caching the lock between the check and the write step (the render steps load
  the schema the same way); replacing the request-text tests (the applied tests are the proof,
  the text tests are cheap). **Routed elsewhere:** a literal holding backslash-u is mis-rendered by
  `domain/sparql.py` for every write, older than this change: a repository issue, not a fix here;
  the refusal of such versions stays until it is closed. **For stage 2:** the runner goes in its
  own module, `services/migration_runner.py` (L3: `migrations.py` already has the file, the
  request and the chain).
- **PD-23 The adversarial tester's findings on the runner (2026-11-14; 54 tests, 3 failing), all
  accepted.**
  1. *A stamp read back that is earlier in the chain than the migration's `to` was taken as
     progress*, so a stamp moved backwards by another writer made the runner apply migrations
     again, without a bound. PD-7 as written is now enforced: after a request the stamp must be
     `to` or a later version of the chain; an earlier one, like an unknown one, is
     `MigrationFailed`. So the loop always ends: each round moves forward in a finite chain or
     fails.
  2. *A restore rewrote a stamp whose schema id held the source tenant's id.* The IRI rewrite of a
     restore leaves the stamps graph alone: its quads are copied as they are.
- **PD-24 The review of stage 2 (four reviewers, 2026-11-14: L1, L2, L3, L4 with L5).** No
  blocker. Accepted:
  1. *A restore accepted whatever the dump's stamps graph held* (a wrong or doubled stamp, a stamp
     of another schema, other triples, or none), and the runner trusts that graph. Until stage 3
     migrates a dump, a restore refuses (`InvalidBody`, before anything is created) a dump whose
     stamps graph does not hold exactly the versions the service runs, one statement per chain
     and nothing else. Stage 3 relaxes "runs" to "a version of the chain" and keeps "nothing
     else" (PD-15). Stamps read from a store are quoted with their escapes in messages and logs
     (L1).
  2. *`Tenancy` and the runner imported each other.* The stamp's read and its conditional write
     move to `services/migrations.py`, with the `SchemaChain` alias and the helpers `versions`
     and `current_version`; the runner imports `Tenancy` plainly; where the toolkit's own
     migrations folder is and how a chain is built from a schema view move from the kit to
     `services` (L3, L4). PD-17 is amended by this.
  3. *A schema with no `version` became the version "None".* The kit refuses it
     (`InvalidMigration`, naming the schema) (L4).
  4. *The runner wrote into `Tenancy.behind`.* `Tenancy` owns it: `set_aside(tenants)` replaces
     the set once, at the end of `migrate_tenants`; `behind` is read-only (L3, L4).
  5. *A listing of a tenant set aside had no test* (the scenario of `rp-service-api`); the feature
     had two behaviours in one scenario and a librarian where the spec says a reader. Two
     scenarios, a reader, and a listing (L2).
  6. *Two pages were wrong about restore*: the stamps graph is accepted and copied as it is
     (`architecture/data-flows.adoc`, `howto/dump-restore.adoc`). Corrected now, with "requests
     for its data" where the pages said every request of a tenant set aside answers 503 (L2).
  7. Smaller ones, all accepted: `MigrationFailed` takes its data as `Conflict` does; the log's
     `migration` field holds a migration's name or nothing; the stronger assertions the L2
     reviewer lists (both files named for a fork; the tenant-level failure of TC-28; the order of
     the IRI-policy record and the first stamp; one idea per assert).
  **Not accepted:** reading the stamps once per database to halve the start-up queries (two per
  database when nothing is pending; about 4 to 10 s for a thousand tenants: measured by L4, not a
  need today); a generated `MigrationChain` class (a chain is never stored nor sent); a real race
  in the fake store for TC-23 (the fake applies an update without yielding; TC-42 on Fuseki is the
  check). The test helpers that build a `Tenancy` keep `stamps=()` by default (D-4), which task
  2.2's text did not say.
- **PD-20, added 2026-11-14.** The PD-23 fix also changed `rewrite` (`domain/tenant_move.py`),
  rated HIGH (the restore path), and PD-24 item 1 adds a refusal in `Tenancy.restore`. Both were
  built before the developer was asked, against the rule that a HIGH risk goes to the developer
  first; the lead reported it to the developer the same day. Both only add: a graph left alone, a
  dump refused. The developer answered "Keep both" (2026-11-14). Asked before stage 3 about its
  changes to the same path (`tenant_dump.restore` and its manifest check, `Tenancy.restore`
  migrating the parsed dump, `dump` writing the tenant's own version), the developer answered
  "Go ahead" (2026-11-14).
- **RISK-10 A template with a variable predicate (`?s ?p ?o`) can still delete a graph's version
  token or registry statement** (found while fixing PD-22 item 3, which refuses those predicates
  only when a template names them). Accepted: removing every triple of a class is a legitimate
  step, and the request cannot tell the two apart. The how-to says to keep the graph's own
  statements out of such a step (`FILTER (?s != ?rp_graph)`).
- **D-7 What PR 1 carries beyond D-5 (lead).** Also `first_version`, `pending_from`, the
  `tenant_behind` problem and its mapping: no caller yet, the stage 2 runner uses them. TC-01 is
  amended: the lock holds no toolkit class that a root does not own (PD-3, "reachable through
  inlined slots"; the toy lock holds `MembershipRule` and `SlotEquality` through `Shelf`).
