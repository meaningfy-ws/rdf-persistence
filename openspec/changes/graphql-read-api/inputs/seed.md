<!-- SECONDARY INPUT: preserved, never groomed. The EPIC (../proposal.md) is the shaped truth. -->

# Seed: read-only GraphQL

## Seed text

From `docs/modules/ROOT/pages/questions.adoc`, "What could strengthen it in the future":

> *GraphQL*, read-only over the same schema and context (option C of
> xref:architecture/api.adoc[the API page]), …

From `docs/modules/ROOT/pages/architecture/api.adoc`, option C:

> A GraphQL schema built at run time from LinkML (Ariadne, schema-first); queries compiled to SPARQL
> `CONSTRUCT`; mutations replace an aggregate and carry a `version` argument. Field names follow the
> JSON-LD context, as GraphQL-LD does.

> *Option C is the backup* for a later implementation: when a client needs deep nested reads, a
> read-only GraphQL endpoint over the same schema and context.

Main risk named there: "no HTTP ETags or status codes; the SPARQL compiler and its N+1 queries are ours".

From `open-decisions.adoc`, D-1: "*C is the backup* for a later implementation." Architecture index:
the GraphQL building block traces to the first consumer's need N-9.

## Open questions for the developer

0. **Which need triggers it?** api.adoc says "when a client needs deep nested reads". Is there such
   a client now, and which queries does it need? The answer sizes the query planner.
1. **When is the GraphQL schema made?**
   - (a) At run time from the LinkML schema, as api.adoc option C says and as the router reads the
     schema: nothing new to generate or keep fresh.
   - (b) At generation time, by LinkML's stock `gen-graphql` (extended) into a `.graphql` file:
     reviewable SDL, guarded by the freshness check (PD-26); one more artefact.
   The two read D-13 differently; the developer decides which one honours it.
2. **Which library?** (a) Ariadne (schema-first, named in api.adoc); (b) Strawberry (code-first,
   type hints); (c) graphql-core directly. (a) fits a schema derived as SDL; (b) fits generated
   Python classes; (c) has the least on top.
3. **How do resolvers reach the store?**
   - (a) Each query compiled into one SPARQL `CONSTRUCT` per level, batched (a data loader).
   - (b) Read whole aggregates with the session and select fields in Python: simplest, reuses the
     frames; reads more than needed.
4. **Reference traversal.** May a query follow a reference into another aggregate, and how deep?
   A fixed maximum depth, a cost limit, or both?
5. **Mount point.** One endpoint per tenant (`/{tenant_segment}/{t}/graphql`) or one global endpoint
   taking the tenant as an argument? Per tenant matches the REST routes and the access check.
6. **Versions.** Expose each aggregate's version as a field, so a client can write through REST with
   `If-Match` after a GraphQL read?
7. **Introspection.** On for everyone, only for signed-in callers, or off in production?

## Developer answers (2026-11-06)

Developer: "i like both a and b, but we shall defer it for now, only remember preference".
- Deferred. If it comes back, the preference is: a schema generated from LinkML, read-only, with
  resolvers over SPARQL and the per-aggregate access check on every node; or a generic
  SPARQL-to-GraphQL layer with access filtered after it runs.
- No planning until the developer reopens it.

## Test scenarios the EPIC must prove

- A nested query returns the same data the REST routes return for the same aggregates.
- A query with filters and paging returns the same items, order and total as the REST listing.
- A prohibited or hidden aggregate is omitted and, by IRI, looks absent; a hidden tenant looks absent.
- A query over the depth or cost limit is refused before reaching the store.
- A mutation is refused.
- A filter value that tries SPARQL injection is bound, never concatenated.
- Adding a class to the schema adds its GraphQL type (and, if generated, the freshness check catches a stale SDL).
