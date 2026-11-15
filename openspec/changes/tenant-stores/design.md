> Derives from: EPIC `tenant-stores` ([proposal.md](proposal.md)), capability `rp-tenancy`.
> The developer's answers of 2026-11-15 are in [inputs/questions-2026-11-15.md](inputs/questions-2026-11-15.md).
> Type: Implementation.

## Context

On `develop` (ae04865) one `Store` reaches every database. `Tenancy` holds it as `self._store` and
uses it for the system database, the application database, and each tenant database. The tenant
database is derived from the tenant IRI (`Iris.resource_name`) with no read. The kit wraps the
consumer's store once (`ToolkitStore`) and passes `kit.store` to the start-up functions (`sweep`,
`migrate_shared`, `migrate_tenants`), to `tenant_dump.dump`, `tenant_dump.restore` (through
`Tenancy.restore`) and `tenant_sweep.sweep_tenant`. A consumer with its own start-up calls the same
three functions with `kit.store` (`howto/application-data.adoc`).

What the brief asked to check against `develop`:

| Claim | On `develop` | In this PLAN |
|---|---|---|
| Copying a tenant between stores is a dump followed by a restore | Holds. `kit.dump_tenant` reads the tenant's database and `kit.restore_tenant` makes a new tenant (new IRI, only the creator granted, migrated in memory to the running version). Neither takes a store today | `restore_tenant(..., store=)` (PD-7) |
| Every wired store must hold the application database and run migrations at start-up | Does not hold as worded. The system and application databases live on the one store (`ensure_application_database`, `_shared_databases`). The developer chose (2026-11-15) to keep both on `default`. What every store needs: each tenant database stamped at create on its own store, and migrated at start-up on its own store | PD-6 |
| The access record must name the store a tenant lives in | Holds as DEC-5 plans. `TenantAccess` has `database_name` only. An optional slot is `SAFE` for the lock (`generation/lock.py`), so the metamodel version stays `"2"` and no migration file is needed | PD-1 |

## Goals / Non-Goals

**Goals:**

- A consumer wires named stores beside `default`, and creates a tenant on one of them (DEC-1).
- Every tenant operation (session, rename, deletion, both sweeps, dump, restore, migration,
  `remove_with_files`) runs on the tenant's own store.
- A record without a store name means `default`: no data migration, no change for a consumer with
  one store.
- Start-up refuses a record that names an unwired store, before anything is dropped (DEC-6).

**Non-Goals:** everything in the EPIC's No-gos. Also: an application database per store (the
developer, 2026-11-15); store choice in HTTP; showing the store name in any response.

## Decisions

Settled in the EPIC and cited, not re-argued: DEC-1 to DEC-7. The new ones:

- **PD-1 The slot.** `store_name` in `model/rp_tenancy.yaml`: slot URI `rp:storeName`, range
  `string`, pattern `^[a-z][a-z0-9-]{0,31}$`, annotation `internal: true` (like `database_name`), on
  `TenantAccess`, optional. `make generate` regenerates the models and rewrites the lock with a
  `SAFE` change, version `"2"` unchanged. The pattern lives in the schema only (anti-patterns).
- **PD-2 `default` is never written.** A tenant created on `default` gets a record with no
  `store_name`, exactly as today. A tenant on another store gets its name. One reading rule:
  `record.store_name or DEFAULT_STORE`. Reason: single-store consumers see no change in records,
  dumps or snapshots. Rejected: always writing it (two shapes of the same fact, old and new).
- **PD-3 Where the stores live.** `Tenancy.__init__` gains `stores: Mapping[str, Store] = {}` (the
  other stores; `default` is the existing positional `store`). It refuses at construction, with
  `ValueError`: a key `default`, a key the generated `TenantAccess.store_name` validator refuses,
  and the same `Store` object under two names (including the default one). The kit runs the same
  identity check on the consumer's raw stores **before** wrapping them in `ToolkitStore`, since
  each wrapper is a new object (PD-9). `DEFAULT_STORE = "default"` is a constant of
  `services/tenancy.py`.
- **PD-4 Routing a tenant.** `Tenancy` keeps a cache `tenant IRI → store name`, filled by `create`,
  `restore` and `_records()` (every start-up sweep reads all records), and dropped for a tenant by
  `finish_deletion`. `async store_name_of(tenant)` answers from the cache, or reads the record once
  on a miss (`get`, the system database on `default`) and caches it; no record raises `NotFound`.
  `async store_of(tenant)` answers the `Store`, or raises `StoreNotWired` for a name not wired.
  Safe to cache because a tenant never moves (DEC-2).
- **PD-5 Sessions take their store.** `_session`, `_add_root`, `_replace_root` and `_stamp` gain a
  **required** keyword `store`, so a site that is missed fails to type-check instead of quietly
  using `default`. `tenant_session` stays a plain function: it checks `behind` and raises
  `TenantBehind` at the call, as today (two tests assert that:
  `test_migration_runner.py:565`, `test_migration_runner_adversarial.py:442`). It then returns an
  inner async context manager that resolves `store_of(tenant)` on entry and opens the session on
  that store. Callers are unchanged. The gate's access check reads the record first, so a request's lookup hits the cache
  after the first one, or reads it once per instance per tenant (the EPIC's "per-request cost").
- **PD-6 Start-up and migrations.** The functions keep their signatures (the developer,
  2026-11-15). Their `store` argument is the `default` store, the object `Tenancy` holds. `Tenancy`
  exposes `stores()`, the mapping of every wired name to its store, `default` included.
  - `sweep`, in this order: (1) read the records; (2) raise `StoreNotWired` naming every unwired
    store the records name, sorted (DEC-6); (3) list the databases of **every** wired store
    (a `StoreUnavailable` stops here, before anything is touched); (4) only then the "no records"
    guard, the finishing of deletions, and the orphan drop, from those listings. An orphan is a
    `{prefix}-t-…` name that no record names, whatever store it is on (DEC-7). Each orphan drop
    suppresses `NotFound` (another instance's sweep, or RISK-4, dropped it first). The bucket side
    is unchanged (one object store, DEC-3).
  - `sweep`, step (3) also checks each record's placement. A record whose database is missing from
    its own store but present on another wired store is logged at ERROR (step
    `misplaced-tenant`, the tenant, both store names) and left alone. This makes RISK-5 visible
    without adding a start-up failure.
  - `migrate_tenants`: each tenant's database on `await tenancy.store_of(tenant.id)`, called
    outside the `try` that catches `MigrationFailed`, so a `StoreNotWired` stops the start-up
    (DEC-6) even for a consumer who calls `migrate_tenants` without `sweep`.
  - `migrate_shared`, `guard_iri_policy`, `ensure_system_database`, `ensure_application_database`:
    `default` only, unchanged.
- **PD-7 Create and restore.** `Tenancy.create(label, root_slots, creator, *, store=DEFAULT_STORE)`
  and `Tenancy.restore(..., store=DEFAULT_STORE)` check the name is wired (`StoreNotWired`) before
  anything is drawn or created. Then they create the database, stamp it, write the root on that
  store, and write the record (with `store_name` per PD-2) on `default`. Every tenant-side call of
  `restore` goes to that store: `create_dataset`, `_stamp`, `import_quads`, the "vanished" check
  (today `tenancy.py:416`) and `_drop_restored` (today `tenancy.py:450`). `_free_tenant` lists the
  databases of every wired store (DEC-7: an id is free on every store). `tenant_dump.restore` and
  `kit.restore_tenant` pass `store` through. The cleanup of a failed restore drops on that store.
- **PD-8 Deletion.** `delete` resolves `store_of(tenant)` **before** it marks the record
  `deleting`, so an instance that does not wire the store (RISK-2) refuses with nothing changed.
  `finish_deletion` drops the database on the record's store, then the bucket, then removes the
  record, then forgets the cache entry.
- **PD-9 The kit.** `ServiceKit(..., stores: Mapping[str, Store] = {})` and
  `install_service(..., stores=)` wrap each store in `ToolkitStore` and give them to `Tenancy`.
  `kit.store` stays the `default` store. `async kit.store_of(tenant) -> Store` mirrors
  `bucket_of` (the developer, 2026-11-15). `dump_tenant` and `sweep_tenant` pass
  `await self.store_of(tenant)` to `tenant_dump.dump` and `tenant_sweep.sweep_tenant`, whose
  signatures are unchanged. A direct caller of those two functions, or of `tenancy.database_of`
  with `kit.store`, can still name the wrong store. That gives `DatabaseGone` (404), never lost
  data, and the how-to lists it as an anti-pattern. `restore_tenant(src, creator, *, store=DEFAULT_STORE)`.
- **PD-10 The error.** `StoreNotWired(PersistenceError, ValueError)` in `domain/exceptions.py`,
  exported like the others. Its message names the store. A consumer that routes its own create
  with a store its user chose checks the choice against the names it wired itself; a name it did
  not wire is a bug in that route. Over HTTP it gets the row
  `(errors.StoreNotWired, INTERNAL_ERROR)` in `entrypoints/problems.py::ERROR_KINDS` (every error
  class has a row; `tests/unit/entrypoints/test_problems.py` checks it, and its `ROWS` gains the
  same row): start-up refuses it before serving, and the only other way to reach it is RISK-2, an
  operator's fault, answered 500 and logged at ERROR by the existing handler.
- **PD-11 Test stores.** Unit tests use two `FakeStore`s. The testkit gains a second Fuseki,
  compose service `fuseki-b` and session fixture `fuseki_b` (`RP_FUSEKI_B_PORT`), started only by
  the tests that ask for it, so the container lane's other tests pay nothing.

## Delivery decisions

- **PD-12 A failed create cleans up after itself** (stage 1, from the adversarial tester's
  FINDING-1). Two instances that draw the same id at the same moment, one creating on `client-a`
  and one on `default`, both pass `_free_tenant`. The loser's database on `client-a` then carries
  a name that the winner's record holds, so no sweep ever drops it (orphans are judged by name
  across stores, DEC-7). With one store the second `create_dataset` raised `Conflict`, so nothing
  was left. Fix: `Tenancy.create` drops the new database from its store, and the bucket if it
  created it, on any failure after `create_dataset` and before the record is written. This is best
  effort, logged at step `create-cleanup` like `_drop_restored`, and the original error is
  re-raised. Rejected: judging orphans per store (it would drop RISK-4's second name's
  databases).
- **PD-14 A cleanup drops only what its own call made** (review L1, C1, Critical). In the same
  race, a restore that loses gets `Conflict` from `create_bucket` (one object store), and
  `_drop_restored` then deleted the **winner's** bucket and its files. Fix: `restore` and `create`
  each record what they made (`database_made`, `bucket_made`), and their cleanup drops only those.
  A unit test uses two `FakeStore`s and a `FileStore` whose `create_bucket` raises `Conflict`.
- **PD-15 One routing rule, one source of stores** (review L3 W1, L4/L5 W1 and W2). The sweep takes
  its stores from `tenancy.stores()`; its `store` argument stays for the signature, unused, as in
  `migrate_tenants`. `store_name_in(record) -> str` beside `DEFAULT_STORE` in `tenancy.py` is the
  one reading of PD-2, used by `Tenancy` and `sweep`.
- **PD-13 One read of the records at start-up.** The sweep reads all records with one query
  (`Tenancy.access_records()`, public, over `_records()`, which also fills the routing cache), not
  one `get` per tenant.

## Algorithm / approach

Worked example, a kit wired to `default` (D) and `client-a` (A), prefix `lib`:

1. `create("Client A library", {}, alice, store="client-a")`: `client-a` is wired. `_free_tenant`
   draws `…/t/x7k2` and checks that `lib-t-x7k2` is on neither D nor A and has no record. Then: A
   `create_dataset("lib-t-x7k2")`, A stamp, bucket `lib-t-x7k2`, root written on A, record written
   on D with `database_name=lib-t-x7k2, store_name=client-a`, cache `x7k2 → client-a`.
2. `tenant_session(x7k2, alice)`: not behind; cache hit `client-a`; the session opens on A.
3. Another instance, cold cache: `require` reads the record from D (as today); `tenant_session`
   misses and reads the record once more, then caches it. Later requests hit the cache.
4. Restart: `sweep` reads the records, which fills the cache. Every store a record names is wired.
   It finishes deletions on each tenant's store, then lists `lib-t-*` on D and A and drops the names
   no record holds. `migrate_tenants` migrates `lib-t-x7k2` on A.
5. Copy to D: `dump_tenant(x7k2, out)` reads from A; `restore_tenant(src, bob)` creates a new
   tenant on D with a new IRI.

Idempotency: create and restore are as today (a failed create leaves an unnamed database for the
sweep; the sweep is safe to run again). `finish_deletion` keeps its `suppress(NotFound)` per drop,
so an interrupted deletion finishes on a rerun on the same store. The cache is only ever filled
from a record, never guessed.

### Anti-patterns

| Don't | Do instead | Why |
|---|---|---|
| Route by guessing `default` on a cache miss | Read the record on a miss | Another instance may have created the tenant on another store |
| A second regex for store names in Python | The generated model's validator | LinkML is the single source (PD-24) |
| Write `store_name: default` | Leave it out (PD-2) | One shape per fact; old records already mean `default` |
| Pass the default store where a tenant's store is meant | `await tenancy.store_of(tenant)` / `kit.store_of` | That is the bug this EPIC removes |
| Sweep only `default` for orphans, or decide orphans per store | Every wired store, by database name across all records (DEC-7) | A tenant's database must never be dropped because it is looked up on the wrong store |
| Check unwired stores after finishing deletions | Check first, then act | DEC-6: nothing dropped |

## Error matrix

| Failure mode | How it is detected | Expected handling |
|---|---|---|
| `create`/`restore` names an unwired store | Name not in `stores()` | `StoreNotWired` before any draw or create; nothing left |
| `stores` has a key `default`, a bad name, or one store twice | `Tenancy`/kit construction | `ValueError` naming the key; the service does not build |
| A record names an unwired store at start-up | `sweep`, after reading records | `StoreNotWired` naming every such store, sorted; nothing finished or dropped; start-up stops |
| A wired store is unreachable at start-up | `list_datasets` raises `StoreUnavailable` in sweep step (3) | Start-up stops before anything is finished or dropped on any store (EPIC rabbit-hole) |
| A wired store is unreachable at runtime, during a create or restore on another store | `_free_tenant` lists every store: `StoreUnavailable` | 503, nothing created. Accepted: DEC-7 needs the id checked on every store |
| A consumer's own create passes a store name its user typed, not wired | `StoreNotWired` | 500, nothing created; the consumer's route checks the name first (PD-10) |
| A record lost its `store_name` (RISK-5) | Sweep step (3): its database is on another store | ERROR log `misplaced-tenant`; requests to it answer 404 until an operator restores the slot |
| Two sweeps, or RISK-4, drop the same orphan | `drop_dataset` raises `NotFound` | Suppressed per orphan |
| An id clashes on another store | `_free_tenant` lists every store | Redrawn, as for a clash today |
| Deletion interrupted on store A | Record stays `deleting` | Next start's sweep finishes on A (`suppress(NotFound)` per drop) |
| A failed restore on A | As today | Best-effort drop on A; what stays is the sweep's |
| Session for a tenant with no record | `store_name_of` miss → `NotFound` | `NotFound` (the gate already answers 404 before this) |
| A request reaches an instance that does not wire the tenant's store (RISK-2) | `store_of` → `StoreNotWired` | 500 `internal-error` (PD-10), logged at ERROR by the existing handler. The how-to says to wire a store on every instance before creating on it |
| A tenant id redrawn after deletion while another instance still caches the old store (RISK-3) | Not detected | Accepted |

## Risks / Trade-offs

- **RISK-1 Shared prefix on a wired server** (the developer, 2026-11-15: accept and document).
  Likelihood low, impact high: another deployment's `{prefix}-t-…` databases on a server we wire
  are dropped at start-up. Mitigation: the how-to says a prefix belongs to one deployment on every
  store it wires. Same risk as on `default` today.
- **RISK-2 A rolling deploy that adds a store.** Likelihood medium during a deploy, impact low:
  an old instance cannot serve a tenant created on the new store, and answers 500 until it
  restarts. Mitigation: the how-to orders the steps (wire everywhere, restart, then create).
- **RISK-3 A stale cache entry.** A tenant is deleted, and its random id is drawn again for a new
  tenant on another store, while an instance still caches the old one. Likelihood negligible (ids
  of at least 4 random characters, redrawn on any clash), impact: requests go to the wrong store
  until restart. Accepted. `finish_deletion` drops the entry on its own instance.
- **RISK-4 Two names for one server.** If two `FusekiStore`s point at the same URL, PD-3 cannot
  see it (they are different objects). The orphan rule is by name across stores, so nothing is
  dropped wrongly, and the second drop of an orphan is a suppressed `NotFound`. Accepted; the
  how-to says not to do it.
- **RISK-5 A writer that does not know `store_name` erases it.** The mapper decodes only the slots
  it knows. A toolkit older than this change (a rollback, or an old instance in a rolling deploy)
  that rewrites a record (`set_grants`, `rename`, `delete`) drops `rp:storeName`. The tenant then
  routes to `default` and answers 404; its database is never dropped, because orphans are judged
  by name. Likelihood low, impact high for that tenant. Mitigations: the how-to says no downgrade
  and no mixed versions once a tenant lives off `default` (upgrade every instance before the
  first create elsewhere); the sweep logs it at ERROR (`misplaced-tenant`); TC-38 proves that this
  toolkit's own rewrites keep the slot. This is the weakest assumption behind DEC-2.
- **Trade-off:** a cache miss costs one extra read of the system database per tenant per instance.
  Rejected: returning the store from the gate's own read, which would change `Authorised` and every
  route for a once-per-instance read.

## Open Questions

None: the developer answered the round of 2026-11-15.
