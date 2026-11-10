<!-- PLAN (design half). PLAN = this file + tasks.md. -->

> Derives from: EPIC `live-tenant-sweep` (proposal.md). Answers: inputs/seed.md (developer,
> 2026-11-06: Q-1 a library call run as an operator command, Q-7 dry run by default, Q-2 to Q-6
> as recommended; 2026-11-10 after the PLAN attack: blob removal is its own opt-in flag and the
> guide sets `file_key` (F1); a kit helper removes a file aggregate with its blobs (F2)).
> Leader's choices are marked "leader"; the developer may overrule them.

## Context

- `Session.load_graph` (`services/session.py`) PUTs a parsed graph at a policy-minted IRI
  (`Iris.mint_loaded_graph`; default `{root}/content/{uuid4}`). A commit names it in `loaded_graphs`
  and writes registry triples about it in `{tenant}/registry` (`registry_triples`: subject `<G>`,
  `rp:graph <G>`, `rp:kind`, `rp:ownedBy <root>`). Nothing records when a graph was loaded.
  REPLACE and REMOVE drop every registry triple whose subject the root owns (`_DROP_ENTRIES`).
- `_entries` writes no registry entry for the tenant root, so a graph loaded for the tenant root is
  never registered (existing gap, F4; out of scope here, filed as an issue).
- `Session.remove` drops the aggregate graph, its registered loaded graphs and its registry triples
  in one update. `Session` holds no `FileStore`.
- Blobs: the consumer writes them with `kit.files.put(bucket, key, data)`. The metamodel names a
  blob in `StoredFile.file_key` (`rp:fileKey`, `internal`), but the adopt guide's toy library keeps
  the bytes under the scan id and leaves `file_key` empty (`adopt.adoc` "keeps the bytes under the
  scan's id instead"; `tests/toy_service.py`).
- File aggregates (`StoredFile` roots) are service-written: the router serves their GET and listing
  only (`router.py`, `is_service_written`); the consumer's own routes create and delete them.
- The bucket and the database of a tenant share one name, `TenantAccess.database_name`
  (`Tenancy.create`; `kit.bucket_of`). `Tenancy.get(tenant)` returns `(TenantAccess, version)`.
- `FileStore` (`services/files.py`) cannot list keys; `S3FileStore` pages `list_objects_v2` only
  inside `delete_bucket`; `FakeFileStore` keeps `dict[key, bytes]`; `testkit/file_store_conformance.py`
  holds the cases every adapter passes.
- The start-up sweep (`services/sweep.py`) never looks inside a tenant (DEC-2) and stays as it is.

## Goals / Non-Goals

**Goals:** `sweep_tenant` finds the unowned loaded graphs and the unnamed blobs of one `active`
tenant older than a grace period, removes graphs only with `remove=True` and blobs only with
`remove_blobs=True`, and returns a generated report; `ServiceKit.remove_with_files` removes a file
aggregate and the blobs only it names; `FileStore.list_blobs`; the guide and the toy library set
`file_key`.
**Non-Goals:** the EPIC's No-gos; a CLI, scheduler or HTTP route for the sweep (PD-1); fixing the
tenant root's unregistered loaded graphs (F4, its own issue).

## Decisions

- **PD-1** (leader, from Q-1 a and Q-7): the trigger is a public library call,
  `sweep_tenant(tenancy, store, files, iris, tenant, *, remove=False, remove_blobs=False,
  older_than=timedelta(hours=1), clock=utc_now)`, and `ServiceKit.sweep_tenant(tenant, *, ...)`
  with the same keywords. **Dry run by default**: with neither flag it reports and changes nothing.
  The consumer runs it as an operator command (a script or an admin route it owns); the adopt guide
  shows the script. Rejected: a toolkit CLI (it would need its own Fuseki and S3 settings loading,
  which the service gets from the consumer's composition root); a background task (Q-1 c).
- **PD-2** (Q-2 a, leader for the mechanism): the grace period `older_than` defaults to **1 hour**.
  A loaded graph's age comes from a **load marker**, the one triple
  `<G> rp:loadedAt "<time>"^^xsd:dateTime` in the registry graph. Its model is a LinkML
  `PendingLoad` (`rp_core.yaml`) whose identifier is the existing `id` slot, holding the graph IRI
  (the subject, not a triple), and whose `loaded_at` has `slot_uri: rp:loadedAt`, so the generated
  shape matches what is stored (N2). Not `graph` as identifier (build of task 1.1): the JSON-LD
  context is one map per slot name, so it would turn `graph` into `@id` for every class and break
  `RegistryEntry`'s `rp:graph` triple.
  The session writes the triple from the model by hand, as `registry_triples` does. The marker
  writes no `rp:graph` triple, so deleting it can never delete a registry entry's triple (F6).
  `load_graph` writes the marker **before** it PUTs the graph: a crash between the two leaves a
  marker with no graph, never a graph without a marker. A commit's `_DROP_ENTRIES` may delete the
  marker of a graph the root owns (same subject); that is harmless. A loaded graph with no marker
  was loaded before this change and counts as old (RISK-2). A blob's age is its object store
  `modified` time (S3 `LastModified`, set by the server clock). Rejected: a time inside the loaded
  graph (it would show in `loaded_graph`); a time-ordered id (the policy lets the id kind vary); a
  two-pass "first seen" sweep (a dry run would have to write).
- **PD-3** (Q-3 a, F1): a blob is **named** when any graph of the tenant database holds a triple
  `?s rp:fileKey "<key>"`. Searching every graph can only keep more blobs. Because a consumer may
  key blobs another way (as the toy library did), blobs are removed only with
  `remove_blobs=True` (developer, 2026-11-10); the docs say to pass it only when every blob key is
  in `file_key`. The toy library and the guide change to set `file_key` (the scan id stays the key).
- **PD-4**: a loaded graph is **unowned** when its IRI matches `Iris.is_loaded_graph(tenant, g)`,
  its root is not the tenant root (F4), and no registry triple `<g> rp:ownedBy ?root` exists. The
  root comes from a new `Iris.loaded_graph_root(iri) -> str | None`, the template's `{root}` group,
  or `None` when the template has none; only a root equal to the tenant excludes a graph (N1:
  `is_loaded_graph(tenant, g, root=tenant)` is true for every graph under a template without
  `{root}`, so it cannot be the test). The candidates come from
  `SELECT DISTINCT ?g WHERE { GRAPH ?g { ?s ?p ?o } }`, filtered by the policy in Python, so the
  tenant's `meta`, `registry`, access and aggregate graphs are never candidates.
- **PD-5**: removing a loaded graph is one guarded update per graph: delete its triples and its
  marker only if, in the same update, no registry triple owns it (`FILTER NOT EXISTS`). A commit
  that registers it between the sweep's read and the delete wins.
- **PD-6** (F5): with `remove=True` the sweep also deletes markers whose graph is owned (the commit
  made them useless), and markers whose graph holds no triples **and** whose `loaded_at` is older
  than the cutoff (a load that never finished). A young marker is kept, so a sweep that runs between
  a marker and its PUT cannot strip the marker. Markers are not reported.
- **PD-7** (F7): reads run in the safe order. Graphs: list the graphs, then read the registry
  owners. Blobs: list the blobs, then read the named keys. Something committed between two reads is
  then seen as owned or named.
- **PD-8** (Q-5 a, Q-6 c): orphans are **deleted**, not quarantined. The sweep returns a generated
  `TenantSweepReport` (`rp_tenancy.yaml`): `tenant`, `older_than_seconds`, `loaded_graphs` (sorted
  IRIs), `blobs` (sorted keys), `removed_loaded_graphs` and `removed_blobs` (whether each list was
  removed), and `skipped_blobs` (keys the object store would not delete). It logs one line per
  removed item (`step`: `sweep-loaded-graph`, `sweep-blob`) as the start-up sweep does.
- **PD-9** (F9): a blob whose delete raises `ValueError` (a key the S3 adapter refuses, written by
  another tool) is logged, listed in `skipped_blobs`, and the sweep goes on.
- **PD-10** (Q-4 a, developer 2026-11-10, F2): `ServiceKit.remove_with_files(tenant, principal, iri,
  if_version)`, built on a service function `remove_with_files(tenancy, files, ...)`: in one session
  it reads the aggregate (`NotFound`), refuses if its version is not `if_version` (`Conflict`,
  nothing changed), collects its `rp:fileKey` values, removes it with `if_version`, then reads which
  of those keys any graph still names, and deletes the others from the tenant's bucket (F8). A
  failed blob delete is logged, not raised: the aggregate is gone and the sweep removes the blob
  later. The consumer's delete route for a file aggregate calls it (the guide shows it). Rejected:
  a `FileStore` inside `Session`.
- **PD-11**: `sweep_tenant` refuses a tenant that is not `active`: `NotFound` for no access record,
  `Conflict` for `deleting`; it reads `access.database_name` for both the database and the bucket
  (F3).
- **PD-12**: `FileStore.list_blobs(bucket) -> list[BlobEntry]` (generated, `rp_files.yaml`:
  `file_key`, `modified`), in key order, every page. Raises `TenantGone` if the bucket does not
  exist. `FakeFileStore` takes a `clock` (default `utc_now`) to stamp `modified` on `put`. A new
  conformance case proves listing for every adapter. This grows a public Protocol (RISK-4).
- **PD-13**: new public names `sweep_tenant`, `remove_with_files`, `TenantSweepReport`,
  `BlobEntry`, `PendingLoad` in `rdf_persistence/__init__.py` and the public API table of
  `architecture/index.adoc`; the building block "Sweep of orphans inside a live tenant" moves from
  deferred to v1.

## Algorithm / approach

```python
async def sweep_tenant(tenancy, store, files, iris, tenant, *, remove=False, remove_blobs=False,
                       older_than=timedelta(hours=1), clock=utc_now) -> TenantSweepReport:
    access, _ = await tenancy.get(tenant)                          # NotFound
    if access.state != TenantState.ACTIVE: raise Conflict(...)
    database = access.database_name                                # also the bucket (F3)
    cutoff = clock() - older_than
    graphs = [g for g in await all_graphs(store, database)
              if iris.is_loaded_graph(tenant, g) and iris.loaded_graph_root(g) != tenant]
    owned, loaded_at = await registry_view(store, database, registry)   # after the listing (PD-7)
    orphans = sorted(g for g in graphs if g not in owned and loaded_at.get(g, EPOCH) < cutoff)
    listed = await files.list_blobs(database)                      # first (PD-7)
    named = await file_keys(store, database)                       # then (PD-3)
    blobs = sorted(b.file_key for b in listed if b.file_key not in named and b.modified < cutoff)
    if remove:
        for g in orphans: await store.update(database, guarded_drop(g))     # PD-5
        await store.update(database, stale_markers(cutoff))                  # PD-6
    skipped = []
    if remove_blobs:
        for key in blobs: try files.delete(database, key) except ValueError: skipped.append(key)
    return TenantSweepReport(...)
```

Worked example: tenant T, book B committed with loaded graph G1; G2 loaded for B 2 h ago and
never committed; G3 loaded 5 min ago; scan S stored with blob k1 (`file_key` k1), scan R removed
with `session.remove` leaving blob k2 (3 h old); blob k3 uploaded 1 min ago, not yet committed.
- `sweep_tenant(..., T)` → `loaded_graphs=[G2], blobs=[k2]`, both `removed_*` false, nothing changed.
- `remove=True` → G2 is gone, k2 stays, `removed_loaded_graphs=True`, `removed_blobs=False`.
- `remove=True, remove_blobs=True` → G2 and k2 are gone; G1, G3, k1, k3 stay; G3's commit then
  succeeds.
- `kit.remove_with_files(T, p, S, v)` → S and k1 are gone; a blob S shares with another scan stays.

### Anti-patterns

| Don't | Do instead | Why |
|---|---|---|
| Build SPARQL with f-strings | module constants + `fill`/`term` | DEC-4 |
| Return dicts or tuples | `TenantSweepReport`, `BlobEntry`, `PendingLoad` | DEC-3 |
| `DROP GRAPH` unconditionally | the guarded `DELETE … FILTER NOT EXISTS` update | PD-5 race |
| Put a timestamp in the loaded graph | the registry marker | PD-2 |
| Write the marker with `rp:graph` | only `rp:loadedAt` | F6 |
| Read named keys before listing blobs | list first | PD-7 |
| Use `Tenancy.get`'s second value as a name | `access.database_name` | F3 |
| Real sleeps for the grace period | an injected `clock` | testing rule |

## Error matrix

| Failure mode | How it is detected | Expected handling |
|---|---|---|
| No such tenant | `Tenancy.get` | `NotFound` |
| Tenant `deleting` | `access.state` | `Conflict`, nothing read or removed |
| Tenant database gone | store query | `DatabaseGone` propagates |
| Tenant bucket gone | `list_blobs` | `TenantGone` propagates, before any removal |
| Commit registers a graph between read and delete | guard in the delete update | graph kept |
| Commit names a blob between the listing and the key read | PD-7 order | blob kept |
| Sweep between a load's marker and its PUT | the marker is young | marker kept (PD-6) |
| Load older than the grace period, committed after the sweep | not detectable | graph emptied; the commit registers an empty graph (RISK-1) |
| Blob uploaded more than `older_than` before its commit | not detectable | removed only with `remove_blobs` (RISK-1) |
| Blob keyed outside `file_key` | not detectable | removed only with `remove_blobs` (RISK-5) |
| Loaded graph of the tenant root | `loaded_graph_root(g) == tenant` | never a candidate (F4) |
| Policy template without `{root}` | `loaded_graph_root` is `None` | every loaded graph is a candidate (N1) |
| Another aggregate starts naming a key between `remove_with_files`' read and delete | not detectable without a lock | blob deleted (N3, as RISK-1) |
| Blob key the adapter refuses (`ValueError`) | exception on delete | logged, listed in `skipped_blobs`, sweep goes on |
| Object store fails mid-sweep | `StoreUnavailable` | propagates; a later run finishes (idempotent) |
| `remove_with_files` at a stale version | version read in the session | `Conflict`, nothing changed |
| A key another aggregate also names | key read after the remove | blob kept |
| Blob delete fails in `remove_with_files` | exception from `files.delete` | logged, not raised; the sweep removes it later |
| Graph with no marker (loaded before this change) | no `rp:loadedAt` | counts as old (RISK-2) |
| Marker another tool wrote unreadable (naive or ill-typed dateTime, a date, a string) | not a timezone-aware datetime | ignored, as if absent (RF-1) |
| Several markers on one graph | more than one `rp:loadedAt` | the youngest counts (RF-1) |
| Two sweeps at once | — | harmless: deletes are idempotent |

## Risks / Trade-offs

- **RISK-1** (likelihood low, impact high: a lost upload): a load or upload committed more than
  `older_than` after it was written is removed. Mitigation: 1 hour default, configurable; dry run
  by default; documented ("commit within the grace period").
- **RISK-2** (likelihood low, impact medium): a graph loaded just before the upgrade has no marker
  and counts as old. Mitigation: upgrade note: do not sweep with removal during a deploy.
- **RISK-3** (likelihood medium, impact low): listing every graph and every blob is slow on a large
  tenant. Accepted for an operator command; S3 is paged.
- **RISK-4** (likelihood low, impact medium): third-party `FileStore` adapters break on the new
  Protocol method. Mitigation: CHANGELOG entry and the conformance case.
- **RISK-5** (likelihood medium, impact high: deleted files): a consumer that keys blobs outside
  `file_key` runs `remove_blobs=True`. Mitigation: a separate flag, off by default; the guide and
  the toy library set `file_key`; the docs name the condition next to the flag.
- Clock skew between the service and the object store shifts a blob's grace period by the skew.
  Accepted: minutes against a one-hour default.

## Review fixes (leader's decisions after the adversarial tester, 2026-11-10)

- **RF-1** (tester, defect 1): an unreadable marker crashed every sweep of the tenant (`TypeError`
  comparing it with the cutoff). The sweep now reads a marker only when it is a timezone-aware
  `datetime`; anything else counts as no marker (old, as RISK-2), and of several markers the
  youngest counts, so a stray marker can never make a graph look older than its real load.
- **RF-2** (build of task 4.1): `remove_with_files` makes no separate version check: it reads the
  keys, then `session.remove(iri, if_version)` refuses a stale version with nothing changed, and a
  replace between the read and the remove also makes the remove refuse; a separate check would add
  a race, not remove one. The "still named" read is a new public `Session.named_file_keys(keys)`,
  because the session's store is private.
- Accepted as is: when a commit wins the PD-5 race, the report still lists the graph with
  `removed_loaded_graphs=True`; the report lists what was found and whether removal ran, not what
  each delete did. A loaded graph of the tenant's access record is swept like any aggregate's when
  no commit owns it.

## Open Questions

None. Follow-up outside this change: the tenant root's loaded graphs are never registered (F4),
GitHub issue #73.
