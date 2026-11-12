# Seed (secondary; never groomed)

Raised while shaping `tenant-root-loads` (see its inputs/seed.md):

> "an application has one database for application metadata and control, but then it has other
> databases under its governance and each database represents a project ... we cannot distinguish
> between app-project, and space within app governance, which includes also other
> databases/triplestores ... we shall be able to simply provide a triplestore dump as nquads, for
> example, and then you load it into a new project and restore its state." (developer, 2026-11-10)

The developer chose to record this need as a candidate EPIC (2026-11-10).

## Leader's recommendations (2026-11-12)

The developer was away and had accepted recommendations by default for the tenancy candidates; the
leader answered each open question. Each answer is a DEC in `../proposal.md` marked "leader's
choice"; the developer may overrule any of them.

- Q-1 (new tenant or over an existing one) -> a new tenant only (DEC-1): creation's crash-safe order
  is reused; replacing = delete, then restore.
- Q-2 (rewrite IRIs or keep them) -> rewrite the tenant-id segment in every IRI under `{base}`
  except principals; literals untouched (DEC-2); only between equal effective IRI policies (DEC-3).
- Q-3 (grants in the dump) -> no; the restorer is the only grantee, as on create (DEC-4).
- Q-4 (one archive or two streams) -> one gzip tar: `manifest.json`, `graphs.nq`, `blobs/<key>`
  (DEC-5). A bare N-Quads file is not accepted: no manifest, no tenant id, no schema version.
- Q-5 (HTTP, Python or both) -> Python only, routed by the consumer (DEC-6).
- Schema versions (with `schema-migrations`) -> record schema id and version in the manifest and
  refuse a mismatch until migrations exist (DEC-7).

Order among the four tenancy candidates: this one first. It needs nothing from the others, closes
the developer's explicit ask (dump as N-Quads, restore into a new project), and its port methods are
what a later move between stores (`tenant-stores`) would reuse.

## Test scenarios the EPIC must prove

- A library tenant with books, a book's loaded graph, a root loaded graph and a scan, dumped and
  restored by another principal, reads back the same (slot values, loaded graphs, scan bytes) under
  a new tenant IRI and the same label.
- The restored tenant takes a versioned replace; the original is unchanged.
- Only the restorer holds a grant on the restored tenant.
- Under a flat IRI policy, every restored IRI carries the new tenant id and the policy accepts it.
- A literal holding the old tenant's IRI is restored unchanged.
- Refused, with nothing created: another schema version, another IRI policy, a quad in a foreign
  graph, a root a validator refuses, an unknown archive member.
- Dumping a deleting tenant is a conflict; an unknown tenant is not found.
- A store failure during the import leaves no access record and no new database or bucket.
- On Fuseki: the export/import round trip, and the whole dump and restore of the toy library.
