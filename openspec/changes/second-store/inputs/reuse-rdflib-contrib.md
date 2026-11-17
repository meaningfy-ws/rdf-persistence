<!-- SECONDARY INPUT: preserved, never groomed. From manual-revision-notes, improvement B-6 (2026-11-17). -->

# Evaluate rdflib's GraphDB and RDF4J clients before writing a raw-HTTP adapter

Source: `../../manual-revision-notes/inputs/improvements.md` B-6 and `analysis.md` §2.1, accepted
by the developer on 2026-11-17 (rule P-0008: reuse a mature library before building).

rdflib (already a dependency) ships `rdflib.contrib.graphdb` and `rdflib.contrib.rdf4j` clients.
They cover repository administration, the Graph Store Protocol, `transaction()` and ACLs. They are
synchronous, so an adapter would run them in a worker thread, as `s3.py` does with boto3.

When this change's PLAN is derived, its first spike (DEC-5) also answers: can these clients back
the `Store` port's eight methods, including the guarded single-request commit? If yes, the
adapter wraps them; if not, the PLAN records which method they cannot serve and why.

The generic SPARQL 1.1 Protocol half of `FusekiStore` is split out by `thematic-structure` (E-5);
whichever comes first owns the split.
