<!-- Parents: openspec/specs/rp-tenancy (each tenant is one database and one bucket; create writes the
     access record last), rp-iri-policy (IRIs carry the tenant id; the policy is fixed per deployment),
     rp-file-store; the developer's need in inputs/seed.md. -->

# EPIC: Dump a tenant and restore it into a new one

> Shaped 2026-11-10; open questions answered by the leader on 2026-11-12 (inputs/seed.md, "Leader's
> recommendations"); the developer may overrule any DEC marked "leader's choice". First of the four
> tenancy candidates (`tenant-dump-restore`, `app-level-data`, `tenant-stores`, `second-store`); its
> PLAN (design.md, tasks.md) is derived.
>
> **Re-shaped 2026-11-12** (clarity gate 1, design.md PD-9): DEC-2 drops the principal exclusion
> (the default principal template also matches tenant IRIs with a `users` segment) and replaces the
> id wherever it stands between delimiters, not only as a whole `/` segment; a policy that glues the
> id to a letter, digit or variable is refused. DEC-10 and the rp-tenancy spec: a bad member among
> the blobs is found after the tenant's database exists (blobs stream one at a time), so it is
> refused with the new database and bucket dropped, not "before anything is created"; the new
> tenant's label is its root's. Segment-collisions rabbit-hole updated to match.

**Golden-thread parent:** capability `rp-tenancy` (each tenant is one database and one bucket, the
access record written last), and the developer's need (2026-11-10): "provide a triplestore dump as
nquads ... load it into a new project and restore its state".

## Appetite

**MEDIUM.** One new capability (dump and restore of one tenant) with its tests and docs. The `Store`
port gains two methods (export and import a whole database as N-Quads); tenancy gains two
operations; one generated record (the dump's manifest). No new container, no HTTP route.

## Why

A project cannot be backed up, copied or moved as a whole. Its state is spread over the tenant's
named graphs (root, aggregates, `meta`, `registry`, loaded graphs) and its bucket, and nothing writes
them out or reads them back. Because every IRI the toolkit mints carries the tenant id, a plain
N-Quads load into a new tenant would be refused by the IRI policy on the first write.

## Solution outline

`dump_tenant` writes one archive: a manifest, every named graph of the tenant's database as N-Quads,
and every blob of its bucket. `restore_tenant` reads such an archive, checks it was made under the
same IRI policy and schema version, rewrites the tenant id in the IRIs to a freshly minted one, and
creates the new tenant the way `create` does (database, bucket, data, access record last), with the
restorer as its only grantee. The new tenant answers as the old one did, under its own IRIs.

```python
with open("library.rpdump", "wb") as out:
    await kit.dump_tenant(library, out)                 # graphs + blobs + manifest, one tar
with open("library.rpdump", "rb") as src:
    copy = await kit.restore_tenant(src, creator=principal_iri)   # -> TenantSummary, new IRI
```

## Key decisions

- **DEC-1** (Q-1; leader's choice, 2026-11-12, **confirmed by the developer 2026-11-13**: "restore
  target as you recommend"; restoring under the original IRI or across IRI policies is not now): restore always creates a
  **new** tenant; it never writes over an existing one. To replace a tenant, delete it and restore.
  Reason: creation already has a crash-safe order (record last, the start-up sweep drops what no
  record names), and no merge semantics are needed. Rejected: restore over an existing tenant (needs
  a merge or a wipe inside a live tenant, and a half-done restore would corrupt live data).
- **DEC-2** (Q-2; leader's choice): IRIs **are rewritten**. Every IRI term (graph name, subject,
  object; never a predicate, datatype or literal) that starts with the deployment's `{base}` has,
  after the base, each occurrence of the source tenant id that stands between delimiters (a
  character other than a letter or digit, or the IRI's end) replaced by the new tenant id; a policy
  that glues the id to a letter, digit or variable is refused (design PD-4). This covers the root, aggregates, parts, skolem IRIs, `meta`, `registry` and loaded graphs
  under any template, since every tenant-scoped template holds `{tenant}` or `{tenant_id}`
  (rp-iri-policy). Literals, including IRIs written inside them, are not rewritten. Reason: the
  restored tenant must pass "Only IRIs the policy would mint are accepted". Rejected: keeping the
  IRIs (a copy beside the original is impossible, and every write would be refused); a prefix
  rewrite (flat templates do not nest IRIs under the tenant IRI).
- **DEC-3** (Q-2 follow-up; leader's choice): restore refuses a dump whose recorded **effective IRI
  policy** differs from the target's (the comparison the start-up check already makes), naming the
  differing fields. So a dump moves between tenants of one deployment, or between deployments with
  the same policy (base and deployment slug included). Reason: then the rewrite is the tenant id
  alone. Rejected: re-minting IRIs across policies (a template-to-template mapping; cut, see No-gos).
- **DEC-4** (Q-3; leader's choice): grants and prohibitions are **not** dumped. The restorer becomes
  the only grantee, with the settings' `creator_role`, as on `create`. Reason: the access record
  lives in the system database, not the tenant's, and principals and roles differ between
  deployments. Rejected: dumping the record (would carry grants to principals who may not exist or
  must not have access to the copy).
- **DEC-5** (Q-4; leader's choice): **one archive file**, a gzip tar with `manifest.json` first, then
  `graphs.nq` (plain N-Quads, readable by any triple store tool), then `blobs/<key>` per blob.
  Reason: one file to move and to keep; the N-Quads inside stay what the developer asked for.
  Rejected: two streams (they can be separated; a backup must not). Rejected: accepting a bare
  N-Quads file without manifest (the toolkit could not know the source tenant id, the policy or the
  schema version; cut).
- **DEC-6** (Q-5; leader's choice): **Python only**: `ServiceKit.dump_tenant` and
  `ServiceKit.restore_tenant`, unguarded like `sweep_tenant`; the consumer routes them and decides
  who may (the how-to recommends `administer` on the tenant for a dump). Reason: archives are large,
  and who may copy a project is the consumer's policy. Rejected: a generic HTTP route (request size
  limits, streaming responses and access policy in one go; a later change if asked).
- **DEC-7** (schema-migrations interaction; leader's choice): the manifest records the schema's `id`
  and `version` (LinkML `version`, may be absent), the toolkit version and a format version (`1`).
  Restore refuses a dump whose schema `id`, `version` or format differ from the running ones, until
  `schema-migrations` can migrate a restored tenant. Reason: data under another schema would surface
  only when a replace fails its shapes. Rejected: restoring anyway with a warning.
- **DEC-8**: the manifest is a LinkML class (`TenantDump`), generated and read through its model
  (D-13, PD-24, AGENTS.md). The archive layout is a contract, documented with its format version.
- **DEC-9** (consistency; leader's choice): the graphs are exported in one read of the store, so they
  are mutually consistent; blobs are copied after, as found. A blob deleted between the listing and
  its read is skipped and logged. For an exact copy the consumer stops writes first. Rejected: a
  snapshot across store and bucket (no such primitive; see No-gos).
- **DEC-10** (restore checks, trust boundary): before anything is created, restore checks the format,
  schema and policy (DEC-3, DEC-7), that every quad is in a named graph the policy mints for the new
  tenant (its `meta`, `registry`, an aggregate graph or a loaded graph), that the root decodes into
  the schema's tenant-root class and passes the consumer's root validators (as `create`), and that
  the manifest and N-Quads members come first, in order. Any failure is `InvalidBody` and nothing is
  created. A bad member among the blobs (another name, not a regular file) is `InvalidBody` too,
  found while the blobs stream in, and the new database and bucket are dropped. Each aggregate is not re-validated against its shapes (cut: the dump came from a toolkit
  of the same schema).

## Rabbit-holes

- **Size.** The graphs are held in memory once (rdflib, for the rewrite); blobs stream one at a time.
  Enough for the tenants known today; streaming the graphs is cut and named in the code
  (`shortcut:`) and in the how-to.
- **Fuseki's dataset endpoints.** Export uses the Graph Store `GET` on the dataset with N-Quads and
  import a `POST` of N-Quads; the first PLAN task proves both on the container before anything
  builds on them.
- **A crash during restore** leaves a database and bucket that no record names: restore drops them
  on a failure it sees (best effort), and the start-up sweep drops what a crash leaves (rp-tenancy).
- **Id collisions.** An object id, or a principal's `sub`, equal to the source tenant id would be
  rewritten too. With random ids from separate specs this is negligible; the rewrite is the same
  everywhere, so references stay consistent; it is accepted (design RISK-3).

## No-gos

- Restoring over an existing tenant, or merging a dump into one.
- Incremental or continuous backup; point-in-time recovery; a consistent snapshot of graphs and
  blobs together.
- Restoring across different IRI policies or base IRIs; moving a tenant while keeping its IRIs
  (a later change, if `tenant-stores` needs it).
- Rewriting IRIs inside literals.
- A bare N-Quads import, an HTTP route, or a CLI.
- Dumping grants, prohibitions, the application's own data (`app-level-data`) or the system
  database.
- Migrating a dump from another schema version (`schema-migrations`).

---

## What Changes

- `rdf_persistence/services/store.py`: the `Store` port gains `export_quads` and `import_quads`;
  `adapters/fuseki.py`, `testkit/fakes.py` and the store conformance suite follow.
- `rdf_persistence/model/service/rp_service.yaml`: the `TenantDump` manifest; regenerated code.
- `rdf_persistence/services/tenant_dump.py` (new): dump, check, rewrite, restore.
- `rdf_persistence/services/tenancy.py`: a restore entry that shares create's order.
- `rdf_persistence/entrypoints/kit.py`: `dump_tenant`, `restore_tenant`.
- Docs: a how-to (dump, restore, limits, the archive format) and a `questions.adoc` entry.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `rp-tenancy`: a tenant can be dumped and restored into a new tenant (ADDED requirements).
- `rp-aggregate-store`: the `Store` port exports and imports a database as N-Quads (ADDED
  requirement).

## Impact

- The `Store` port grows by two methods: a consumer's own `Store` implementation must add them
  (none known besides the toolkit's); **BREAKING** for such an implementation only.
- The archive format becomes a public contract (format version 1).
