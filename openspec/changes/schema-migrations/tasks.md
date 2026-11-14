> Derives from: EPIC `schema-migrations` (proposal.md). Three stages, one PR each into `develop`.
> Stage 3 starts after `app-level-data` (PR #102) is merged. Type: Implementation.

`T` and `U` are toy library tenants. "The toy chain" is `tests/fixtures/library/migrations/`.
`STAMPS` is `stamps_graph_iri(base)`; `LIB` is the toy schema id `https://example.org/ns/library`;
`RP` is `https://meaningfy.ws/ns/rdf-persistence`. Runner tests use `FakeStore` and build chains
in `tmp_path`; schema edits in generation tests follow `tests/unit/generation/test_boundary_check.py`'s
`Edit`. Every test follows `docs/modules/ROOT/pages/develop/testing.adoc`. The adversarial tester
runs right after task 2.2, the riskiest (write order, atomicity, concurrency). Gates per task:
`make test-changed` (`make test-fast` after a change to `domain` or a port), `make check-quality`,
`make clean-code`; `make generate` after any schema change.

## 1. The lock and the rules (stage 1, PR 1)

- [x] 1.1 Models. In `rdf_persistence/model/rp_core.yaml`: the slot `data_schema_version` (PD-2).
  In `rdf_persistence/model/service/rp_service.yaml`: `Migration`, `MigrationStep` (PD-4, PD-5) and
  `ProblemSlug` `tenant_behind`. In `rdf_persistence/generation/model/rp_generation.yaml`:
  `SchemaLock`, `LockedClass`, `LockedSlot`, `LockedEnum` (PD-3) and the `migrations` slot of
  `GenerationTarget`. `rp.yaml` gets `version: "1"`, the toy `library.yaml` `version: "1"`.
  `make generate`, then refresh what the generated-code guards compare
  (`tests/fixtures/model-shape.yaml`, the toy TypeScript, the public-imports list) by their own
  commands. No behaviour yet; the generated classes exist and `make test-fast` passes.
- [x] 1.2 Lock and diff. Test first, in a new `tests/unit/generation/test_lock.py`. Then a new
  `rdf_persistence/generation/lock.py`: `summarise(view, folder) -> SchemaLock`,
  `changes(old, new)` classified per the PD-3 table, and `draft(old, new) -> Migration`.
- [x] 1.3 The steps in the pipeline. Test first, in `tests/unit/generation/test_lock_step.py`,
  `test_hard_check.py`, `tests/unit/services/test_migration_files.py` and
  `tests/unit/domain/test_sparql.py`. Then: `stamps_graph_iri` (`domain/iris.py`) and
  `InvalidMigration` (`domain/exceptions.py`, exported as its neighbours are); in a new
  `services/migrations.py`, the request text of PD-5, PD-7, PD-8 (built with `domain/sparql.py`)
  and `load_migration(path) -> Migration` (PD-6); in `generation/steps.py`, a check step (the PD-3
  comparison and the loading of the existing migration files) and a write step (stages the lock,
  writes a draft only when absent, outside the manifest); the hard checks of PD-1 and PD-14 in
  `generation/checks/hard.py`; `config.py` reads `migrations`. Wire the two targets:
  `pyproject.toml` (`rdf_persistence/model/migrations`, shipped in the wheel) and
  `tests/fixtures/library/pyproject.toml` (`migrations`). `make generate` writes both locks.

| ID | Input | Expected |
|---|---|---|
| TC-01 | toy schema | lock has `Book` with its class IRI, IRI type, path and each slot's IRI, range IRI, required, multivalued, inlined; the tenant root `Library` with its induced slots; the classes of owned parts; no mixin, no abstract class, no toolkit class that a root does not own (D-7); enum values by `meaning` |
| TC-02 | add a class; add an optional slot; drop `required`; single to multivalued; add an enum value | each classified safe |
| TC-03 | remove a slot IRI from `Book` | destructive; `draft` has one step titled `DROP … (deletes data)` with the where and delete patterns of the design's example |
| TC-04 | remove a class; add a required slot; set `required`; multivalued to single; change a range; remove an enum value | each needs-a-step; `draft` has one `unresolved` step per change, naming class and slot |
| TC-05 | rename a slot in LinkML keeping `slot_uri`; rename a non-root class keeping `class_uri` | no change |
| TC-05a | rename a root (the toy `Shelf`) keeping `class_uri` and no `rp_iri_type`; change `rp_path`; flip a slot's `inlined` | each "not migratable": `rp-generate` fails naming it, with any version |
| TC-06 | TC-03's edit, version unchanged | `rp-generate` and `rp-generate --check` fail naming `Book` and the slot, say to set a new `version`; lock and outputs unchanged |
| TC-07 | TC-03's edit, `version: "2"`, no file | succeeds, printing the draft's path; `migrations/1__2.yaml` holds the draft; lock says `2`; the manifest does not list the draft; a second run changes nothing and removes nothing |
| TC-08 | TC-07, the developer edited the file | the run keeps the file byte for byte; `--check` reports nothing |
| TC-09 | TC-02's edits, same version | lock rewritten, no migration file; with `version: "2"`, `1__2.yaml` with no steps |
| TC-09a | TC-04's edit with `version: "2"` | the run succeeds and drafts the `unresolved` step; the next run and `--check` fail naming file and step |
| TC-10 | target with an own root class and no `migrations`; `migrations` and no `version`; `version: 1.10` unquoted | each fails with a hard problem naming the target; the toolkit's `rp_service`, `rp_wire`, `rp_generation` targets pass without `migrations` |
| TC-11 | migration file with: an `unresolved` step; `_:b`, `[ ]` or `( )` in an insert; `GRAPH`; `?rp_registry`; a pattern that does not parse; a pattern `?s ?p ?o } } ; CLEAR ALL ; INSERT DATA { <a> <b> <c>`; neither delete nor insert | `InvalidMigration` naming file and step; `rp-generate` fails with it |
| TC-11a | a step using `?rp_graph` in its where and insert | loads |
| TC-12 | lock hand-edited | the freshness check reports it stale |
| TC-13 | version `"1.0/beta"` to `"2"` | file name `1.0_beta__2.yaml` (PD-4) |
| TC-14 | version set back to one the chain already left; the lock's schema id differs; lock unreadable; no lock | the first three fail; no lock: the lock is written and no migration |
| TC-15 | request text for a migration of two steps | steps in order, then the rotation, then the stamp move; each operation carries the `from` guard; with no steps: the stamp move alone |

## 2. Stamps and the runner (stage 2, PR 2)

- [x] 2.1 Chain. Test first, in `tests/unit/services/test_migration_chain.py`. Then
  `MigrationFailed`, `TenantBehind` (`domain/exceptions.py`, exported) and, in
  `services/migrations.py`, `load_chain(folder, schema_id, current)` (PD-4) answering the ordered
  versions and migrations.
- [x] 2.2 Runner. Test first, in `tests/unit/services/test_migration_runner.py` and the existing dump and
  restore tests. Then, in `services/migrations.py`: `stamp_if_none`, `stamps`,
  `migrate_database(store, database, chains)` (PD-7, PD-10), `migrate_shared` and
  `migrate_tenants(tenancy, store, chains) -> set[str]` (PD-9, PD-11); `Tenancy.behind` and the
  refusal in `Tenancy.tenant_session`; `Tenancy` takes `stamps`, and `Tenancy.create` and
  `ensure_system_database` stamp what they create (PD-10); `fake_session` and the test helpers
  that build a `Tenancy` pass the toy stamps;
  `check_graphs` (`domain/tenant_move.py`) accepts the stamps graph (PD-15). **Adversarial tester
  right after this task.**
- [x] 2.3 Service. Test first, in `tests/unit/entrypoints/` and `tests/feature/` (a new
  `schema_migrations.feature`, written with `bdd-gherkin`: the toy service runs version `1` with a
  chain of one version, so only "a tenant behind the schema" (TC-37, `T` stamped `9` before
  start-up) and "a new tenant" (TC-34) run at feature level; the other spec scenarios are covered
  by the unit cases named below). Then:
  `install_service(migrations=...)` and `ServiceKit` load both chains; the lifespan order of PD-9;
  `entrypoints/problems.py` maps `TenantBehind` to `tenant-behind` (503) and `InvalidMigration`,
  `MigrationFailed` to `unavailable`; `tests/toy_service.py` and `tests/e2e/library_app.py` pass the
  toy chain; `adopt.adoc`'s `install_service` examples gain `migrations` (the full docs are 3.4).

| ID | Input | Expected |
|---|---|---|
| TC-20 | files `1__2`, `2__3`, current `3` | versions `[1, 2, 3]`; with no file and current `1`: `[1]` |
| TC-21 | fork (`1__2`, `1__3`); gap (`1__2`, current `3`); cycle; two files for one step; foreign `schema_id` | each `InvalidMigration` naming the files |
| TC-22 | a file that TC-11 refuses | `InvalidMigration` naming file and step |
| TC-23 | chain `[1, 2]`: a database with no stamp; `ensure_system_database` creating the system database | the first stamped `1`, then migrated to `2`; the new system database holds both stamps current (also with the IRI-policy record already there) and the runner sends it nothing; two writers stamping at once leave one stamp |
| TC-24 | `T` at `1` holds a book with `lib:shelf "A3"`; `1__2` moves it to another predicate of the current toy `Book` | the book has the value under the new predicate, none under `lib:shelf`; it decodes with the toy mapper and its shape validates; `T`'s `LIB` stamp is `2` |
| TC-25 | TC-24 run again; and the same request sent twice | the store receives no update the second time; sent twice, the data equals TC-24's |
| TC-26 | TC-24; the book's token before and after | differs; `dcterms:modified` equal; a replace of the book through a session with the token read before the migration raises `Conflict`; a migration with no steps leaves every token |
| TC-27 | `T` has a loaded graph holding `<x> lib:shelf "Z"` and an owned part (skolem IRI) with `lib:shelf` | loaded graph untouched; the part migrated; registry entries equal before and after; a live sweep of `T` reports no orphan and the stamps stay |
| TC-28 | chain `[1, 2, 3]`, `2__3`'s request makes the fake store fail | `T` is at `2` with `1__2` applied; `T` set aside, the log names `2__3` |
| TC-29 | `T`'s request fails (injected), `U`'s does not | `T` in the returned set and in `behind`, data and stamp of `T` equal to before; `U` at `2`; the log names `T` and `1__2`; a second `migrate_tenants` that succeeds empties `behind` |
| TC-30 | the system database's request fails in `migrate_shared` | `MigrationFailed` |
| TC-30a | the access records hold an old predicate that `RP`'s `1__2` renames | `migrate_shared` then `tenancy.tenants()` decodes them; `tenants()` before it raises `StoredDataInvalid` (shows the order matters) |
| TC-31 | `T`'s stamp is `9` (not in the chain); `T` holds two `LIB` stamps | each: `T` set aside, nothing sent to `T` |
| TC-32 | chain `[1, 2, 3]`; the fake's `after_update` hook, after the runner's `1__2` request, applies `2__3` as another instance would | the read-back is `3`: no failure, nothing more sent, data migrated once |
| TC-33 | tenant in state `deleting`; tenant whose database is gone | skipped; set aside |
| TC-34 | `Tenancy.create` | the new database holds both stamps at the current versions; create, dump, restore at the same version succeeds |
| TC-35 | `tenant_session(T)` with `T` in `behind`; `U`; a dump of `T` | `TenantBehind`; a session; the dump is made |
| TC-36 | toolkit chain `[1, 2]` and consumer chain `[1, 2]` | the toolkit's request is sent first, in every database |
| TC-37 | feature: a reader gets a book of a tenant set aside; of another tenant | `503` with problem type `tenant-behind`; `200` |
| TC-38 | feature: service built with a chain that forks | `InvalidMigration` |
| TC-39 | `install_service` without `migrations` | `TypeError` (required keyword) |
| TC-39a | the lifespan entered twice (as tests do) after a failure then a success | `behind` is empty the second time |

Spec scenario to test case: a new tenant TC-34; a tenant behind the schema TC-35, TC-37; an added
optional slot TC-02, TC-09; a removed slot without a new version TC-06; with a new version TC-07,
TC-08; a change that would change stored IRIs TC-05a; an unresolved draft TC-09a, TC-22; a renamed
slot TC-24; a second start TC-25, TC-32, TC-42; a failing migration TC-29; what a migration leaves
alone TC-27; a client with an old version token TC-26; restoring an older dump TC-51; a dump from
an unknown version TC-52; `rp-service-api`: a chain that forks TC-38, a tenant set aside TC-37
(one book asked for, and the books listed).

## 3. Dump, the application database, Fuseki, docs (stage 3, PR 3; after #102)

- [x] 3.1 Dump and restore (PD-15). Test first, in the existing dump and restore unit tests. Then
  `migrate_dataset(dataset, chains)` in `services/migration_runner.py` (PD-17); `services/tenant_dump.py` (`dump`
  reads the stamp; `_check_manifest` takes the chain) and `Tenancy.restore` (migrate the parsed
  dataset first).
- [x] 3.2 (closed by tasks 2.2 and 2.3, design D-1) The application database (PD-16). Test first. `migrate_shared` includes it when it
  exists; `ensure_application_database` stamps the one it creates (PD-10); the lifespan order of PD-9.
- [x] 3.3 Containers. In `tests/integration/store/`: the migration request against Fuseki.
- [ ] 3.4 Docs. A new `howto/migrate.adoc` (the rules table, the five recipes of PD-5, what cannot
  be migrated, reworking an unmerged version, dump first, stop old instances, what a tenant set
  aside looks like and how to recover); in `docs/modules/ROOT/pages/howto/adopt.adoc`, section "7. Change the model" rewritten to point
  to it and sections "4. Generate" and "12. Serve the application" gain `version`, `migrations`; `architecture/index.adoc` (building block no longer
  deferred) and `data-flows.adoc` (the start-up flow, where the stamp is stored; no consumer
  terms); `questions.adoc` (the question the page answers); `nav.adoc`; `howto/dump-restore.adoc`
  (PD-15); the durations table in `develop/index.adoc`; `openspec/changes/README.md` row 11;
  `CHANGELOG` is release-please's.

| ID | Input | Expected |
|---|---|---|
| TC-50 | dump of `T` whose `LIB` stamp is `1`, service at `2` | manifest `schema_version` is `1` |
| TC-51 | restore that dump into a service at `2` whose `1__2` changes a `Book` predicate and a predicate of the tenant root | the new tenant is at `2`, book and root migrated, the root vetted in its new shape |
| TC-52 | manifest with no version; version `9`; another schema id; a dump with no stamps graph; an `RP` stamp unknown to the toolkit chain | each `InvalidBody`; nothing created |
| TC-53 | restore whose migration fails on the dataset | `InvalidBody` naming the migration; no new database, bucket or record |
| TC-54 | schema with an application class, application database at `1`, chain `[1, 2]` | migrated to `2` by `migrate_shared`; its failure is `MigrationFailed`; a new one is stamped current |
| TC-40 | Fuseki: a three-operation request whose last operation fails | nothing changed (RISK-4) |
| TC-41 | Fuseki: TC-24 and TC-26 | as with the fake |
| TC-42 | Fuseki: two runners at once on one database (`asyncio.gather`), chain `[1, 2, 3]` | data migrated once, stamp `3`, neither fails |

## Roadmap

- [x] 1.1 · [x] 1.2 · [x] 1.3 · [x] 2.1 · PR 1 (#109) · [x] 2.2 · adversarial tester · [x] 2.3 · [x] 3.2 · PR 2 ·
  (#112) · [ ] 3.1 · [ ] 3.3 · [ ] 3.4 · PR 3

## Verification

Per stage, before its PR: `make check-all` and `make test-containers` once, the result pasted in
the PR body (the owner's rule R-0001, loaded by the rulebook skill: heavy checks run locally, their
result goes in the PR body); `openspec validate schema-migrations --strict`; `make check-docs` in
stage 3. The PLAN was attacked by a fresh reviewer (design.md PD-18) and is clarity-gated
(≥ 9/10) before task 1.1.
