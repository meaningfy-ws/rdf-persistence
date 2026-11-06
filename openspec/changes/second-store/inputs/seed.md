<!-- SECONDARY INPUT: preserved, never groomed. The EPIC (../proposal.md) is the shaped truth. -->

# Seed: a second store

## Seed text

From `docs/modules/ROOT/pages/questions.adoc`, "What could strengthen it in the future":

> *A second store* (Oxigraph, Virtuoso) with a capability descriptor, and schema migrations.

From `docs/modules/ROOT/pages/architecture/index.adoc`, building blocks:

> |Second store (Oxigraph, Virtuoso) and a capability descriptor
> |deferred
> |Needs an adapter mapping a database to a set of graphs; the descriptor arrives with it.

From the archived `toolkit-v1-foundation/proposal.md`, No-gos: "A second store (Oxigraph, Virtuoso),
the outbox, …".

## What the code does today (checked 2026-11-06)

- `rdf_persistence/services/store.py`: `Store` protocol (`query`, `update`, `put_graph`,
  `create_dataset`, `drop_dataset`, `list_datasets`) and `ToolkitStore`, which turns `BadQuery` into
  `SparqlError`.
- `rdf_persistence/adapters/fuseki.py`: dataset administration through `/$/datasets`.
- `rdf_persistence/testkit/store_conformance.py`: one set of cases run against the fake and Fuseki.
- Tenancy: database `{prefix}-t-{uuid hex}` per tenant, system database `{prefix}-system` (PD-6a).
- No capability descriptor exists.

## Open questions for the developer

0. **Which store, and why?** Oxigraph (Rust, MIT/Apache-2.0, small, embeddable, one dataset per
   server) or Virtuoso (mature, large, GPL-2.0 open source, one quad store per server, SPARQL
   dialect quirks)? A named reason (cost, an operator's existing deployment, performance) decides
   what the descriptor must cover.
1. **How does a tenant map onto a single-dataset store?**
   - (a) A graph prefix per tenant inside one dataset: one server; isolation by query discipline only.
   - (b) One server process per tenant: real isolation; operationally heavy.
   - (c) Refuse multi-tenancy on that store (one tenant per deployment): simplest; limits the store's use.
2. **What does the descriptor say?** Candidates: multiple datasets, atomic multi-operation update,
   Graph Store `PUT`, dataset administration, `ASK` reliability, maximum request size. Which are
   flags the services adapt to, and which are hard requirements?
3. **Where is the descriptor declared?** A static property of the adapter class, a LinkML record
   returned by the adapter, or probed at start-up?
4. **Embedded or server?** Oxigraph can run in process (pyoxigraph). Is an embedded store in scope
   (for example for tests or single-user tools), or only an HTTP server?
5. **Does `schema-migrations` wait for this EPIC?** If migrations must run on every supported store,
   doing this first avoids writing them twice.

## Test scenarios the EPIC must prove

- The `Store` conformance suite passes on the second store's container.
- The toy library's end-to-end test passes with the second store.
- Two tenants on the second store never see each other's aggregates, loaded graphs or registry.
- A guarded commit on the second store is atomic: a refused version check writes nothing.
- The start-up sweep finds and drops orphans on the second store without touching active tenants.
- A store lacking a required capability stops the service at start-up with a message naming it.
- Every query template still resists injection on the second store.
