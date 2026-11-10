# GitHub issue #70: List the graphs loaded for an aggregate (loaded_graph needs an IRI nothing public returns later)

## Summary

List the graphs loaded for an aggregate through a session. `Session.loaded_graph(iri, graph_iri)` (#56) reads a loaded graph back, but only when the caller already holds `graph_iri`; nothing public tells a later request which graphs an aggregate has loaded.

## Context

Consumer: MWB2, change `v1-06-project-resources`, tasks 2.4 (browse an uploaded ontology's terms) and 3.7. rdf-persistence locked at develop `0344b23`.

## What is missing

`load_graph` returns the new graph's IRI, and the session records it in its registry, but the registry read (`Session._registered_loaded`) is private. Under a flat, opaque IRI policy the graph IRI cannot be derived. A later request (a different session) that wants to read an aggregate's loaded graph has no public way to find its IRI. The only alternatives are storing the IRI again in the consumer's model (duplicating the registry) or querying the registry with SPARQL; both do the toolkit's job.

## Expected behaviour / proposed capability

```python
class Session:
    def loaded_graphs(self, iri: str) -> list[str]:
        """The IRIs of the graphs loaded for the aggregate ``iri``, in load order.

        Raises InvalidIri, NotFound (no such aggregate), DatabaseGone.
        """
```

Intended use:

```python
async with store.session(tenant) as session:
    (graph_iri,) = session.loaded_graphs(document_iri)
    graph = session.loaded_graph(document_iri, graph_iri)
```

Access is the caller's, as for `loaded_graph` (PD-7).

## Why it belongs in rdf-persistence

The registry of loaded graphs is the toolkit's; any application that loads RDF for an aggregate and reads it in a later request needs to find it again.

## Acceptance

- Given an aggregate with one loaded graph, when a new session asks for its loaded graphs, then it gets that graph's IRI.
- Given the aggregate's graph was replaced, when asked, then only the new graph's IRI is listed.
- Given an aggregate with no loaded graph, when asked, then the list is empty.
- Given the aggregate was removed, when asked, then `NotFound`.

## Impact on the consumer

Blocks MWB2's ontology browse (route and screen). MWB2's container test for "replace leaves exactly one graph" counts graphs with a SPARQL query through `Store.query` today; it switches to this read once available.

