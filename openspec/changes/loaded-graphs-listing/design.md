<!-- PLAN (design half). PLAN = this file + tasks.md. -->

> Derives from: EPIC `loaded-graphs-listing` (proposal.md), GitHub issue #70.

## Context

`Session` (`rdf_persistence/services/session.py`) keeps a registry graph per tenant. A commit
(`add_graph`, `replace_graph`) writes one entry per loaded graph: the graph IRI, `owned_by` the
aggregate, kind `loaded_graph`. `_registered_loaded(iri)` reads them with `READ_LOADED` and returns
them sorted. It returns `[]` when the aggregate does not exist. `_graph(iri)` raises `InvalidIri`
for an IRI the policy does not mint; `_stored(graph)` raises `NotFound` when the aggregate's graph
holds no version. `remove` deletes the aggregate's graph, its loaded graphs and its registry entries.
`FakeStore` raises `DatabaseGone` on any query of a dropped dataset.

## Goals / Non-Goals

**Goals:** a public, async `Session.loaded_graphs(iri)` (DEC-1 to DEC-4); the adopt guide and the
question page name it.
**Non-Goals:** see the EPIC's No-gos.

## Decisions

- **PD-1**: Signature and contract:

  ```python
  async def loaded_graphs(self, iri: str) -> list[URIRef]:
      """The IRIs of the graphs loaded for the aggregate ``iri``, sorted by IRI.

      The session checks no access; the caller gates the read like ``get_graph`` (PD-7).

      Raises:
          InvalidIri: ``iri`` is not an aggregate IRI the policy mints for the tenant.
          NotFound: The aggregate has no graph.
          DatabaseGone: The tenant database does not exist.
      """
  ```

- **PD-2**: The body reuses what exists: `await self._stored(self._graph(iri))`, then
  `return await self._registered_loaded(iri)`. No new SPARQL. `_registered_loaded` stays private
  and unchanged: `replace_graph` and `loaded_graph` call it without the aggregate check, which they
  do not need. Rejected: renaming `_registered_loaded` to the public name (it would add the
  existence query to `replace_graph` and `loaded_graph`, and change their errors).
- **PD-3**: The method sits right after `loaded_graph` in the class, so the two reads of loaded
  graphs are side by side.

## Algorithm / approach

```python
async def loaded_graphs(self, iri):
    await self._stored(self._graph(iri))   # InvalidIri, NotFound, DatabaseGone
    return await self._registered_loaded(iri)
```

Worked example: an aggregate committed with `loaded_graphs=[g1]`, then replaced with
`loaded_graphs=[g2]` → `[g2]`. Replaced with `loaded_graphs=None` → still `[g2]`.

### Anti-patterns

| Don't | Do instead | Why |
|---|---|---|
| A new SPARQL query string | reuse `READ_LOADED` via `_registered_loaded` | one registry read, one place |
| Check access in the session | the caller's `require_aggregate` | DEC-4, PD-7 |
| Promise load order in docs | "sorted by IRI" | DEC-1 |

## Error matrix

| Failure mode | How it is detected | Expected handling |
|---|---|---|
| IRI the policy does not mint | `_graph` | `InvalidIri`, no query sent |
| Aggregate never stored or removed | `_stored` finds no version | `NotFound` |
| Aggregate with no loaded graph | registry has no entry | `[]` |
| Graph loaded but never committed | not in the registry | not listed |
| Tenant database dropped | store query | `DatabaseGone` propagates |
| Aggregate removed between the two reads | registry entries already deleted | `[]` (RISK-1) |

## Risks / Trade-offs

- **RISK-1** (likelihood low, impact low): a concurrent `remove` between the existence check and the
  registry read returns `[]` instead of `NotFound`. Accepted: the caller's next read of the
  aggregate reports `NotFound`; no stale IRI is ever returned.
- **RISK-2** (likelihood low, impact low): a consumer relies on the order matching load order with
  several loaded graphs. Mitigated: the docstring, the spec and the adopt guide say "sorted by IRI".

## Open Questions

None.
