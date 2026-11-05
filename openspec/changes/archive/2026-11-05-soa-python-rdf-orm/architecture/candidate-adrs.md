# Candidate ADRs

Change: `soa-python-rdf-orm` · task 6.5. Template: Meaningfy `ADR_TEMPLATE.md`. Grouped by C4
level. Each ADR traces to drivers (AD-*n*, K-*n* in [`business-context.md`](business-context.md))
and to the diagrams in [`c4-views.md`](c4-views.md). **Decision Outcome is "Open — for the
developer"** unless a DEC-*n* in `proposal.md` already decides it; options are presented, not
chosen. The developer's answers of 2026-11-03 (DEC-15…DEC-39) decide or narrow most of them; see
`docs/modules/ROOT/pages/architecture/soa/decisions.adoc`.

| Id | C4 level | Title | Status |
|---|---|---|---|
| ADR-01 | Context | Scope of the system: library only, or library + generator + service kit | Decided (DEC-32) |
| ADR-02 | Context | Where authorization is enforced | Decided (DEC-15, DEC-17, DEC-26) |
| ADR-03 | Context | Master of the domain model | Decided for now (DEC-19) |
| ADR-04 | Container | Contract between the service and the UI | Decided (DEC-17, DEC-18, DEC-27) |
| ADR-05 | Container | Store and transaction strategy | Partly decided (DEC-16) |
| ADR-06 | Container | Source and format of external change events | Decided (DEC-23) |
| ADR-07 | Component | Persistence pattern of the core | Open (constrained by DEC-4, DEC-13) |
| ADR-08 | Component | Mapping at runtime or generated | Open — recommendation recorded |
| ADR-09 | Component | Storage strategy of an aggregate (root + owned closure, or graph per aggregate) | Decided (DEC-20, DEC-29) |
| ADR-10 | Component | Behaviour on stores without atomic commits | Open — recommendation recorded |
| ADR-11 | Component | Declaring aggregate boundaries in the model | Decided (DEC-34) |
| ADR-12 | Component | Commit policy — aggregates per commit | Decided (DEC-21) |
| ADR-13 | Component | Where the version lives; optimistic concurrency by default | Decided (DEC-22) |
| ADR-14 | Component | Dispatch of domain events | Decided (DEC-23) |
| ADR-15 | Code | Multi-valued slots and language-tagged strings | Decided (DEC-35) |
| ADR-16 | Context | Migrations in the scope of the first EPIC | Partly decided (DEC-25) |

**Count.** Sixteen ADRs exceed the skill's 6–10 guideline. ADR-11 to ADR-16 were added for the
round-4 open questions (SoA:design-implications, angles ddd, dx, evolution); ADR-12 and ADR-13 could
be folded into ADR-09 once the developer prefers fewer, broader records.

---

## C4 Context — decisions

### ADR-01: Scope of the system — library only, or library + generator + service kit

#### Context and Problem Statement
The brief asks for an ORM or repository library (brief L6–L9), but also for a JSON-LD middleware
over the store (brief L11) and the full MWBv2 chain up to the JS UI (DEC-7, DEC-10). The
realisation matrix shows the biggest gaps outside the library: route/contract generator
(BL-10) and service kit (BL-11). Drivers: AD-1, AD-6, AD-8, AD-15.

#### Considered Options

##### Option 1: Library only
rdf-persistence ships L1/L2 (BL-1…BL-8). Services are hand-written per project.
- Good, because the scope is smallest and testable in isolation.
- Good, because it composes with any service framework.
- Bad, because every project rebuilds routes, contracts and conditional writes (AD-7 unmet).

##### Option 2: Library + companion packages (codegen templates, service kit)
Same core; separately versioned companions for approach B and the FastAPI kit.
- Good, because the MWBv2 chain is covered end to end (DEC-7).
- Good, because the core stays framework-free; companions can be dropped.
- Bad, because three packages must be versioned together.

##### Option 3: Integrated platform (generic service, approach C)
One deployable that serves any LinkML model at runtime, like mu-cl-resources.
- Good, because fastest start for RAD (AD-7).
- Bad, because weak typing for domain logic; competes with semantic.works rather than composing.

#### Decision Outcome
**Decided (DEC-32):** option 2. rdf-persistence is the library plus a generator and a service
kit, versioned as companion packages; it is the foundation MWBv2 is implemented on.

#### Consequences
- BL-9…BL-14 are part of the roadmap; the core stays framework-free and the companions depend on it, never the reverse.

#### Confirmation
Package layout and import-linter contracts: the core must not import the service kit.

---

### ADR-02: Where authorization is enforced

#### Context and Problem Statement
DEC-8 fixes that authorization is borrowed and the persistence layer is ACL-agnostic. It leaves
open *where* the enforcement point sits. Graph level is the only portable granularity (K-3);
triple level needs Fluree or GraphDB. Drivers: AD-11, AD-12. Diagrams: §5.2, L2 V1/V2/V3.

#### Considered Options

##### Option 1: Store-native policies (port in pass-through)
- Good, because triple level and data-centric policies (Fluree), closest to the wanted language.
- Good, because safe even for free SPARQL from clients.
- Bad, because vendor-specific; licence (BUSL) or commercial (GraphDB).

##### Option 2: Authorizing SPARQL proxy in front of the store
- Good, because transparent to the library; semantic.works ecosystem.
- Bad, because `sparql-parser` fails DEC-5, trusts headers, and breaks update atomicity (K-1).

##### Option 3: In-process enforcement port with an external decision engine
- Good, because portable across stores; engines pass DEC-5 (OpenFGA, SpiceDB, pycasbin).
- Good, because counts and single reads are scoped by construction.
- Bad, because graph level only; a scope translator must be built (BL-12); unsafe for free client SPARQL.

#### Decision Outcome
**Partly decided.** DEC-8: borrow, never build an engine; the library exposes a port and stays ACL-agnostic. DEC-17: the UI never sends SPARQL, so the in-process port (option 3) is safe and is the base mode; with DEC-20, graph scopes are aggregate scopes. DEC-15: triple level stays required. Option 2 (proxy) is dropped. DEC-26 (amends DEC-8): triple level by both routes behind one port — GraphDB FGAC in pass-through where GraphDB is licensed, and a thin in-house evaluator over the change set and the generated queries for the open stores. Graph-level decisions stay borrowed.

#### Consequences
- The library never stores policy; the port has three modes (pass-through, scope, change check).
- Mode choice fixes the variant: Option 1 → V3/V4, Option 2 → V2, Option 3 → V1/V5.

#### Confirmation
UC-W4 scenarios run for each mode in the conformance suite; a test proves counts are scoped.

---

### ADR-03: Master of the domain model

#### Context and Problem Statement
The MWBv2 chain is UML → model2owl → OWL/SHACL → LinkML (mwb2 L31). model2owl's LinkML export
needs fixes (mwb2 L29); schema-automator can import SHACL (SoA:angles/codegen). Which artefact is
edited by the Model Custodian decides round-trips and regeneration. Drivers: AD-5, AD-17, K-6.

#### Considered Options

##### Option 1: UML is master; LinkML is generated (via SHACL import)
- Good, because one curation point in Enterprise Architect; SEMIC conventions.
- Bad, because LinkML-only features (custom annotations for templates) must be expressible in UML or lost.

##### Option 2: Curated LinkML is master after the first import
- Good, because LinkML is developer-friendly and drives every target directly.
- Bad, because UML and LinkML drift unless a reverse check exists.

##### Option 3: UML master plus a LinkML overlay (annotations merged at build)
- Good, because keeps UML authority while letting developers annotate.
- Bad, because a merge step to build and maintain.

#### Decision Outcome
**Decided for now (DEC-19):** option 2, curated LinkML is the master. UML may return upstream later (then option 3, an overlay that keeps the mapper's annotations).

#### Consequences
- Option 1 or 3 keeps model2owl as a quality gate; Option 2 makes LinkML lint the gate.

#### Confirmation
`make generate-models` is deterministic from the chosen master (UC-W1 guarantee 3).

---

## C4 Container — decisions

### ADR-04: Contract between the service and the UI

#### Context and Problem Statement
The UI must use mainstream JS tooling (AD-7) and JSON-LD (AD-6). SoA:angles/service: JSON:API is
cheapest for JS developers; JSON-LD + Hydra enables generic admin UIs; GraphQL has no portable RDF
binding; graph-direct SPARQL pushes RDF into the browser. Diagrams: L2 V1, V2; UC-W5, UC-W6.

#### Considered Options

##### Option 1: Compacted JSON-LD + OpenAPI (Hydra optional)
- Good, because typed clients from OpenAPI (orval/hey-api) and JSON-LD for consumers.
- Bad, because a Hydra generator is extra work if a generated admin is wanted.

##### Option 2: JSON:API in the semantic.works dialect
- Good, because existing Ember frontends and mu ecosystem work unchanged (V2).
- Bad, because no JSON-LD on the wire; dialect coupling.

##### Option 3: Both, from one resource model (API Platform design)
- Good, because serves both ecosystems; content negotiation.
- Bad, because two renderers to maintain and test.

##### Option 4: Graph-direct reads (read-only SPARQL) + Option 1 for writes
- Good, because flexible queries without new endpoints (runbook "near-direct" UI).
- Bad, because domain rules bypassed on reads; needs store-native or proxy authorization.

#### Decision Outcome
**Partly decided.** Option 4 is rejected (DEC-17: the UI never reaches the store). Option 2 is rejected (DEC-18: no semantic.works compatibility; its good features are re-implemented). DEC-27: both — REST with compacted JSON-LD + OpenAPI first (option 1, Turtle and N-Triples by content negotiation), GraphQL second (LinkML `gen-graphql` gives the schema; resolvers over the aggregate session are new work).

#### Consequences
- Every option requires stable IRIs and versions exposed as ETags (BL-11).

#### Confirmation
Generated client compiles against the contract in CI; UC-B10.2 E2E passes.

---

### ADR-05: Store and transaction strategy

#### Context and Problem Statement
DEC-2 requires SPARQL 1.1 portability; DEC-4 reuses rdflib, pyoxigraph and existing clients. One
update request is the only portable atomic unit (K-1); Oxigraph has no conflict detection (K-2);
multi-request transactions are vendor APIs. Fluree is to be compared with Fuseki/GraphDB (mwb2
L23). Drivers: AD-2, AD-3, AD-9.

#### Considered Options

##### Option 1: Portable default — one guarded update per commit on any SPARQL 1.1 store
- Good, because works on Fuseki, Oxigraph, Fluree HTTP, GraphDB, RDF4J.
- Bad, because one aggregate per commit; confirmation needs an extra ask.

##### Option 2: Vendor transactions first (RDF4J / GraphDB)
- Good, because real multi-request ACID; read-your-writes.
- Bad, because vendor lock-in for the strongest guarantee; commercial for GraphDB.

##### Option 3: Fluree as the primary store
- Good, because triple-level policies, history, JSON-LD native, conflict detection.
- Bad, because BUSL-1.1 (legal check), young v4, no cascade delete.

#### Decision Outcome
**Partly decided (DEC-16):** classic W3C triple stores only; option 3 (Fluree) is dropped. Option 1 is the portable default; option 2 (RDF4J / GraphDB transactions) is a store capability used when present. Conformance targets: Oxigraph, Fuseki, RDF4J, GraphDB.

#### Consequences
- The Store Port must declare capabilities so the unit of work picks the strongest one (BL-5).
- The capability descriptor must also report whether the store serialises guarded updates against concurrent writers: Fuseki/TDB2, in-memory Oxigraph and Fluree HTTP do; on-disk Oxigraph does not (its adapter needs a write lock); RDF4J/GraphDB untested (K-11).

#### Confirmation
Conformance suite (BL-8) passes on Oxigraph and Fuseki in CI, plus the chosen primary store.

---

### ADR-06: Source and format of external change events

#### Context and Problem Statement
Events serve UI refresh and cross-aggregate consistency (AD-4, AD-10). No single standard exists;
RDF Patch is the closest; semantic.works emits change sets from its proxy; Fluree emits head
events only. Diagram: §5.3.

#### Considered Options

##### Option 1: Library outbox + relay
- Good, because store-agnostic; atomic with the data; ordered.
- Bad, because a relay process to run; outbox graph to prune.

##### Option 2: Store or proxy change capture
- Good, because nothing to build in V2 and V3.
- Bad, because ordering and content depend on the vendor; none in plain Fuseki/Oxigraph.

Format (independent): RDF Patch vs semantic.works change sets vs domain events (typed, per aggregate).

#### Decision Outcome
**Decided (DEC-23):** option 1, a library outbox relayed to a message broker (Redis-protocol; Valkey recommended for its BSD licence). Event format: typed domain events; RDF Patch not chosen.

#### Consequences
- Option 1 adds BL-7 and BL-13; Option 2 ties L6 to the variant.

#### Confirmation
UC-W7 scenarios: duplicate delivery, channel outage, gap replay.

---

## C4 Component — decisions (inside the Data-Management Service / rdf-persistence)

### ADR-07: Persistence pattern of the core

#### Context and Problem Statement
DEC-4 says our code is "only the ORM / repository / unit-of-work layer". DEC-13 asks whether unit
of work and the cosmic-python patterns are needed, or whether better alternatives exist.
Generated LinkML classes must stay persistence-free (SoA:index anti-patterns: Active Record
coupling). Round 4 (SoA:angles/ddd, dx; design-implications) found that most of SQLAlchemy's
flush machinery (dependency ordering, autoflush) has no job in RDF: IRIs are minted client-side,
there are no foreign keys, and over plain SPARQL flush and commit are the same request. A Data
Mapper costs no lines against Active Record (ODMantic 9 lines, Django 11). Drivers: AD-1, AD-2,
AD-4, AD-13, AD-18, AD-19.

#### Considered Options

##### Option 1: Thin aggregate session (Spring Data JDBC boundaries + SQLAlchemy identity map and change detection + Ecto change set as a value)
- Good, because works with generated, persistence-free classes; one commit = one printable change set = one request.
- Good, because familiar to SQLAlchemy and cosmic-python users without autoflush or lazy-load traps.
- Bad, because still a session lifetime to explain; snapshots cost memory for large aggregates.

##### Option 2: Full SQLAlchemy-style unit of work (autoflush, cascades across any objects)
- Good, because the most familiar to SQLAlchemy users.
- Bad, because its ordering machinery is useless in RDF; implicit flushes hide requests (AD-19).

##### Option 3: Active Record (neomodel / Django style)
- Good, because best first-contact DX (`obj.save()`).
- Bad, because couples generated classes to persistence; per-object saves break the aggregate rule.

##### Option 4: Stateless repository with explicit change sets only (Ecto / Spring Data JDBC style)
- Good, because no hidden tracking; the aggregate is saved whole.
- Bad, because the caller builds change sets by hand; whole-aggregate rewrite may be costly on RDF.

##### Option 5: Event sourcing
- Good, because full history and natural events.
- Bad, because a different storage model; rejected by the DDD angle for this library's scope.

#### Decision Outcome
Open — for the developer. Constrained by DEC-4 (we build this layer) and DEC-13 (answer the
boundary question). The round-4 evidence favours Option 1 (SoA:design-implications "Do we need a
Unit of Work?"); this is a recommendation of the review, not a decision.

#### Consequences
- Option 1 or 4 keeps generated classes clean; Option 3 needs generated base classes.
- Option 1 needs a session-required-or-repository-required answer (session alone for scripts, repositories per aggregate for services).

#### Confirmation
A one-page CRUD example per option is reviewed for DX (DEC-12) before the core is written; the
commit sequence (§5.1) is proven on Oxigraph and Fuseki.

---

### ADR-08: Mapping at runtime or generated (development approach)

#### Context and Problem Statement
Approach A reads `class_uri`/`slot_uri` at runtime; approach B generates mappers, repositories
and routes; approach C interprets the schema in a generic service (SoA:variants); approach D
has no generation: hand-written classes (code-first, the EPIC's SQLAlchemy-like entry mode) carry
the same mapper metadata through `Annotated` markers and class attributes instead of generated
`linkml_meta`. The MWBv2
runbook wants generated, never-edited code (mwb2 L31). Drivers: AD-1, AD-5, AD-13.

#### Considered Options

##### Option 1: A — runtime mapper only
- Good, because least generator code; one generic, well-tested mapper.
- Bad, because routes and contracts are hand-written or generic.

##### Option 2: B — generated mappers, repositories, routes, client
- Good, because typed end to end; matches the runbook.
- Bad, because we own templates and regeneration discipline.

##### Option 3: A now, B as an additive layer later
- Good, because ships the core first; templates call the runtime mapper.
- Bad, because two paths to document for a while.

##### Option 4: D — hand-written classes (code-first)
- Good, because fastest start; no generator in the loop; the same runtime mapper serves it.
- Bad, because no schema single source of truth; no generated SHACL, TS or OpenAPI unless
  reverse-generated from the classes. Whether the model master is the schema or the code stays
  open (ADR-03).

#### Decision Outcome
Open — for the developer, who asked for the more reliable and maintainable path. **Recommended: option 3** (runtime mapper now, generated repositories, routes and clients later, all calling it): one generic mapper is tested once; generated mapping repeats template bugs and tracks LinkML template changes.

#### Consequences
- Any option needs BL-9 (IRI types, language strings) in the generated classes.

#### Confirmation
UC-W1 guarantee 2: generated classes persist with zero hand-written mapping.

---

### ADR-09: Storage strategy of an aggregate

#### Context and Problem Statement
DEC-13: which classes change together. SoA:angles/ddd compares three layouts: A1 root + owned
closure (children with IRIs derived from the root), A2 one named graph per aggregate, A3 concise
bounded description (blank-node closure). A3 cannot be guarded (K-8). A2 competes with graphs
used as the authorization unit (K-3; Fluree policies cannot target a named graph). Drivers:
AD-2, AD-4, AD-12.

#### Considered Options

##### Option 1: A1 root + owned closure; aggregates share graphs
- Good, because works with any data layout and existing datasets; graphs stay free for tenancy and access control.
- Bad, because graph-level authorization cannot isolate one aggregate.

##### Option 2: A2 one named graph per aggregate
- Good, because graph = aggregate = replace unit; atomic graph replace and per-graph ETags.
- Bad, because many graphs; cross-aggregate queries span graphs; conflicts with graph-based access control and V2.

##### Option 3: A1 by default, A2 as opt-in per aggregate type (placement as a deployment decision)
- Good, because fits both new document-like aggregates and legacy data.
- Bad, because two code paths to test.

#### Decision Outcome
**Decided (DEC-20):** option 2, one named graph per aggregate. DEC-29: the graph IRI is derived deterministically from the root's IRI by one function (for example `<root>/graph`), so graph metadata and entity data do not share a subject. Graph-level authorization becomes aggregate-level; tenancy moves to dataset/repository or IRI namespace.

#### Consequences
- Option 2 makes ADR-02 Option 3 natural (graph scopes = aggregates) but removes graphs as tenancy unit.
- Every option requires IRIs for owned children (skolemise blank nodes on import).

#### Confirmation
Concurrency tests: two sessions edit one aggregate → exactly one commits (§5.1 conflict path).

---

### ADR-10: Behaviour on stores without atomic commits

#### Context and Problem Statement
Virtuoso in autocommit and semantic.works' proxy split updates (K-1). UC-W2 minimal guarantee 2
requires that success is never reported for a partial write. SoA:angles/stores open q. 2.
Drivers: AD-2, AD-9.

#### Considered Options

##### Option 1: Refuse — start-up fails if the store cannot guarantee atomic commits
- Good, because guarantees stay simple and true.
- Bad, because excludes V2 and some Virtuoso set-ups.

##### Option 2: Degrade with compensation and an explicit degraded result
- Good, because V2 stays possible.
- Bad, because compensation is best effort; concurrent readers may see partial state.

##### Option 3: Configurable, refuse by default
- Good, because safe default, explicit opt-in.
- Bad, because both paths must be maintained.

#### Decision Outcome
Open — for the developer. **Recommended: option 3** (refuse by default, degrade on explicit opt-in), consistent with the `strict` commit policy (DEC-21).

#### Consequences
- Option 2 or 3 adds the compensation log (rdflib `AuditableStore` idea) to BL-5.

#### Confirmation
Capability probe test; fault-injection test on a chunking store.

---

### ADR-11: Declaring aggregate boundaries in the model

#### Context and Problem Statement
LinkML has no composition construct (K-9): `inlined` is a serialisation hint, `tree_root` a
document container. The generator and the session need to know roots, owned slots and references
(UC-B1.2). Whether UML composite aggregation survives model2owl is not checked. Drivers: AD-4,
AD-5, AD-20.

#### Considered Options

##### Option 1: Explicit annotations (`aggregate_root: true` on classes; `owned: true`, `on_replace: delete` on slots)
- Good, because unambiguous; does not overload serialisation hints.
- Bad, because the Model Custodian must annotate; annotations must survive the UML → LinkML chain.

##### Option 2: Convention: owned = `inlined: true` and not `shared`, or range without identifier
- Good, because zero extra annotation for most models.
- Bad, because changing a serialisation hint silently changes transaction boundaries.

##### Option 3: Convention with annotations as override, checked at build time
- Good, because cheap default plus explicit control; build fails on two owners, owned cycles, missing IRIs.
- Bad, because two sources of truth to explain.

##### Option 4: Carry UML composite aggregation through model2owl / uml2linkml
- Good, because the boundary is drawn where the Model Custodian already models.
- Bad, because not verified that the chain carries it; may need model2owl changes.

#### Decision Outcome
**Decided (DEC-34):** an `AggregateRoot` mixin from a shared rdf-persistence LinkML schema marks roots, an `owned` annotation marks owned slots, references are slots ranging over another root; build-time checks as in option 3. Option 4 only if UML returns upstream (DEC-19).

#### Consequences
- The chosen rule is implemented once in the Boundary Checker (BL-10) and read at runtime by the session (approach A).

#### Confirmation
Generator golden tests: models with two owners, cycles and blank-node children fail the build.

---

### ADR-12: Commit policy — aggregates per commit

#### Context and Problem Statement
One request can commit several aggregates atomically, so "one aggregate per transaction" is a
policy, not a technical limit (SoA:angles/ddd). Vendor transactions tempt wider ones. Drivers:
AD-2, AD-4, AD-19.

#### Considered Options

##### Option 1: `strict` — a commit touching more than one aggregate is rejected
- Good, because enforces small aggregates and eventual consistency between them.
- Bad, because scripts and migrations need an override.

##### Option 2: `warn` — log and continue
- Good, because teaches the rule without blocking; still atomic.
- Bad, because warnings get ignored; boundaries erode.

##### Option 3: `allow` — no rule
- Good, because least friction.
- Bad, because larger guards raise contention; DDD rule left to discipline.

#### Decision Outcome
**Decided (DEC-21):** `strict` by default; `warn` and `allow` stay as session configuration. Scripts and migrations opt out explicitly.

#### Consequences
- The policy lives in the Aggregate Session (BL-2); the service kit may set `strict` for API routes.

#### Confirmation
UC-W2 extension 4a scenarios for each policy value.

---

### ADR-13: Where the aggregate version lives, and whether optimistic concurrency is on by default

#### Context and Problem Statement
No Python RDF mapper protects against lost updates (K-2). The version can be a domain field
(cosmic-python) or persistence metadata held by the mapper (keeps LinkML classes clean;
`version_of(obj)` gives the ETag). Mainstream defaults differ: on by default (Pony, Rails
`lock_version`) vs opt-in (Beanie). Drivers: AD-2, AD-13, AD-19.

#### Considered Options

##### Option 1: Mapper metadata, on by default (version triple on every root)
- Good, because generated classes stay persistence-free; lost updates prevented without effort.
- Bad, because one extra triple per aggregate and a write on the root at every change (contention per aggregate).

##### Option 2: Domain field, on by default
- Good, because visible to domain code and API models.
- Bad, because a persistence concern in generated classes; must be added to the model.

##### Option 3: Mapper metadata, opt-in per aggregate type
- Good, because no cost where not needed.
- Bad, because the safe behaviour is not the default.

#### Decision Outcome
**Decided (DEC-22):** option 1, mapper metadata, on by default. Version, provenance and annotation sets are orthogonal concerns kept out of the domain classes; annotation sets (Web Annotation, PROV-O) are a new requirement, each in its own graph per aggregate.

#### Consequences
- Confirmation by an ASK on an append-only commit record (K-7), sent to the primary, is needed whatever the option on stores without transactions or commit receipts; a "last transaction" marker would report false conflicts. New aggregates need a `FILTER NOT EXISTS` creation guard.

#### Confirmation
Conflict tests (§5.1); L4 `If-Match` mapped to the version.

---

### ADR-14: Dispatch of domain events

#### Context and Problem Statement
Cross-aggregate reactions run after commit in new sessions (eventual consistency). cosmic-python
dispatches in memory only and loses events on a crash; an outbox written in the same operation is
durable (SoA:angles/ddd, stores P-i). ADR-06 covers the external source and format; this ADR
covers in-process vs relayed dispatch. Drivers: AD-4, AD-10, AD-20.

#### Considered Options

##### Option 1: In-process bus only
- Good, because simplest; no extra process.
- Bad, because events are lost between commit and dispatch on a crash; no external subscribers.

##### Option 2: Outbox relay only
- Good, because durable, ordered, at least once; one path for internal and external consumers.
- Bad, because latency for in-process handlers; a relay to run.

##### Option 3: Both — bus after commit for in-process handlers, outbox relay for durable and external delivery
- Good, because fast local reactions and nothing lost.
- Bad, because handlers must be idempotent (may see an event twice).

#### Decision Outcome
**Decided (DEC-23):** option 3, both — bus after commit for in-process handlers, outbox relay for durable and external delivery. Handlers must be idempotent.

#### Consequences
- Option 2 or 3 adds BL-13; Option 3 makes idempotent handlers a documented rule.

#### Confirmation
UC-W7 scenarios: crash after commit, duplicate delivery, channel outage, gap replay.

---

## C4 Code — decisions

### ADR-15: Representation of multi-valued slots and language-tagged strings

#### Context and Problem Statement
RDF properties are multi-valued and unordered by default; LinkML generates `list[T]`. Language
tags are lost along the LinkML chain (K-6). The DX angle proposes set semantics with a
deterministic order on load, and `LangString` as a language map. Drivers: AD-13, AD-18, AD-21.

#### Considered Options

##### Option 1: `list[T]` with set semantics, deterministic order on load; `LangString = dict[lang, str]`
- Good, because matches LinkML output and JSON-LD language maps; plain types.
- Bad, because list order looks meaningful but is not; duplicates must be removed on save.

##### Option 2: `set[T]` (or `RdfSet[T]`) and a `LangString` class with `.best(lang_prefs)`
- Good, because honest semantics; helpful API for language fallback.
- Bad, because needs LinkML template changes; less familiar in Pydantic and JSON.

##### Option 3: Ordered lists via `rdf:List` / sequence when the model says ordered
- Good, because supports real order where needed.
- Bad, because heavier triples and queries; only for slots marked ordered (combine with 1 or 2).

#### Decision Outcome
**Decided (DEC-35): option 1** (`list[T]` with set semantics, `LangString` as a language map), because it matches LinkML output with no template change.

#### Consequences
- The choice fixes BL-1 behaviour, BL-9 template work and the JSON-LD context generated for the UI.

#### Confirmation
Round-trip tests: load → save without change produces an empty change set.

---

## C4 Context — decision added in round 4

### ADR-16: Migrations in the scope of the first EPIC

#### Context and Problem Statement
No Python RDF migration runner, LinkML diff or LinkML → SPARQL compiler exists (K-10). The
runner is small; the diff compiler is larger. Day-2 evolution is a driver (AD-17). Drivers:
AD-17, AD-22.

#### Considered Options

##### Option 1: Runner only (hand-written, reviewed SPARQL scripts; checksum, lock, log)
- Good, because small and enough for early projects; mu-migrations-compatible files.
- Bad, because every rename is written by hand.

##### Option 2: Runner + schema diff + migration compiler (Alembic style: generate, review, run)
- Good, because mechanical changes (IRI renames, defaults) are generated; destructive ones gated.
- Bad, because larger scope; risk of over-trusting generated scripts.

##### Option 3: Defer migrations; regenerate and reload data
- Good, because no scope now.
- Bad, because unworkable once data is in production.

##### Option 4: Contribute a SPARQL compiler to linkml-map upstream instead of a diff compiler
- Good, because shared maintenance in the LinkML ecosystem.
- Bad, because upstream pace and acceptance are outside our control.

#### Decision Outcome
**Partly decided (DEC-25):** no migration generation in the first EPIC (option 3 for now), but option 2 is a likely goal: keep the schema version in the store, LinkML rename hints and a migration principal in the policy port.

#### Consequences
- Option 1 needs BL-14; Option 2 adds BL-15. Which principal runs migrations under DEC-8 must be decided with ADR-02.

#### Confirmation
Migration test: apply to a fixture dataset; SHACL conformance and golden counts.
