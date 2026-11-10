> Derives from: EPIC `tenant-root-loads` (proposal.md). One stage, one PR into `develop`.
> Type: Implementation.

`T` is the toy library tenant, `B` a book, `g`, `h` graphs loaded with `load_graph`. In the session
tests, create the root first with `session.add_graph(T, root_triples)`, then commit it with
`session.replace_graph(T, root_triples, version, loaded_graphs=[…])`. "Flat policy" is the policy
of `test_tenant_sweep.py` whose loaded-graph template has no `{root}`.

## 1. Register the root's loaded graphs

- [x] 1.1 Test first, in `tests/unit/services/test_session_loaded_graphs.py` (fake store); then
  PD-1 in `Session._entries` (not `_graph`: PD-5 withdrawn, issue #76), and the `session.py` module docstring
  (the root's loaded graphs are registered). TC-02 goes in `tests/unit/services/test_tenant_sweep.py`
  on `make_world` (it has a `Tenancy` and a created tenant); TC-10 opens its session with
  `listings=`, built like the `listings()` fixture of `tests/unit/services/test_session_find.py`.
  Gates: `make test-fast`, `make check-quality`, `make clean-code`.

| ID | Input | Expected |
|---|---|---|
| TC-01 | `g = load_graph(T, ttl)`; commit root with `[g]`; new session | `loaded_graphs(T) == [g]`; `loaded_graph(T, g)` holds exactly the Turtle's triples |
| TC-02 | TC-01, then `Tenancy.rename(T, "New", record_version, principal)` | `loaded_graphs(T) == [g]`; `g` unchanged |
| TC-03 | TC-01, then commit root with `[]` | `loaded_graphs(T) == []`; `g` holds no triple |
| TC-04 | TC-01, then `session.remove(T, root_version)` | `g` holds no triple; no registry entry `ownedBy T` |
| TC-05 | root committed with `[g]`, `B` committed with `[h]`; commit root with `[]` | `loaded_graphs(B) == [h]`, `h` unchanged |
| TC-06 | as TC-05; commit `B` with `[]`, then remove `B` | `loaded_graphs(T) == [g]`, `g` unchanged |
| TC-07 | as TC-05; commit root without `loaded_graphs` (`None`) | `loaded_graphs(B) == [h]`, `loaded_graphs(T) == [g]` (root variant of `test_replace_without_a_list_leaves_the_loaded_graphs_of_another_aggregate_alone`) |
| TC-08 | flat policy; `B` committed with `[h]`; commit root with `[h]` | `InvalidIri`; nothing written |
| TC-10 | TC-01 | registry holds no `rp:kind rp:Aggregate` entry for `T/meta`; `session.find(Book)` returns exactly the committed books (regression guard) |

## 2. The sweep

- [x] 2.1 Test first, in `tests/unit/services/test_tenant_sweep.py` (fakes, injected clock); then
  PD-2: drop the skip in `_candidate_graphs`, delete `Iris.loaded_graph_root`, and update the
  `tenant_sweep.py` module docstring and the `_candidate_graphs` docstring. Delete
  `test_a_loaded_graph_names_the_root_its_template_holds` and
  `test_an_iri_that_is_not_a_loaded_graph_names_no_root` (`tests/unit/domain/test_iris_policy.py`);
  in `test_a_template_without_a_root_variable_names_no_root`, keep the `is_loaded_graph` assertion
  and delete the `loaded_graph_root` one; in `test_tenant_sweep.py`, delete the
  `loaded_graph_root` assertion of the flat-policy test. Gates: `make test-changed`,
  `make check-quality`, `make clean-code`.

| ID | Input | Expected |
|---|---|---|
| TC-11 (replaces `test_the_tenant_roots_loaded_graph_is_never_a_candidate`) | root loads `g` (committed with the root) and `h` (never committed), both 2 h old; sweep `remove=True` | report lists `h` only; `h` is gone; `g` exists and `loaded_graphs(T) == [g]` |
| TC-12 | as TC-11; sweep without `remove` | report lists `h`, not removed; both exist |
| TC-13 | root load `h` 5 min old, never committed; sweep `remove=True` | `h` kept (grace period) |
| TC-14 | flat policy; as TC-11 | as TC-11 |

## 3. On Fuseki, and the docs

- [ ] 3.1 Integration tests; gate:
  `make test-containers TEST_PATH="tests/integration/store/test_loading.py tests/integration/tenancy/test_tenant_sweep.py"`.

| ID | File | Input | Expected |
|---|---|---|---|
| IT-01 | `tests/integration/store/test_loading.py` | TC-01 on Fuseki | as TC-01 |
| IT-02 | `tests/integration/tenancy/test_tenant_sweep.py` | TC-11 on Fuseki | as TC-11 |
| IT-03 | `tests/integration/store/test_loading.py` | TC-03 on Fuseki | as TC-03 |

- [ ] 3.2 Docs. In `docs/modules/ROOT/pages/architecture/data-flows.adoc`: the Terms row
  "Tenant root" (it has no registry entry *of its own*, but its loaded graphs have entries); the
  sweep row of `#sweeps` (drop "Skips graphs loaded for the tenant root … issue #73"); the
  loaded-graph state diagram in `#files` (unchanged, check it). In
  `docs/modules/ROOT/pages/howto/adopt.adoc#sweep-live-tenant`, the upgrade note: root loads made
  before this change are unregistered and are reported by the dry run. Gates: `make check-docs`,
  `make check-diagrams`.

## 4. Close

- [ ] 4.1 `make check-all`, `make test-containers`; `openspec validate tenant-root-loads --strict`;
  PR into `develop` closing #73; merge on green CI; archive the change.
