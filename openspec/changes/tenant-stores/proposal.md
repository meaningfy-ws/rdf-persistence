<!-- Parents: openspec/specs/rp-tenancy (each tenant is one database; the access record stores its
     database name; the start-up sweep); openspec/changes/second-store (another store product behind
     the `Store` port); the developer's need in inputs/seed.md. -->

# EPIC: Tenants on several wired stores

> Shaped 2026-11-10; open questions answered by the leader on 2026-11-12 (inputs/seed.md, "Leader's
> recommendations"); the developer may overrule any DEC marked "leader's choice". Third of the four
> tenancy candidates. Not planned: the PLAN is derived at the start of its epic session.

**Golden-thread parent:** capability `rp-tenancy` (a tenant is one database, named in its access
record), and the developer's need (2026-11-10): "other databases under its governance ... which
includes also other databases/triplestores". This EPIC is about **where** a tenant's database lives
(several servers wired at once); **which product** a server is belongs to `second-store`.

## Appetite

**MEDIUM.** One capability: the kit takes several named stores, the access record names a tenant's
store, and tenancy, sessions, the start-up sweep and the live-tenant sweep route by it. Same product
on every store (Fuseki, until `second-store`); one object store; no moves.

## Why

The kit is wired to one triple store, so every tenant database lives on one server. An application
that governs projects kept on other servers (for size, cost, or a client's own infrastructure)
cannot manage them as tenants.

## Solution outline

The consumer wires named stores; the existing `store` argument is the store named `default`, which
also holds the system database (and the application database of `app-level-data`). Creating a
tenant in Python may name a store; the generic create route uses `default`. The access record keeps
the store's name beside the database name; a record without one means `default`, so existing data
needs no migration. Sessions, deletion, both sweeps and `remove_with_files` open the tenant's own
store. A tenant's store never changes, so the kit may cache it per tenant.

```python
kit = ServiceKit(..., store=FusekiStore(main_url, ...),
                 stores={"client-a": FusekiStore(client_a_url, ...)})
summary = await kit.tenancy.create("Client A library", root_slots, creator, store="client-a")
async with kit.session(summary.id, principal) as session:     # opens on client-a
    ...
```

## Key decisions

- **DEC-1** (Q-1; leader's choice, 2026-11-12, the developer may overrule): the **consumer's code**
  chooses: `Tenancy.create(..., store=name)` in Python; the generic `POST` route always uses
  `default`; a consumer that lets users choose routes the create itself. Reason: the smallest change
  that lets an application decide; a rule or a request field can come later. Rejected: a store field
  in the generic create body (exposes server names to clients); a chooser callback (no consumer yet).
- **DEC-2** (Q-2; leader's choice): a tenant **never moves** between stores in this EPIC. A copy on
  another store is `tenant-dump-restore` (dump, then restore with `store=`, which gets a new tenant
  IRI); a move that keeps the IRIs is a later change. Reason: a move needs a write freeze and an
  IRI-keeping restore, each its own risk. Because the store never changes, caching it is safe.
- **DEC-3** (Q-3; leader's choice): files **do not** follow: every bucket stays on the one wired
  object store. Reason: no need named for it; buckets are already per tenant. Rejected: a named
  object store per triple store (doubles the wiring for no known consumer).
- **DEC-4** (Q-4; leader's choice): **separate from and before `second-store`**, which it does not
  need: several Fuseki servers are the developer's case. When `second-store` lands, each named store
  carries its own capability descriptor and the start-up check runs per store. Rejected: merging the
  two (a LARGE EPIC mixing two independent risks).
- **DEC-5**: the access record gains `store_name` (LinkML slot, optional, internal, pattern of a
  store name); absent means `default`. Generated, never hand-written (D-13, PD-24).
- **DEC-6** (leader's choice): the service **refuses to start**, naming the store, when an access
  record names a store that is not wired. Reason: loud and simple; silently skipping would hide
  tenants and a later sweep could misjudge them. A consumer retiring a store deletes or copies its
  tenants first.
- **DEC-7**: the start-up sweep lists every wired store and drops a `{prefix}-t-…` database only when
  no access record names that database name; it never touches a store that is not wired. Database
  names stay unique across stores (the tenant id is drawn once and checked against every store).

## Rabbit-holes

- **The sweep's "no records" guard** (`services/sweep.py`) must consider resources on every store.
- **Per-request cost.** Routing needs the record's store; the gate already reads the record for the
  access check, so the store comes with it or from the cache, never an extra read per request.
- **Unreachable store at start-up**: `StoreUnavailable` stops the start-up as today for `default`;
  for the others too (DEC-6 spirit). Serving the other tenants while one store is down is cut.

## No-gos

- Moving a tenant between stores, or keeping its IRIs across stores.
- A store per bucket; a second object store.
- Queries across tenants or stores.
- Store choice in the generic HTTP create route, or a choosing rule in the toolkit.
- Different products per store (that is `second-store`), and per-store capability checks before it.
- Serving while a wired store is unreachable.

---

## What Changes

- `rdf_persistence/model/rp_tenancy.yaml`: `TenantAccess.store_name`; regenerated code.
- `rdf_persistence/services/tenancy.py`: named stores, `create(..., store=)`, routing of sessions,
  deletion and `finish_deletion`; `_free_tenant` checks every store.
- `rdf_persistence/services/sweep.py`, `services/tenant_sweep.py`, `services/file_removal.py`: the
  tenant's store.
- `rdf_persistence/entrypoints/kit.py` and `install_service`: `stores=`; the start-up check of DEC-6;
  `restore_tenant(..., store=)` when `tenant-dump-restore` has landed.
- Tests: unit tests on two fake stores; one integration test with two Fuseki containers.
- Docs: a how-to (wiring several stores, choosing one at create) and a `questions.adoc` entry.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `rp-tenancy`: a tenant's database may live on another wired store (ADDED requirements).

## Impact

- The access record's schema gains an optional slot; existing records read as `default`.
- `ServiceKit` and `install_service` gain an optional `stores` argument; nothing else changes for a
  consumer with one store.
- `atomic-commit` (#83), `cross-aggregate-unique-keys` and `aggregate-events` work inside one tenant,
  so inside one store; nothing here crosses stores.
