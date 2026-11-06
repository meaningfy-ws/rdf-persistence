<!-- Parents: openspec/specs/rp-tenancy (the start-up sweep); architecture v1,
     docs/modules/ROOT/pages/architecture/index.adoc (building blocks: "Sweep of orphans inside a
     live tenant", deferred). Seeds: inputs/seed.md. -->

# EPIC: Sweep orphans inside a live tenant

> Candidate EPIC, shaped 2026-11-06 from the v1 future list. Not planned: the PLAN (design.md, tasks.md) waits for the developer's answers in inputs/seed.md.

**Golden-thread parent:** capability `rp-tenancy` (requirement "The start-up sweep finishes
interrupted work") and the deferred building block "Sweep of orphans inside a live tenant" of
`docs/modules/ROOT/pages/architecture/index.adoc`.

## Appetite

**SMALL.** One capability, tenancy, touched in a few places: the sweep, the file-store port and its
adapters, and the docs. The registry and the naming scheme are reused as they are.

## Why

The start-up sweep (`rdf_persistence/services/sweep.py`) drops only whole `{prefix}-t-` databases and
buckets that no access record names; it never looks inside a live tenant. Two kinds of orphan
build up there. A graph loaded by `Session.load_graph` (`services/session.py`) at
`{root}/content/{uuid4}` stays unseen if no commit names it in `loaded_graphs`. A blob written with
`FileStore.put` (`services/files.py`) under a key no `StoredFile.file_key` names (`model/rp_files.yaml`)
stays too, and `Session.remove` drops an aggregate's loaded graphs but not its blobs. Both are erased
only with their tenant.

## Solution outline

A sweep that runs inside a live tenant finds the loaded graphs no registry entry owns and the blobs
no stored aggregate names, and removes them without ever removing something a commit still needs.
The tenant keeps serving while it runs, or the sweep says plainly when it may run. Operators can see
what it removed. When and how it is triggered is for the developer to decide (inputs/seed.md).

## Key decisions

- **DEC-1**: Loaded graphs are named `{aggregate_iri}/content/{uuid4}` and owned through registry
  entries in `{tenant_iri}/registry` (`rp:ownedBy`, `rp:kind loaded_graph`). Source: archived
  design.md PD-6a, PD-8, PD-8a. The sweep reads that registry; it adds no second record of ownership.
- **DEC-2**: The start-up sweep keeps its v1 behaviour and its safety rule: it drops nothing when
  the access records are missing (PD-8c), and it never touches the inside of an `active` tenant
  (`rp-tenancy`). The live-tenant sweep is a separate requirement, not a widening of it.
- **DEC-3**: Any new record (for example a sweep report) is a LinkML class, generated; data goes
  through generated models, not dicts. Source: AGENTS.md, Project specifics; D-13; PD-24.
- **DEC-4**: SPARQL is built only through `domain/sparql.py` (`term`, `fill`), with templates as
  module constants in the service that sends them. Source: PD-3; `rp-aggregate-store`.

## Rabbit-holes

- **The race with a commit in flight.** A graph loaded a moment ago, not yet committed, looks like
  an orphan. A grace period or a marker is needed; which one is open (Q-2).
- **Listing a large bucket.** S3 lists by pages; a tenant with many blobs makes the sweep long.
- **Blob references outside `file_key`.** A consumer may name a blob some other way; the sweep can
  only trust the slot the metamodel declares.

## No-gos

- Changing the start-up sweep's rules or when it runs.
- Sweeping the system database, the tenant's `meta` or `registry` graphs, or aggregate graphs.
- Garbage-collecting earlier versions of a blob or keeping a blob history.
- A scheduler or job runner inside the toolkit, unless the developer chooses it (Q-1).
- Any consumer term, model or code.

---

## What Changes

- `rdf_persistence/services/sweep.py` (or a sibling service): the live-tenant sweep.
- `rdf_persistence/services/files.py`: the `FileStore` port gains a way to list a bucket's keys;
  `adapters/s3.py`, the testkit fake and `testkit/file_store_conformance.py` follow.
- `docs/modules/ROOT/pages/architecture/index.adoc`: the building block moves from deferred to v1.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `rp-tenancy`: adds the live-tenant sweep (ADDED requirement; the start-up sweep is unchanged).

## Impact

- The `FileStore` port grows one method: every adapter and fake implementing it must follow.
- Possibly a new public name (`sweep_tenant` or similar), listed in the architecture's public API.
