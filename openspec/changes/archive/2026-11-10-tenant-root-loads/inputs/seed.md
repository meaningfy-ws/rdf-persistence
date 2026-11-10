# Seeds and Q&A: tenant-root-loads (secondary; never groomed)

## Seed: issue #73 (verbatim summary)

`Session.load_graph(tenant_iri, ...)` accepts the tenant root (the policy treats it as an
aggregate), and a commit of the root with `loaded_graphs=[g]` passes `_check_commit`, but
`Session._entries` returns no registry entries for the tenant root. The loaded graph is therefore
never registered: `loaded_graph(tenant_iri, g)` raises `NotFound`; `loaded_graphs(tenant_iri)`
returns `[]`; `remove` and `replace_graph` do not drop it. Found by the PLAN attack of
`live-tenant-sweep` (F4), which made the live-tenant sweep skip loaded graphs whose root is the
tenant. Options in the issue: refuse root loads, or register them like any aggregate's.

## What the code does today (checked 2026-11-10)

- `services/session.py` `Session._entries`: `if iri == self._tenant: return []`.
- `services/session.py` `Session._graph`: the tenant root's graph is `T/meta`.
- `services/tenant_sweep.py` `_candidate_graphs`: drops graphs whose `loaded_graph_root` is the tenant.
- The only consumer, mapping-workbench-v2, calls `load_graph` only for ontology-file aggregates
  (`mwb2/services/files.py`), never for the tenant root.

## Q&A with the developer (2026-11-10)

- **Approach (Q-1).** First asked refuse vs register; the developer asked what it meant and raised a
  wider need (below). After the explanation: "the rdf files are just another file, and treated as
  such, but kept in a dedicated named graph. yes we can support these." **Answer: register the
  tenant root's loaded graphs like any aggregate's.**
- **Sweep (Q-2).** **Answer: drop the sweep's skip** of root loads; loads made before the fix are
  unregistered and are reported, removed only with `remove=True`.
- **Appetite and autonomy (Q-3).** **Answer: TINY; commit, push, PR and merge on green CI without
  asking.**
- **Scenarios (Q-4).** Picked when refusal was the option: root load refused, root commit refused,
  aggregates unaffected, old root loads swept. With Q-1 now "register", the first two become: a root
  load registered by a commit can be read back and listed; a replace of the root keeps or drops it.
  "Aggregates unaffected" and "old root loads swept" stand.

## The wider need the developer raised (recorded, out of this EPIC)

"an application has one database for application metadata and control, but then it has other
databases under its governance and each database represents a project ... we cannot distinguish
between app-project, and space within app governance, which includes also other
databases/triplestores ... we shall be able to simply provide a triplestore dump as nquads, for
example, and then you load it into a new project and restore its state."

Shaped as three candidate EPICs (developer's choice, 2026-11-10): `tenant-dump-restore`,
`tenant-stores`, `app-level-data`. Also mentioned and left open: loading an aggregate from an RDF
file into its own named graph, checked against the shapes ("that is why APIs are there, no?").
