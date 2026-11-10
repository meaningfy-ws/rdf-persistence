<!-- Parents: openspec/specs/rp-tenancy; openspec/changes/second-store (another store product);
     the developer's need in inputs/seed.md. -->

# EPIC: A tenant's database on another triple store

> Candidate EPIC, shaped 2026-11-10. Not planned: the PLAN waits for the developer's answers to the
> open questions below.

**Golden-thread parent:** capability `rp-tenancy`; related candidate `second-store` (another store
product behind the `Store` port). This EPIC is about *where* a tenant's database lives, not which
product it is.

## Appetite

**LARGE.** Tenancy, the kit's wiring, the start-up sweep and the access record all move from "one
store" to "a store per tenant".

## Why

The kit is wired to one triple store, so every tenant database lives on it. An application that
governs projects kept on other servers (or other products) cannot manage them as tenants.

## Solution outline

The access record names the store a tenant's database lives on, and the kit opens sessions,
creates, sweeps and deletes on that store, from a set of stores the consumer wires in.

## Key decisions

None yet.

## Open questions

- Q-1: Who chooses the store of a new tenant: the creator, a rule, or the consumer's code?
- Q-2: Can a tenant move between stores (with `tenant-dump-restore`)?
- Q-3: Do files follow the same choice (a bucket on another object store)?
- Q-4: Order with `second-store`: one EPIC first, or merged?

## Rabbit-holes

- The start-up sweep must list every wired store and must never drop a database on a store it was
  not wired to.

## No-gos

- A query across tenants on different stores.

---

## What Changes

- The access record gains the tenant's store; tenancy and the kit route each tenant to its store.

## Capabilities

### Modified Capabilities

- `rp-tenancy`: a tenant on another store (ADDED requirement).

## Impact

- The access record's schema changes; the kit takes several stores.
