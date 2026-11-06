<!-- SECONDARY INPUT: preserved, never groomed. The EPIC (../proposal.md) is the shaped truth. -->

# Seed: a sweep inside a live tenant

## Seed text

From `docs/modules/ROOT/pages/questions.adoc`, "What could strengthen it in the future":

> *A sweep inside a live tenant* for blobs and loaded graphs that no aggregate names (deferred in
> xref:architecture/index.adoc#building-blocks[architecture v1]).

From `docs/modules/ROOT/pages/architecture/index.adoc`, building blocks:

> |Sweep of orphans inside a live tenant (blobs, loaded graphs no aggregate names)
> |deferred
> |Orphans are invisible and erased with their tenant.

> A loaded graph no commit registers stays, unseen, until its tenant is deleted: the start-up sweep
> drops only whole tenant databases and buckets, and the sweep inside a live tenant is deferred.

## What the code does today (checked 2026-11-06)

- `rdf_persistence/services/sweep.py`: drops `{prefix}-t-` databases and buckets no access record
  names; finishes `deleting` tenants; nothing inside a live tenant.
- `rdf_persistence/services/session.py`: `load_graph` PUTs a new `{root}/content/{uuid4}` graph;
  `remove` drops the aggregate's registered loaded graphs in the same update; nothing touches blobs.
- `rdf_persistence/services/files.py`: the `FileStore` port has `put`, `get`, `delete`,
  `create_bucket`, `delete_bucket`, `list_buckets`; no way to list the keys in a bucket.
- Blobs are written by the consumer's own route (`docs/modules/ROOT/pages/howto/adopt.adoc`,
  `kit.files.put(bucket, scan_id, …)`); the aggregate names the blob in `StoredFile.file_key`.

## Open questions for the developer

1. **When does the sweep run?**
   - (a) A library call the consumer schedules (`await sweep_tenant(...)`): no scheduler in the
     toolkit; the consumer must remember to run it.
   - (b) Part of the start-up sweep, per tenant: no new trigger, but start-up gets slower with every
     tenant, and v1's rule "never touches anything inside an active tenant" must then be reworded.
   - (c) A background task started by `install_service`: automatic, but a scheduler in the toolkit,
     and several instances would sweep the same tenant at once.
2. **How is work in flight protected?**
   - (a) A grace period: only graphs and blobs older than N minutes are swept. Simple; needs a
     creation time (S3 `LastModified`; for graphs, a statement written at load time, or none today).
   - (b) A pending marker: `load_graph` and file upload record a pending entry that the commit
     clears. Exact, but every load and upload writes one more statement.
   - (c) Run only while the tenant takes no writes (a maintenance window). Safe, but needs a lock or
     an operator.
3. **What counts as naming a blob?** (a) only `StoredFile.file_key` values in aggregate graphs; (b)
   also keys a consumer declares through another slot (needs a schema annotation). (a) is safe and
   simple; (b) covers consumers that model files differently.
4. **Does `Session.remove` start deleting the blobs of the aggregate it removes?** (a) Yes, in the
   same call, after the graph update: fewer orphans, but a blob delete cannot join the SPARQL update,
   so a crash still leaves orphans. (b) No: the sweep is the only cleaner. (b) keeps `remove` as it is.
5. **Delete or quarantine?** (a) delete at once; (b) move to a quarantine (a graph or key prefix)
   removed by a later run. (b) allows an undo after a sweep bug; it doubles the work.
6. **What does the sweep report?** (a) log lines only, as the start-up sweep does; (b) a returned
   report record (generated from LinkML), so a consumer can expose it; (c) both.
7. **Dry run?** Should the sweep support listing orphans without removing them? Useful for
   operators; one more mode to test.

## Developer answers (2026-11-06)

Developer chose "a": an operator command, as a dry run by default (answers Q-1 and Q-7).
- The developer found the question unclear. Remaining questions go to them with a recommendation each.
- Still open: Q-2 to Q-6. Recommendations to propose: a grace period for in-flight work;
  `file_key` only; `Session.remove` deletes its blobs; delete rather than quarantine; a returned
  report (a LinkML record) plus log lines.

Developer: "accept recommendations, and continue" (2026-11-06).
- Accepted: a grace period (only items older than a set age, e.g. 1 hour) protects work in flight; only `file_key` names a blob; `Session.remove` deletes its aggregate's blobs; delete, not quarantine; a returned report (a LinkML record) plus log lines.
- Every question still open: the leader drafts a recommendation when the PLAN is derived, and the developer accepted recommendations by default (2026-11-06). Each one is recorded in the PLAN as the leader's choice, and the developer may overrule it.

## Test scenarios the EPIC must prove

- A loaded graph never named by a commit is removed once eligible; committed loaded graphs stay.
- A blob whose aggregate was removed is removed; blobs of stored aggregates are unchanged byte for byte.
- A graph loaded and committed during a sweep is never removed (race).
- A blob uploaded and committed during a sweep is never removed (race).
- The tenant's `meta` and `registry` graphs and every aggregate graph are never touched.
- The sweep of one tenant never touches another tenant's database or bucket.
- The sweep runs against the testkit fakes and against Fuseki and Garage with the same outcome.
- The start-up sweep's v1 scenarios still pass unchanged.
