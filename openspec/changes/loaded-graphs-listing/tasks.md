> Derives from: EPIC `loaded-graphs-listing` (proposal.md), GitHub issue #70.

## 1. Session read

- [x] 1.1 Test first, in `tests/unit/services/test_loading.py` (fake store): the scenarios of
  `specs/rp-aggregate-store/spec.md` (one loaded graph found by a new session; after a replace with
  a new list only the new graph; `None` keeps it; none loaded → `[]`; removed → `NotFound`; never
  stored → `NotFound`; a foreign IRI → `InvalidIri`; a dropped database → `DatabaseGone`). Then add
  `Session.loaded_graphs` to `rdf_persistence/services/session.py` (design PD-1 to PD-3).
  Gates: `make test-changed`, `make check-quality`, `make clean-code`.
- [x] 1.2 In `tests/integration/store/test_loading.py` (Fuseki): a graph loaded and committed in
  one session is listed by a second session, and `loaded_graph` reads it with that IRI.
  Gate: run with the container lane before the PR.

## 2. Docs

- [x] 2.1 `docs/modules/ROOT/pages/howto/adopt.adoc`: a row for `loaded_graphs(iri)` in the
  `Session` method table, and the "Reading a loaded graph back" paragraph shows finding the IRI
  with it. `docs/modules/ROOT/pages/questions.adoc`: the "read back a graph I loaded" answer names
  it. Gate: `make check-docs`.

## Roadmap

- [x] 1.1 · [x] 1.2 · [x] 2.1

## Verification

`make check-all` and `make test-containers` green; `openspec validate loaded-graphs-listing
--strict` passes; issue #70 closed by the PR.
