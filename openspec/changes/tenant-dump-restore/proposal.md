<!-- Parents: openspec/specs/rp-tenancy; the developer's need in inputs/seed.md. -->

# EPIC: Dump a tenant and restore it into a new one

> Candidate EPIC, shaped 2026-11-10. Not planned: the PLAN waits for the developer's answers to the
> open questions below.

**Golden-thread parent:** capability `rp-tenancy` (each tenant is one database and one bucket).

## Appetite

**MEDIUM.** One new capability (export and restore of a tenant) with its tests and docs; tenancy
and the file store touched lightly.

## Why

A project cannot be backed up, copied or moved as a whole. Its state is spread over the tenant's
named graphs (aggregates, `meta`, `registry`, loaded graphs), its bucket and its access record, and
nothing writes them out or reads them back.

## Solution outline

Export a tenant as N-Quads (every named graph of its database) plus its blobs, and restore such a
dump into a new tenant, so the new tenant answers as the old one did, under its own IRIs.

## Key decisions

None yet.

## Open questions

- Q-1: Restore into a new tenant only, or also over an existing one?
- Q-2: Rewrite the IRIs to the new tenant's (they all start with the tenant IRI), or keep them?
- Q-3: Are grants part of the dump, or does the restorer become the only owner?
- Q-4: One archive file (N-Quads + blobs), or two streams?
- Q-5: Over HTTP, from Python, or both?

## Rabbit-holes

- Rewriting IRIs inside literals and loaded graphs.
- Large tenants: streaming, not one string in memory.

## No-gos

- Incremental or continuous backup; point-in-time recovery.

---

## What Changes

- A kit operation to export a tenant and one to restore a dump into a new tenant.

## Capabilities

### Modified Capabilities

- `rp-tenancy`: export and restore (ADDED requirement).

## Impact

- New public operations; the dump format becomes a contract.
