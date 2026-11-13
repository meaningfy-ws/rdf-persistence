> Derives from: EPIC `tenant-dump-restore` (proposal.md). One stage, one PR into `develop`.
> Type: Implementation.

`T` is the toy library tenant, `B` a book, `S` a scan with one blob, `g` a graph loaded for `B`, `r`
a graph loaded for `T`'s root, `P` a principal other than `T`'s creator. "Flat policy" is the policy
of `test_tenant_sweep.py` whose templates are `{base}{tenant_id}/{type}/{id}`. Unit tests use the
fakes (`testkit/fakes.py`); integration tests use the Fuseki and Garage containers.

## 1. The port

- [x] 1.1 Spike on the Fuseki container (a throwaway test in `temp/`, not committed): which endpoint
  answers a dataset-level `GET` with `Accept: application/n-quads` and takes a `POST` of N-Quads;
  record the answer in design.md PD-1. If neither works, switch to the RISK-1 fallback and tell the
  lead before 1.2.
- [x] 1.2 Test first: two cases in `testkit/store_conformance.py` (run by
  `tests/unit/testkit/test_fake_store.py` on the fake and `tests/integration/store/test_store_conformance.py`
  on Fuseki); then PD-1 in `services/store.py` (`Store`, `ToolkitStore`), `adapters/fuseki.py` and
  `testkit/fakes.py`. Gates: `make test-fast`, `make check-quality`, `make clean-code`,
  `make test-containers TEST_PATH=tests/integration/store/test_store_conformance.py`.

| ID | Input | Expected |
|---|---|---|
| TC-01 | database with two named graphs (a language-tagged and a typed literal; one graph holds a blank node used as subject of two triples); export, import into an empty database | both graphs isomorphic in the second database (the blank node still links its two triples); no default-graph triple in either |
| TC-02 | export of a dropped database | `DatabaseGone` |
| TC-03 | import into a dropped database | `DatabaseGone` |

## 2. The manifest and the rewrite

- [x] 2.1 PD-2: `TenantDump` in `model/service/rp_service.yaml`; `make generate`; the freshness and
  conformance checks pass. Gates: `make test-changed`, `make check-quality`.
- [x] 2.2 Test first, `tests/unit/services/test_tenant_dump_rewrite.py`; then PD-4 (`rewrite`,
  `glued_templates`). No change to `domain/iris.py`. Gates: `make test-fast`, `make check-quality`,
  `make clean-code`.

| ID | Input | Expected |
|---|---|---|
| TC-04 | the worked example's six terms (design.md) | each rewritten or kept as the table says |
| TC-05 | flat policy; aggregate, part and loaded graph of tenant `p4x8k2m` | each carries the new id; `iris.is_aggregate_graph` / `is_loaded_graph` accept them for the new tenant |
| TC-06 | an IRI under another base holding the old id as a segment | unchanged |
| TC-07 | policies `{base}{tenant_id}-{id}` (aggregate) and `{tenant}.meta` (meta); their IRIs for the old id; and an IRI holding the old id glued to letters (`…/x9f1…`, `…/9f1…x`) | the first two carry the new id and the policy accepts them for the new tenant; the glued one is unchanged |
| TC-08 | default policy; the aggregate `{T}/users/{id}` (`rp_path` `users`) as graph, subject and object | all three carry the new id |
| TC-09 | `glued_templates` of the default policy, of `{base}t{tenant_id}`, of `{tenant}{id}` | `[]`; names `tenant_template`; names `aggregate_template` |

## 3. Dump and restore

- [x] 3.1 Test first, `tests/unit/services/test_tenant_dump.py` (fakes, `make_world` of
  `test_tenant_sweep.py` for a created tenant); then `services/tenant_dump.py` (PD-3, PD-5, PD-7),
  `Tenancy.restore`, `_new_record` and `_free_tenant` renamed `free_tenant` (PD-6),
  `ServiceKit.dump_tenant` / `restore_tenant` (PD-8) and `test_public_api.py`. Gates: `make test-fast`, `make check-quality`, `make clean-code`.
  The lead runs the adversarial tester right after this task (new trust boundary, write order).

| ID | Input | Expected |
|---|---|---|
| TC-10 | `T` with `B`, `g`, `r`, `S`; dump; restore by `P` | new tenant `T'` ≠ `T`, same label; `B'` reads the same slots; `loaded_graphs(B') == [g']`, `loaded_graphs(T') == [r']` with the same triples; `S'`'s blob bytes equal |
| TC-11 | TC-10, then replace `B'` at its read version | succeeds; `B` unchanged |
| TC-12 | `T` with grants for three principals; dump; restore by `P` | `T'`'s record grants only `P`, `creator_role` |
| TC-13 | flat policy; TC-10 | as TC-10 |
| TC-14 | `B`'s title is the literal of `T`'s IRI | `B'`'s title is the same literal |
| TC-15 | dump of a `deleting` tenant; of an unknown tenant | `Conflict`; `NotFound`; `out` empty |
| TC-16 | a blob deleted between `list_blobs` and `get` (fake hook) | dump succeeds without it; logged `dump-blob-gone` |
| TC-17 | manifest with schema version `1.0.0`, service at `1.1.0` | `InvalidBody` naming both; no database, bucket or record created |
| TC-18 | manifest with object id length 13, service 12 | `InvalidBody` naming `object_id.length`; nothing created |
| TC-19 | a quad in `http://elsewhere.example/g`; a quad in the default graph | `InvalidBody`; nothing created |
| TC-20 | a root validator that refuses | `InvalidBody`; nothing created |
| TC-21 | manifest not first; `graphs.nq` a symlink member; not gzip | `InvalidBody`; nothing created |
| TC-22 | `import_quads` fails (`FakeStore.on`) | the error is raised; no new record; the new database and bucket are gone |
| TC-23 | TC-22 with `drop_dataset` failing too | the import's error is raised; cleanup failure logged `restore-cleanup`; the next start-up sweep drops the database |
| TC-24 | a tenant with its root only | dump and restore succeed |
| TC-25 | `T`'s root relabelled `New` through a session, its record left at `Old` (a rename cut between the two); dump; restore | succeeds; `T'`'s root and record are both labelled `New`; the manifest says `Old` |
| TC-26 | the fake drops the new database (a start-up sweep) after the last blob `put`, before the record | `PersistenceError`; no record; the bucket is gone |
| TC-27 | an archive whose blob members are `blobs/a`, then `notes.txt`; and one whose blob member is a directory | `InvalidBody`; `blobs/a` was `put` first; no record; the new database and bucket are gone |

## 4. On the containers, and the docs

- [x] 4.1 Integration test `tests/integration/tenancy/test_tenant_dump.py`: IT-01 = TC-10 on Fuseki
  and Garage; IT-02 = TC-17. Gate:
  `make test-containers TEST_PATH=tests/integration/tenancy/test_tenant_dump.py`.
- [x] 4.2 Docs: a how-to `docs/modules/ROOT/pages/howto/dump-restore.adoc` (the two calls, routing
  them (dump with `require(..., Action.ADMINISTER)`; restore with `gate.caller`, PD-11), the archive format v1, what is not dumped, the limits:
  same policy, same schema version, no template gluing the tenant id to a letter or digit, in-memory
  size of the graphs, stop writes for an exact copy, no deploy or restart during a restore, declare a
  schema `version`); the page in the nav; a `questions.adoc` entry ("How do I back up or copy a project?");
  the data-flows page gains the dump and restore flows. Gates: `make check-docs`,
  `make check-diagrams`.

## 5. Close

- [ ] 5.1 `make check-all`, `make test-containers`; `openspec validate tenant-dump-restore --strict`;
  PR into `develop`; merge on green CI; archive the change.
