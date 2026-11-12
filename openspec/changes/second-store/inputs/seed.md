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

## Developer answers (2026-11-06)

Developer: "as a second stores, I was thinking of TentrisDB, Oxygraph, GraphDB".
- Answers Q-0 with three candidates: Tentris, Oxigraph and GraphDB. The EPIC compares them (licence,
  datasets per tenant, atomic multi-operation update, SPARQL 1.1 Update and Graph Store support,
  embedded or server) before picking an order.
- The capability descriptor is what makes several stores possible.
- Still open: Q-1 to Q-5, and the comparison itself.

Developer: "accept recommendations, and continue" (2026-11-06).
- Every question still open: the leader drafts a recommendation when the PLAN is derived, and the developer accepted recommendations by default (2026-11-06). Each one is recorded in the PLAN as the leader's choice, and the developer may overrule it.

## Test scenarios the EPIC must prove

- The `Store` conformance suite passes on the second store's container.
- The toy library's end-to-end test passes with the second store.
- Two tenants on the second store never see each other's aggregates, loaded graphs or registry.
- A guarded commit on the second store is atomic: a refused version check writes nothing.
- The start-up sweep finds and drops orphans on the second store without touching active tenants.
- A store lacking a required capability stops the service at start-up with a message naming it.
- Every query template still resists injection on the second store.

## Leader's recommendations (2026-11-12)

The developer accepted recommendations by default (2026-11-06); the leader answered each open
question while reshaping the four tenancy candidates. Each answer is a DEC in `../proposal.md`
marked "leader's choice"; the developer may overrule any of them.

- Q-0 (which store) -> GraphDB first (DEC-5): repositories map onto the toolkit's databases, so
  tenancy, the sweep and IRIs stay as they are. Oxigraph and Tentris serve one dataset per server.
  A spike on the container confirms repository admin, Graph Store `PUT`, atomic multi-operation
  updates, dataset N-Quads, and the free edition's licence for CI; if it fails, back to the
  developer with Oxigraph (one tenant per server).
- Q-1 (tenants on a single-dataset store) -> not supported; such a store is refused (DEC-6).
- Q-2 (what the descriptor says) -> `datasets`, `atomic_update_request`, `graph_store_put`,
  `dataset_quads`; all required, no fallbacks (DEC-7). `atomic_update_request` is what guarded
  commits, `cross-aggregate-unique-keys` and `atomic-commit` (#83) rely on.
- Q-3 (where declared) -> statically by the adapter, a generated model; the conformance suite
  proves every claim (DEC-8).
- Q-4 (embedded) -> server only (DEC-9).
- Q-5 (`schema-migrations` waits?) -> no; migrations use the port (DEC-10).
- Boundary with `tenant-stores`: this EPIC is the product; `tenant-stores` is several wired stores.
  Each named store carries a descriptor (DEC-11). Appetite cut from LARGE to MEDIUM by DEC-6.

Order: fourth of the four, and after `cross-aggregate-unique-keys` and `atomic-commit` (#83).

## Test scenarios the EPIC must prove (amended 2026-11-12)

The list above stands, with "the second store" read as GraphDB, plus:

- The spike's five facts, each recorded with its evidence before any adapter code.
- An update request whose second operation fails leaves the first undone, on GraphDB and on Fuseki
  (the atomicity case added to the conformance suite).
- A store declaring any of the four capabilities false stops the start-up, naming store and
  capability.
- A tenant dumped on Fuseki restores on GraphDB (with `tenant-stores`: wired side by side).
