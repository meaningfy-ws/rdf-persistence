---
kind: rule
id: P-0041
type: preference
strength: default
status: active
scope:
  - activity:coding
  - activity:planning
when: code or a design needs an RDF term, a namespace, prefix bindings or an RDF utility (literals, language strings, IRIs, CURIE expansion, graph helpers)
do: use rdflib's terms layer and utilities (Literal, URIRef, Namespace, NamespaceManager bindings, rdflib.util and the like) instead of a toolkit-made equivalent
instead_of: hand-rolled term types, prefix dicts, CURIE splitting or string IRI concatenation
because: rdflib's RDF terms layer is solid and already a domain-allowed dependency; a second implementation costs and drifts (P-0008 applied to rdflib)
source: 2026-11-28 'can we use Literal from rdfterm? I believe that Literal can be broadly adopted, no?' 'the same applies to namespaces, rdf lib Namespace already has good functions/implementations, and namespace bindings' 'their RDF Terms layer is solid in general' 'and utility functions'
added: 2026-11-28
approved: 2026-11-28
last_confirmed: 2026-11-28
private: false
---
