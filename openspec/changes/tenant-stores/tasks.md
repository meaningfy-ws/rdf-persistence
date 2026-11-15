> Derives from: EPIC `tenant-stores` (proposal.md). Two stages, one PR each into `develop`.
> Type: Implementation.

`PD-n` is a decision of [design.md](design.md). `D` is the `default` store and `A` the store wired
as `client-a`, two `FakeStore`s in unit tests (two Fuseki containers in 2.2). `T` is a tenant of
the toy library (`tests/toy.py`), `B` a `Book`. The prefix is the settings' (`lib` in the toy).

Every task is test first. Its gate is `make test-changed check-quality`, or
`make test-fast check-quality` where the task says so (it changes `domain` or a `services` port, or
its reach is wide). After the lead commits a schema change: `make check-generated`.

## Stage 1: tenants routed by store, in `services` (PR 1)

- [ ] 1.1 PD-1, PD-10: `store_name` on `TenantAccess` in `model/rp_tenancy.yaml`; `make generate`
  (the lock changes `SAFE`, version stays `"2"`); `make refresh-snapshot` and read its diff.
  `StoreNotWired(PersistenceError, ValueError)` in `domain/exceptions.py`, exported where the
  others are, with its `INTERNAL_ERROR` row in `entrypoints/problems.py::ERROR_KINDS` and in
  `tests/unit/entrypoints/test_problems.py::ROWS`. Tests in `tests/unit/domain/` beside the existing access-record model tests. Gate:
  `make test-fast check-quality`.

| ID | Input | Expected |
|---|---|---|
| TC-01 | a `TenantAccess` with `store_name` of `client-a`, `a`, 32 characters `a…` | valid |
| TC-02 | `store_name` of `Client-A`, `-a`, `1a`, `""`, 33 characters | each a `ValidationError` |
| TC-03 | a record graph written today (no `rp:storeName`) through the toy mapper | decodes; `store_name is None` |
| TC-04 | the toolkit's lock after `make generate` | `schema_version == "2"`; no migration file added |

- [ ] 1.2 PD-3, PD-4, PD-5: `Tenancy(stores=)`, `DEFAULT_STORE`, `stores()`, `store_name_of`,
  `store_of`, the cache, `_session(..., store=)`, `tenant_session` resolving the store. Tests in
  `tests/unit/services/test_tenancy_stores.py`. Gate: `make test-fast check-quality`.

| ID | Input | Expected |
|---|---|---|
| TC-05 | `Tenancy(D, …, stores={"default": A})`; `{"Client": A}`; `{"a": A, "b": A}` | each a `ValueError` naming the key |
| TC-06 | `stores()` of a tenancy with `{"client-a": A}` | `{"default": D, "client-a": A}` |
| TC-07 | a record with no `store_name`, cold cache | `store_of(T)` is `D`; `D`'s operation count (`FakeStore.sent()`) grows by one query |
| TC-08 | a record with `store_name="client-a"`; `store_of` called twice | `A`; the second call reads nothing (`FakeStore` operation count) |
| TC-09 | a record naming `client-b`, not wired | `store_of` raises `StoreNotWired` naming `client-b` |
| TC-10 | no record for `T` | `store_name_of` raises `NotFound` |
| TC-11 | `T` on `A`; `async with tenant_session(T, alice)` and a book written | the book's graph is on `A`, nothing new on `D` |
| TC-12 | `T` in `behind` | `TenantBehind` raised at the call of `tenant_session`, before any read (the two existing tests stay green) |
| TC-38 | `T` on `A`; `set_grants`, then `rename`, then `delete` | after each rewrite the record still has `store_name="client-a"` |

- [ ] 1.3 PD-2, PD-7, PD-8: `create(..., store=)`, `restore(..., store=)` (and the pass-through in
  `tenant_dump.restore`), `_free_tenant` on every store, cleanup of a failed restore on its store,
  `finish_deletion` on the record's store and dropping the cache entry, `delete` resolving the
  store before it marks. `store` is a required keyword of `_session`, `_add_root`,
  `_replace_root` and `_stamp`. In `restore`, the sites are `create_dataset`, `_stamp`,
  `import_quads`, the "vanished" check and `_drop_restored`. Tests in
  `tests/unit/services/test_tenancy_stores.py` and `test_tenant_dump.py`. Gate:
  `make test-fast check-quality`.

| ID | Input | Expected |
|---|---|---|
| TC-13 | `create("L", {}, alice)` | database, stamp and root on `D`; record has no `store_name` (PD-2) |
| TC-14 | `create("L", {}, alice, store="client-a")` | database, stamp and root on `A`; record on `D` with `store_name="client-a"`; `D` has no `lib-t-…` database |
| TC-15 | `create(..., store="client-b")` | `StoreNotWired`; no draw, no database, bucket or record anywhere |
| TC-16 | `id_source` forces the first id; its database exists on `A` only | redrawn; the tenant gets the second id |
| TC-17 | `T` on `A`, `delete` then `finish_deletion` | database dropped from `A`; `D`'s databases unchanged; record removed; `store_name_of(T)` then raises `NotFound` |
| TC-18 | `finish_deletion` where `A` already lacks the database (an interrupted run) | bucket dropped, record removed, no error |
| TC-19 | a dump of a tenant on `D`, `restore(…, store="client-a")` | the new tenant's database on `A`, record names `client-a`, new IRI |
| TC-20 | a restore on `A` whose import fails | the database is dropped from `A`; the error is the original |
| TC-39 | a restore on `A` whose database vanishes from `A` before the record is written | the "vanished" error; the check read `A`'s listing, not `D`'s |
| TC-40 | `A` raises `StoreUnavailable` on `list_datasets`; `create` on `D` | `StoreUnavailable`; nothing created on `D` |
| TC-41 | a record naming `client-b` (unwired); `delete(T, version)` | `StoreNotWired`; the record is still `active` |

- [ ] 1.4 PD-6: `sweep` (the DEC-6 check first, then the "no records" guard and the orphan drop on
  every wired store) and `migrate_tenants` per tenant store; `remove_with_files` and
  `sweep_tenant` covered through the routed session and an explicit store. Tests in
  `tests/unit/services/test_sweep.py`, `test_migration_runner.py`, `test_remove_with_files.py`,
  `test_tenant_sweep.py`. Gate: `make test-fast check-quality`. **The adversarial tester runs
  after this task** (write order: nothing dropped before the check).

| ID | Input | Expected |
|---|---|---|
| TC-21 | an active `T` on `A`, an orphan `lib-t-zzzz` on `A`, an orphan `lib-t-yyyy` on `D` | both orphans dropped; `T`'s database on `A` unchanged |
| TC-22 | records naming `client-b` and `client-c` (unwired), a `deleting` tenant on `A`, an orphan on `D` | `StoreNotWired` whose message names `client-b, client-c`; the deleting tenant's database and the orphan are still there |
| TC-23 | the system database is new, and a `lib-t-…` database exists on `A` only | sweep skipped with the existing warning; nothing dropped |
| TC-24 | a `deleting` tenant on `A` | finished on `A`; `D` untouched |
| TC-25 | `A` raises `StoreUnavailable` on `list_datasets`; a `deleting` tenant and an orphan on `D` | `sweep` raises it; the deleting tenant's database and the orphan are still on `D` |
| TC-42 | an orphan on `D` that `drop_dataset` reports `NotFound` (dropped meanwhile) | the sweep goes on; the other orphans are dropped |
| TC-43 | a record with no `store_name` whose database exists on `A`, not on `D` | an ERROR log, step `misplaced-tenant`, naming the tenant, `default` and `client-a`; nothing dropped |
| TC-26 | a tenant on `A` with a pending migration step, one on `D`; `ensure_system_database`, `ensure_application_database`, `migrate_shared`, `migrate_tenants` | each tenant migrated on its own store, stamps moved on each; `A` holds no system or application database |
| TC-27 | `remove_with_files` on a tenant on `A` | the aggregate removed on `A`, its blobs deleted |
| TC-28 | `sweep_tenant(tenancy, A, …)` for a tenant on `A`, an orphan loaded graph there | found and, with `remove`, dropped on `A` |

Stage 1 closes with the lead's `make check-all` and `make test-containers`, the review (L1, L2, L3
separate; L4+L5 one pass), the fix pass, rebase on `develop`, PR 1, merge on green CI.

## Stage 2: the kit, two Fuseki servers, BDD and docs (PR 2)

- [ ] 2.1 PD-9: `ServiceKit(stores=)`, `install_service(stores=)`, `kit.store_of`, and `dump_tenant`,
  `sweep_tenant`, `restore_tenant(store=)` routed. Tests in `tests/unit/entrypoints/`. Gate:
  `make test-changed check-quality`.

| ID | Input | Expected |
|---|---|---|
| TC-29 | `install_service(..., stores={"client-a": A})`; a tenant created in Python on `client-a`; `GET` of a book over HTTP | 200, read from `A` |
| TC-30 | the generic `POST /tenants` on that app | the tenant is on `D` (DEC-1) |
| TC-31 | `kit.store_of(T)` for `T` on `A`; for an unknown tenant | the `ToolkitStore` around `A`; `NotFound` |
| TC-32 | `dump_tenant` of `T` on `A`, `restore_tenant(..., store="default")` | the copy is on `D`, its books read back |
| TC-33 | `install_service(..., stores={"default": A})`; `stores={"a": A, "b": A}`; `store=A, stores={"a": A}` (same raw object) | each a `ValueError` before the app is returned |
| TC-34 | the app's start-up with a record naming an unwired store | start-up raises `StoreNotWired`; no route served |
| TC-35 | the response bodies of `GET` and `PUT` on the access record and of `GET /tenants` | no `storeName` in any of them |

- [ ] 2.2 PD-11: compose service `fuseki-b` (the same `image:` tag as `fuseki`, no `build:`, so
  no second image is built) and session fixture `fuseki_b` in
  `rdf_persistence/testkit/containers/`; `tests/integration/tenancy/test_tenant_stores.py`. Gate:
  `make test-containers TEST_PATH=tests/integration/tenancy/test_tenant_stores.py`, then
  `make check-quality`.

| ID | Input | Expected |
|---|---|---|
| TC-36 | two Fuseki containers, a tenant on each, a book in each | each book on its own server only (`list_datasets` and a query on the other server) |
| TC-37 | an orphan `{prefix}-t-…` database made on the second server, and an active tenant there; `sweep` | the orphan dropped; the tenant's database and its book unchanged |

- [ ] 2.3 BDD: `tests/feature/tenant_stores.feature` with the spec delta's scenarios (two tenants on
  two stores, an existing record, deletion on the tenant's store, an orphan on another store, a
  store no longer wired, copy by dump and restore) and its steps in
  `tests/feature/test_tenant_stores.py` on two `FakeStore`s. The spec's other three scenarios are
  covered by unit tests: "not wired at create" by TC-15, "id free on every store" by TC-16,
  "migrations on each store" by TC-26. Gate: `make test-changed check-quality`.

- [ ] 2.4 Docs: `howto/tenant-stores.adoc` (wiring, choosing a store at create, copying by dump and
  restore, retiring a store, the deploy order of RISK-2, the prefix rule of RISK-1, one server
  under one name of RISK-4, no downgrade or mixed versions of RISK-5, checking a user's store
  choice in a consumer's own create route, and the anti-pattern of passing `kit.store` for a
  tenant to `dump`, `sweep_tenant` or `database_of`), its entry in the nav and in `questions.adoc`, a paragraph in
  `howto/application-data.adoc` (the start-up functions' `store` is the default store), and the
  rows of the durations table if a target's time moved. Gate: `make check-docs`.

Stage 2 closes like stage 1. Then P-0004: the reconciliation of `proposal.md`, in PR 2 before it
merges. It includes the stale lines the gate found: "Not planned: the PLAN is derived…", "when
`tenant-dump-restore` has landed", and `services/file_removal.py` in What Changes (no change: it is
routed through the session).

## Roadmap

- [ ] 1.1 · [ ] 1.2 · [ ] 1.3 · [ ] 1.4 · (tester) · PR 1 · [ ] 2.1 · [ ] 2.2 · [ ] 2.3 · [ ] 2.4 ·
  reconcile · PR 2

## Verification

The TC tables above as tests; `make check-all` and `make test-containers` before each PR;
`openspec validate tenant-stores --strict`; the clarity gate on this pair (≥ 9/10).
