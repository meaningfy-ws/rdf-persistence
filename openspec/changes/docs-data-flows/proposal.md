<!-- Parents: docs/modules/ROOT/pages/architecture/index.adoc (Building blocks);
     docs/modules/ROOT/pages/architecture/api.adoc (Anatomy of a request). Seeds: inputs/seed.md. -->

# EPIC: Document where data lives and what each operation does

> Shaped and delivered 2026-11-10 at the developer's request (inputs/seed.md). Docs only.

**Golden-thread parent:** the building-blocks table of `architecture/index.adoc` and the anatomy of
one `PUT` in `architecture/api.adoc`, which describe the flows only in part.

## Appetite

**TINY.** One new architecture page, its nav entry and one question. No code changes.

## Why

The storage layout and the per-operation flows are scattered over the building-blocks table, the
anatomy of one replace and the how-to. A reader cannot see in one place where tenants, aggregates,
the registry and files are kept, what each create, read, list, replace or delete writes, or which
rules refuse what.

## Solution outline

`architecture/data-flows.adoc`: the storage map on the toy library's IRIs; the gate; aggregate,
file, loaded-graph and tenant operations from the route or Python call down to the SPARQL; one
table of every rule and check; the sweeps. It links to what is already written instead of
repeating it.

## Key decisions

- **DEC-1**: The page describes; it is not normative. The truth stays in `openspec/specs/`.
- **DEC-2**: Steps already documented (the anatomy of a `PUT`, the access check, the IRI policy
  how-to) are linked, not repeated.

## No-gos

- No code, model or spec change.

## Evidence

`evidence/docs-owed.md` (inventory, accepted by the developer 2026-11-10) and
`evidence/cold-read.md`.
