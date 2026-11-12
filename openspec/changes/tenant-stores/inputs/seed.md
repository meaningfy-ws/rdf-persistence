# Seed (secondary; never groomed)

Raised while shaping `tenant-root-loads` (see its inputs/seed.md):

> "an application has one database for application metadata and control, but then it has other
> databases under its governance and each database represents a project ... we cannot distinguish
> between app-project, and space within app governance, which includes also other
> databases/triplestores ... we shall be able to simply provide a triplestore dump as nquads, for
> example, and then you load it into a new project and restore its state." (developer, 2026-11-10)

The developer chose to record this need as a candidate EPIC (2026-11-10).

## Leader's recommendations (2026-11-12)

The developer was away and had accepted recommendations by default; the leader answered each open
question. Each answer is a DEC in `../proposal.md` marked "leader's choice"; the developer may
overrule any of them.

- Q-1 (who chooses the store) -> the consumer's code: `create(..., store=name)`; the generic route
  uses `default` (DEC-1).
- Q-2 (moving a tenant) -> no move in this EPIC; a copy on another store is dump + restore with
  `store=` (new IRIs); a move keeping IRIs is a later change (DEC-2).
- Q-3 (files follow) -> no; one object store (DEC-3).
- Q-4 (order with `second-store`) -> separate, and before it: several Fuseki servers need no
  capability descriptor; `second-store` later adds a descriptor per named store (DEC-4).
- Added: a record naming an unwired store stops the start-up (DEC-6); the sweep drops only what no
  record names, on every wired store (DEC-7). Appetite cut from LARGE to MEDIUM by these no-gos.

Order: third of the four. It reuses `tenant-dump-restore`'s restore (with `store=`) for copies, and
must place `app-level-data`'s application database on `default`.

## Test scenarios the EPIC must prove

- Two tenants on two stores: each book lives and reads back only on its tenant's store.
- A record without a store name opens on `default` (no migration).
- Deleting a tenant on `client-a` drops only there; an interrupted deletion is finished there.
- The start-up sweep drops an orphan on `client-a` and leaves its active tenant alone.
- A record naming an unwired store stops the start-up, naming it, with nothing dropped.
- A new tenant id is free on every store (a clash on `client-a` is redrawn).
- The live-tenant sweep and `remove_with_files` act on the tenant's own store.
- Dump on `default`, restore with `store="client-a"`: the copy lives on `client-a`.
- On two Fuseki containers: the two-tenants scenario and the orphan sweep.
