> Derives from: EPIC `tenant-root-loads` (proposal.md). Implements DEC-1 to DEC-4.
> Type: Implementation.

## Context

`Session` (`services/session.py`) registers an aggregate's graphs in `T/registry`: one `Aggregate`
entry for `B/graph` and one `LoadedGraph` entry per loaded graph named in a commit
(`Session._entries`). For the tenant root `T`, whose graph is `T/meta` (`Session._graph`),
`_entries` returns `[]`, so a root load is accepted (`load_graph`, `_check_commit`) but never
registered (issue #73). `services/tenant_sweep.py` `_candidate_graphs` skips every graph whose
`Iris.loaded_graph_root` is the tenant, the only caller of `loaded_graph_root`.

Every reader and writer already works by registry entry and owner: `_registered_loaded(T)` reads
entries `ownedBy T`; `REPLACE` drops the owner's entries and unlisted loaded graphs, then writes the
listed ones; `loaded_graphs(T)` reads the version of `T/meta` (`_stored`) then the entries. So the
fix is in `_entries` alone, plus removing the sweep's skip.

## Goals / Non-Goals

**Goals:** the requirements of this change: "The tenant root's loaded graphs are registered"
(`specs/rp-aggregate-store/spec.md`) and "Orphans inside a live tenant are removed", as modified
(`specs/rp-tenancy/spec.md`).

**Non-goals:** the No-gos of the EPIC; any change to `REPLACE`, `REMOVE`, `ADD` or the listing
query.

## Decisions

- **PD-1** (DEC-1, DEC-2): `Session._entries(T, …)` returns one `LoadedGraph` entry per graph in
  `loaded_graphs`, owned by `T`, and no `Aggregate` entry. For any other aggregate it is unchanged.
- **PD-2** (DEC-3): `_candidate_graphs` keeps every graph `is_loaded_graph(tenant, g)` accepts;
  `Iris.loaded_graph_root` and its tests are deleted (no other caller).
- **PD-3** (DEC-4): no migration. A root load committed before the fix has no entry; the sweep
  reports it once it is older than the grace period, and removes it with `remove=True`. The
  consumer can re-register it instead by committing the root with it in `loaded_graphs`.
- **PD-4**: the tenant's other root writes need no change. Create (`Tenancy._add_root`) commits with
  no loaded graphs; the generic `PUT` (`Aggregates.replace`), rename (`Tenancy._relabel_root`) and a
  consumer's `UnitOfWork.commit` pass `loaded_graphs=None`, which `replace_graph` turns into the
  registered ones (`_registered_loaded`), now including the root's. (`Tenancy._replace_root` writes
  the access record on the system database, never `T`: the policy refuses an access template equal
  to the tenant, `Iris._require_distinct_graphs`.)
- **PD-5** (attack, note): `_graph` and `_entries` recognise the root by `str(iri) == str(self._tenant)`,
  so a session opened with a `URIRef` tenant and called with a plain string (or the reverse) still
  treats the root as the root. Today `URIRef("a") == "a"` is false and the root would get an
  `Aggregate` entry and graph `T/graph`.

- **PD-6** (gate): the second clarity gate scored the PLAN 8.7/10 with five gaps (root created
  first in the session tests; TC-02 on a world with a `Tenancy`; TC-10's session with `listings`;
  the two stale docstrings; a third integration test). The developer decided on 2026-11-10: fix
  all five and proceed without a third gate run. All five are fixed in tasks.md.

## Algorithm / approach

```python
def _entries(self, iri, graph, loaded_graphs):
    loaded = [RegistryEntry(graph=str(g), kind=RegistryKind.LOADED_GRAPH, owned_by=iri)
              for g in loaded_graphs]
    if str(iri) == str(self._tenant):   # the root's graph is meta: no Aggregate entry (DEC-2, PD-5)
        return loaded
    return [RegistryEntry(graph=str(graph), kind=RegistryKind.AGGREGATE, owned_by=iri), *loaded]
```

Worked example (default policy, `T = …/libraries/t1`):

| Step | Registry after |
|---|---|
| `load_graph(T, ttl)` → `g = T/content/u1` | `g rp:loadedAt t0` (marker) |
| `replace_graph(T, root, v1, loaded_graphs=[g])` | marker, `g rp:kind rp:LoadedGraph; rp:ownedBy T` |
| rename the tenant (`loaded_graphs=None`) | the same entry, re-written |
| `replace_graph(T, root, v3, loaded_graphs=[])` | no entry; `g` emptied |

### Anti-patterns

| Don't | Do instead | Why |
|---|---|---|
| Write an `Aggregate` entry for `T/meta` | Only `LoadedGraph` entries for the root (PD-1) | The listing query reads `Aggregate` entries; the root would join listings (DEC-2) |
| Compare the root with `iri == self._tenant` | `str(iri) == str(self._tenant)` (PD-5) | `URIRef("a") == "a"` is false; the root would be stored as aggregate `T/graph` |
| Special-case the root in `REPLACE`, `REMOVE`, `ADD` or `READ_LOADED` | Leave the templates as they are | They work by owner; the root needs only entries |
| Keep `Iris.loaded_graph_root` "in case" | Delete it with its tests (PD-2) | Its only caller is the skip this change removes; it was never released |
| Write anything else `ownedBy T` in the registry | Only loaded-graph entries own by `T` | A root replace drops every entry `ownedBy T` (`_DROP_ENTRIES`) |
| Migrate old root loads in code | Let the sweep report them (PD-3, DEC-4) | No consumer made any; a dry run shows them |

## Error matrix

| Input | Result |
|---|---|
| Root commit names `g` that another aggregate owns | `InvalidIri`, nothing written (unchanged `OWNED_ELSEWHERE`) |
| Root commit names `g` the policy does not mint for `T` | `InvalidIri`, nothing written (unchanged) |
| Root commit at a stale version | `Conflict`, nothing written (unchanged guard) |
| `loaded_graph(T, g)` for an unregistered `g` | `NotFound` (unchanged) |
| Sweep finds an unregistered root load older than the grace period | reported; removed only with `remove=True` |
| Under a policy whose loaded-graph template has no `{root}` | `is_loaded_graph` finds every load; ownership decides, as for aggregates (unchanged N1 test) |
| Same policy: a root commit names a load a book has committed | `InvalidIri` (`OWNED_ELSEWHERE`), nothing written |
| Root replace with `loaded_graphs=[]` | the root's loads emptied; a book's loads untouched (entries are scoped by owner) |
| Book replace with `[]`, or book remove | the root's loads untouched |
| `Session.remove(T, v)` (no route calls it; a consumer can) | now also empties the root's loaded graphs and drops their entries, as for any aggregate; before, only `meta` |
| `iri` and the session's tenant differ only as `URIRef` vs `str` | treated as the root (PD-5) |
| The store fails during a root commit | one update request: nothing written; the store's error (`StoreUnavailable`, `DatabaseGone`) is raised unchanged; nothing new is logged |

## Risks / Trade-offs

- **RISK-1** — a consumer relies on root loads being invisible (low likelihood: none known; low
  impact). Accepted: the behaviour was a defect (#73).
- **RISK-2** — a root load made before the fix, still wanted, is removed by a sweep with
  `remove=True` (low; medium). Mitigation: the dry run lists it first; the how-to says so (PD-3).
- **RISK-3** — an `rp_path` named `content` under the default policy makes a root load's IRI
  `T/content/<id>` also a valid aggregate IRI (low; low). No data collides: the aggregate's graph
  is `…/graph`, its own loads parse with itself as root, owners differ. Accepted; noted here.
- **RISK-4** — the races are the existing aggregate ones, not new: two commits naming the same
  graph both pass `OWNED_ELSEWHERE` (a read before the update); a sweep that empties an old root
  load just before a commit names it leaves a registered empty graph. The sweep's in-update
  `FILTER NOT EXISTS ownedBy` keeps sweep against commit safe. Accepted, as for aggregates.
- **Assumption** — nothing else in the registry is `ownedBy T`, or a root replace would drop it
  (`_DROP_ENTRIES`). Checked: only `session.py`, `tenant_sweep.py` and `listing.py` read or write
  `owned_by`.

## Open Questions

None.
