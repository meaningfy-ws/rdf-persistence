<!-- Parents: issue #73; openspec/specs/rp-aggregate-store ("RDF files load into a graph of their
     own", "A loaded graph can be read back", "An aggregate's loaded graphs can be listed");
     openspec/specs/rp-tenancy ("Orphans inside a live tenant are removed"). Seeds: inputs/seed.md. -->

> Type: Strategic.

# EPIC: Register the tenant root's loaded graphs

> Shaped 2026-11-10 from issue #73 with the developer (inputs/seed.md).

**Golden-thread parent:** issue #73, and the requirements of `rp-aggregate-store` on loaded graphs,
which hold for every aggregate but fail for the tenant root.

## Appetite

**TINY.** One concern in one place: the session's registry entries for the tenant root, and the
sweep's special case that exists only because of it.

## Why

An RDF file loaded for the tenant root (`load_graph(T, …)`) and committed with the root is never
registered. It cannot be read back or listed, a replace of the root never drops it, and the
live-tenant sweep has to skip every root load because each one looks like an orphan. The tenant
root is meant to behave like an aggregate; for loaded graphs it does not.

## Solution outline

A loaded graph committed with the tenant root is registered like one committed with any aggregate:
`loaded_graph(T, g)` reads it, `loaded_graphs(T)` lists it, and a replace of the root that drops
it from `loaded_graphs` empties it. The live-tenant sweep then needs no exception for the root:
root loads made before the fix are unregistered, so it reports them, and removes them only when
asked.

## Key decisions

- **DEC-1**: Support root loads by registering them — the developer: an RDF file is just another
  file, kept in a named graph of its own; rejected: refusing `load_graph` and `loaded_graphs`
  for the tenant root (InvalidIri).
- **DEC-2**: Only `LoadedGraph` entries for the root, no `Aggregate` entry for `T/meta` — listings
  read `Aggregate` entries, and the tenant root is not an item of any listing; rejected: an
  `Aggregate` entry for `meta`.
- **DEC-3**: The live-tenant sweep drops its skip of root loads — the developer (Q-2); a root load
  made before the fix is unreachable, so it is an orphan like any other; rejected: keeping the skip.
- **DEC-4**: No migration of root loads made before the fix — no consumer makes them (mapping-
  workbench-v2 loads only for file aggregates); the sweep reports any that exist.

## Rabbit-holes

- **The root's other writes.** The tenant root is written by create tenant, the generic `PUT`,
  rename and a consumer's `UnitOfWork`. Each passes `loaded_graphs` as `None` (keep what is
  registered); once entries exist, each must keep them, not drop them.
- **Policies whose loaded-graph template has no `{root}`.** The sweep and the commit check must not
  start treating another aggregate's loaded graph as the root's.

## No-gos

- No `Aggregate` registry entry for `meta`; the tenant root does not appear in listings.
- No change to how `meta`, the registry or aggregate graphs are named.
- No export, restore, other stores or app-level data: those are the candidate EPICs
  `tenant-dump-restore`, `tenant-stores` and `app-level-data`.
- No loading of an aggregate itself from an RDF file.

---

## What Changes

- `rdf_persistence/services/session.py`: the tenant root's loaded graphs get registry entries.
- `rdf_persistence/services/tenant_sweep.py`: the skip of root loads goes.
- `docs/modules/ROOT/pages/architecture/data-flows.adoc` and `howto/adopt.adoc`: the root's loaded
  graphs and the sweep, as they now behave.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `rp-aggregate-store`: the tenant root's loaded graphs are registered (ADDED requirement).
- `rp-tenancy`: the live-tenant sweep no longer skips root loads (MODIFIED requirement).

## Impact

- Behaviour change for `load_graph(T, …)` callers: their graphs become readable and listed. None
  are known.
