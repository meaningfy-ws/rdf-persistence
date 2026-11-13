> Derives from: EPIC `atomic-commit` (proposal.md, issue #83). Two stages, one PR each into `develop`.
> Type: Implementation.

A and B are stored books of the toy library tenant `T` (`tests/toy.py`: `TENANT`, `book_iri`,
`dune`, `toy_mapper`), C and D new books. "Another session" is a second `Session` on the same
store. Before stage 1 the lead runs GitNexus impact on `Session.add_graph`, `replace_graph`,
`remove` and `UnitOfWork.commit` and stops on anything beyond the callers listed in design.md.

## 1. The atomic transaction

- [x] 1.0 Issue #76 (PD-12), test first in `tests/unit/services/test_session_loaded_graphs.py`
  or a new `tests/unit/services/test_session_tenant_root.py` (fake store). Gates:
  `make test-fast`, `make check-quality`, `make clean-code`. Commit with `Refs: atomic-commit
  DEC-7` and `Closes #76` in the PR.

| ID | Input | Expected |
|---|---|---|
| TC-00a | session opened with `URIRef(TENANT)`; `add_graph(TENANT_str, root_triples)` | stored in `T/meta`; no `Aggregate` entry for it |
| TC-00b | session opened with `TENANT` as `str`; `get_graph(URIRef(TENANT))` after TC-00a's write | returns the root from `T/meta` |

- [x] 1.1 The marker in the metamodel: `CommitMarker` in `rdf_persistence/model/rp_core.yaml`
  (PD-1), `make generate`, `vocabulary.py` terms. Gates: `make test-fast`, `make check-quality`,
  `make clean-code`.

- [x] 1.2 `Session.transaction()` and `Transaction` (PD-2 to PD-7), test first in
  `tests/unit/services/test_session_transaction.py` (fake store); then the single-aggregate
  methods become one-change transactions (PD-5). The existing tests in
  `tests/unit/services/test_session*.py`, `test_tenancy*.py`, `test_aggregates*.py` stay green;
  the only ones allowed to change are those asserting the old conflict message text (PD-14) or a
  count of update requests (TC-28); the builder lists each changed test in the report.
  `Conflict.iris` in `domain/exceptions.py`. `FakeStore.update` atomic per request (PD-13), test
  first in `tests/unit/testkit/test_fakes.py`. Gates: `make test-fast`, `make check-quality`,
  `make clean-code`.

| ID | Input | Expected |
|---|---|---|
| TC-01 | `t.replace_graph(A,…,a1)`, `t.add_graph(C,…)`, `t.remove(B,b1)` | A at the returned token, C stored, B gone; registry has C's entry and not B's; no `rp:CommitMarker` left |
| TC-02 | as TC-01, but another session replaces A first | `Conflict`, `iris == (A,)`; A as the other session left it, no C, B stored |
| TC-03 | `t.replace_graph(A,…,a1)`, `t.add_graph(B,…)` (B exists) | `Conflict`, `iris == (B,)`; A at `a1` |
| TC-04 | `t.remove(B,b1)` after another session replaced B | `Conflict`, `iris == (B,)`; B stored |
| TC-05 | `t.replace_graph(A,…)` then `t.remove(A,…)` | `ValueError` at the second call; nothing sent (store's update count unchanged) |
| TC-06 | `raise RuntimeError` inside the block after one change | `RuntimeError`; nothing sent |
| TC-07 | the tenant root `T` and book A in one transaction | `T` in `meta`, no `Aggregate` entry for `meta`; A updated |
| TC-08 | A with loaded graph `g`; transaction replaces A with `loaded_graphs=[]` and adds C | `g` emptied, its entry gone; C stored |
| TC-09 | empty transaction | no update sent |
| TC-10 | a store stub whose `update` raises `StoreUnavailable` | `StoreUnavailable`; store unchanged |
| TC-11 | two transactions on A from two sessions, both at `a1`, sent one after the other | the first passes, the second `Conflict(iris=(A,))` |
| TC-12 | transaction replaces A and B; `FakeStore.after_update` (PD-13) lets another session replace A before the `ASK` | success (PD-4: B holds the new token); A as the other session left it, B as committed |
| TC-12a | `t.remove(B,b1)` alone; another session replaced B first | `Conflict(iris=(B,))`, B stored (removes only, PD-4) |
| TC-13 | `t.replace_graph(A_str,…)` then `t.remove(URIRef(A_str),…)` | `ValueError` at the second call (claim keyed on the graph) |
| TC-14 | fake store: `INSERT DATA {…} ; CREATE GRAPH <existing>` | `BadQuery`; the insert not visible (PD-13) |

- [x] 1.3 `UnitOfWork` on the transaction (PD-8, without batches), test first in
  `tests/unit/services/test_mapper_unit_of_work.py`; update the class docstring (all or nothing).
  Gates: `make test-changed`, `make check-quality`, `make clean-code`.

| ID | Input | Expected |
|---|---|---|
| TC-20 | uow gets A and B; another session changes B; uow changes A, adds B, commits | `Conflict(iris=(B,))`; A and B unchanged in the store (issue #83 acceptance 1) |
| TC-21 | uow adds C, D and a third new book, removes A, commits | all four changes stored with new tokens (acceptance 2) |
| TC-22 | uow gets A; `version(A)` | equals `Session.get_graph(A)`'s token |
| TC-23 | uow gets A, changes it, commits; `version(A)` | the new token, different from TC-22's |
| TC-24 | `version(X)` for an unread IRI | `LookupError` naming X |
| TC-25 | `remove(obj)` of a root not read here | `ValueError` |
| TC-26 | uow gets A, B; changes A; removes B; A changed meanwhile; commit | `Conflict(iris=(A,))`; B still stored |
| TC-27 | after TC-20, the uow's held A and its `version(A)` | unchanged by the failed commit |
| TC-27a | uow adds new C, then `remove(C)` | `ValueError` at `remove` |
| TC-27b | uow gets A, `add(A)`, `remove(A)`, commit | A removed; `add(A)` after that raises `ValueError` |
| TC-28 | existing `test_a_commit_writes_only_what_was_added_and_only_once` | still green: one update request per commit now, so it asserts one request |

- [x] 1.4 On Fuseki: `tests/integration/store/test_transaction.py`, and the store conformance case
  of RISK-1 in `rdf_persistence/testkit/store_conformance.py` (an update request whose second
  operation fails at run time, `LOAD` of a missing file, leaves the first unapplied, PD-13
  "Found"), run against the fake and Fuseki. Gate:
  `make test-containers TEST_PATH="tests/integration/store/test_transaction.py tests/integration/store/test_mapper.py tests/integration/store/test_store_conformance.py"`
  (adjust to the conformance runner's file name).

| ID | Input | Expected |
|---|---|---|
| IT-01 | TC-01 on Fuseki | as TC-01 |
| IT-02 | TC-02 on Fuseki | as TC-02 |
| IT-03 | TC-20 on Fuseki | as TC-20 |
| IT-04 | 20 concurrent transactions each replacing A at `a1` plus adding its own new book (`asyncio.gather`) | exactly one succeeds; exactly one new book stored |
| IT-05 | conformance: request `INSERT DATA {…} ; LOAD <file:///nonexistent/none.ttl>` (PD-13 "Found") | `BadQuery` or `StoreUnavailable`; the first insert not visible |

- [x] 1.5 Docs: `architecture/data-flows.adoc` (the commit flow: one request, the marker; the
  `rp:CommitMarker` term), `howto/adopt.adoc` (multi-aggregate commits, `Conflict.iris`,
  `version`, `remove`; the behaviour change), `questions.adoc` ("Can I save several aggregates at
  once?"). Gates: `make check-docs`, `make check-diagrams`.

- [ ] 1.6 Close stage 1: `make check-all`, `make test-containers`; PR into `develop`
  (`Refs: atomic-commit`, `Closes #83` only after stage 2); merge on green CI.

## 2. The size limit and batch mode

- [ ] 2.1 `max_roots`, `CommitTooLarge`, `commit(batches=True)` (PD-8, PD-9), test first in
  `tests/unit/services/test_mapper_unit_of_work.py`. Gates: `make test-changed`,
  `make check-quality`, `make clean-code`.

| ID | Input | Expected |
|---|---|---|
| TC-30 | `max_roots=2`, three new books, `commit()` | `CommitTooLarge` naming 3 and 2; no request sent (acceptance 3) |
| TC-31 | `max_roots=2`, three new books, `commit(batches=True)` | two update requests; three books stored |
| TC-32 | as TC-31 with a store stub failing the second request; then a new uow adds the same three books, `commit(batches=True)` | three books stored once each; the first two kept their first versions (idempotent re-run) |
| TC-32a | as TC-32 with books that each own an anonymous chapter (no id) | idempotent: three books once each (skolem IRIs compared as blank nodes, PD-9) |
| TC-32b | as TC-32, the same uow retries `commit(batches=True)` after the failure | only the third book is sent; three books stored |
| TC-33 | `max_roots=2`, batch re-run where one added book exists with a different title | `Conflict(iris=(that book,))`, message says how many batches committed |
| TC-34 | `max_roots=2`, exactly two roots, `commit()` | one request, both stored |

- [ ] 2.2 Fuseki: IT-06, a 500-book commit with the default limit (PD-10), timed; the time goes in
  the durations table of `docs/modules/ROOT/pages/develop/index.adoc`. If it fails or exceeds
  30 s, lower the default and record the value in design.md PD-10. Gate:
  `make test-containers TEST_PATH=tests/integration/store/test_transaction.py`.

- [x] 2.3 Docs: batch mode in `howto/adopt.adoc` (not atomic overall; re-run converges).
  Gate: `make check-docs`.

- [ ] 2.4 Close: `make check-all`, `make test-containers`; `openspec validate atomic-commit --strict`;
  PR into `develop` closing #83; merge on green CI; archive the change.
