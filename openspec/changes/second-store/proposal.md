<!-- Parents: openspec/specs/rp-aggregate-store; openspec/specs/rp-testkit ("Adapters are tested
     against real containers"); architecture v1, docs/modules/ROOT/pages/architecture/index.adoc
     (building blocks: "Second store (Oxigraph, Virtuoso) and a capability descriptor", deferred).
     Seeds: inputs/seed.md. -->

# EPIC: A second store product behind the Store port

> Shaped 2026-11-06 from the v1 future list; reshaped 2026-11-12 (open questions answered by the
> leader, inputs/seed.md "Leader's recommendations"; the developer may overrule any DEC marked
> "leader's choice"). Fourth of the four tenancy candidates. Not planned: the PLAN is derived at the
> start of its epic session; its first task is the spike of DEC-5.

**Golden-thread parent:** capabilities `rp-aggregate-store` and `rp-testkit`, and the deferred
building block "Second store and a capability descriptor" of
`docs/modules/ROOT/pages/architecture/index.adoc`. This EPIC is about **which product** a store is;
**where** a tenant lives (several wired stores) is `tenant-stores`.

## Appetite

**MEDIUM** (was LARGE). One capability: a second adapter, a capability descriptor checked at
start-up, its test container, and the conformance suite and toy end-to-end test run on it. Tenancy,
the sweep and the IRIs do not change: the chosen product keeps "a database per tenant" (DEC-6).

## Why

The `Store` port (`rdf_persistence/services/store.py`) assumes SPARQL 1.1, a Graph Store `PUT`,
dataset administration (`create_dataset`, `drop_dataset`, `list_datasets`) and, silently, that one
update request with several operations applies all or nothing (the guarded commit relies on it;
`cross-aggregate-unique-keys` and `atomic-commit` #83 will rely on it more). Its only adapter is
Fuseki. A consumer whose operator runs another product cannot use the toolkit, and nothing states
what a store must offer.

## Solution outline

A consumer wires the GraphDB adapter in its composition root instead of Fuseki (or, with
`tenant-stores`, beside it) and gets the same behaviour, proven by the same conformance suite and
end-to-end test. Every adapter declares a capability descriptor; at start-up the service checks each
wired store's descriptor against what the toolkit requires and refuses to start, naming the missing
capability, rather than weaken tenant isolation or atomic guarded commits.

```python
store = GraphDbStore(url, user, password)        # repositories play the role of databases
store.capabilities                               # StoreCapabilities(datasets=True, atomic_update_request=True, ...)
install_service(app, ..., store=store)           # refuses to start if a required capability is False
```

## Key decisions

- **DEC-1**: The port stays in `services`, adapters in `adapters`, independent of `entrypoints`
  (PD-1). Services build all SPARQL through `domain/sparql.py`; adapters forward and build none (PD-3).
- **DEC-2**: Adapters are tested against their real container; the testkit's `Store` conformance
  suite is the contract, and a divergence from the fake is a bug in the fake (archived DEC-4; PD-16).
- **DEC-3**: The capability descriptor is a LinkML class (`StoreCapabilities`), generated and read
  through its model (D-13; PD-24; AGENTS.md).
- **DEC-4**: Fuseki stays supported and stays the default in the toy library's tests.
- **DEC-5** (Q-0; leader's choice, 2026-11-12, **confirmed by the developer 2026-11-13**: "second
  store yes"): of the developer's three candidates, **GraphDB first**, GraphDB Free accepted although
  it is not open source. Its repositories map one to one onto the toolkit's databases
  (created and deleted over its REST API), it implements SPARQL 1.1 Update and the Graph Store
  protocol (RDF4J), and runs as a server in a container. Oxigraph and Tentris serve one dataset per
  server, so they would need a graph-prefix tenancy (DEC-6, rejected) or a process per tenant. The
  PLAN's first task is a spike on the container proving: repository create, list and drop; a Graph
  Store `PUT`; that one update request with several operations is atomic; dataset N-Quads export and
  import (`tenant-dump-restore`); and that the free edition's licence allows CI use. If any fails,
  the epic stops and returns to the developer with Oxigraph (one tenant per server) as the
  alternative. Rejected: Oxigraph first (MIT/Apache and light, but no datasets); Tentris first (no
  dataset administration; SPARQL Update support to confirm).
- **DEC-6** (Q-1; leader's choice): **no mapping of tenants onto a single-dataset store**. A store
  must offer datasets; one that does not is refused at start-up (DEC-7). Rejected: (a) a graph prefix
  per tenant (isolation by query discipline only; tenancy, sweep and IRIs would all change), (b) a
  server process per tenant (operations, not a library concern), (c) one tenant per deployment (a
  special mode of every service).
- **DEC-7** (Q-2; leader's choice): the descriptor states four capabilities, all **required** in this
  EPIC: `datasets` (create, drop, list), `atomic_update_request` (one update request with several
  operations applies all or none: the guarded commit, `cross-aggregate-unique-keys` and
  `atomic-commit` #83 rely on it), `graph_store_put`, `dataset_quads` (whole-database N-Quads export
  and import, from `tenant-dump-restore`). The services never adapt; they refuse. Rejected: optional
  flags with fallback code paths (two behaviours to test, no store needing them yet).
- **DEC-8** (Q-3; leader's choice): declared statically by the adapter (a `capabilities` attribute
  returning the generated model), never probed at start-up; the conformance suite proves every
  capability an adapter claims, including atomicity (an update whose second operation fails leaves
  the first undone). Rejected: probing (writes to a live store at every start).
- **DEC-9** (Q-4; leader's choice): **server only**; no embedded store. Reason: the toolkit's
  stores are shared by services; an embedded store is a test convenience the fake already gives.
- **DEC-10** (Q-5; leader's choice): `schema-migrations` **does not wait** for this EPIC: migrations
  go through the `Store` port, so they run on any store that passes the conformance suite. Order:
  after `cross-aggregate-unique-keys` and `atomic-commit` (#83), so the atomicity they rely on is
  the one the descriptor states and the suite proves.
- **DEC-11**: With `tenant-stores`, each named store carries its own descriptor, and the start-up
  check runs per store.

## Rabbit-holes

- **Dialect and term differences.** GraphDB may normalise literals (dates, numbers) or answer `ASK`
  and blank nodes differently; each divergence is a conformance case, fixed in the adapter, never in
  the services.
- **Repository configuration.** Creating a repository needs a configuration document; keep one
  fixed configuration in the adapter (no per-tenant tuning).
- **Licence.** GraphDB Free is free of charge but not open source; the adapter talks HTTP only and
  adds no dependency. The spike confirms CI use is allowed.

## No-gos

- More than one second product in this EPIC (Oxigraph, Tentris later, each its own change).
- Graph-prefix tenancy, a process per tenant, or a one-tenant mode.
- Optional capabilities with fallback behaviour.
- Moving data between stores (`tenant-dump-restore` copies; `tenant-stores` places).
- Store-specific features (full-text, reasoning) through the port.
- Removing or changing the Fuseki adapter's behaviour.
- An embedded store.
- Any consumer term, model or code.

---

## What Changes

- `rdf_persistence/adapters/graphdb.py` (new): the `Store` adapter.
- `rdf_persistence/model/`: `StoreCapabilities`; regenerated code.
- `rdf_persistence/services/store.py`: `capabilities` on the port; the start-up check; the Fuseki
  adapter and the fake declare theirs.
- `rdf_persistence/testkit/store_conformance.py`: the atomicity case and one case per capability.
- `rdf_persistence/testkit/containers/`: the GraphDB container and fixture.
- `docs/modules/ROOT/pages/architecture/`: the building block moves from deferred to v1; the
  comparison of the three candidates.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `rp-aggregate-store`: the second adapter and the capability descriptor (ADDED requirements).

## Impact

- CI gains a container job for GraphDB.
- The `Store` port gains `capabilities`: a consumer's own `Store` must declare it (**BREAKING** for
  such an implementation only).
