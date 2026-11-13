# Spike 1.1: Fuseki dataset-level N-Quads GET and POST

Change `tenant-dump-restore`, task 1.1, PD-1 and RISK-1. Run 2026-11-13 on the project's Fuseki test
container (image `rdf-persistence-test/fuseki:5.6.0`, TDB2 dataset), with a throwaway test in `temp/`
(not committed).

## Question

Which Fuseki endpoint (a) answers a dataset-level `GET` with `Accept: application/n-quads`
returning every named graph, and (b) accepts a dataset-level `POST` of N-Quads
(`Content-Type: application/n-quads`) that adds quads into named graphs?

## Answer

Yes. Both `/{ds}/data` and `/{ds}` do both jobs, with identical bodies. Use **`/{ds}/data`**: it is the
Graph Store endpoint the adapter already uses for `put_graph` (`DATA_ENDPOINT`), so no new constant.
`/{ds}/get` answers `GET` the same way but refuses `POST` (405 `Read-only`), so it is not a candidate
for the import.

| Request | Status | Content type | Body |
|---|---|---|---|
| `POST /sp/data` (6 quads, 2 named graphs) | 200 | application/json | `{"count":6,"tripleCount":0,"quadCount":6}` |
| `POST /sp` (same body) | 200 | application/json | same counts |
| `POST /sp/get` | 405 | text/plain | `HTTP method not allowed: POST : Read-only` |
| `GET /sp/data` `Accept: application/n-quads` | 200 | application/n-quads | every named graph plus the default graph |
| `GET /sp` same | 200 | application/n-quads | identical |
| `GET /sp/get` same | 200 | application/n-quads | identical |

## Observations

- **Default graph.** Yes: the `GET` returns default-graph triples as three-term lines beside the
  four-term quads. The seeded `<d> <p> "dflt"@en` came back as
  `<http://example.org/d> <http://example.org/p> "dflt"@en .`. Parsed by rdflib's `Dataset`, they land in
  `urn:x-rdflib:default`. This confirms the PD-1 statement.
- **Round trip.** `GET /sp/data` of the source, `POST /sp2/data` into a fresh dataset (`count 11`, all
  quads), then `GET /sp2/data`: every graph (g1, g2, default) is isomorphic to the source
  (`rdflib.compare.isomorphic` True, 6/6, 4/4, 1/1 triples).
- **Blank nodes.** Fuseki relabels blank nodes on output (`_:B<hash>`), so labels do not survive, but
  structure does: a blank node used as subject of two triples in g1 still links both, and a blank node
  object spanning g1 to g2 stays consistent across the graphs of one document. A blank node is scoped to
  one `POST` body: posting the same body a second time added a fresh copy of the blank-node triples (11
  lines became 19) while the IRI-only quads were deduplicated. So the import is additive, and a repeated
  import duplicates blank-node subgraphs; restore always imports once into a new empty dataset.
- **Literals.** `"chat"@fr` and `"42"^^xsd:integer` came back unchanged in the output and in the
  isomorphism check.
- **Additive, not replacing.** `POST` adds to what is there (the second `POST` kept the first's quads).
- **Dropped dataset.** `GET /nope/data`, `GET /nope`, `POST /nope/data` and `POST /nope` all answer
  **404**. The adapter's `_raise_for_status` already maps 404 (and 405) to `on_missing`, which defaults
  to `DatabaseGone` in `_send`, so `export_quads` and `import_quads` need no new mapping.

## Reproduction

Throwaway `temp/spike_fuseki_nquads_test.py` (with `temp/conftest.py` loading the container plugin),
run with `make test-containers TEST_PATH=temp/spike_fuseki_nquads_test.py PYTEST_ADDOPTS="-s -p no:cacheprovider"`.
Plain `httpx` against the `fuseki` fixture: create dataset `sp` via `/$/datasets`, seed one default-graph
triple with `/sp/update`, `POST` six N-Quads (language-tagged and typed literals, a blank node with two
triples in g1, a blank-node link from g1 to g2), then the `GET`/`POST` matrix above, a round trip into
`sp2`, and the dropped-dataset probes. 1 test passed in 8 s.
