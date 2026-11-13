> Derives from: EPIC `tenant-dump-restore` (proposal.md). Implements DEC-1 to DEC-10.
> Type: Implementation.

## Context

A tenant is its database `{prefix}-t-{id}` (root in `T/meta`, aggregate graphs, `T/registry`,
loaded graphs) and its bucket of the same name; its access record lives in the system database
(`services/tenancy.py`). `Tenancy.create` validates the root, draws a free tenant IRI
(`_free_tenant`), creates the database and the bucket, writes the root, and writes the access record
last; `services/sweep.py` drops at start-up any `{prefix}-t-…` database or bucket no record names.
The IRI policy (`domain/iris.py`, `Iris`) mints every tenant-scoped IRI from templates that hold
`{tenant}` or `{tenant_id}`; `effective_policy` and `policy_differences` already compare two
policies (start-up check, rp-iri-policy). The `Store` port (`services/store.py`) has no whole-dataset
read or write; `FusekiStore` (`adapters/fuseki.py`) speaks the dataset's `data` endpoint for
`put_graph`. `FakeStore` (`testkit/fakes.py`) keeps an rdflib `Dataset` per database.

## Goals / Non-Goals

**Goals:** the requirements of `specs/rp-tenancy/spec.md` and `specs/rp-aggregate-store/spec.md` of
this change.

**Non-goals:** the EPIC's No-gos; any HTTP route; any change in what `create`, the sweep or the
session do (`create` only shares `_new_record` and calls `free_tenant` by its public name, PD-6).

## Decisions

- **PD-1** (port): `Store.export_quads(dataset) -> bytes` (N-Quads of every named graph, one read)
  and `Store.import_quads(dataset, nquads: bytes) -> None` (adds the quads). `ToolkitStore` passes
  both through. Fuseki: `GET` on the dataset's Graph Store endpoint with `Accept: application/n-quads`,
  and `POST` there with `Content-Type: application/n-quads`; task 1.1 proved the endpoint is
  `/{ds}/data` (`DATA_ENDPOINT`, as `put_graph`; `/{ds}` behaves the same; a dropped dataset answers
  404, mapped to `DatabaseGone` by the existing status mapping): see
  `evidence/spike-fuseki-nquads.md`. Fake: serialise/parse its
  `Dataset` as `nquads`. Default graph: Fuseki's dataset `GET` returns the default graph's triples
  as three-term lines beside the named graphs' quads (TDB2, no union default graph); the toolkit
  never writes the default graph, so it is empty, and the export passes whatever is there through
  unfiltered. The fake does the same (it exports its default graph too), so the conformance suite
  pins one behaviour; restore refuses a default-graph quad (PD-5). Blank nodes pass through as
  N-Quads labels (loaded graphs keep them; `load_graph` does not skolemise), and the import gives
  them fresh store identities, so each graph comes back isomorphic, not label-equal.
- **PD-2** (DEC-8): `TenantDump` in `model/service/rp_service.yaml` (beside `IriPolicy`), slots:
  `format_version` (integer, `1`), `created_at` (datetime), `toolkit_version`, `schema_id` (uri),
  `schema_version` (optional string), `source_tenant` (uri), `source_tenant_id`, `label`,
  `iri_policy` (`IriPolicy`, the effective one). Generated with `make generate`; never hand-written.
  `label` is the access record's, for a human choosing a dump; restore does not use it (PD-5).
  `schema_version` comes from the running view today; once `schema-migrations` records a schema
  version per tenant, the manifest takes the tenant's recorded version instead (that change edits
  `dump`).
- **PD-3** (DEC-5): the archive is `tarfile` mode `w|gz` / `r|gz` (stdlib, streaming): member 1
  `manifest.json` (the model's JSON), member 2 `graphs.nq`, then one `blobs/<key>` per blob. Every
  member is a regular file (`member.isfile()`; a link, directory or device is refused). Restore reads
  in that order and never seeks back: the manifest and the N-Quads are read and checked before
  anything is created; each `blobs/` member is then read and `put` one at a time, after the database
  and bucket exist (PD-6). A wrong first or second member, or a bad archive before the blobs, is
  `InvalidBody` with nothing created; a bad member among the blobs (other name, not a regular file,
  truncated gzip) is `InvalidBody` raised inside `Tenancy.restore`, so PD-6's cleanup drops what was
  created.
- **PD-4** (DEC-2): `rewrite(dataset, base, old_id, new_id) -> Dataset`, a pure function in
  `services/tenant_dump.py`: for each quad, each `URIRef` among graph, subject and object that starts
  with `base` gets, in the text after `base`, every occurrence of `old_id` that is delimited on both
  sides by a character outside `[a-z0-9]` or by the IRI's end replaced by `new_id`. Predicates,
  datatypes, literals and blank nodes are untouched. There is no principal exclusion: the default
  `principal_template` `{issuer}/users/{sub}` has a free `{issuer}`, so a principal pattern also
  matches tenant IRIs with a `users` segment (an aggregate under `rp_path` `users`; `users` is not a
  layout word) and would leave their subjects and objects on the old id while their graph names move
  (gate 1, finding 1). A principal IRI under `base` whose `sub` equals the source tenant id is
  rewritten instead (RISK-3). Why delimiters, not `/` segments (gate 1, finding 2): the template
  patterns admit `/ : . -` between variables, so valid policies such as `{base}{tenant_id}-{id}` or
  `{tenant}.meta` put the id next to `-` or `.`; a delimited match covers them with the same code. A
  template that glues the id to a letter, digit or another variable cannot be rewritten safely, so
  `glued_templates(policy) -> list[str]` (same module) names every effective template in which the
  character before `{tenant_id}`, or after `{tenant_id}` or `{tenant}`, is in `[a-z0-9]` or is another
  variable; restore refuses such a policy first (PD-5).
- **PD-5** (DEC-10): checks, all before any create: format version; `schema_id`/`schema_version`
  against the loaded schema view (`view.schema.id`, `view.schema.version`); policy via
  `policy_differences(manifest.iri_policy, iris.effective_policy)`; `glued_templates` of the
  service's effective policy is empty (PD-4); after the rewrite, every quad's graph is
  `iris.meta(T')`, `iris.registry(T')`, or one `iris.is_aggregate_graph(T', g)` or
  `iris.is_loaded_graph(T', g)` accepts; no quad in the default graph; the root (subjects of `T'` in
  `meta(T')`) decodes with the mapper into the tenant-root class and the root validators accept it
  (old `None`, who = the restorer). The new tenant's label is the decoded root's, never the
  manifest's (gate 1, finding 3): `Tenancy.rename` writes the root before the record, so a rename
  cut between the two leaves the record's label stale while the root holds the new one; taking the
  root's keeps such a tenant restorable, and the root is the data the restored tenant answers from.
  Failure: `InvalidBody` with the reason.
- **PD-6** (DEC-1, DEC-4): `Tenancy.free_tenant()` is the public name of today's `_free_tenant` (one
  caller, `create`, renamed with it); `restore` in `tenant_dump.py` draws `T'` with it before the
  rewrite, which needs the new id. `Tenancy.restore(tenant, data, label, blobs, creator)` takes that
  `T'`, the rewritten `Dataset`, the root's label, an iterator of `(key, bytes)` read from the archive
  one member at a time, and the restorer: create database and bucket, `import_quads`, `put` each blob
  as the iterator yields it, then, before the record, check that the database is still in
  `list_datasets()` and the bucket in `list_buckets(prefix)` (a start-up sweep elsewhere may have
  dropped them during a long restore, gate 1 finding 4); if either is gone, raise
  `PersistenceError("the new tenant's database or bucket vanished during the restore")`. Then write
  the access record built as in `create` (`creator_role` for the restorer), `active`. On any
  exception after the database exists (the vanished check included): best-effort `drop_dataset` and
  `delete_bucket` (each failure logged, step `restore-cleanup`), then re-raise. The record-building
  lines are shared with `create` by extracting `_new_record(tenant, name, label, creator)`. A draw
  that `free_tenant` judged free can be taken by a concurrent `create` before the database exists;
  `create_dataset` then fails and nothing is written, as for two concurrent creates today.
- **PD-7** (DEC-9): `dump`: `get` the record (`NotFound`), `Conflict` if `deleting`; `export_quads`
  once; `list_blobs`; for each, `get` (a `NotFound` is logged, step `dump-blob-gone`, and skipped).
  Blob bytes are written one at a time; the N-Quads are one `bytes` (shortcut: in memory; upgrade
  to streaming when a tenant outgrows memory, named in the code). The manifest's `label` is the
  record's (PD-2); restore takes the root's (PD-5).
- **PD-8** (DEC-6): `ServiceKit.dump_tenant(tenant: str, out: BinaryIO) -> TenantDump` and
  `ServiceKit.restore_tenant(src: BinaryIO, creator: str) -> TenantSummary`, docstrings like
  `sweep_tenant`'s; both exported from the public API (`test_public_api.py`).

- **PD-10** (as built, task 3.1; the design was silent): `Tenancy.vet_restored_root(tenant, graph,
  restorer) -> label` decodes and validates the root, because the mapper, root class and validators
  are `Tenancy`'s; `toolkit_version` comes from `importlib.metadata` (`"unknown"` when not installed),
  since `services` may not import the top-level package; the manifest is also refused when
  `tenant_id_of(source_tenant) != source_tenant_id` (an empty or odd id would make `rewrite` match
  everywhere); the cleanup ignores a `NotFound` drop (never created or already gone) and catches
  `Exception`, not `BaseException`, so a cancelled restore leaves its orphans to the start-up sweep;
  `dump` takes a keyword-only `clock`; the public API exports `TenantDump` (the kit methods ride on
  `ServiceKit`).
- **PD-11** (task 4.2 finding): only the dump is routed behind `require(..., Action.ADMINISTER)` on
  the tenant. A restore has no tenant yet, so `require` cannot guard it: the consumer verifies the
  caller with `gate.caller`, applies its own rule on who may create a tenant, and passes
  `caller.principal` as `creator` (the `restore_tenant` docstring and the how-to say so).
- **PD-12** (adversarial tester after 3.1; accepted findings). A restore refuses with `InvalidBody`,
  cleaning up as PD-6 when the database already exists, and never writes the record:
  F1, an archive whose gzip stream does not end with its end-of-stream marker (CRC and length
  checked), even when it is cut exactly at a member boundary (what a dump that failed half-way, or a
  truncated upload, leaves); the gzip stream is read to its end before the record is written.
  F2, a blob key with a `..` or `.` path segment. F3, two blob members with the same key.
  F4, a member name that is not valid UTF-8. Kept as is (design silent, not a defect): a subject or
  object naming another tenant's IRI inside an accepted graph is restored verbatim, never rewritten
  (PD-5 checks graph names only); an id in an IRI's query or fragment moves with the path.
- **PD-13** (stage review, PR #89; the lead's decisions on the findings). Accepted:
  - *Decompression budget* (L1 C1, L4 C1): restore charges `member.size + tarfile.BLOCKSIZE` per
    member against a total budget, checked from the header **before** each read, and refuses past
    it with `InvalidBody`, nothing created when the overflow is before the blobs. The budget is a
    new `ServiceSettings` slot `max_restore_bytes` (LinkML, `make generate`; default 1 GiB), passed by
    `ServiceKit.restore_tenant` as `restore(..., max_bytes=...)`; `max_body_bytes` is not reused. The
    manifest has its own cap, `MAX_MANIFEST_BYTES = 64 KiB`. The parsed N-Quads bytes are released
    once parsed. RISK-2 stays for honest tenants; this bounds hostile ones.
  - *End marker* (L4 W3, L1 S1): format v1 (unreleased) ends with an empty regular member `end`;
    `dump` writes it last, `restore` refuses an archive whose blobs are not followed by `end`, or
    that has anything after it, then drains the gzip stream (bounded by the budget) so its trailer
    is checked. The `tar.offset` / `fileobj.tell()` check is removed.
  - *Record write outside the cleanup* (L4 W1): `Tenancy.restore` writes the access record after
    the `try` whose `except` drops the database and bucket; a failed record write leaves orphans
    for the start-up sweep (RISK-6), never a record without its database.
  - *Checks owned by the writer* (L3 W1, S1): `rewrite`, `glued_templates` and the graph check move
    to a pure `domain/tenant_move.py` (no I/O); `Tenancy.restore(parsed, source_tenant_id, blobs,
    creator)` draws the tenant itself, rewrites, checks graphs, vets the root and
    writes; `free_tenant` and `vet_restored_root` become private again. `tenant_dump.py` keeps the
    archive: read, manifest checks, N-Quads parse, the blob iterator. Supersedes PD-6's
    `free_tenant` and PD-10's public `vet_restored_root`.
  - *One blob-key rule* (L1 W1): a pure `domain` function is the only key rule, used by the S3
    adapter, `FakeFileStore.put` (so the fake refuses as Garage does) and restore (as `InvalidBody`).
    The adversarial round-trip case with a newline key becomes a refusal case.
  - *Smaller*: `except (ParserError, ValueError)` around the N-Quads parse (L4 W2); one N-Quads
    format name, `media.N_QUADS`, everywhere (L3 S4, L4 W4); one log line per dump (`step="dump"`,
    tenant, blob count) and per restore (`step="restore"`, source tenant, new tenant), no content
    (L4 S5); `Conflict` (the drawn id was taken; retry) listed in `restore_tenant`'s docstring
    (L4 S6); the blocking reads and writes of `src`/`out` named in the kit docstrings and a
    `shortcut:` comment, as is the whole-blob read (L3 S5, L4 S8); `except ValueError` only in the
    root check (L4 S4); explicit "found" text in the member message (L4 S3).
  - *Restore trusts graph content* (L1 W2, the lead's choice; the developer may overrule): restore
    checks structure (graph names, the root, keys), not each aggregate against its shapes. The
    `restore_tenant` docstring and the how-to say: restore only archives your own deployment wrote
    or that come from a party you trust as much as a tenant creator.
  - *Tests* (L2 W1, W3-W8, S1, S2, S4): TC-13 checks parts and splits the policy check; Hypothesis
    settings `derandomize=True`; one assert per idea with a message; a dump changes nothing; a root
    that does not decode; the missing `glued_templates` rows; `PersistenceError` not `Exception`;
    `ToolkitStore` pass-through lines; graph diff in the conformance message; TC-23 names the
    database. Tests for the budget, the end marker and the record-write order.
  - *Docs* (L2 W2, S3, L3 W2, cold reader): the how-to and data-flows list every refusal cause and
    when cleanup applies; the architecture index lists the port's dataset-level Graph Store
    GET/POST, `Tenancy.restore` and the two kit calls; the how-to introduces `kit`, `t`, `path`
    and imports, maps each error to its HTTP status, says a restore makes a new IRI (links to the
    old one break), explains the two labels, says the toolkit has no write freeze (the consumer
    stops writes), says where a schema declares `version`, and links terms to their pages.
  Rejected: `creator` typed as the verified caller (L1 S4; the kit takes principal IRIs as strings
  everywhere); trimming error details (L1 S2, L4 S5; the caller uploaded the archive); CI on more
  Python versions (L4 W3 b; the end marker removes the dependency on tarfile internals); further
  splitting of `tenant_dump.py` (L3 S3).

## Algorithm / approach

## Algorithm / approach

```python
async def dump(tenancy, store, files, iris, view, tenant, out):
    record, _ = await tenancy.get(tenant)                         # NotFound
    if record.state == TenantState.DELETING: raise Conflict(...)
    quads = await store.export_quads(record.database_name)
    manifest = TenantDump(format_version=1, schema_id=view.schema.id, ...,
                          source_tenant=tenant, source_tenant_id=iris.tenant_id_of(tenant),
                          label=record.label, iri_policy=iris.effective_policy)
    with tarfile.open(fileobj=out, mode="w|gz") as tar:
        add(tar, "manifest.json", manifest.model_dump_json().encode())
        add(tar, "graphs.nq", quads)
        for blob in await files.list_blobs(record.database_name):
            add(tar, f"blobs/{blob.key}", await files.get(...))   # NotFound -> log, skip
    return manifest

async def restore(tenancy, iris, view, src, creator):
    with tarfile.open(fileobj=src, mode="r|gz") as tar:           # streaming, never seeks back
        members = iter(tar)
        manifest = read_manifest(tar, next(members, None))        # InvalidBody: name, isfile, model
        check_manifest(manifest, view, iris)                      # PD-5 first half, glued_templates
        quads = read_member(tar, next(members, None), "graphs.nq")
        tenant = await tenancy.free_tenant()                      # PD-6
        data = rewrite(parse_nquads(quads), base, manifest.source_tenant_id, iris.tenant_id_of(tenant))
        label = check_graphs_and_root(data, tenant, ...)          # PD-5 second half -> root's label
        blobs = (read_blob(tar, member) for member in members)    # InvalidBody inside: cleanup runs
        return await tenancy.restore(tenant, data, label, blobs, creator)   # PD-6
```

The N-Quads and the parsed dataset are held in memory once (shortcut, as PD-7); blobs are read and
`put` one at a time, so a blob is in memory only while it is written.

Worked example (default policy, base `https://ex.org/`, segment `libraries`):

| Source IRI | Restored IRI |
|---|---|
| `https://ex.org/libraries/9f1…` (root) | `https://ex.org/libraries/4c2…` |
| `https://ex.org/libraries/9f1…/books/a1…/graph` | `https://ex.org/libraries/4c2…/books/a1…/graph` |
| `https://ex.org/libraries/9f1…/books/a1…/graph/.well-known/genid/77…` | same, `9f1…` -> `4c2…` |
| `https://ex.org/libraries/9f1…/users/b7…` (an aggregate whose `rp_path` is `users`) | `https://ex.org/libraries/4c2…/users/b7…` |
| `http://purl.org/dc/terms/title` (predicate) | unchanged |
| `"see https://ex.org/libraries/9f1…"` (literal) | unchanged |

### Anti-patterns

| Don't | Do instead | Why |
|---|---|---|
| Rewrite with string replace over the N-Quads text | Rewrite parsed `URIRef` terms (PD-4) | Text replace also rewrites literals, predicates and ids glued to other characters |
| Write the access record before the data | Record last (PD-6) | A crash must leave only orphans the sweep drops |
| Build a dict for the manifest | The generated `TenantDump` (PD-2) | LinkML is the single source |
| Copy the dumped access record or grants | Build a fresh record (DEC-4) | Grants are deployment-specific |
| Add a new exception type | `InvalidBody`, `Conflict`, `NotFound` | The kit's callers already map them |
| Build SPARQL in the adapter | Use Graph Store `GET`/`POST` only | Adapters forward, they build no SPARQL (PD-3 of v1) |

## Error matrix

| Input | Result |
|---|---|
| Dump of an unknown tenant | `NotFound`; nothing written to `out` |
| Dump of a `deleting` tenant | `Conflict`; nothing written to `out` |
| Store unreachable during export | `StoreUnavailable` raised unchanged; `out` may hold a partial archive (the caller discards it) |
| Blob listed, gone before its read | skipped, logged `dump-blob-gone`; the dump succeeds |
| Archive not gzip/tar, first member not `manifest.json` or second not `graphs.nq`, either not a regular file | `InvalidBody`; nothing created |
| Service policy glues the tenant id to a letter, digit or variable (`glued_templates`) | `InvalidBody` naming the templates; nothing created |
| A member after `graphs.nq` not a regular file under `blobs/`, or the stream breaks among the blobs | `InvalidBody` (or the read error); database and bucket dropped (PD-6), no record |
| Database or bucket gone before the record is written (a start-up sweep ran meanwhile) | `PersistenceError`; what is left dropped (PD-6), no record |
| Manifest that does not validate against `TenantDump` | `InvalidBody` |
| Format version not `1` | `InvalidBody` naming it |
| Schema id or version differs | `InvalidBody` naming both values |
| Effective policy differs | `InvalidBody` naming the differing fields (`policy_differences`) |
| A quad in the default graph or a foreign graph | `InvalidBody` naming the graph; nothing created |
| No root, or the root fails to decode | `InvalidBody` |
| Root label differs from the record's (a rename cut between root and record) | restored; the new tenant takes the root's label |
| A root validator refuses | `InvalidBody` (its message) |
| `free_tenant` exhausts its draws | `PersistenceError` (unchanged) |
| Store or object store fails after the database exists | error re-raised; database and bucket dropped (best effort, failures logged); no record |
| Crash after the database exists | start-up sweep drops database and bucket (unchanged rp-tenancy) |
| An empty tenant (root only, no blob) | a valid dump; restores to a tenant with the root only |

## Risks / Trade-offs

- **RISK-1** — Fuseki's dataset-level N-Quads `GET`/`POST` behaves differently from expected
  (medium; high: it blocks the EPIC). Mitigation: task 1.1 proves it first; fallback is a `CONSTRUCT`
  per named graph and `put_graph` per graph, which the port already supports.
- **RISK-2** — a large tenant exhausts memory (low today; medium). Accepted: `shortcut:` comments
  name the limit; the how-to says to size memory to the tenant.
- **RISK-3** — a delimited token after `{base}` equal to the source tenant id is rewritten too: an
  object id equal to it, a principal IRI under `base` whose `sub` equals it, or (with 4-character
  hex-only tenant ids and UUID object ids) one 4-character group of a UUID (negligible with random
  ids of usual length; low impact). The rewrite is one deterministic function over every term, so
  references stay consistent: the restored aggregate or part gets a different id, the same
  everywhere. Where the result no longer fits the policy (a template word equal to the tenant id),
  PD-5's graph and root checks refuse the restore; nothing is corrupted silently. Accepted.
- **RISK-4** — a schema without `version` cannot tell two schema versions apart, so DEC-7 passes
  (medium; medium). Mitigation: the how-to tells consumers to declare `version`; `schema-migrations`
  makes it mandatory.
- **RISK-5** — a dump taken during writes holds a blob the graphs no longer name, or lacks one they
  name (low; low). Accepted (DEC-9); the live-tenant sweep removes the first kind.
- **RISK-6** — a restore takes minutes; a service instance that starts meanwhile runs the start-up
  sweep, which drops the restore's database and bucket because no record names them yet (medium on a
  multi-instance or restarted deployment; medium). Mitigation: PD-6 checks both still exist before
  writing the record and fails cleanly otherwise; a sweep between that check and the record write
  (milliseconds) is accepted. The how-to says: no deploy or restart during a restore.
- **Assumption** — the access record is the only tenant state outside the tenant's database and
  bucket. Checked: `Tenancy` writes only the record and the IRI policy record to the system database.

## Open Questions

None. Every question was answered as the leader's choice (proposal.md DEC-1 to DEC-10); the developer
may overrule them before the epic session.

## Gate record

- **PD-9** (clarity gate): gate 1 (2026-11-12): 7.5/10, findings folded in. Finding 1 → PD-4 (no
  principal exclusion), RISK-3, worked example, TC-08; finding 2 → PD-4 delimited match plus
  `glued_templates` refusal (PD-5), TC-07, TC-09; finding 3 → PD-5 label from the root, TC-25;
  finding 4 → PD-6 existence check, RISK-6, TC-26; finding 5 → PD-3 and the algorithm stream the
  blobs, TC-27; finding 6 → PD-6 `free_tenant` and the `restore` signature; finding 7 → PD-1, TC-01;
  finding 8 → PD-2. EPIC and spec edits are logged under "Re-shaped 2026-11-12" in proposal.md.
