# Angle: DDD boundaries, aggregates and transactions (DEC-13)

Analyst, round 3 angle `angle-ddd` (2026-11-03). Layers: **L1 domain & persistence**, with
consequences for L0 (how boundaries are declared in LinkML), L2 (what the store can make
atomic), L4 (ETag, nested writes) and L6 (domain events, outbox).

The developer's question: *how do we manage DDD boundaries — which classes depend on each other,
which go together in one transaction, which can go independently in a message or a separate
transaction? SQLAlchemy handles transactions across several tables. Do we need a Unit of Work and
the other cosmic-python patterns, or is there something better?*

- Clones (shallow, siblings of this repo), all indexed with `gitnexus analyze`:

| Clone | Commit | Licence | GitNexus index |
|---|---|---|---|
| `sqlalchemy` | 57ddc05 (2026-11-02) | MIT | 48 881 nodes, 116 817 edges, 1 879 clusters, 300 flows |
| `spring-data-relational` | e466925 (2026-10-23) | Apache-2.0 | 16 407 nodes, 47 562 edges, 967 clusters, 300 flows |
| `ecto` | c8091a1 (2026-11-01) | Apache-2.0 | 298 nodes, 293 edges, no clusters (Elixir parsed poorly; read source directly) |
| `cosmicpython-code` | 14c8479 (2025-06-10) | no SPDX licence | 325 nodes, 514 edges, 24 clusters, 8 flows |

- Also read in code: `linkml` (existing clone, `linkml_runtime` `SchemaView.is_inlined`, metamodel
  `meta.yaml`).
- Docs read: cosmicpython.com ch. 7 (Aggregates), Spring Data JDBC "Domain Driven Design" page,
  Spring Data Commons "Domain events" page, Prisma transactions page, LinkML "Inlining" page,
  Vernon, *Effective Aggregate Design* Part III (PDF, pp. 11–15). Hibernate, Django, Marten, Axon
  and pyeventsourcing are described from their public docs (URLs given) and general knowledge.
  Where a claim was not checked in code it is marked so.

---

## 1. Summary

1. **Most of SQLAlchemy's Unit of Work is not needed for RDF.** Its hardest part, the
   topological sort of flush actions (`orm/unitofwork.py:390-466`), exists because SQL has
   foreign-key constraints and server-generated keys: a child row needs its parent's primary key
   copied into its foreign key (`orm/dependency.py:616-640`, `sync._populate`). RDF has neither.
   IRIs are minted on the client, triples are a set, and order does not matter inside one
   update. What remains worth taking is small: an identity map, change tracking by snapshot
   diff, cascades along composition, a version check, and `commit()`.
2. **Portable SPARQL has no flush that is separate from commit.** SQLAlchemy flushes many times
   inside one database transaction and commits once (`session.py:4577-4680`). Over plain SPARQL
   1.1, every request is its own transaction. So `flush` and `commit` are the same thing,
   autoflush before queries is impossible, and read-your-writes is limited to the identity map
   (or to a vendor transaction, see T5).
3. **Spring Data JDBC is the closest model to copy.** It has one repository per aggregate root.
   It saves the whole aggregate, deleting and re-inserting the owned children
   (`WritingContext.java` `save()`/`update()`: `setRootAction` → `deleteReferenced` →
   `insertReferenced`). It keeps the version on the root only (`updateWithVersion`,
   `JdbcAggregateChangeExecutionContext.java:384-390`), references other aggregates by id
   (`AggregateReference`), and does no lazy loading. Translated to RDF, that is one
   `DELETE … INSERT … WHERE` per commit.
4. **Ecto's explicit changesets and `Ecto.Multi` show how the commit can be a value.** A Multi is
   a data structure you can inspect (`multi.ex` moduledoc, `to_list/1`). It is validated before
   the transaction starts and can be unit-tested without a database. For us, the commit becomes a
   pure **ChangeSet**: deletes, inserts, guards and events. It compiles to one SPARQL Update, and
   the same ChangeSet is the delta for events (E2/E4) and the dry-run preview.
5. **The DDD rules hold in RDF, for modelling reasons more than technical ones.** One SPARQL
   Update can atomically change several aggregates at no extra cost. Vernon's rule "one aggregate
   per transaction" is therefore about contention and coupling, not about what the store can do.
   Recommendation: enforce it by **policy** (`strict` / `warn` / `allow`), not by architecture.
6. **New finding: one request with several guarded operations is not all-or-nothing.** When a
   `DELETE/INSERT … WHERE` guard matches nothing, the operation does nothing and the request
   still succeeds, so the next operation in the same request still runs. An all-or-nothing
   commit therefore needs **one single operation whose WHERE joins every guard**, with ground
   (constant) delete and insert templates. Owned children must then have IRIs, because SPARQL
   forbids blank nodes in DELETE templates. This refines pattern P-b in `angle-stores.md`.
7. **LinkML can declare boundaries, but only partly.** `identifier` separates entities from value
   objects, and `inlined` / `shared` hint at ownership. But `inlined` is documented as
   serialization-only (`meta.yaml:1783-1800`, "only applicable in tree-like serializations"), and
   `tree_root` is a document container, not an aggregate root (`meta.yaml:1298-1311`). There is
   no composition construct. We need an annotation convention, or one derived from UML
   composite aggregation, plus generation-time checks.

---

## 2. Landscape

DEC-5: > 200 stars AND a commit in the last 12 months. Stars and dates come from `gh api`,
2026-11-03. These are mostly **benchmarks for patterns** (none is an RDF dependency
candidate), so DEC-5 is recorded for completeness.

| Candidate | Repo / stars / last push | Licence | Lang | DEC-5 | Transaction model | Aggregate stance | Layers |
|---|---|---|---|---|---|---|---|
| **SQLAlchemy 2.x ORM** | sqlalchemy/sqlalchemy 12 276★, 2026-11-02 | MIT | Py | pass | Implicit UoW: Session + identity map + dirty tracking; flush is topologically sorted; DB tx; `begin_nested` savepoints | none (object graph; cascades per relationship) | L1 |
| **Spring Data JDBC** | spring-projects/spring-data-relational 828★, 2026-10-26 | Apache-2.0 | Java | pass | `@Transactional` per repository call; whole-aggregate save | **explicit**: repository per root, version on root, by-id references, no lazy loading | L1 |
| **Ecto** | elixir-ecto/ecto 6 500★, 2026-11-01 | Apache-2.0 | Elixir | pass | No UoW. Explicit changesets + `Ecto.Multi` (named, inspectable op list) in `Repo.transaction` | implicit via `cast_assoc` / `on_replace` (owned children) | L1 |
| **cosmic-python** (book + code) | cosmicpython/code 2 726★ (last 2025-06-10); book 3 879★ (2025-09-08) | no SPDX licence (book CC-BY-NC-ND per site; *not verified for code*) | Py | **fail** on recency (code); ideas only | Abstract UoW over SQLAlchemy session; message bus; events collected from `repo.seen` | **explicit**: repository per aggregate, `version_number` on root | L1, L6 |
| Hibernate ORM / JPA | hibernate/hibernate-orm 6 482★, 2026-11-02 | Apache-2.0 | Java | pass | Persistence context, automatic dirty checking, `FlushMode.AUTO`, `@Version`, cascade types, `orphanRemoval` ([user guide](https://docs.jboss.org/hibernate/orm/current/userguide/html_single/Hibernate_User_Guide.html)) — *docs, not code* | none | L1 |
| Django ORM | django/django 91 489★, 2026-11-02 | BSD-3 | Py | pass | No UoW. `save()` writes immediately; `transaction.atomic()` blocks + savepoints; **`transaction.on_commit()`** hooks; `select_for_update` ([docs](https://docs.djangoproject.com/en/stable/topics/db/transactions/)) — *docs* | none | L1 |
| Prisma ORM (TS) | prisma/prisma 47 659★, 2026-11-02 | Apache-2.0 | TS | pass | Nested writes (parent + children in one call); interactive `db.transaction(async tx => …)`; no isolation option; manual retry on 40001 ([docs](https://www.prisma.io/docs/orm/prisma-client/queries/transactions)) | nested writes ≈ aggregate write | L1, L5 |
| Marten (.NET) | JasperFx/marten 3 470★, 2026-11-02 | MIT | C# | pass | `IDocumentSession` UoW over PostgreSQL; documents + event streams; optimistic stream version ([docs](https://martendb.io/)) — *docs* | document = aggregate; event-sourced aggregates | L1, L6 |
| Axon Framework | AxonIQ/AxonFramework 3 628★, 2026-11-02 | Apache-2.0 | Java | pass | Event-sourced aggregates, command bus, sagas, UoW per command — *docs* | explicit (`@Aggregate`, `@AggregateIdentifier`) | L1, L6 |
| Eventuous (.NET) | Eventuous/eventuous 513★, 2026-10-12 | Apache-2.0 | C# | pass | Event-sourced aggregates, expected stream version — *docs* | explicit | L1, L6 |
| pyeventsourcing | pyeventsourcing/eventsourcing 1 689★, 2026-10-14 | BSD-3 | Py | pass | Event-sourced aggregates, optimistic append, notification log — *docs* | explicit | L1, L6 |
| LinkML (boundary metadata) | linkml/linkml 680★, 2026-11-02 | Apache-2.0 | Py | pass | n.a. | `identifier`, `inlined`, `inlined_as_list`, `shared`, `tree_root`, `annotations` | L0 |

---

## 3. Deep dives

### 3.1 SQLAlchemy 2.x — Session / Unit of Work

**Purpose and origin.** Built by Mike Bayer (2005–) as the Python SQL toolkit plus a Data Mapper
ORM modelled on Fowler's *PoEAA*. Design angle: **database-first Data Mapper with an implicit
UoW**. Fit: L1 benchmark for developer experience and UoW mechanics. It is not a dependency for an
RDF mapper, apart from the cosmic-python examples built on it.

**Architecture (GitNexus + source).**
- `Session` owns `identity_map = identity._WeakInstanceDict()`, plus `_new` and `_deleted`
  (`session.py:1817-1826`). `SessionTransaction` (`session.py:859`) nests, with `begin_nested()`
  as a savepoint (`:2018`). `expire_on_commit=True` by default (`:1549`, `:1150`).
- `Session._flush` (`session.py:4577`) collects new, dirty and deleted states, detects orphans
  (`_is_orphan` → delete), and builds a `UOWTransaction`. It opens a (sub)transaction, runs
  `flush_context.execute()`, then `finalize_flush_changes()`, and commits or rolls back that
  inner transaction. GitNexus cypher on `_flush` callees: `_autobegin_t`, `_begin`,
  `register_object`, `execute`, `finalize_flush_changes`, `_commit_all_states`, `commit`,
  `rollback`.
- `UOWTransaction` (`unitofwork.py:155-487`; GitNexus `Class:…UOWTransaction`) works in steps.
  Presort actions are iterated until a fixpoint, because cascades can add states
  (`:390-404`). It then calls `topological.find_cycles(dependencies, postsort_actions)`. On a
  cycle it breaks per-mapper actions into per-state actions (`:406-440`). Finally,
  `execute()` runs `topological.sort` or `sort_as_subsets` (`:442-466`).
- The dependency processors (`dependency.py`: `_OneToManyDP:336`, `_ManyToOneDP:645`,
  `_ManyToManyDP:987`) exist to **copy primary keys into foreign keys** (`_synchronize` →
  `sync._populate`, `:616-640`) in the right order.
- Optimistic concurrency: `version_id_col`; on UPDATE, rows matched != expected →
  `StaleDataError` (`persistence.py:963-969`). **If the dialect does not report row counts,
  SQLAlchemy only warns: "versioning cannot be verified"** (`persistence.py:971-975`). This is
  the exact analogue of SPARQL Update, which returns no match count.
- Cascades: `"save-update, merge"` by default; `delete`, `delete-orphan` opt-in
  (`util.py:189-250`, `relationships.py:420`).

**Implementation principles relevant to us.**
- Implicit tracking: any attribute change on an object in the identity map makes it dirty. There
  is no `save()`. Developers like this ("just change it and commit"), but it hides when SQL runs
  (autoflush before queries, `session.py:3192`; the `no_autoflush` escape hatch, `:3159`).
- The transaction boundary is the database's: many flushes, one commit. Savepoints give partial
  rollback.

**RDF translation.** Keep the identity map, the snapshot diff (P9), `commit()`, orphan
deletion along composition (P11), and the version check. Drop the topological sort and the
dependency processors: IRIs are client-minted (I1) and there are no foreign-key constraints, so
the order of triples inside one update does not matter. Drop autoflush, because a flush would be
an irreversible, separate commit over portable SPARQL. Drop savepoints, unless the store has
vendor transactions (T8).

**Scores** (as an ORM benchmark; C5 and C7 are not applicable).

| C | Score | Justification | Evidence |
|---|---|---|---|
| C1 | 5 | Complete UoW, identity map, cascades, savepoints, versioning | `session.py`, `unitofwork.py`, `persistence.py` |
| C2 | 5 | Textbook Data Mapper + UoW + Identity Map | `UOWTransaction`, `_WeakInstanceDict` |
| C3 | 4 | Excellent docs; implicit autoflush and expiry surprise newcomers | `session.py:3159-3192`, `:1150` |
| C6 | 3 | Imperative mapping keeps domain classes free of persistence code (cosmic-python ch. 2); no aggregate concept | `cosmicpython-code/src/allocation/adapters/orm.py` |
| C8 | 5 | 12 k★, very active, large test suite (`test/orm/test_cycles.py`, …) | gh api |
| C9 | 3 | SQL-only | — |
| C10 | 4 | Stable 2.x API; large internal surface (UoW core ≈ 10 k LOC in 6 files) | `wc -l` |

**Verdict: borrow ideas** (identity map, `with Session() as s, s.begin():`, cascade vocabulary,
the "cannot verify" warning). **Avoid** copying the topological flush and autoflush.

### 3.2 Spring Data JDBC — aggregate-oriented persistence

**Purpose and origin.** A Spring Data module led by Jens Schauder (VMware/Broadcom), built as a
**DDD-first** alternative to JPA: "simple, limited, opinionated". It deliberately has no
persistence context, no lazy loading and no dirty checking. Design angle: **aggregate-first**.
Fit: the L1 design model for rdf-persistence's repositories (approach B generates one per
aggregate root).

**Architecture (GitNexus + source).**
- `WritingContext<T>` (`spring-data-relational/…/conversion/WritingContext.java:45`).
  - `save()`: if new → `InsertRoot` plus `insertReferenced()`; else → `UpdateRoot(root,
    previousVersion)` plus `deleteReferenced()` plus `insertReferenced()`.
  - GitNexus cypher on `save` callees confirms: `isNew`, `setRootAction`, `deleteReferenced`,
    `insertReferenced`, `addAction`.
  - The docs say: "entities referenced from an aggregate root are deleted and recreated"
    ([DDD page](https://docs.spring.io/spring-data/relational/reference/jdbc/domain-driven-design.html)).
- The version lives on the root only. `executeUpdateRoot` → `updateWithVersion` →
  `OptimisticLockingUtils.updateFailed` (`spring-data-jdbc/…/JdbcAggregateChangeExecutionContext.java:127-140,384-390`).
  A delete is also version-guarded (`deleteWithVersion`, `:139-140`).
- Cross-aggregate references: `AggregateReference<T, ID>`, "a reference to the aggregate root of
  a different aggregate" (`core/mapping/AggregateReference.java`). The docs say that references
  across aggregates "are guaranteed to become consistent eventually". Mapping assumption: "no
  other entity points toward non-root entities".
- Transactions: `SimpleJdbcRepository` is `@Transactional(readOnly = true)` with `@Transactional`
  writes (`SimpleJdbcRepository.java:51,71,77,108`). One repository call is one transaction
  unless an outer `@Transactional` widens it.
- Events and callbacks: `BeforeConvert`, `BeforeSave` and `AfterSave` events, plus entity
  callbacks (`JdbcAggregateTemplate.java:735-773`). Domain events come from `@DomainEvents` and
  `@AfterDomainEventPublication` on the root, published on `save*` and `delete*`, but not on
  `deleteById`, because "we would never have access to the aggregate instance"
  ([commons docs](https://docs.spring.io/spring-data/commons/reference/repositories/core-domain-events.html)).

**RDF translation.** This is almost one-to-one.
- An aggregate is the root plus its owned closure.
- `save(root)` becomes one guarded `DELETE {old owned triples} INSERT {new owned triples} WHERE
  {root version guard}`.
- An `AggregateReference` becomes an IRI-typed slot (`Ref[T]`).
- "No lazy loading" means one CONSTRUCT loads the whole aggregate.
- We can improve on delete-and-reinsert: diff against the loaded snapshot (P9), so unchanged
  triples are not rewritten. It is still one request, and foreign triples are kept (P8).

**Scores.**

| C | Score | Justification | Evidence |
|---|---|---|---|
| C1 | 3 | Aggregates, versioning, events; deliberately no lazy loading, dirty tracking or cache | `WritingContext.java` |
| C2 | 5 | Repository per aggregate root, whole-aggregate save, root version, by-id references | as above |
| C3 | 4 | Predictable ("what you save is what is written"); write amplification surprises users | DDD page |
| C6 | 5 | The best DDD fit surveyed | DDD page, `AggregateReference` |
| C8 | 4 | 828★, active, Spring-backed | gh api |
| C9 | 3 | Relational only | — |
| C10 | 5 | Small, explicit semantics | — |

**Verdict: borrow ideas (primary design model).**

### 3.3 Ecto — explicit changesets and `Ecto.Multi`

**Purpose and origin.** Elixir's data-mapping library (José Valim, Dashbit). Functional, so it
has no mutable objects, no identity map and no UoW. Design angle: **explicit change as data**.
Fit: L1 design idea for an inspectable commit, and for testing domain logic without a store.

**Evidence.**
- `Ecto.Multi` moduledoc (`lib/ecto/multi.ex:1-120`) says it is "a data structure for grouping
  multiple Repo operations … performed in a single database transaction and provides a way to
  introspect the queued operations without actually performing them".
  - Changesets are checked **before** the transaction starts.
  - `run/3` lets later operations see earlier results.
  - "We can also easily unit test our transaction without actually running it."
  - Operations: `insert/update/delete/one/all/run/merge/append` (`multi.ex:196-513`).
- `optimistic_lock/3` (`changeset.ex:3644`) → `Ecto.StaleEntryError` or a `stale` changeset
  error (`repo/schema.ex:1120-1130`).
- Owned children: `cast_assoc` with `on_replace: :delete | :nilify | :raise`
  (`changeset.ex:199-225, 1215`). This makes the replace semantics explicit per association.

**RDF translation.** Our UoW should *produce* a `ChangeSet` value: removed quads, added quads,
guards, events and touched aggregates. `commit()` compiles it to one SPARQL Update. Then:
- `uow.preview()` / `changeset.to_sparql()` shows it, like `Multi.to_list`.
- Domain tests assert on the ChangeSet with no store.
- The same value feeds the outbox (E1), RDF Patch (E2) and a JSON:API Atomic Operations response.
- The `on_replace` vocabulary maps to how a composition slot behaves when its value is replaced
  (delete the orphan; keep it if shared).

**Scores.** C2 5 (explicit, inspectable), C3 4 (verbose but transparent), C6 4 (pure domain
functions), C8 5 (6.5 k★), C10 5. **Verdict: borrow ideas** (ChangeSet as a value, validation
before commit, `on_replace` semantics).

### 3.4 cosmic-python (Percival & Gregory)

**Purpose and origin.** The code companion to *Architecture Patterns with Python* (O'Reilly,
2020). It teaches DDD, ports and adapters, and event-driven architecture in Python. It is
Meaningfy's house style (skill `cosmic-python`). Design angle: **teaching patterns**. Fit: the
L1 service-layer patterns of the generated backend.

**Evidence.**
- `AbstractUnitOfWork` (`src/allocation/service_layer/unit_of_work.py`) is a context manager.
  `__exit__` → `rollback()`; `commit()` is explicit; `collect_new_events()` drains
  `product.events` for every aggregate in `self.products.seen`. GitNexus `context
  collect_new_events` confirms this in the same file. The SQLAlchemy UoW uses
  `REPEATABLE READ`.
- The repository tracks `seen` on `add`, `get` and `get_by_batchref`
  (`adapters/repository.py:9-24`), so the UoW knows which aggregates were touched.
- Aggregate `Product` holds `version_number` (incremented in `allocate`) and `events`
  (`domain/model.py:8-30`).
- `MessageBus.handle` (`service_layer/messagebus.py`) keeps an in-memory queue. After each
  handler it adds `uow.collect_new_events()`. Event-handler errors are logged and swallowed;
  command-handler errors are raised.
- Book ch. 7 (online): "one aggregate = one repository"; one transaction changes one aggregate;
  the version number belongs in the domain (it lists three options); retry on conflict; "the
  smaller, the better, for performance". It quotes Evans' definition only.
- **Gap:** events are dispatched in memory *after* commit. A crash between the commit and the
  handlers loses them. There is no outbox in the code (grep `outbox` → none).
  `redis_eventpublisher.py` publishes from a handler.

**RDF translation.**
- Repository per aggregate: adopt.
- UoW: adopt, with the thin RDF semantics above.
- `seen` → the identity map's touched-aggregate set.
- Events: collect them on the aggregate, but **persist them as outbox triples in the same
  update** (E1). This closes the book's crash window.
- Version number: we *disagree* with the book here, because LinkML-generated classes must stay
  persistence-free. The mapper keeps the version as session metadata (`uow.version_of(order)`),
  not as a domain field. That also gives the ETag for L4.

**Scores.** C2 5, C3 4, C6 5, C8 2 (code untouched since 2025-06), C10 4. **Verdict: adopt the
patterns** (the house standard). Add the outbox it leaves out.

### 3.5 Other benchmarks (docs only, not cloned)

| Benchmark | Idea worth taking | Idea to avoid |
|---|---|---|
| Hibernate/JPA | `@Version` as a standard concept; `orphanRemoval` (= P11); cascade types | `FlushMode.AUTO`, automatic dirty checking of *everything* loaded (hidden writes) |
| Django | `transaction.on_commit(fn)`: run side effects only after a successful commit; "no UoW" simplicity | `atomic()` cannot be honoured over portable SPARQL (several requests); per-`save()` statements |
| Prisma | **Nested writes**: create or update a parent with its children in one call. This is the aggregate write shape for a TS client and JSON API | interactive transactions across HTTP (not portable for SPARQL) |
| Marten / Axon / Eventuous / pyeventsourcing | expected-version append, stream per aggregate, sagas or process managers for cross-aggregate flows | event sourcing as the *primary* store: in a data-centric system the RDF graph *is* the truth and must stay queryable by SPARQL. Fluree's ledger (`angle-stores.md`) already gives history |

---

## 4. DDD theory → RDF practice

### 4.1 The rules

From Vernon, *Effective Aggregate Design* III, p. 15 (checked in the PDF):
1. Model true invariants in consistency boundaries.
2. Design small aggregates.
3. Reference other aggregates by identity.
4. Use eventual consistency outside the boundary ("after asking whose job it is").

Vernon also notes (p. 12) that with document-like storage "the root is effectively modified
every time a collected part is modified". This applies directly to a root version triple and to
graph-per-aggregate: every change to a part bumps the root, so contention is per aggregate. Keep
aggregates small.

Evans/cosmic-python add one rule: one transaction changes one aggregate. Spring Data adds that
non-root entities are never referenced from outside their aggregate.

### 4.2 What an aggregate is in a graph — three options

| Option | Definition | Load | Save | Concurrency | ACL fit (DEC-8) | Costs |
|---|---|---|---|---|---|---|
| **A1 Root + owned closure** (recommended default) | Root IRI plus the transitive closure over *owned* (composition) slots. Children have IRIs derived from the root (`<root>/lines/1` or `<root>#line-1`) | one CONSTRUCT along owned predicates (property paths generated from the model) | one guarded `DELETE{…}INSERT{…}WHERE{guards}` with ground templates | version / token triple on the root (T2) | graph-level ACL applies to the *graph the aggregate lives in* (tenant, context), independent of aggregates | delete set must be known: from the loaded snapshot (P9); foreign triples kept (P8) |
| **A2 Named graph per aggregate** | All triples of the aggregate in `GRAPH <root-graph>` | GSP `GET` or `CONSTRUCT {…} WHERE {GRAPH <g>{…}}` | GSP `PUT` (atomic replace, idempotent, P-f) or a guarded update scoped to the graph | ETag per graph (needs our L4 or a proxy, P-g) | **conflicts** with graph-as-ACL-unit (semantic.works and graph-based authz use graphs for *access*); Fluree policies cannot target a named graph | many graphs; cross-aggregate queries need `GRAPH ?g` or a union default graph (store-specific configuration); the graph is used up for aggregates instead of provenance or tenancy |
| **A3 CBD** (Concise Bounded Description) | Subject plus blank-node closure | `DESCRIBE` (store-specific) | replacing a CBD with blank nodes cannot be guarded (blank nodes are not allowed in DELETE templates) | weak | as A1 | blank nodes block guarded deletes; skolemise (I4) and it becomes A1 |

Recommendation: **A1 by default; A2 as an opt-in storage strategy** (B10) for document-like
aggregates when graphs are not already used for tenancy or ACL. Keep the graph decision with
the *deployment* (policy-driven graph placement, P12), not hard-coded in the model.

### 4.3 How the store's transaction facts constrain the design (from `angle-stores.md`)

- **One SPARQL Update request = the only portable atomic unit.** So commit = one request, and an
  aggregate is naturally the content of one commit.
- **Several aggregates in one request are equally atomic.** RDF makes the "multi-aggregate
  transaction" technically free, so the DDD rule must be a *policy* (B6), not a technical limit.
- **Guards do not abort a request (new, §1 item 6).** Given
  `DELETE{…}INSERT{…}WHERE{g1} ; DELETE{…}INSERT{…}WHERE{g2}`, a failed `g1` silently skips the
  first operation while the second still runs. All-or-nothing therefore needs **one** operation:

  ```sparql
  DELETE { <ground triples removed, all aggregates> }
  INSERT { <ground triples added> ; <outbox triples> ; <root> rp:version 8 ; <root> rp:lastTx <urn:uuid:T> }
  WHERE  { <rootA> rp:version 7 . <rootB> rp:version 3 }   # every guard; 1 solution or 0
  ```

  - With constant guards, the WHERE yields exactly one empty solution, or none. Zero solutions
    → nothing at all is written.
  - Afterwards, `ASK { <root> rp:lastTx <urn:uuid:T> }` tells "committed" from "conflict"
    (T2 caveat). This needs a second round trip, but it is only a detection step.
  - The delete template must be ground: no blank nodes, so owned children need IRIs (I4
    skolemisation).
  - Cascade targets found dynamically (for example, inbound references) must be resolved by a
    read *before* commit. Inbound references from *other* aggregates lie outside the boundary,
    so we leave them alone or clean them up eventually (rule 4).
- **Vendor transactions** (RDF4J/GraphDB T3, Fluree embedded) enable read-your-writes and true
  multi-request work. The aggregate rule stays a policy there too.
- **Chunking proxies** (semantic.works `sparql-parser`, Virtuoso autocommit) break the single
  operation: guard and writes can land in different chunks. Refuse by default, or degrade with
  a warning (T4/T7).
- **Writers outside the library** that do not bump versions defeat the guard. Document this; a
  token triple per commit at least detects *our own* concurrent writers.

### 4.4 Declaring boundaries in LinkML (so they are derived, not hand-written)

What LinkML gives (code-checked):

| LinkML construct | Meaning | Use for boundaries | Evidence |
|---|---|---|---|
| `identifier: true` / `key` on a class's slot | the class is an entity with a stable id | a class without an identifier = a **value object**, always inlined (forced inlined) | `schemaview.py:2147-2160` (`is_inlined`: "range is a class with no identifier/key … forces inlining") |
| `inlined` / `inlined_as_list` | by value vs by reference **in tree serializations** | candidate marker for *owned* (composition) when the range has an identifier | `meta.yaml:1783-1800`: "only applicable in tree-like serializations, e.g json, yaml" — so this is overloading, not a semantic declaration |
| `shared` | many-to-one / many-to-many (range may be referenced by many) | `shared: true` → never owned; `shared: false` + `inlined` → owned | `meta.yaml:1861-1871` |
| `tree_root` | container class of a serialized document | **not** an aggregate root; at most one per schema | `meta.yaml:1298-1311` |
| `annotations` (free-form) | extension point | explicit `aggregate_root: true` (class), `owned: true` / `on_replace: delete` (slot) | metamodel `annotations` |

There is no composition construct. UML composite aggregation (black diamond) would be the
natural source in the MWBv2 chain (UML → model2owl → LinkML). Whether model2owl or the LinkML
derivation carries `aggregationKind=composite` was **not checked** (open question).

**Proposed derivation rules (B1/B2).**
1. A slot is **owned** if it has the annotation `owned: true`, or, by convention, `inlined: true`
   with `shared` not true, or its range class has no identifier (a value object).
2. **Aggregate roots** are classes with an identifier that are never the range of an owned slot,
   or classes annotated `aggregate_root: true`.
3. **Aggregate** = root + the transitive closure over owned slots.
4. Every other slot whose range has an identifier is a **reference by IRI**. It generates as
   `Ref[T]` (an IRI wrapper), not as a navigable object.
5. Generation-time checks (fail the build):
   - a class owned by two roots;
   - a cycle through owned slots;
   - a reference from outside an aggregate to one of its non-root entities (a warning, per
     Spring Data's assumption);
   - an owned entity without derivable IRIs (needed for guarded deletes).

### 4.5 Bounded contexts

- A bounded context maps to a LinkML schema module, with its own repositories and its own graph
  set or dataset.
- Across contexts, only IRIs (references) and events (E*) pass. There are no shared Python
  classes.
- This uses the import-linter discipline the repo already has (`.importlinter`). Contexts
  become packages with contracts, so code generation would emit one package per context.

---

## 5. Patterns catalogue (DEC-13)

| # | Pattern | Problem it solves | Where implemented (evidence) | RDF translation | Verdict |
|---|---|---|---|---|---|
| 1 | Aggregate (root + owned parts) | where invariants are enforced; what changes together | Spring Data JDBC `WritingContext`; cosmic-python `Product`; Axon `@Aggregate` | root IRI + owned closure (A1) or graph (A2), declared in LinkML (§4.4) | **adopt** |
| 2 | Repository per aggregate root | hide persistence; load and save whole aggregates only | Spring Data `CrudRepository<Order,…>`; cosmic-python `AbstractRepository` | generated `OrderRepository` (approach B) or generic `Repository[Order]` (A); `get` = one CONSTRUCT | **adopt** |
| 3 | Reference by identity | decouple aggregates; avoid loading the world | `AggregateReference` (Spring); Vernon rule 3 | `Ref[T]` IRI slot; explicit `repo.get(ref)`; no lazy navigation across boundaries | **adopt** |
| 4 | Unit of Work (implicit, SQLAlchemy-style) | track every change, flush in dependency order | `Session` / `UOWTransaction` (`unitofwork.py`) | identity map + snapshot diff + commit; **no topological sort, no autoflush** | **adopt a thin version** |
| 5 | Whole-aggregate save | no dirty tracking needed; predictable writes | Spring `deleteReferenced` + `insertReferenced` | one guarded DELETE/INSERT per commit; diff to stay minimal | **adopt** (merged with 4) |
| 6 | Explicit ChangeSet / Multi | inspectable, testable, validate-before-commit | `Ecto.Multi`, `Ecto.Changeset` | `ChangeSet` value → SPARQL text, outbox, RDF Patch; `uow.preview()` | **adopt** |
| 7 | Identity map | one object per identity; read-your-writes for `get` | `_WeakInstanceDict` (`identity.py:126`) | keyed by (class, IRI) per UoW (I3) | **adopt** |
| 8 | Optimistic version on root | lost updates between concurrent writers | `version_id_col` / `StaleDataError`; Spring `updateWithVersion`; Ecto `optimistic_lock`; cosmic `version_number` | `rp:version` + `rp:lastTx` token; single conjunctive guard; ASK to detect; mapper-managed (not a domain field) | **adopt** |
| 9 | Cascade / orphan removal | owned parts die with the root or when detached | SQLAlchemy `delete-orphan`; JPA `orphanRemoval`; Ecto `on_replace: :delete` | delete owned closure; never cascade across references | **adopt** (R4, P11) |
| 10 | One aggregate per transaction | contention, coupling | Evans/Vernon; cosmic ch. 7 | **policy** `strict / warn / allow`, since one request can technically commit many | **adopt as a policy** |
| 11 | Domain events on the aggregate | record what happened for other aggregates or contexts | cosmic `product.events`; Spring `@DomainEvents` | `aggregate.events` collected by the UoW | **adopt** |
| 12 | Transactional outbox | events never lost or invented on crash | not in cosmic code; standard pattern | outbox triples in the **same** INSERT template; relay → SSE / webhook / Kafka (E1) | **adopt** |
| 13 | After-commit hooks | run side effects only on success | Django `transaction.on_commit`; Spring `AfterSave` | `uow.on_commit(fn)`; message bus dispatch after commit | **adopt** |
| 14 | Message bus (commands + events) | orchestrate handlers; each handler gets a new UoW | cosmic `MessageBus` | in-process bus in the generated service layer; handlers on other aggregates run in **new** UoWs | **adopt (service layer, optional)** |
| 15 | Process manager / saga | multi-aggregate business flows without distributed transactions | Axon sagas; Marten / Wolverine | saga state is itself an aggregate; triggered by outbox events; idempotent (T9) | **borrow (later)** |
| 16 | Event sourcing | full history; rebuild state from events | Marten, Axon, Eventuous, pyeventsourcing | conflicts with "the graph is the truth"; history from Fluree's ledger or the outbox log instead | **avoid as primary** |
| 17 | Savepoints / nested transactions | partial rollback | SQLAlchemy `begin_nested`; Django `atomic` | only with vendor transactions (T8); otherwise the ChangeSet is simply rebuilt in memory | **n.a. by default** |
| 18 | Autoflush / read-your-writes in queries | queries see pending changes | SQLAlchemy `_autoflush`; Hibernate `FlushMode.AUTO` | impossible over portable SPARQL; warn when querying with pending changes; vendor transaction (T5) when available | **avoid** |
| 19 | Nested writes | create a parent with its children in one API call | Prisma | JSON:API compound documents / Atomic Ops → one aggregate save | **borrow (L4/L5)** |
| 20 | Retry on conflict | optimistic failures are normal | cosmic ch. 7; Fluree `transact(fn)`; Prisma manual 40001 retry | `@retry_on_conflict` reloads and replays the handler (T6) | **adopt** |
| 21 | CQRS read side | queries that cross aggregates | rdfproxy read models (X10) | read models / SPARQL views bypass aggregates by design | **adopt** (reads only) |

---

## 6. Do we need a Unit of Work? — recommended design sketch

**Answer: yes, but a thin "aggregate session".** It combines Spring Data JDBC's boundaries,
SQLAlchemy's convenience (identity map + automatic change detection on *aggregates you
loaded*), and Ecto's explicit ChangeSet as its product. Event sourcing and an implicit
SQLAlchemy-style UoW with autoflush are both rejected.

```python
with uow:                                        # new identity map; nothing sent yet
    order = uow.orders.get(order_iri)            # 1 CONSTRUCT: root + owned closure; snapshot kept
    customer_ref = order.customer                # Ref[Customer] — an IRI, not a loaded object
    order.add_line(sku, qty)                     # domain method; appends OrderLineAdded event
    print(uow.preview())                         # ChangeSet: −/+ triples, guards, events (dry-run)
    uow.commit()                                 # 1 SPARQL Update (single guarded op + outbox)
                                                 # → ASK token → on_commit hooks → bus dispatch
# leaving without commit = rollback = discard the in-memory ChangeSet
```

Semantics:
1. **Load.** `repo.get` loads the whole aggregate in one query (B3). There is no lazy loading
   inside an aggregate, and none across aggregates (B5).
2. **Track.** The UoW records the aggregates touched through its repositories (cosmic `seen`).
   On commit it diffs each one against its snapshot (P9). Writes cover only mapped (owned)
   predicates (P8).
3. **Compile.** The ChangeSet becomes **one** `DELETE{ground}INSERT{ground+version+token+outbox}
   WHERE{all guards}` (B7, T1, T2, E1). The aggregate-count policy is applied here (B6).
4. **Confirm.** An ASK on the token distinguishes success from `ConcurrencyConflict`.
   `@retry_on_conflict` replays (T6).
5. **After commit.** The identity map is cleared, or kept as `expire_on_commit=False`. Then
   `on_commit` hooks run, the in-process bus dispatches domain events, and handlers that change
   *other* aggregates open **new** UoWs (eventual consistency, rule 4). The outbox relay
   delivers externally.
6. **Capability-driven** (T7):
   - RDF4J/GraphDB: the same ChangeSet is sent inside a vendor transaction, and read-your-writes
     becomes available.
   - Fluree embedded: `transact(fn)`.
   - Chunking proxy: refuse unless `allow_degraded=True` (then T4 compensations plus a warning).
7. **Version as metadata.** The mapper owns the version. `uow.version_of(order)` gives the ETag
   for L4 `If-Match` (B11). Generated domain classes stay persistence-free.
8. **Reads that cross aggregates** go to read models or queries (X10), not to repositories.

What developers write is a repository call, domain methods, and `commit()`. They see one request
per commit and can print it. No ordering rules, autoflush or lazy-load traps are left to learn.

---

## 7. How it plugs into MWBv2 and an ACL-agnostic rdf-persistence

- **L0:** UML composition → LinkML `annotations` (`aggregate_root`, `owned`) or the
  `inlined`+`shared` convention. The generator derives aggregates, validates them (B2), and
  emits property paths for loading and ground-template builders for saving.
- **L1:** the aggregate session above. Repositories are generated per root (approach B) or
  generic (approach A, reading `SchemaView` at runtime).
- **L2:** one request per commit on any SPARQL 1.1 store; vendor adapters are optional.
- **L3 (DEC-8):** the session is ACL-agnostic. The enforcement port scopes the *graphs* the
  CONSTRUCT and the Update touch. Under A1 the graph stays free for tenancy and ACL, which is why
  A1 is the default. Under A2, graph-per-aggregate competes with graph-level ACL.
- **L4:** one resource per aggregate root. Owned parts appear as included or embedded
  resources (JSON:API `include`, JSON-LD framing with `@embed` from `inlined`). Writes are nested
  writes or Atomic Operations → one aggregate save. ETag/If-Match comes from the root version.
- **L6:** outbox triples → relay → SSE/webhooks; the event payload is the ChangeSet (RDF Patch,
  or mu changeSets).

## 8. Variant and approach fit

| Item | V1 portable | V2 semantic.works | V3 Fluree | V4 GraphDB | V5 CQRS reads | A runtime | B generated | C generic |
|---|---|---|---|---|---|---|---|---|
| Aggregate session (single guarded op, B7) | **enables** | **blocked** by chunking (degrade only) | supports (HTTP: guarded WHERE; embedded: real tx + conflict) | supports (+ vendor tx) | write side only | supports (boundaries from `SchemaView`) | **best** (generated repositories, templates) | partial (boundaries read at runtime; no domain methods) |
| Graph-per-aggregate (A2) | supports | conflicts (graphs = access) | weak (policies cannot target a graph) | supports | supports | supports | supports | supports |
| Outbox in same update (E1/B9) | enables | redundant (delta-notifier exists) | optional (ledger history) | enables | feeds the read replica | supports | supports | supports |
| One-aggregate policy (B6) | policy | n.a. (no atomicity anyway) | policy | policy (multi-request tx tempts wider transactions) | n.a. | supports | supports | supports |

## 9. Corrections to the integrated docs

1. `index.adoc` "Patterns worth borrowing → Aggregates" says "generated from LinkML
   composition". **LinkML has no composition construct.** `inlined` is serialization-only by
   its own definition (`meta.yaml:1783-1800`). Say instead: "derived from an annotation
   convention or `inlined`+`shared`, ideally sourced from UML composition".
2. `index.adoc` bottom line 3 ("a commit must become one request, guarded by a version check")
   is true but incomplete. **Several guarded operations in one request are not all-or-nothing.**
   The guard must sit in one single operation, with ground templates (§4.3). That also forbids
   blank nodes in owned parts.
3. `index.adoc` "Gaps → a unit of work over any SPARQL 1.1 store": add that it is much smaller
   than SQLAlchemy's. It needs no dependency sort, no autoflush and no savepoints, so its cost is
   low.

## 10. Proposed new features (area **B — Boundaries**)

| Id | Area | Feature | Seen in |
|---|---|---|---|
| B1 | Boundaries | **Aggregate declaration in the model**: root classes and owned slots, from LinkML annotations / the `inlined`+`shared` convention / UML composition | Spring Data JDBC (by structure); Axon `@Aggregate`; idea for LinkML |
| B2 | Boundaries | **Boundary validation at generation time**: single owner, no owned cycles, no outside references to non-root entities, IRIs derivable for owned parts | Spring Data assumption (docs); idea |
| B3 | Boundaries | **Whole-aggregate load** in one query (root + owned closure); no lazy loading inside the boundary | Spring Data JDBC; cosmic ch. 7 |
| B4 | Boundaries | **Whole-aggregate save** with replace-owned-subtree semantics, minimised by snapshot diff | Spring `deleteReferenced`+`insertReferenced`; refines P2/P9 |
| B5 | Boundaries | **Typed cross-aggregate references** (`Ref[T]` IRI) resolved explicitly; no navigation across boundaries | Spring `AggregateReference`; Vernon rule 3 |
| B6 | Boundaries | **Aggregates-per-commit policy** (strict / warn / allow) | Evans/Vernon; cosmic ch. 7 (none enforces it) |
| B7 | Boundaries | **Single conjunctive guarded operation**: all version guards in one WHERE, ground DELETE/INSERT templates → all-or-nothing on any SPARQL 1.1 store; refines T1/T2 | idea (new; SPARQL 1.1 Update semantics) |
| B8 | Boundaries | **Inspectable ChangeSet / dry-run** (pure value; unit-testable without a store; compiled to SPARQL, RDF Patch, Atomic Ops) | `Ecto.Multi` `to_list`; `Ecto.Changeset` |
| B9 | Boundaries | **Domain events collected on aggregates**, written to the outbox in the same request, dispatched after commit; refines E1 | cosmic `collect_new_events`; Spring `@DomainEvents` |
| B10 | Boundaries | **Aggregate storage strategy**: shared graph (A1) vs graph-per-aggregate (A2, GSP PUT, DROP GRAPH) | GSP; Solid resources; OldMan X15 |
| B11 | Boundaries | **Mapper-managed aggregate version** exposed as an ETag (domain classes stay persistence-free) | Spring `@Version` on root; cosmic (in-domain variant) |
| B12 | Boundaries | **After-commit hooks** (`on_commit`) | Django `transaction.on_commit`; Spring `AfterSaveEvent` |
| B13 | Boundaries | **Boundary-aware delete**: cascade inside the boundary; inbound references from other aggregates refused (ASK), left dangling, or cleaned up eventually (event) | SQLAlchemy `delete-orphan`; Ecto `on_replace`; refines R4/P11 |
| B14 | Boundaries | **Bounded-context partitioning**: per-context schema module → own package, repositories and graphs; cross-context only IRIs and events | cosmic-python; import-linter |
| B15 | Boundaries | **No-autoflush contract**: warn when a query runs with pending changes; read-your-writes only via the identity map unless the store offers T5 | SQLAlchemy `no_autoflush` (inverse) |
| B16 | Boundaries | **Process manager / saga support**: saga state as an aggregate, triggered by outbox events, idempotent | Axon, Marten/Wolverine |

## 11. Open questions for the developer

1. **Boundary source:** should aggregates be declared by explicit LinkML annotations
   (`aggregate_root`, `owned`), or inferred from `inlined`+`shared`? Can UML composition be
   carried through model2owl / uml2linkml (not checked)?
2. **Multi-aggregate commits:** default policy `warn` or `strict`?
3. **Storage strategy:** is A1 (shared graph, root version triple) the default, with A2
   graph-per-aggregate opt-in? This conflicts with graphs used for ACL or tenancy (DEC-8, V2).
4. **Version location:** mapper metadata (recommended, keeps LinkML classes clean) or a domain
   field as in cosmic-python?
5. **Event dispatch:** in-process message bus in the generated service layer, outbox relay only,
   or both?
6. **Blank nodes:** require IRIs for all owned entities (needed for guarded deletes), and
   skolemise blank nodes on import?

## 12. Not checked

- Hibernate, Django, Prisma (nested writes), Marten, Axon, Eventuous and pyeventsourcing were
  not cloned; their claims come from docs and general knowledge.
- The licence of the cosmic-python code repo was not checked (the GitHub API reports
  NOASSERTION).
- I did not test the single conjunctive guarded update against real stores. It follows from the
  SPARQL 1.1 Update semantics (a WHERE with zero solutions writes nothing; blank nodes are not
  allowed in DELETE templates). Test it on Oxigraph, Fuseki, GraphDB and Fluree before relying
  on it.
- Ecto's GitNexus index produced no clusters or flows (Elixir support); evidence is from direct
  source reading.

---

## Round 5

Candidates: **SA** = SQLAlchemy 2.x (`sqlalchemy` @57ddc05) · **SDJ** = Spring Data JDBC
(`spring-data-relational` @e466925) · **Ecto** (@c8091a1) · **CP** = cosmic-python code (@14c8479).
All four are relational or ORM benchmarks, so RDF-, LPG-, authz- and UI-specific features are
n.a. by construction. I confirmed that none of the four has an RDF, policy or UI module (grep of
`lib/`, `src/main` and `src/` for `rdf|sparql|policy|acl`: no hits beyond SQL GRANT helpers).

### (a) v4 cross-check

Legend: P present · p partial · A absent · – n.a.

| Id | SA | SDJ | Ecto | CP | Evidence |
|---|---|---|---|---|---|
| B1 aggregate declaration in model | A | **P** | p | p | SDJ: aggregate = everything reachable from the root, by structure (`WritingContext` paths via `findPersistentPropertyPaths(…isRelation)`); Ecto: `has_many`/`embeds_*` + `on_replace`; CP: by convention (`Product` holds `batches`). SA: relationships only, no root concept |
| B2 boundary validation at build time | A | p | A | A | SDJ asserts "no other entity points toward non-root entities" (docs) but does not check it (grep `validate.*aggregate`: none) |
| B3 whole-aggregate load | p | **P** | p | p | SDJ "No lazy loading or caching is done" (`src/main/antora/…/jdbc/why.adoc:21`); SA via `selectinload` options, not by default; Ecto explicit `preload`; CP loads `Product` + batches by mapper config |
| B4 whole-aggregate save | p | **P** | p | p | SDJ `deleteReferenced`+`insertReferenced`; SA cascade `save-update` + dirty diff; Ecto `cast_assoc` replace semantics; CP via SA session |
| B5 typed cross-aggregate references | A | **P** | A | p | `AggregateReference<T,ID>`; CP references by `sku`/`batchref` strings (`domain/model.py`) |
| B6 aggregates-per-commit policy | A | A | A | A | none enforces it (grep `aggregate` in UoW/tx code: none); CP states the rule only in the book |
| B7 single conjunctive guarded op | – | – | – | – | SPARQL-specific; relational analogue is the DB transaction |
| B8 inspectable change set / dry run | p | p | **P** | A | Ecto `Multi.to_list/1` (`multi.ex:764`); SA `session.new/dirty/deleted` + `inspect(obj).attrs.x.history` (no compiled preview); SDJ `AggregateChange` passed to `BeforeSaveEvent` (`JdbcAggregateTemplate.java:746-750`) |
| B9 events on aggregate → outbox → after commit | A | p | A | p | SDJ `@DomainEvents` (commons docs; publication relative to tx not stated); CP `collect_new_events` + in-memory bus; **no outbox in any** (grep `outbox`: 0 hits in all four) |
| B10 aggregate storage strategy | – | – | – | – | graph-specific |
| B11 mapper-managed version → ETag | p | p | p | A | SA `version_id_col` (mapped column on the class); SDJ `@Version` field on the root; Ecto `optimistic_lock` field; CP `version_number` in the domain (`model.py:12`). None keeps it outside the domain class; none emits an ETag |
| B12 after-commit hooks | **P** | P | A | A | SA `SessionEvents.after_commit` (`orm/events.py:1846`); SDJ `AfterSaveEvent` (`JdbcAggregateTemplate.java:754-757`, inside the tx; Spring `@TransactionalEventListener(AFTER_COMMIT)` for true after-commit, docs); Ecto: none (grep `after_commit\|on_commit` in `lib`: 0) |
| B13 boundary-aware delete | P | P | P | A | SA `delete-orphan` (`util.py:247`); SDJ deletes referenced entities with the root (`deleteWithVersion`, `:139-140`); Ecto `on_delete`/`on_replace: :delete` (`changeset.ex:199-225`) |
| B14 bounded-context partitioning | A | A | A | p | CP one package per context in the book (ch. 13 epilogue); not enforced in code |
| B15 no-autoflush contract | p | P | P | p | SA `no_autoflush` (`session.py:3159`), autoflush on by default; SDJ "no dirty tracking and no session" (`why.adoc:25`); Ecto has no session; CP inherits SA |
| B16 saga / process manager | A | A | A | A | grep `saga\|process.manager`: 0 hits |
| PG1–PG4 | – | – | – | – | property-graph projection |
| EV1 migration runner | p | A | p | A | SA → Alembic (separate project); Ecto → `Ecto.Migration` in `ecto_sql` (separate repo, not in this clone); SDJ relies on Flyway/Liquibase |
| EV2–EV9 | A | A | A | A | none in these repos (Alembic / ecto_sql are outside the clones; EV3 has an analogue in Alembic autogenerate, not checked here) |
| AZ30–AZ36 | – | – | – | – | authorization out of scope |
| G28–G34 | – | – | – | – | LinkML/RDF generation |
| G35 typed field metamodel | P | p | p | – | SA `Model.field` instrumented attributes (operators on class attributes); SDJ via Querydsl/`Criteria` strings; Ecto query macros on schema fields |
| G36 generated typed filter/input types | A | A | A | – | not generated (Prisma is the precedent) |
| T12 read-tracked optimistic commit | – | – | – | – | Fluree-specific |
| T13 read-only mode guard | p | P | A | A | SA engine `execution_options(postgresql_readonly=…)` dialect-level (docs); SDJ `@Transactional(readOnly = true)` (`SimpleJdbcRepository.java:51`) |
| T14 cross-store unit of work | **P** | A | A | A | SA `Session(binds=…)` + `twophase` (`session.py:1222-1226`); Ecto has no cross-repo transaction |
| S20–S23 | – | – | – | – | store-specific |
| X23, X24 | – | – | – | – | JSON-LD / MCP |
| E10 | – | – | – | – | notification channels |
| I7 reversible IRI minting | – | – | – | – | IRI-specific |
| I8 deferred id minting (at flush) | P | P | P | p | SA and SDJ get DB-generated PKs at flush/insert (`IdValueSource`, `WritingContext:62`); Ecto `autogenerate`; CP uses natural keys |
| P20 reference-aware flush ordering | **P** | p | p | p | SA topological sort (`unitofwork.py:442-466`); SDJ orders root before referenced actions by path; Ecto inserts parent before assocs; CP inherits SA. **For RDF it is not needed** (§1 item 1) |
| U11–U13 | – | – | – | – | UI |
| D14 stale-write / duplicate warning | – | – | – | – | multi-valued RDF specific |
| D15 parameter redaction in logs | P | A | p | A | SA `hide_parameters` (`engine/create.py:262`); Ecto `:log` option per repo call (`repo/schema.ex:1274`) controls logging, not redaction |
| D16 formal HTTP contract model | – | – | – | – | service |
| D17 inspectable compiled query | P | p | P | p | SA `str(stmt)` / `compile(compile_kwargs={"literal_binds": True})` (docs); Ecto `Repo.to_sql` (ecto_sql, docs); SDJ SQL logging only |
| D18 explicit-loading sentinel | p | A | **P** | A | Ecto `Ecto.Association.NotLoaded` (`association.ex:3`); SA `lazy="raise"` (`strategies.py:714`) |
| D19 test kit | p | A | p | p | CP `FakeRepository` / `FakeUnitOfWork` (tests in repo, book ch. 5–6); Ecto SQL sandbox (ecto_sql); SA `testing` plugin is internal |
| D20 shipped real-store fixtures | – | – | – | – | RDF stores |
| D21 tested documentation | P | A | p | A | SA `test/base/test_tutorials.py` runs the tutorials; Ecto doctests in guides (not checked) |
| D22 CURIEs everywhere | – | – | – | – | IRI-specific |
| D23 "did you mean" | A | P | A | A | SDJ `PropertyReferenceException` used in `QueryMapper.java` (commons message lists suggestions; docs) |
| D24 stable error codes + doc page | **P** | A | A | A | SA `code = "l7de"` etc. (`exc.py:269,429`) → sqlalche.me/e/… |
| D25 deterministic multi-value order | – | – | – | – | RDF sets |
| D26 typing regression tests | P | A | A | A | SA `test/typing/plain_files`, `test_mypy.py` |
| D27 fault-injection tests | A | A | A | A | not found |
| D28 contract fuzzing | – | – | – | – | service |
| D29 store-port observability (OTel) | p | p | p | A | SA engine events (no OTel in core); SDJ Micrometer via Spring (docs); Ecto `:telemetry` events (`repo/supervisor.ex:30`) |

**Counts over the 32 rows that apply to at least one benchmark** (B1–B16 minus B7/B10; EV1; EV2–EV9 as one row; G35, G36, T13, T14, I8, P20, D15, D17, D18, D19, D21, D23, D24, D26, D27, D29):
- SA: present 11, partial 10, absent 11
- SDJ: present 10, partial 8, absent 14
- Ecto: present 6, partial 11, absent 15
- CP: present 0, partial 11, absent 19, n.a. 2

All other v4 ids are n.a. **Headline:** no benchmark has an outbox (B9), a commit policy (B6),
build-time boundary validation (B2) or sagas (B16). These are the genuinely new parts of the
rdf-persistence design.

### (b) Page review — corrections to `angles/ddd.adoc` and `design-implications.adoc`

1. **ddd.adoc:14** and **design-implications.adoc:24-25** say the sort "exists to copy
   server-generated primary keys into foreign keys". This is incomplete. **Fix:** "exists because
   foreign-key constraints require parent rows before child rows (and reverse order for
   deletes), and because parent keys, often generated by the database, must be copied into child
   foreign keys". Client-assigned keys still need the order in SQL; only the absence of FK
   constraints removes it in RDF.
2. **design-implications.adoc:27** "autoflush has no place" overstates it. **Fix:** add "over
   portable SPARQL; with a vendor transaction (RDF4J/GraphDB, Fluree embedded) autoflush inside
   the transaction is possible (T5)".
3. **ddd.adoc:18** "several aggregates atomically at no extra cost". **Fix:** add the caveat "but
   with a larger conflict surface: one stale guard aborts the whole commit, and requests grow".
4. **ddd.adoc:164-169, and design-implications.adoc:54-58 (sequence diagram)** carry a missing
   caveat: confirming via `ASK { <root> rp:lastTx <T> }` gives a **false conflict** if another
   writer commits to the same root between our update and the ASK (it overwrites `rp:lastTx`).
   **Fix:** confirm against an append-only commit record written in the same update (for example
   the outbox entry `<urn:tx:T> a rp:Commit`), not against an overwritten triple on the root.
5. **ddd.adoc:168** is missing a caveat for **new aggregates**: a constant guard cannot express
   "does not exist yet". **Fix:** add "creation guards use `FILTER NOT EXISTS { <root> rp:version
   ?v }`, which keeps one-or-zero solutions".
6. **ddd.adoc:62** "simple, limited, opinionated" / "no persistence context, no lazy loading, no
   dirty checking" is correct but uncited. **Fix:** cite `spring-data-jdbc/README.adoc:6-7` and
   `src/main/antora/modules/ROOT/pages/jdbc/why.adoc:21,25` ("No lazy loading or caching is
   done", "There is no dirty tracking and no session").
7. **ddd.adoc:78** "Elixir's data-mapping library (José Valim, Dashbit)". **Fix:** "created at
   Plataformatec in 2013, now Dashbit; maintainers Eric Meadows-Jönsson, José Valim, Felipe
   Stival, Greg Rychlewski" (`README.md:203-204`, `mix.exs:44`).
8. **ddd.adoc:68** "Domain events … published on save* and delete*" is missing a caveat: the docs
   do not say whether publication happens inside the transaction. **Fix:** add "(inside the
   repository call; after-commit delivery needs `@TransactionalEventListener(AFTER_COMMIT)` —
   docs, not code-checked)". This also strengthens the outbox argument.
9. **ddd.adoc:197** cites `(X19)` for ETag / `If-Match`. **Check:** the angle-ddd proposal is
   B11. **Fix:** "(B11; HTTP side X19)".
10. **design-implications.adoc:76** "Optimistic concurrency on by default (as Rails
    `lock_version`, Pony)" is not my evidence, but Rails enables it only when a `lock_version`
    column exists (opt-in by schema). **Fix:** "(Pony: on by default; Rails: on once a
    `lock_version` column exists)" — flag for the angle-dx analyst.

That makes 10 page corrections (8 on ddd.adoc, 2 on design-implications.adoc only; items 1 and 4
touch both).

### (c) Final verdict and three things to remember

**Verdict: ideas** — none is a dependency. Spring Data JDBC is the design model, Ecto the
change-set model, SQLAlchemy the developer-experience benchmark, and cosmic-python the house
patterns to adopt in the service layer.

Three things a system architect must remember:
1. **The UoW to build is small.** It is an identity map, a snapshot diff, cascades along owned
   slots, and one guarded request per commit. There is no dependency sort, no autoflush and no
   savepoints. Do not port SQLAlchemy's machinery.
2. **Atomicity comes from one single guarded operation, not from one request.** Several guarded
   operations in one request can half-apply. Owned parts need IRIs. Confirm the commit through an
   append-only commit record, not an overwritable root triple.
3. **Boundaries must be declared, because LinkML cannot express them.** Use annotations or a
   convention, validated at build time. Cross-aggregate effects then go through an outbox written
   in the same update; no benchmark ships that, so it is ours to build.

### (d) Purpose and origin + variant fit (deep-dived candidates)

#### Purpose and origin

| Candidate | Built for | Who / context | Design angle | Where it fits (L0–L6) |
|---|---|---|---|---|
| SQLAlchemy 2.x | Pythonic SQL toolkit + Data Mapper ORM, so Python objects map onto relational schemas without hiding SQL | Mike Bayer, since 2005; community project, sponsored | database-first Data Mapper with implicit UoW | **L1 benchmark only**: identity map, cascade vocabulary, events, DX. Not a dependency; its flush engine solves a problem RDF does not have |
| Spring Data JDBC | a DDD-friendly alternative to JPA: "simple, limited, opinionated" (`README.adoc:6-7`) | Spring team (Jens Schauder), VMware → Broadcom | aggregate-first | **L1 design model**: repository per root, whole-aggregate load and save, root version, by-id references. Approach B generates its equivalent |
| Ecto | data mapping and validation for Elixir, with explicit, functional change tracking | Plataformatec (2013) → Dashbit; Meadows-Jönsson, Valim et al. (`mix.exs:44`) | change-as-data | **L1 idea**: the change set as a value (B8), validate before commit, `on_replace` semantics; also L6 (the change set doubles as the event delta) |
| cosmic-python | teaching DDD, ports and adapters and event-driven architecture in Python | Harry Percival & Bob Gregory (MADE.com), O'Reilly 2020 | pattern teaching | **L1 service layer** of the generated backend (Meaningfy house style): repository, UoW, message bus, domain events. L6 needs the outbox it omits |

#### Variant and approach fit

| Candidate (as idea source) | V1 portable | V2 semantic.works | V3 Fluree | V4 GraphDB | V5 CQRS | A runtime | B generated | C generic |
|---|---|---|---|---|---|---|---|---|
| SQLAlchemy (identity map, cascades, events) | supports | supports (mapper side only) | supports | supports; with vendor transactions even autoflush is possible | write side | supports | supports | partial |
| Spring Data JDBC (aggregate session) | **enables** | **blocked** for atomicity (chunking proxy) | supports | supports | write side; reads go to projections | supports (boundaries from `SchemaView`) | **best fit** (one generated repository per root) | partial (no domain methods) |
| Ecto (change set as value) | enables | supports: the change set can be emitted as mu changeSets | supports: maps onto `transact(fn)` | supports: the same change set goes inside a vendor transaction | feeds read-replica events | supports | supports | supports: a generic service can still build change sets |
| cosmic-python (UoW, bus, events) | enables | partial: the bus is redundant with delta-notifier | supports | supports | supports (events feed projections) | supports | **best fit** (generated service layer) | weak (no domain handlers) |

### (e) New features

None proposed. One refinement goes to the leader for **B7**: "confirmation through an
append-only commit record; creation guards via `FILTER NOT EXISTS`". It is a correction of B7's
description, not a new id. Why it matters: without it, B7 reports false conflicts under
concurrent writes to the same aggregate.

**Not checked (round 5):** Alembic, ecto_sql and Spring Data Commons were not cloned. Claims
about them (migrations, the sandbox, `@TransactionalEventListener`, "did you mean" text) come
from docs or general knowledge. The false-conflict scenario in (b) item 4 follows from the
update semantics and was not run against a store.
