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

### Decisions from the developer's answers to the open questions

Source: `inputs/developer-answers-2026-11-03.md`. Consequences:
`docs/.../architecture/soa/decisions.adoc`; ADR status in `architecture/candidate-adrs.md`.

- **DEC-15**: **Triple-level access control stays a requirement**, alongside graph-level
  control. Fluree-style policies (data-centric, SHACL-like targeting) are the wanted style.
  Whether the triple-level evaluator may be built in-house (it is a small decision engine, which
  DEC-8 forbids) is **open** (developer, 2026-11-03).
- **DEC-16**: **Open W3C standards and classic triple stores** (GraphDB, Oxigraph, Fuseki,
  RDF4J and similar). No custom or non-standard databases; a commercial product only for very
  large value. **Fluree is not adopted** (variant V3 dropped) (developer, 2026-11-03).
- **DEC-17**: **The UI never accesses the triple store.** It talks only to the middleware,
  through REST or GraphQL APIs. Graph-direct reads from the UI (variant V5, ADR-04 option 4)
  are rejected (developer, 2026-11-03).
- **DEC-18**: **No compatibility with semantic.works** (variant V2 dropped). Its good features
  are reused as ideas or re-implemented (developer, 2026-11-03).
- **DEC-19**: **LinkML is the model master for now**; UML stays liked and may return as an
  upstream source later (ADR-03 option 2) (developer, 2026-11-03).
- **DEC-20**: **One named graph per aggregate**, named with the IRI of the aggregate root
  (ADR-09 option 2). Graph-level access control then works per aggregate (developer, 2026-11-03).
- **DEC-21**: **Commit policy `strict` by default** (one aggregate per commit); `warn` and
  `allow` stay available as configuration (ADR-12) (developer, 2026-11-03).
- **DEC-22**: **The aggregate version is mapper metadata**, not a domain field (ADR-13
  option 1). Version, like logging, provenance and annotations, is an orthogonal concern kept
  out of the domain classes. **New requirement:** several sets of annotations (discussions,
  comments, provenance, …) can be attached to any domain object (developer, 2026-11-03).
- **DEC-23**: **Events through both paths**: an in-process bus after commit and an outbox
  relayed to a message broker, ideally Redis-like (ADR-14 option 3, ADR-06 option 1)
  (developer, 2026-11-03).
- **DEC-24**: **No property-graph need and no run-time reasoning today** (DEC-14 closed; the
  seams stay because they cost nothing) (developer, 2026-11-03).
- **DEC-25**: **No migration generation in the first EPIC**, but it is a likely goal for
  maintainability; the design must keep it possible (ADR-16) (developer, 2026-11-03).

Round 2 (source: `inputs/developer-answers-2026-11-03-round2.md`):

- **DEC-26** (amends DEC-8): **Triple-level access control by both routes**, behind one
  `PolicyEnforcementPort`: GraphDB FGAC in pass-through where GraphDB is licensed (Meaningfy is
  a GraphDB partner), and a **thin in-house evaluator** over the change set and the generated
  queries for the open stores. Graph-level decisions stay borrowed (OpenFGA, pycasbin); only
  the triple-level evaluator is built (developer, 2026-11-03).
- **DEC-27**: **Both API styles**: REST first, GraphQL second. REST responses are **compacted
  JSON-LD** (plain JSON with an `@context`), so the UI gets JSON-LD; content negotiation also
  serves Turtle and N-Triples (ADR-04 option 1, then GraphQL) (developer, 2026-11-03).
- **DEC-28**: **Annotation sets are their own small aggregates** targeting the object; they do
  not count towards the `strict` policy of the annotated aggregate (developer, 2026-11-03).
- **DEC-29**: **The graph IRI is derived deterministically from the root's IRI** (one function,
  for example `<root>/graph`), not the root's IRI itself: it is as easy to manage and keeps
  statements about the graph apart from statements about the entity. The developer accepted the
  review's recommendation (developer, 2026-11-03).
- **DEC-30**: **Zitadel's AGPL and rdfproxy's GPL are acceptable** (developer, 2026-11-03).
- **DEC-31**: **No reasoning for now**, not even a build-time Owlready2 check (developer,
  2026-11-03).
- **DEC-32**: **Scope is library + generator + service kit** (ADR-01 option 2): rdf-persistence
  is the foundation on which MWBv2 is implemented (developer, 2026-11-03).
- **DEC-33**: **The access-rule vocabulary is built on SHACL** (targeting, SPARQL `ASK`
  conditions), with ODRL terms for actions and effects, validated by SHACL shapes and enforced
  by the thin evaluator of DEC-26. The ideas to carry into the design (Fluree, mu sparql-parser,
  Solid, OpenFGA) are listed in `decisions.adoc` (developer, 2026-11-03).

Round 3 (source: `inputs/developer-answers-2026-11-03-round3.md`):

- **DEC-34**: **Aggregate boundaries are declared in LinkML** with an `AggregateRoot` mixin from
  a shared rdf-persistence schema on root classes and an `owned` annotation on owned slots;
  a slot whose range is another root is a reference. The build fails on two owners, owned
  cycles and owned children without IRIs (ADR-11) (developer, 2026-11-03).
- **DEC-35**: **Multi-valued slots are `list[T]` with set semantics**; `LangString` is a
  language map (ADR-15 option 1) (developer, 2026-11-03).
- **DEC-36**: **Shape-driven UI forms are wanted**: edit and view forms generated from the SHACL
  that LinkML emits (feature U4). LGPL and GPL front-end components are acceptable because the
  project will be open source. Candidates are shacl-form and RDForms; none is chosen yet
  (developer, 2026-11-03).

Round 4 (source: `inputs/developer-answers-2026-11-03-round4.md`):

- **DEC-37**: **Typed metamodel: a generated companion (`Person_`) per model class**, built on
  one runtime `Field` object. **Domain classes are never written by hand**: the domain package
  of a project built on rdf-persistence is generator output only, and a check forbids any
  other class there. Attaching fields at run time to hand-written classes is therefore not
  needed (developer, 2026-11-03).
- **DEC-38**: **Async only, for now.** One async API; no generated sync copy and no `run_sync`.
  Scripts, migrations and imports call it through `asyncio.run`; adapters for sync stores
  (rdflib, pyoxigraph) run each store call on a worker thread so the event loop is not blocked.
  A sync API can be added later if users need it (developer, 2026-11-03).

Clarification (source: `inputs/developer-clarification-2026-11-04-mwbv2.md`):

- **DEC-39**: **MWBv2 is the Mapping Workbench v2**, Meaningfy's application for XML-to-RDF
  mappings. **rdf-persistence is the technology stack for developing it rapidly**: library,
  generator and service kit (DEC-32). MWBv2 lives in its own repo and depends on this one;
  generic capabilities belong here, mapping-specific ones in MWBv2 (developer, 2026-11-04).

Left open by the developer, with the review's recommendation recorded in `decisions.adoc`:
the design of the core (ADR-07), runtime or generated mapping (ADR-08), how aggregate
boundaries are declared in LinkML (ADR-11), the typed metamodel, list or set for multi-valued
slots (ADR-15; either is acceptable), repository or session, the reuse threshold for services
and UI components, and stores without atomic commits (ADR-10).

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
