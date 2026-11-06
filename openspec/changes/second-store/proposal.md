<!-- Parents: openspec/specs/rp-aggregate-store; openspec/specs/rp-testkit ("Adapters are tested
     against real containers"); architecture v1, docs/modules/ROOT/pages/architecture/index.adoc
     (building blocks: "Second store (Oxigraph, Virtuoso) and a capability descriptor", deferred).
     Seeds: inputs/seed.md. -->

# EPIC: A second store behind the Store port

> Candidate EPIC, shaped 2026-11-06 from the v1 future list. Not planned: the PLAN (design.md, tasks.md) waits for the developer's answers in inputs/seed.md.

**Golden-thread parent:** capabilities `rp-aggregate-store` and `rp-testkit`, and the deferred
building block "Second store (Oxigraph, Virtuoso) and a capability descriptor" of
`docs/modules/ROOT/pages/architecture/index.adoc`.

## Appetite

**LARGE.** Several related capabilities: a new adapter, a capability descriptor the services read, a
mapping from the toolkit's "database" to what the second store offers, a new test container, and the
conformance suite run against it. Tenancy and the sweep move from "a database per tenant" to
whatever the descriptor allows.

## Why

The `Store` port (`rdf_persistence/services/store.py`) assumes SPARQL 1.1, a Graph Store `PUT`, and
dataset administration (`create_dataset`, `drop_dataset`, `list_datasets`). Its only adapter,
`adapters/fuseki.py`, implements the last three through Fuseki's admin API (`/$/datasets`). Tenancy
gives each tenant its own database (PD-6a), and the start-up sweep lists databases by prefix
(`services/sweep.py`). A store with one dataset per server (Oxigraph, Virtuoso) cannot back v1 as
it is; the architecture notes it "needs an adapter mapping a database to a set of graphs; the
descriptor arrives with it".

## Solution outline

A consumer can wire a second store in its composition root instead of Fuseki and get the same
behaviour: aggregates, versioned writes, loaded graphs, tenancy, the sweep and the API, proven by the
same conformance cases and end-to-end test. Where the second store lacks something Fuseki has, a
capability descriptor says so, and the services either adapt or refuse to start with a clear
message, never silently weaken a guarantee such as tenant isolation or atomic guarded commits.

## Key decisions

- **DEC-1**: The port stays in `services` and adapters stay in `adapters`, independent of
  `entrypoints` (PD-1). Services keep building all SPARQL through `domain/sparql.py`; adapters
  forward SPARQL and build none (PD-3).
- **DEC-2**: Adapters are tested against their real container; the testkit's `Store` conformance
  suite (`testkit/store_conformance.py`) is the contract, and a divergence from the fake is a bug in
  the fake (archived DEC-4; PD-16; `rp-testkit`).
- **DEC-3**: The capability descriptor, if it is a record, is a LinkML class, generated; it is read
  through the generated model (D-13; PD-24; AGENTS.md).
- **DEC-4**: Fuseki stays supported and stays the default in the toy library's tests.

## Rabbit-holes

- **Atomic multi-operation updates.** The guarded commit sends several operations joined by `;` in
  one request and relies on them applying together. Each candidate store must be checked.
- **Tenant isolation without databases.** Graph-prefix isolation is weaker: a bug in one query
  could read another tenant's graphs.
- **Dialect differences.** Virtuoso's SPARQL differs from the standard in places; literal and
  blank-node handling differ between stores.
- **Licences.** Virtuoso Open-Source is GPL-2.0; the adapter talks to it over HTTP only.

## No-gos

- More than one second store in this EPIC.
- Running two stores at once, or moving data between stores.
- Store-specific features (full-text, reasoning) exposed through the port.
- Removing or changing the Fuseki adapter's behaviour.
- Any consumer term, model or code.

---

## What Changes

- `rdf_persistence/adapters/`: a new store adapter.
- `rdf_persistence/services/store.py`: the capability descriptor, read by tenancy and the sweep.
- `rdf_persistence/services/tenancy.py`, `services/sweep.py`, `domain/iris.py`: the mapping from a
  tenant to a database or a set of graphs, as the descriptor allows.
- `rdf_persistence/testkit/containers/`: the second store's container and fixture.
- `docs/modules/ROOT/pages/architecture/`: the building block moves from deferred to v1.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `rp-aggregate-store`: adds the second adapter and the capability descriptor (ADDED requirements).

## Impact

- CI gains a container job for the second store.
- A new optional dependency or extra for the adapter, pinned as the others (PD-2).
