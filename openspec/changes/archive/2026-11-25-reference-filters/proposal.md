<!-- Parents: issue #308 (inputs/seed.md); openspec/specs/rp-service-api (the listing),
     rp-aggregate-store (find); builds on consumer-gap-fixes DEC-5, DEC-6 and its design D-1 to D-3.
     Q&A: inputs/qa.md (2026-11-24). Serves (D-12): MWB2 v2-06-conceptual-mapping finding T-1
     (the CM list filtered by source version). -->

# EPIC: Listing filters through a reference

## Appetite

**MEDIUM**: one new capability (a filter path through references) in the listing and `find`,
with its tests and docs. The neighbours (the services model, the renderer, OpenAPI) are touched
lightly. It is one stage and one PR. It starts after `consumer-gap-fixes` stage 4 (#312, the
absent filter) has merged, because both change `Listings._filtered` and `condition_patterns`.

## Why

A listing filters only on the listed root's own slots (`slot=value`, `slot~=text`, and
`absent=slot` once #312 lands). A consumer that wants "the mappings whose source element has
version V" cannot ask for it. It would have to list the elements, then list the mappings for
each one, and the combined result can be neither paged nor counted correctly. MWB2 holds back its
source-version filter until the toolkit can do this (#308).

## Solution outline

- **A filter name may be a path.** `ref.slot` filters the listed aggregates by a slot of the
  aggregate their reference `ref` points to, for example
  `GET /mappings?has_source.has_source_version=<iri>`. Up to three references may be chained:
  `a.b.c.slot`. The last segment takes equality or contains (`~=`), as a root slot does.
- **Each hop is resolved against the model.** Every segment but the last must be a listable
  reference to an aggregate root in the same database. Its range class supplies the next
  segment's slots. A bad path is a 400 `bad-query`, as a bad slot name is today.
- **Each hop reads the referenced aggregate's own graph.** A value counts only where the
  referenced aggregate states it in its own named graph. In a listing, a crossed aggregate the
  caller may not read does not match.
- **`find` takes the same spelling**: `find(Book, **{"sequel_of.label": "Dune"})`.
- **One renderer.** `condition_patterns` renders a path condition, so the page, the count and
  `matches` agree.

## Key decisions

- **DEC-1:** the path rides on the existing model. `Filter.filter_slot` carries the dotted name
  unchanged. `Condition` gains `condition_via`, the ordered predicate IRIs of the hops. It is
  empty for a root slot, so a path-less condition is exactly today's condition (`make generate`).
  Rejected: a separate `PathFilter` class, which would be a second code path through `_filtered`.
- **DEC-2:** a path holds 1 to 3 hops (owner, Q1). A hop is a listable slot that is not owned and
  whose range is an aggregate root class (abstract allowed), but not the tenant root. The tenant
  root lives in the meta graph. The range class must also live in the listing's database
  (`database_of`) (Q6). The next segment is looked up among the range
  class's own listable slots, so a slot that only a subclass declares is refused (Q7).
- **DEC-3:** the last segment takes equality or contains. `absent=` with a path is refused with
  `BadQuery`, and so is `sort=` with a path (Q2, Q3).
- **DEC-4:** each path filter matches on its own: "some referenced aggregate satisfies it". Two
  filters through the same multivalued reference may be satisfied by different targets (Q4).
  This is documented.
- **DEC-5:** in a listing, a hop never lands in one of the caller's hidden graphs, the graphs a
  read Prohibition hides (`hidden_graphs`), which is what the listing already applies to roots. A root reached
  only through a hidden aggregate leaves the page and the `total` (Q5). `find` passes no hidden
  graphs and so still ignores prohibitions (PD-6).
- **DEC-6:** in `find`, a keyword with a dot is a path. It is passed as `**{"a.b": v}` (Q8), with
  no new API.
- **DEC-7:** OpenAPI gets no parameter per path. The listing operation's description and
  `reference/http-api.adoc` describe the syntax (Q9).
- **DEC-8:** one stage and one PR into `develop`. The EPIC lands with it (Q13).

## Rabbit-holes

- **Row duplication.** A multivalued reference with several matching targets would repeat the
  root in the page's `SELECT` (it has no `DISTINCT`) and break paging. A path condition must
  therefore render as `FILTER EXISTS { … }`, as contains does.
- **The graph of a hop.** The graph is `<target>/graph` (`graph_iri`, PD-4). Without that
  binding, a statement about the target that sits in some other aggregate's graph would match.
- **Stage 4 of `consumer-gap-fixes` lands first** and reshapes `condition_patterns` (D-2) and
  `_filtered`. This PLAN names its functions, so the builder re-reads them after the merge
  (RISK-1).
- **The reserved names** (`sort`, `limit`, `offset`, `absent`) are compared on the whole
  parameter name. A dotted name is never reserved, so `absent.x=1` is a path whose first segment
  is a slot named `absent`. Such a slot is not listable, so the answer is `BadQuery`.

## No-gos

- No sort through a reference.
- No reverse paths (filtering by what refers to the root).
- No path through an owned part, a `uri` slot or the other database.
- No absence through a path.
- No correlated semantics (DEC-4).
- No path fed to unique keys, guards or `matches` by the toolkit. The renderer can carry one;
  nothing builds one there.
- No change to how existing filters behave or render.

---

## What Changes

As delivered (one PR, see Reconciliation):

- Services model: `Condition.condition_via` (multivalued, ordered predicate IRIs), regenerated.
- Listing: a dotted filter name resolves hop by hop (`Listings._filtered` through `_resolved` and
  `_hop`), and `condition_patterns` renders a path condition through a new `hop_patterns` in
  `core/domain/sparql.py` (the PLAN's D-2 name; this outline said `path_patterns`). The listing
  passes its hidden graphs to it. `iris/domain/layout.py` gains `GRAPH_SUFFIX`.
- `Session.find`: a dotted keyword is a path (docstring only; no code).
- Reference collections: a membership rule refuses a path (design D-13), so the No-go "no path fed
  to guards or `matches`" holds.
- OpenAPI: every aggregate listing operation carries one description of the path syntax. Docs:
  `reference/http-api.adoc` ("Filters through references"), the `find` docstring, and the
  CHANGELOG ("Added").

## Capabilities

### Modified Capabilities

- `rp-service-api`: a listing filters through up to three references.
- `rp-aggregate-store`: `find` filters through a reference.

## Impact

`rdf_persistence/model/technical/persistence/rp_persistence_services.yaml` (regenerated, with the
shape snapshot and the served TypeScript golden gaining `via`), `persistence/services/listing.py`,
`persistence/services/session.py` (docstring only), `core/domain/sparql.py`,
`iris/domain/layout.py`, `iris/services/iris.py` (`GRAPH_SUFFIX`),
`collaboration/services/reference_collections.py` (D-13), `api/entrypoints/openapi.py` (and the
served OpenAPI golden), `docs/.../reference/http-api.adoc`, the CHANGELOG and the scenario map.
The consumer gets them after a release and its lock refresh, then offers its source-version filter.

## Reconciliation

| Shaped | Delivered | PR |
|---|---|---|
| DEC-1 `via` on `Condition`, one renderer | as shaped | #356 |
| DEC-2 1 to 3 hops, aggregate roots of one database, range's own slots | as shaped | #356 |
| DEC-3 equality and contains only; `absent`/`sort` refuse a path | as shaped | #356 |
| DEC-4 independent path filters | as shaped, documented | #356 |
| DEC-5 hidden graphs at every hop in a listing; `find` ignores them | as shaped | #356 |
| DEC-6 dotted keyword in `find` | as shaped, no code | #356 |
| DEC-7 one OpenAPI description, no parameters | as shaped; the cap is read from `MAX_HOPS` ("up to 3 references") | #356 |
| DEC-8 one stage, one PR | as shaped | #356 |
| No-go: no path fed to guards or `matches` | held by refusing a path in a membership rule (D-13), which the shape had not seen reaching them | #356 |

Nothing shaped was left out. The delivery decisions D-7 to D-13 and the review findings are in
`design.md`.
