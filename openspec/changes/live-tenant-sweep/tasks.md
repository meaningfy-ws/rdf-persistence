> Derives from: EPIC `live-tenant-sweep` (proposal.md). One stage, one PR into `develop`.

## 1. Model and port

- [x] 1.1 Schema (design PD-2, PD-8, PD-12): `PendingLoad` (`id` as identifier, holding the graph IRI; `loaded_at`
  with `slot_uri: rp:loadedAt`) in `rp_core.yaml`; `BlobEntry` (`file_key`, `modified`) in
  `rp_files.yaml`; `TenantSweepReport` (`tenant`, `older_than_seconds`, `loaded_graphs`, `blobs`,
  `removed_loaded_graphs`, `removed_blobs`, `skipped_blobs`) in `rp_tenancy.yaml`, reusing existing
  slots where they exist. `make generate`; model-shape fixture updated.
  Gates: `make test-changed`, `make check-quality`.
- [x] 1.2 Test first: a conformance case "blobs are listed in key order with their modified time;
  a missing bucket is TenantGone" in `testkit/file_store_conformance.py`; then
  `FileStore.list_blobs` (PD-12) in `services/files.py`, `FakeFileStore` (with `clock`) and
  `S3FileStore` (paged `list_objects_v2`). Gates: `make test-changed`, `make check-quality`,
  `make clean-code`.

## 2. Load marker

- [x] 2.1 Test first (`tests/unit/services/test_loading.py`): `load_graph` writes the one marker
  triple `<G> rp:loadedAt <clock()>` in the registry before it PUTs the graph (the fake store's
  `sent` order); a failed PUT leaves the marker; a commit of G keeps G's registry entry intact.
  Then the change in `Session.load_graph` (PD-2). Gates: `make test-fast`, `make check-quality`,
  `make clean-code`.

## 3. The sweep

- [x] 3.1 Test first (`tests/unit/services/test_tenant_sweep.py`, fakes, injected clock): the spec
  scenarios and each line of design.md's worked example; dry run changes nothing; `remove` and
  `remove_blobs` act independently; markers of owned graphs and old empty ones go only with
  `remove=True`, young ones stay (PD-6); a registry entry survives marker cleanup; under a policy
  whose loaded-graph template has no `{root}`, an old orphan is still found (N1); the tenant root's
  loaded graph, `meta`, `registry`, access and aggregate graphs and another tenant are untouched;
  read order (PD-7); `skipped_blobs` (PD-9); `NotFound`/`Conflict` (PD-11). Then
  `Iris.loaded_graph_root` (with its own unit test in `tests/unit/domain/`) and
  `services/tenant_sweep.py` (`sweep_tenant`, its SPARQL constants). Gates: `make test-changed`,
  `make check-quality`, `make clean-code`.
- [x] 3.2 `ServiceKit.sweep_tenant` (entrypoints/kit.py) delegating to `sweep_tenant` with the
  kit's tenancy, store, files and iris; public exports (PD-13) and `assert_public_imports`.
  Gates: `make test-changed`, `make check-quality`.
- [x] 3.3 Adversarial tester (riskiest task: deletion and its races): tests only, trying to make
  the sweep remove what a commit names or will name, or touch another tenant.

## 4. Remove with files

- [x] 4.1 Test first (`tests/unit/services/test_remove_with_files.py`, fakes): removes the
  aggregate and its blob; `Conflict` at a stale version with nothing changed; a key another
  aggregate names stays; a failing blob delete still removes the aggregate and logs (PD-10). Then
  `remove_with_files` (service) and `ServiceKit.remove_with_files`.
  Gates: `make test-changed`, `make check-quality`, `make clean-code`.

## 5. Toy library, containers and docs

- [ ] 5.1 The toy library (`tests/toy_service.py` and its routes) sets `file_key` to the scan id and
  deletes a scan with `kit.remove_with_files`; a feature or e2e test shows a scan's blob survives
  `sweep_tenant(remove=True, remove_blobs=True)` and goes with its delete. Gate: `make test-changed`.
- [ ] 5.2 Integration (`tests/integration/`): the sweep against Fuseki and Garage gives the worked
  example's outcome; `S3FileStore` passes the listing conformance case. Gate: `make test-containers`.
- [ ] 5.3 Docs: adopt guide ("Sweep a live tenant": the operator script, the two flags and when
  `remove_blobs` is safe, the grace period, RISK-1, RISK-2; the toy library sets `file_key`; the
  file delete route calls `remove_with_files`), `architecture/index.adoc` (building block to v1,
  public API table), `questions.adoc` (the future-list entry becomes an answer), CHANGELOG
  (`FileStore.list_blobs` for adapter authors). Gate: `make check-docs`.
- [x] 5.4 File the GitHub issue for F4 (the tenant root's loaded graphs are never registered) and
  link it from design.md: #73.

## Roadmap

- [x] 1.1 · [x] 1.2 · [x] 2.1 · [x] 3.1 · [x] 3.2 · [x] 3.3 · [x] 4.1 · [ ] 5.1 · [ ] 5.2 · [ ] 5.3 · [ ] 5.4

## Verification

`make check-all` and `make test-containers` green; `openspec validate live-tenant-sweep --strict`;
one L2+L3 review pass; the PR merged on green CI.
