<!-- Parents: GitHub issue #70; openspec/specs/rp-aggregate-store/spec.md ("A loaded graph can be
     read back"). Consumer need: MWB2 v1-06-project-resources tasks 2.4, 3.7. Seeds: inputs/. -->

# EPIC: List the graphs loaded for an aggregate

**Golden-thread parent:** GitHub issue #70 and the `rp-aggregate-store` capability, whose
`loaded_graph(iri, graph_iri)` read needs a graph IRI that nothing public returns later.

## Appetite

**TINY.** One concern in one place: make the session's existing registry read public, with the
aggregate check in front of it, its tests and its docs.

## Why

`load_graph` returns the new graph's IRI and a commit registers it, but only the session's private
`_registered_loaded` can read the registry back. Under a flat, opaque IRI policy the graph IRI
cannot be derived, so a later request has no public way to read an aggregate's loaded graph. A
consumer would have to store the IRI again in its own model (a second registry) or query the
registry with SPARQL (the toolkit's job). MWB2's ontology browse is blocked on it.

## Solution outline

`Session.loaded_graphs(iri)` returns the IRIs of the graphs registered as loaded for the aggregate
`iri`, sorted by IRI. It refuses an IRI the policy does not mint (`InvalidIri`) and an aggregate
that does not exist (`NotFound`). Like `loaded_graph`, it checks no access.

```python
async with kit.session(tenant, principal) as session:
    (graph_iri,) = await session.loaded_graphs(document_iri)
    graph = await session.loaded_graph(document_iri, graph_iri)
```

## Key decisions

- **DEC-1**: The list is sorted by IRI, not in load order; the registry records no order and keeps
  none. Source: developer, 2026-11-10 (`inputs/seed.md` Q1). Rejected: recording a load order in the
  registry (schema change for an order no consumer needs: after a replace there is one graph).
- **DEC-2**: `loaded_graphs` is `async` and returns `list[URIRef]`, the type `load_graph` returns and
  `replace_graph(loaded_graphs=...)` takes, so the result passes straight back into a commit; a
  `URIRef` is a `str`, so it also passes to `loaded_graph`. Source: leader. Rejected: the issue's
  sync `def ... -> list[str]` (every store read is async).
- **DEC-3**: A missing aggregate raises `NotFound`, an aggregate without loaded graphs returns `[]`.
  Source: issue #70 acceptance.
- **DEC-4**: The session checks no access; the caller gates the read like `loaded_graph` (PD-7 of
  the foundation). Source: issue #70.

## Rabbit-holes

- Making the aggregate check and the registry read one atomic query. Two reads in one session are
  enough: a concurrent `remove` empties the registry, so the race yields `[]`, never a stale IRI.
- An HTTP route for it. Consumers write their own routes with the kit.

## No-gos

- No change to the registry, the LinkML schemas or any write path.
- No change to `loaded_graph`, `load_graph` or `replace_graph`.
- No access check inside the session.

---

## What Changes

- `rdf_persistence/services/session.py`: add `Session.loaded_graphs`.
- `docs/modules/ROOT/pages/howto/adopt.adoc` and `docs/modules/ROOT/pages/questions.adoc`: name it
  where `loaded_graph` is described.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `rp-aggregate-store`: adds the requirement that an aggregate's loaded graphs can be listed.

## Impact

- Public `Session` API grows by one method; nothing removed or changed.
- Unblocks MWB2 `v1-06-project-resources` tasks 2.4 and 3.7.
