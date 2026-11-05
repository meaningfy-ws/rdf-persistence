# Scoring rubric — SoA review (change: soa-python-rdf-orm)

Each library is scored 0–5 per criterion (0 = absent, 1 = toy, 3 = usable with gaps,
5 = exemplary). Every score MUST cite evidence: a file:line in the clone, a GitNexus finding
(symbol / process / cluster), or a documentation URL. Claims from READMEs/docs that the code
does not back are marked "claimed, not found in code".

| # | Criterion | What 5 looks like |
|---|---|---|
| C1 | **Feature coverage** | Full CRUD, relationships (1-1, 1-n, n-m, inverse), query API, transactions / unit of work, identity map, named graphs, lang-tagged & typed literals, JSON-LD in/out, validation (SHACL / schema) |
| C2 | **Approach & design patterns** | Clear, named patterns (Data Mapper vs Active Record, Repository, Unit of Work, Identity Map, Session, Query Object, lazy loading); persistence concerns separated from domain objects |
| C3 | **Developer friendliness** | Typed, discoverable API; short happy path; good errors; IDE support; docs with tutorials + reference; examples |
| C4 | **Ease of implementation / adoption** | Small dependency footprint, simple install/config, works with in-memory and remote stores out of the box |
| C5 | **Reuse of mature foundations** (DEC-4/5) | Builds on rdflib / pyoxigraph / SPARQLWrapper / LinkML / pydantic instead of re-implementing RDF model, parsers, stores, SPARQL clients |
| C6 | **Data-centric & DDD fit** | Model-first (LinkML / ontology / schema → domain), domain objects free of persistence code, repository-per-aggregate possible, cosmic-python layering possible |
| C7 | **SPARQL 1.1 portability** | Works against any SPARQL 1.1 Query + Update endpoint (and Graph Store Protocol); no store-specific API lock-in |
| C9 | **Composability / ecosystem fit** (added round 3) | Speaks open standards (SPARQL 1.1 protocol/update/GSP, JSON-LD, SHACL, LinkML, OIDC/JWT, RDF/JS); swappable behind a port; no lock-in |
| C10 | **Maintainability & operability** (added round 3) | Small surface, stable API/semver, simple deployment, upgrade path, observability |
| C8 | **Health** | Tests + CI, coverage, code size sane, recent activity, >1 maintainer, licence clear |

Also record (not scored): **JS-friendliness** — does it expose / generate an HTTP contract
(JSON:API, JSON-LD, GraphQL, OpenAPI) or TS types that a JavaScript client can consume.

## Purpose and origin (required from round 4; developer, 2026-11-03)

Every report MUST carry a `## Purpose and origin` section: what the tool is FOR (the problem it
was built to solve), WHO built it and in which context (project, institution, product), its
design ANGLE (ontology-first, schema-first, API-first, client-first, store-first,
publishing-first, app-platform, …), and therefore WHERE it could fit in our layers L0–L6 —
or why it does not fit at all. The leader keeps the groomed register in one place:
`docs/modules/ROOT/pages/architecture/soa/catalogue.adoc`.

## Per-library report shape

```
# <library>
- Repo / commit analysed / licence / size (files, LOC) / GitNexus index stats
- Docs read: <URLs and in-repo paths>
## Summary (3–5 lines)
## Architecture (from GitNexus: main clusters, key classes, execution flows) — with evidence
## Implementation principles (how mapping, identity, sessions/transactions, querying,
   serialisation actually work in the code) — with evidence
## Patterns catalogue (pattern → where in code)
## Docs vs code (claims confirmed / not found)
## Scores C1–C8 (table: score + one-line justification + evidence)
## JS-friendliness
## Reuse verdict for rdf-persistence: adopt / extend / borrow ideas / avoid — and which ideas
## Risks / anti-patterns observed
```

## Feature taxonomy — single source

The feature systematisation lives in ONE groomed place:
`docs/modules/ROOT/pages/architecture/soa/feature-taxonomy.adoc` (ids M*, I*, R*, L*, P*, Q*, S*,
X*, D*, O*, A*). Each report MUST include a `## Feature inventory` table: feature id → present /
partial / absent / n.a. → evidence. Features not in the taxonomy go under
`### Proposed new features` with a proposed id; the leader merges them into the taxonomy page.

## Method — iterative systematisation (developer, 2026-11-03)

1. **Round 1** — per-library deep analysis (GitNexus + docs), against taxonomy v0.
2. **Merge** — the leader merges every "Proposed new feature" into the next taxonomy version
   (v1, v2, …), deduplicating and assigning ids.
3. **Round 2..n — cross-check** — each newly added feature is studied across ALL the other
   libraries: how they handle it, or confirmation (with evidence of where it would be) that it
   is missing. Repeat until a round adds no new features.
4. The final taxonomy + matrix is the systematisation published in the Antora docs; later
   points of view (DDD fit, JS/RAD fit, reuse) are analysed over that matrix.
