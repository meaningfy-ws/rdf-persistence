<!-- Parents: openspec/specs/rp-service-api; docs/modules/ROOT/pages/architecture/api.adoc (option C,
     "the backup for a later implementation"); D-1 in
     docs/modules/ROOT/pages/architecture/open-decisions.adoc. Seeds: inputs/seed.md. -->

# EPIC: A read-only GraphQL API

> Candidate EPIC, shaped 2026-11-06 from the v1 future list. Not planned: the PLAN (design.md, tasks.md) waits for the developer's answers in inputs/seed.md.
>
> **Backlog position (2026-11-12):** deferred by the developer (2026-11-06); unchanged. See `openspec/changes/README.md`.

**Golden-thread parent:** capability `rp-service-api` and option C of
`docs/modules/ROOT/pages/architecture/api.adoc` (decision D-1: "C is the backup for a later
implementation").

## Appetite

**LARGE.** Several related capabilities: a GraphQL schema derived from the LinkML schema, resolvers
compiled to SPARQL, the access check per resolver, and its tests. A new dependency and a new route
join the service kit.

## Why

v1 serves aggregates through one generic REST router (`entrypoints/router.py`): one aggregate per
`GET`, listings with equality filters and paging (`services/listing.py`, PD-15a), owned parts nested
by one frame per type (PD-12). A client that needs an aggregate with the aggregates it references,
or a few fields of many, makes one call per aggregate. The API page keeps option C, GraphQL over the
same schema and context, as the backup "when a client needs deep nested reads".

## Solution outline

A client sends a GraphQL query for one tenant and gets the aggregates it asks for, with their owned
parts and the aggregates they reference, in one response, filtered and paged with the same rules
as the REST listings. Field names follow the JSON-LD context, so a GraphQL result reads like the
plain JSON the router serves. Every object in a response has passed the same access check the REST
routes apply. Nothing is written through GraphQL.

## Key decisions

- **DEC-1**: Read-only: queries only, no mutations. Source: the seed ("read-only GraphQL over the
  same schema and context"); writes stay on the REST router with `ETag`/`If-Match` (D-1).
- **DEC-2**: The GraphQL schema is derived from the LinkML schema and field names follow the JSON-LD
  context; no GraphQL type is written by hand. Source: api.adoc option C; D-13; PD-24.
- **DEC-3**: Access is the in-process ODRL check per tenant and per aggregate (D-4, `rp-access`); a
  hidden tenant and an absent one look alike (PD-13a).
- **DEC-4**: SPARQL is built only through `domain/sparql.py` (PD-3); one injection test per query
  template (archived proposal, rabbit-holes).
- **DEC-5**: REST stays the primary API (D-1: A and B together); GraphQL is added beside it.

## Rabbit-holes

- **N+1 queries.** Nested references resolved one by one; batching is needed (api.adoc names it).
- **Unbounded queries.** Depth and cost limits are needed, or one query reads a whole tenant.
- **Errors without HTTP status.** GraphQL answers 200 with errors; a hidden aggregate must not be
  told apart from an absent one there either.
- **Caching.** No `ETag` per response; versions can be exposed as fields.

## No-gos

- Mutations and subscriptions.
- Queries across tenants.
- A general SPARQL or query language beyond the REST listing's filters.
- GraphQL-LD or a JSON-LD wire format for GraphQL responses.
- Property-level filtering (see `fine-grained-access`).
- Any consumer term, model or code.

---

## What Changes

- `rdf_persistence/entrypoints/`: a GraphQL route mounted by `install_service`.
- `rdf_persistence/services/`: query planning to SPARQL `CONSTRUCT`, reusing the listing's plans.
- `rdf_persistence/generation/`: a GraphQL schema target, if Q-1 chooses generation time.
- `docs/modules/ROOT/pages/architecture/api.adoc`: option C moves from backup to implemented.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `rp-service-api`: adds a read-only GraphQL endpoint (ADDED requirements).

## Impact

- A new runtime dependency (a GraphQL server library), pinned as the others (PD-2).
- The OpenAPI document gains or links the GraphQL route.
