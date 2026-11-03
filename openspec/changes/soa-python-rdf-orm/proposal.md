# EPIC: State of the art — Python RDF ORM and repository-pattern libraries

<!-- DRAFT — seeded from inputs/brief-2026-11-03.md; shaping questions still open. -->

## Appetite

MEDIUM (draft — to confirm).

## Why

rdf-persistence will offer developer-friendly persistence over triple stores: either a
model-first ORM (SQLAlchemy-like, CRUD + transactions handled) or a LinkML-generated domain plus a
cosmic-python repository layer. It must support rapid application development and be friendly to the JavaScript
ecosystem, in the spirit of mu.semte.ch / semantic.works. Before designing it we need to know
what existing Python libraries, RAD platforms and JS object mappers already do, which patterns
work, and what to reuse or avoid.

## Solution outline

Review three families: (A) Python ORM / mappers over RDF, (B) model → API RAD platforms
(mu.semte.ch, LinkedDataHub, Prez, grlc, GraphQL-over-RDF), (C) JS/TS object mappers (LDkit,
LDO, LDflex). Clone the candidate libraries as siblings of this repo, index them with GitNexus, and extract each
one's implementation principles. Score each on reuse of mature foundations (DEC-4), features, approach and design patterns, developer
friendliness and ease of implementation, weighted towards data-centric and domain-driven design.
Publish the review as Antora developer-docs pages.

## Key decisions

- **DEC-1**: Analysis is code-level (clone + GitNexus), not README-level — claims in docs are often
  aspirational; rejected: desk review of docs only.
- **DEC-2**: rdflib is the reference RDF stack; candidates are judged on SPARQL 1.1 (query +
  update) portability; rejected: store-specific APIs as a baseline.

- **DEC-3**: The review covers RAD platforms and JS clients, not only Python ORMs — the target is
  a mu.semte.ch-like developer experience reachable from JS; rejected: Python-only scope.

- **DEC-4**: Do not reinvent the wheel — rdf-persistence builds on mature, maintained
  foundations: rdflib (model, parsing, serialisation incl. JSON-LD, in-memory store),
  pyoxigraph (transactional store), and existing SPARQL 1.1 clients (SPARQLWrapper, rdflib's
  SPARQLStore/SPARQLUpdateStore). Our code is only the ORM / repository / unit-of-work layer on
  top. The review therefore scores each candidate on how well it *reuses* these foundations, and
  flags any mature library we should adopt or extend instead of writing our own; rejected:
  own RDF model, parser, store or SPARQL client (developer, 2026-11-03).

- **DEC-5**: Reuse threshold — a library qualifies as a dependency to build on when its
  repository has > 200 GitHub stars AND a commit within the last 12 months. A package published
  from a qualifying project's org or monorepo (e.g. oxrdflib under oxigraph, linkml-runtime
  under linkml) inherits that standing. Libraries below the threshold are studied for design
  ideas only, never taken as dependencies (developer, 2026-11-03).
- **DEC-6**: Two explicit inclusions in the review regardless of DEC-5 counts:
  (a) **Owlready2** — covers the ontology world (OWL classes as Python classes, reasoning)
  alongside the linked-data world (RDF/SPARQL); canonical repo on Bitbucket, active 2026;
  (b) **semantic.works (formerly mu.semte.ch, GitHub org `mu-semtech`)** — the reference RAD
  architecture; its stars are spread over ~55 small repos, so DEC-5 undercounts it
  (developer, 2026-11-03).

- **DEC-7**: The review maps the **whole building-block chain of the MWBv2 approach**
  (inputs/brief-2026-11-03-mwb2-scope.md): modelling (UML/model2owl, LinkML) → generated Python
  backend (domain + persistence + authorization) → generated data-management service →
  modern JS/TS clients consuming JSON-LD. Purpose: give the developer the full map of what
  exists so the build-vs-reuse decision can be taken afterwards (developer, 2026-11-03).
- **DEC-8**: Authorization (ACL / RBAC, graph-level and ideally triple-level) is **never
  reinvented**: existing engines, store-native policies, proxies and identity providers
  (e.g. Zitadel) are surveyed and borrowed; preference for a declarative, SPARQL-like or
  data-centric policy language (as in Fluree policies or semantic.works sparql-parser). The
  persistence layer must be **ACL-agnostic** — it can run behind an authorizing proxy or with a
  pluggable policy enforcement point (developer, 2026-11-03).
- **DEC-9**: Analysis is iterative — after the per-library rounds, further passes add new
  analysis angles across all candidates until a pass yields nothing new (developer, 2026-11-03).

- **DEC-10**: The SoA goes beyond persistence: it must equip the developer to **craft several
  variants of system architecture and development approach** (e.g. Python ORM over any SPARQL
  store + JSON-LD API; semantic.works-style microservices behind an authorizing SPARQL proxy;
  data-centric DB with native policies such as Fluree; generated Hydra/JSON-LD API platform;
  Solid/LDP). Building blocks are mapped on layers — L0 modelling & codegen, L1 domain &
  persistence, L2 stores & transactions, L3 identity & authorization, L4 data-management
  service / API, L5 JS client & UI, L6 change events — and each variant is composed from them
  with trade-offs (developer, 2026-11-03).

- **DEC-11**: End goal: a **coherent ecosystem of existing and new components** for an
  architecture that is easy to use and to maintain. Candidates are additionally scored on
  composability / ecosystem fit (C9) and maintainability & operability (C10)
  (developer, 2026-11-03).

- **DEC-12**: The review is the basis for choosing and designing a library **developers love**:
  every candidate gets a developer-experience (DX) deep-dive and score (shortest CRUD example,
  concepts to learn, typing, error messages, footguns) (developer, 2026-11-03).

- **DEC-13**: The review answers the **DDD consistency-boundary question**: which classes change
  together in one transaction (aggregates), which are decoupled through messages / domain events
  (eventual consistency), how mainstream ORMs (SQLAlchemy session, JPA persistence context,
  Spring Data JDBC aggregates, Ecto changesets, Django) handle multi-object transactions, and
  whether Unit of Work and the other cosmic-python patterns are needed — or better alternatives
  exist (developer, 2026-11-03).
- **DEC-14**: Property-graph (Neo4j / openCypher / GQL) support is a **side question**: assess
  how hard it would be to support property graphs behind the same ports; focus stays on triple
  stores (developer, 2026-11-03).

## Rabbit-holes

- Scoring every abandoned toy project — keep a short list with an inclusion rule.
- Running each library end-to-end against a live store — code reading first, spikes only if a
  score hinges on it.

## No-gos

- *Implementing* ACL / RBAC in this change (DEC-8: survey and borrow only; the library stays
  ACL-agnostic).
- Writing any rdf-persistence implementation code in this change.
- Graph databases with their own non-SPARQL query model (TypeDB, Atomic Server, TerminusDB,
  Fluree) beyond a short benchmark note.
- Ontology-authoring libraries (owlready2, funowl) beyond a short note.

---

## What Changes

- Antora developer-docs component with the state-of-the-art review pages: method, feature
  taxonomy (single groomed place), per-library findings, building-blocks map (L0–L6),
  architecture variants.

## Capabilities

### New Capabilities

- `soa-review`: the acceptance criteria of the review's documentation deliverable (build-versus-
  reuse decision support, evidence-backed findings, open decisions kept open).

### Modified Capabilities

## Impact

Docs only. Sibling clones live outside the repo (`../<lib>`).
