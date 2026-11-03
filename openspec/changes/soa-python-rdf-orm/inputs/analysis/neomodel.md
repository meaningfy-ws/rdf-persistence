# neomodel

- **Repo:** https://github.com/neo4j-contrib/neomodel (clone `/home/lps/work/repos/neomodel`), docs https://neomodel.readthedocs.io/
- **Commit analysed:** `2f4a904` (master, 2026-10-20), version 7.0.0 (`neomodel/_version.py`; Changelog "Version 7.0.0 2026-08")
- **Licence:** MIT (`LICENSE`); author Robin Edwards; maintainers Marius Conjeaud, Antoine Nguyen, Athanasios Anastasiou (`pyproject.toml`)
- **Size:** `neomodel/` 54 files, 17,526 LOC. The async API (`async_/`, 6,440 LOC) is hand-written, and the sync API (`sync_/`, 6,370 LOC) is **generated** from it by `bin/make-unasync` (unasync + black + isort), so the hand-maintained core is about 11k LOC. `test/` holds 23,438 LOC and 866 `def test_` functions, about half of them generated sync twins.
- **GitNexus index:** `neomodel`, 208 files, 4,226 symbols, 9,552 edges, 193 clusters, 300 processes
- **Docs read:** `doc/source/getting_started.rst`, `transactions.rst`, `hooks.rst`, `pydantic.rst`, `properties.rst` (headings), `Changelog`, https://neomodel.readthedocs.io/en/latest/ (TOC, v7.0.0), https://github.com/neo4j-contrib/neomodel (1.1k stars, 241 forks, SonarCloud and RTD badges)

## Summary

neomodel is a mature (since 2013) Django-flavoured **Active Record** Object Graph Mapper for Neo4j. Nodes are Python classes with declarative `Property` descriptors and `RelationshipTo/From` definitions; a metaclass collects them. Each class gets a `.nodes` manager that returns a lazy, chainable, generic-typed `NodeSet` query object compiled to Cypher through a `QueryAST`. Transactions are explicit (`with db.transaction:` / decorator / `begin-commit-rollback`), and their state lives in `ContextVar`s. Relationship cardinality is checked on the client when connecting. A CLI installs schema constraints and indexes. A Pydantic bridge (v7) exports models for API layers. It has no identity map and no unit of work: each `save()` is one round-trip. It is the best-in-class benchmark for the declaration API, the query builder and transaction ergonomics, and transfers to RDF with clear translations.

## Architecture (from GitNexus)

GitNexus clusters split by `Async_` (178 and 41 symbols) and `Sync_` (189 and 40 symbols), which mirrors the unasync generation. The key classes, confirmed by `context`/`cypher`:

- **Declaration:** `async_/node.py:25` `NodeMeta` (metaclass: registers `Property` descriptors, caches `__all_properties__/__all_relationships__/__required_properties__`, rejects reserved names `id/element_id/deleted`, warns on single-member exclusion groups), `:148` `AsyncStructuredNode`, `async_/relationship.py:51` `AsyncStructuredRel` (edge with properties), `async_/property_manager.py:17` `AsyncPropertyManager` (inflate/deflate, `__properties__`).
- **Properties:** `properties.py:91` `Property[V]` (generic; `required`, `unique_index`, `index`, `fulltext_index`, `vector_index`, `default`, `db_property`, `inflate/deflate` at `:223-242`) with 15 subclasses (`StringProperty:291`, `IntegerProperty:349`, `ArrayProperty:368`, `DateTimeProperty:518`, `JSONProperty:598`, `AliasProperty:618`, `UniqueIdProperty:671`, …).
- **Relationships:** `async_/relationship_manager.py:487` `AsyncRelationshipDefinition` with `RelationshipTo:677`, `RelationshipFrom:696`, `Relationship:715` (undirected); `:51` `AsyncRelationshipManager` (`connect:128`, `reconnect:294`, `disconnect:347`, `disconnect_all:364`, `filter:402`, `order_by:412`); cardinality managers in `async_/cardinality.py` (`AsyncZeroOrOne:23`, `AsyncOneOrMore:72`, `AsyncOne:115`, default `ZeroOrMore`).
- **Query:** `async_/match.py:520` `QueryAST`, `:575` `AsyncQueryBuilder`, `:1415` `AsyncBaseSet`, `:1650` `AsyncNodeSet` (GitNexus `context` lists methods `get/get_or_none/first/first_or_none/filter/exclude/order_by/traverse/annotate/subquery/intermediate_transform/resolve_subgraph/bulk_*`), `:2109` `AsyncTraversal`, `:1404` `Path`, aggregation helpers `Collect/Last/Size/RawCypher` (`:1581-1631`), `match_q.py:165` `Q` objects (AND/OR/NOT).
- **Database facade:** `async_/database.py:44` `AsyncDatabase` (`adb`/`db`) delegates to `AsyncConnectionManager` (`connection.py:91`, ContextVars at `:124-136`), `AsyncQueryRunner` (`query.py:134`, `cypher_query(..., resolve_objects=…)` at `:242`) and `AsyncSchemaManager` (`schema.py:36`, `install_labels:203`, `install_all_labels:170`, `drop_constraints:99`). The v7 changelog records this as a god-object split behind an unchanged facade.
- **Transactions:** `async_/transaction.py:19` `AsyncTransactionProxy` (context manager plus decorator, `__call__` for options), `:94` `BookmarkingAsyncTransactionProxy`, `:117` `ImpersonationHandler`.
- **Class registry:** `_node_class_registry.py`, with lazy discovery from the live class hierarchy in v7 to resolve label sets to classes.
- **CLI scripts:** `scripts/neomodel_install_labels.py`, `neomodel_remove_labels.py`, `neomodel_inspect_database.py` (reverse-engineers models from data), `neomodel_generate_diagram.py` (PlantUML/arrows).
- **Contrib:** `contrib/pydantic.py:257` `PydanticBridge` (`to_pydantic_model`, `to_pydantic`, `from_pydantic`, `pydantic_schema`), `contrib/async_/semi_structured.py` (ad-hoc properties), `contrib/spatial_properties.py:524` `PointProperty`.
- **GitNexus processes** are mostly config and CLI flows (e.g. `proc_230_transaction_timeout`, `TRANSACTION_TIMEOUT → From_env`). The core CRUD paths appear as definitions (`StructuredNode.save`, `bulk_save`, `NodeSet.bulk_create`), not as traced processes.

## Implementation principles

- **Mapping:** `Property` descriptors on the class are collected by `NodeMeta.__new__` (`node.py:36-125`), and `deflate` (Python → DB) and `inflate` (DB → Python) convert values per property (`properties.py:223-242`). The label is the class name, or `__label__`. Inheritance adds every ancestor's label (`node.py:730` `inherited_labels`), and on read the registry maps the node's label set to the most specific class, giving polymorphic loading.
- **Identity:** the database `element_id`. `__eq__`/`__hash__` compare `element_id` (unsaved nodes compare by object identity, `node.py:171-200`). `UniqueIdProperty` (uuid4 hex with a unique constraint) provides application keys. **There is no identity map**: two fetches return two objects.
- **Save:** Active Record. `save()` (`node.py:801-845`) issues `MATCH … SET` on update (with backtick-escaped keys and positional parameters against injection) or a bulk `UNWIND … CREATE` on create; `@hooks` wraps `pre_save/post_save` (`hooks.py`). `bulk_save` does at most two round-trips (v7). `create_or_update`/`get_or_create` use `MERGE` (`_build_merge_query`, `node.py:241`).
- **Relationships:** lazy. `person.friends` is a manager that queries on `.all()`, `.filter()` and so on. Eager loading is explicit through `NodeSet.traverse('city__country', Path(..., optional=True))` and `resolve_subgraph()`. Cardinality is enforced **client-side** in `connect()` with a pre-count (`cardinality.py:122-135`), with an optional soft mode (`config.soft_cardinality_check`). `exclusion_group` (v7) adds mutually exclusive relationships.
- **Querying:** Django-style lookups `filter(age__gt=3, name__istartswith="m", lives_in__name="X")` with `Q` objects; operators include `lt/gt/in/isnull/regex/exists/includes/...` (`match.py:162-171`). The query builder fills a `QueryAST` (match, optional_match, where, order_by, skip, limit, subgraph) and then renders Cypher. Slicing maps to SKIP/LIMIT, `len()` to `count()`, `in` to existence. The escape hatch is `db.cypher_query(q, params, resolve_objects=True)`, which inflates raw results back to model objects.
- **Transactions:** `db.transaction`, `db.read_transaction`, `db.write_transaction` and `db.parallel_read_transaction`, each usable as a context manager, decorator or `db.begin/commit/rollback`. Rollback happens on exception, and `ConstraintValidationFailed` is translated to `UniqueProperty` (`transaction.py:51-62`). Timeouts and bookmarks (causal consistency) are supported. State is per context through `ContextVar` (`connection.py:124-136`), so threads and asyncio tasks are safe while the driver is shared process-wide (v7).
- **Sync and async:** a single async source of truth; the sync code is generated (`bin/make-unasync`). Both are first-class public APIs (`from neomodel import db, adb`).
- **Schema:** constraints and indexes are derived from `unique_index/index/fulltext_index/vector_index` and applied explicitly by `neomodel_install_labels` or `db.install_all_labels()`. They are never applied implicitly at import.
- **Serialisation:** the Pydantic bridge generates a pydantic v2 model from a node class (required, default, choices, `max_length`, PATCH-style `optional`), plus `to_pydantic`, `from_pydantic` and `pydantic_schema` → JSON Schema (`contrib/pydantic.py:159-282`).

## Patterns catalogue

| Pattern | Where |
|---|---|
| Active Record | `async_/node.py:801` `save`, `:632` `delete`, `:785` `refresh` |
| Metaclass-driven declarative mapping | `async_/node.py:25` `NodeMeta` |
| Descriptor-based typed properties with inflate/deflate | `properties.py:91` `Property[V]` |
| Manager / Query Object (lazy, chainable, generic) | `node.py:133` `_NodesProperty`, `match.py:1650` `AsyncNodeSet[T]` |
| Query AST → renderer | `match.py:520` `QueryAST`, `:575` `AsyncQueryBuilder` |
| Specification objects (Q, AND/OR/NOT) | `match_q.py:165` |
| Template-method hooks | `hooks.py` (`pre_/post_save`, `pre_/post_delete`, `post_create`) |
| Transaction script / context-manager-decorator proxy | `async_/transaction.py:19` |
| Context-local session state | `async_/connection.py:124-136` (`ContextVar`) |
| Facade over collaborators | `async_/database.py:44` → ConnectionManager / QueryRunner / SchemaManager |
| Registry (label set → class) for polymorphic loading | `_node_class_registry.py` |
| Code generation async → sync | `bin/make-unasync` |
| Reverse engineering (data → model code) | `scripts/neomodel_inspect_database.py` |
| Bridge / adapter to pydantic | `contrib/pydantic.py:257` |

## Docs vs code

- "Full transaction support", context manager / decorator / manual, read/write, timeouts, bookmarks: **confirmed** (`transaction.py:19-140`, `database.py:241-256`).
- "Thread safety": **confirmed** as ContextVar-scoped session and transaction state (`connection.py:124-136`); the shared driver is described in the v7 changelog.
- "Schema enforcement through cardinality restrictions": **confirmed, client-side only** (`cardinality.py:122-135`). Concurrent writers can still violate it; the DB enforces nothing for relationships.
- Hooks `pre_save, post_save, pre_delete, post_delete, post_create` (`hooks.rst`): **confirmed** (`hooks.py`); `post_create` is not called by `get_or_create`/`create_or_update` (documented).
- Pydantic bridge "v1 maps scalar properties; relationship expansion left for a follow-up" (Changelog 7.0.0): **confirmed** by the docs. Relationship expansion is absent, as stated.
- Identity map / unit of work: **never claimed**; absent in code.

## Scores C1–C8

Scored for its own store; the RDF-specific items in C1 and C7 are mapped to their Neo4j equivalents.

| # | Score | Justification | Evidence |
|---|---|---|---|
| C1 Feature coverage | 4 | Full CRUD, directed and undirected relationships with properties, cardinality, rich queries, transactions, bulk ops, validation. No identity map or UoW; JSON-LD/named graphs n.a. | `node.py`, `relationship_manager.py`, `match.py`, `transaction.py` |
| C2 Design patterns | 4 | Clear, named patterns (Active Record, Manager/QuerySet, AST builder, hooks, context-local tx, facade). Persistence is mixed into domain objects (Active Record) | see catalogue |
| C3 Developer friendliness | 5 | Django-like happy path, generic typing (v7, mypy-clean in CI), good errors (`DoesNotExist` per class, `AttemptedCardinalityViolation`, `UniqueProperty`), 4k lines of RTD docs, sync and async | `node.py:36-40`; RTD TOC; Changelog 7.0.0 |
| C4 Ease of adoption | 4 | Two runtime deps (`neo4j`, `typing-extensions`), explicit connection URL, CLI tools. Needs a running Neo4j; no in-memory store | `pyproject.toml` |
| C5 Reuse of foundations | 4 | Builds on the official neo4j driver and pydantic (optional). Its own Cypher builder is appropriate (no standard AST library) | `pyproject.toml`; `contrib/pydantic.py` |
| C6 Data-centric / DDD | 2 | Code-first classes. Active Record couples domain and persistence, so a repository per aggregate means wrapping it. Reverse engineering from data exists; no schema-language input | `node.py:801`; `scripts/neomodel_inspect_database.py` |
| C7 Portability | 1 | Neo4j and Cypher only (Bolt driver, `elementId`, APOC for inspect). By design not portable | `async_/connection.py`, `node.py:640` (`elementId` + `DETACH DELETE`) |
| C8 Health | 5 | 866 tests (two APIs), CI integration tests against Neo4j with Codecov, CodeQL, mypy, SonarCloud, regular releases (6.0 → 7.0 in 2025-12 → 2026-08), 3+ maintainers, 1.1k stars | `.github/workflows/`; Changelog; GitHub page |

## Feature inventory

| Id | Status | Evidence |
|---|---|---|
| M1 | present | `StructuredNode` subclasses with `Property` descriptors |
| M2 | absent | Only Python classes (model diagram output, no input) |
| M3 | partial | Reverse codegen from DB data (`neomodel_inspect_database.py`); sync code generated from async |
| M4 | present | Inherited labels plus registry resolution to the most specific class (`node.py:730`, `_node_class_registry.py`) |
| M5 | present | `required`, `choices`, regex/email, type deflate on save/load; cardinality on connect |
| I1 | present | `UniqueIdProperty` (uuid4) or DB `element_id` |
| I2 | n.a. | No blank-node equivalent; embedded data via `JSONProperty` |
| I3 | absent | `__eq__` by `element_id` only (`node.py:171`) |
| R1 | present | `ArrayProperty` (ordered list); multi-relationships |
| R2 | present | `RelationshipTo/From/Relationship`, relationship models with properties (`StructuredRel`) |
| R3 | present | Lazy managers; eager `traverse()`/`Path(optional=True)`/`resolve_subgraph` |
| R4 | absent | `delete()` = `DETACH DELETE` of the node only; no cascade |
| L1 | present | Typed properties with inflate/deflate; `DateTimeProperty`, `PointProperty`, … |
| L2 | n.a. | — |
| P1 | present | `save/delete/refresh`, `nodes.get/filter` |
| P2 | partial | `SET` of all properties on save (no dirty tracking) |
| P3 | absent | — |
| P4 | present | `db.transaction` (context manager, decorator, manual), read/write, timeouts |
| P5 | absent | — (bookmarks give causal consistency, not optimistic locking) |
| P6 | partial | Multi-database names (ContextVar `database_name`); no named graphs |
| P7 | present | `bulk_create/bulk_save/bulk_create_or_update` (UNWIND) |
| Q1 | present | `nodes.get(uid=…)`, `element_id` lookups |
| Q2 | present | `filter()` lookups plus `Q` (`match.py`, `match_q.py`) |
| Q3 | present | `cypher_query(resolve_objects=True)`, `StructuredNode.cypher` |
| Q4 | present | Slicing, `order_by`, `annotate`, `Collect/Last/Size`, `subquery` |
| Q5 | present | `traverse('a__b__c')`, `Path`, relationship filters `lives_in__name=` |
| S1–S3 | n.a. | Neo4j only |
| S4 | absent | Single backend |
| X1, X2 | absent | — |
| X3 | partial | Via `django_neomodel` (external) |
| X4 | present | `pydantic_schema()` → JSON Schema (`contrib/pydantic.py:251`) |
| X5 | partial | Hooks; Django signals via `django_neomodel` |
| D1 | present | Generic `NodeSet[T]`, typed property access, mypy in CI (v7) |
| D2 | present | Full async API (`adb`, `AsyncStructuredNode`) |
| D3 | partial | Django via external package; pydantic bridge for FastAPI |
| D4 | present | RTD: getting started, topic guides, API reference (sync and async) |
| D5 | partial | Tests need a live Neo4j; no in-memory fake |
| O1, O2 | n.a. | — |
| A1 | partial | `db.impersonate(user=…)` (Neo4j Enterprise) — noted only |

### Proposed new features

- **P9 Read/write transaction designation:** `read_transaction` vs `write_transaction` (routing to replicas). This maps to a SPARQL query endpoint vs an update endpoint.
- **P10 Transaction timeouts and causal bookmarks:** per-transaction timeout plus bookmarks passed between processes.
- **P11 Bulk upsert / get-or-create (MERGE semantics):** `bulk_create_or_update`, `get_or_create` keyed on chosen properties.
- **R5 Relationship cardinality constraints:** `One / ZeroOrOne / OneOrMore / ZeroOrMore`, checked on connect, with a soft mode (SHACL `sh:minCount/maxCount` analogue).
- **R6 Mutually exclusive relationships:** `exclusion_group` (SHACL `sh:xone` analogue).
- **R7 Relationship (edge) models with properties:** `StructuredRel` (RDF analogue: RDF-star / reification / n-ary class).
- **M7 Schema install / migration CLI:** derive and apply DB constraints and indexes from the model (`install_labels`); for RDF, emit SHACL shapes and text indexes.
- **M8 Reverse engineering from data:** generate model classes from existing data (`inspect_database`); for RDF, from VoID or SHACL induction.
- **D6 Lifecycle hooks:** `pre_/post_save`, `pre_/post_delete`, `post_create` on entities and relationships.
- **D7 Single-source sync and async APIs:** async-first code with the sync API generated by unasync.
- **X8 Pydantic / JSON-Schema bridge:** export the model as pydantic and JSON Schema for API layers.

## JS-friendliness

Indirect only. It has no HTTP layer of its own. `pydantic_schema()` yields JSON Schema, and `to_pydantic` makes FastAPI response models trivial, from which OpenAPI → TS types can be produced. It has no JSON-LD and no linked-data contract.

## Reuse verdict for rdf-persistence: **borrow ideas** (API ergonomics; not the Active Record core)

Patterns that transfer to RDF, with the translation:

| neomodel | rdf-persistence translation |
|---|---|
| `Property` descriptors with `required/default/choices`, inflate/deflate | pydantic fields (LinkML-generated) plus a mapper that converts to rdflib `Literal` with xsd datatype/lang (L1/L2) |
| Label = class, inherited labels, registry → most specific class | `rdf:type` set (class plus superclasses from LinkML `is_a`), resolved to the most specific pydantic class on load (M4) |
| `RelationshipTo/From/Relationship` | slot with `range` = class; `From` = SPARQL inverse path `^p` / LinkML `inverse`; undirected has no direct RDF analogue (use two predicates or `owl:SymmetricProperty`) |
| Cardinality managers | LinkML `required/multivalued/minimum_cardinality`, checked on save or by SHACL (R5) |
| `StructuredRel` (edge properties) | Avoid in v1; if needed use an n-ary class or RDF-star (R7) |
| `.nodes` manager → lazy `NodeSet[T]` with `filter(field__op=…)`, `Q`, slicing, `order_by` | `Repository[T].query().filter(...)` compiled to a SPARQL SELECT with FILTERs, wrapped by CONSTRUCT (as LDkit and Prez do); keep it lazy and generic-typed |
| `traverse('a__b')` / `Path(optional=True)` | SPARQL property paths and OPTIONAL blocks for eager loading (Q5, R3) |
| `QueryAST` → renderer | Same split: AST (or `sparql-grammar`, see Prez) → SPARQL string |
| `cypher_query(resolve_objects=True)` | raw SPARQL CONSTRUCT → mapper → objects (Q3) |
| `db.transaction` as context manager **and** decorator, read/write variants, ContextVar-scoped | `with session.begin():` / `@transactional`; local stores give a real transaction (pyoxigraph/rdflib); remote stores buffer one SPARQL Update request (atomic per request) (P4) |
| Hooks `pre_/post_save/delete` | Domain events or session hooks; keep them out of domain classes (cosmic-python) |
| `install_labels` CLI | `rdf-persistence install-shapes` emitting SHACL from LinkML (M7) |
| Pydantic bridge | Unnecessary if the domain is already pydantic (LinkML gen-pydantic); keep JSON-Schema export (X4) |
| async-first plus unasync-generated sync | Strong candidate for D2 without double maintenance (D7) |

Do **not** copy: Active Record (it conflicts with DEC "domain free of persistence code" and cosmic-python), save without dirty tracking (it rewrites all properties), client-side cardinality checks without transactional isolation, or the global `db` singleton as the only entry point (prefer an injectable session or unit of work).

## Risks / anti-patterns observed

- Active Record couples persistence to the domain. Testing needs a live Neo4j (`test/conftest.py`), and there is no in-memory fake.
- No identity map: aliasing bugs are possible (two objects for one node, last write wins).
- Cardinality and exclusion checks are read-then-write on the client, so they race under concurrency unless wrapped in a transaction.
- A global module-level `db`/`adb` singleton with module-level config makes dependency injection awkward.
- 7.0 made several breaking API moves (bulk ops moved to `NodeSet`, `match()` return type changed). A long-lived OGM accumulates API churn, so rdf-persistence should keep its public surface small from day one.

## Round 2 cross-check (taxonomy v1)

Checked against `docs/modules/ROOT/pages/architecture/soa/feature-taxonomy.adoc` (v1). Each "absent" was confirmed with a grep over `neomodel/`: skolem, hydra, jsonapi, find_by_, facet, readonly, owl and user-defined-function registration return nothing relevant. The `imports`/`infer`/`diff` hits are Python imports and unrelated comments. Line numbers refer to `async_/`; the generated `sync_/` twins have the same structure.

| Id | Status | Evidence |
|---|---|---|
| M6 | absent | Classes are written in code; `inspect_database` generates source (codegen), not runtime classes |
| M7 | present | The property name is the DB key by convention, with a per-field `db_property` override (`doc/source/properties.rst:165-180`, `properties.py:91`) |
| M8 | n.a. | — |
| M9 | partial | `AliasProperty(to=…)`: a second attribute on the same stored property (`properties.py:618-670`) |
| M10 | present | Methods on `StructuredNode` subclasses (Active Record, `async_/node.py:148`) |
| M11 | absent | Undefined DB properties are silently ignored on inflate (`async_/property_manager.py:88`, `:109`); `SemiStructuredNode` keeps them (`contrib/async_/semi_structured.py:5`) |
| M12 | absent | Labels only (`node.py:730` `inherited_labels`) |
| M13 | present | `install_labels` / `install_all_labels` create constraints and indexes (`async_/schema.py:170`, `:203`, `:346`); CLI `scripts/neomodel_install_labels.py` |
| M14 | present | `scripts/neomodel_inspect_database.py` (models from data, needs APOC) |
| M15 | absent | — |
| I4 | n.a. | No blank nodes in LPG |
| R5 | present | `AsyncOne/ZeroOrOne/OneOrMore` (`async_/cardinality.py:23-177`), with soft mode |
| R6 | present | `exclusion_group` (`node.py:89-104` warning; Changelog 7.0.0) |
| R7 | present | `AsyncStructuredRel` with properties (`async_/relationship.py:51`) |
| R8 | absent | Reverse navigation needs `RelationshipFrom` or `Relationship` to be declared (`relationship_manager.py:677-715`) |
| L3 | present | Custom `Property` subclasses with `inflate/deflate` (`properties.py:91`, `:223-242`; `doc/source/extending.rst`) |
| P8 | present | `save()` SETs only defined keys, so other node properties are preserved (`node.py:812-830`) |
| P9 | absent | No dirty tracking; all properties are SET on every save (`node.py:810`) |
| P10 | partial | Relationships: `connect/disconnect/replace` are add/remove/set (`relationship_manager.py:128-364`); `ArrayProperty` is replaced whole |
| P11 | absent | `DETACH DELETE` of the node only (`node.py:640`) |
| P12 | n.a. | No graphs; the database is chosen by name via a ContextVar (`async_/connection.py:130`) |
| P13 | present | read/write transactions, timeouts, bookmarks (`async_/transaction.py:19-140`) |
| P14 | present | `bulk_create_or_update`, `bulk_get_or_create` with `merge_by` (`async_/match.py:1754-1800`, `node.py:241`) |
| P15 | partial | `parallel_read_transaction` (Enterprise) plus ContextVar-isolated sessions (`transaction.py:34-42`, `connection.py:124-136`) |
| Q6 | present | Positional `$pN` parameters plus identifier escaping (`node.py:812-825`, `schema.py:346` `escape_identifier`) |
| Q7 | partial | `QueryAST` holds string fragments rendered by `AsyncQueryBuilder` (`async_/match.py:520`, `:575`) |
| Q8 | absent | Django kwargs lookups, not method names |
| Q9 | present | `traverse()` and `resolve_subgraph()` fetch related nodes in one query (`match.py:1934`, `:2000`) |
| Q10 | present | `resolve_subgraph` nests path rows into objects (`match.py:2000`) |
| Q11 | absent | `cypher_query` runs anything |
| Q12 | present | `fulltext_index` plus `FulltextFilter` (`properties.py:51`, `semantic_filters.py`, `match.py:534`) |
| Q13 | absent | No UDF registration from Python |
| Q14 | absent | — |
| Q15 | partial | `len()`/`get_len` counts, `annotate` with `Collect/Size` aggregations (`match.py:1458`, `:1946`); no facets or capped counts |
| Q16 | n.a. | — |
| Q17 | present | Results resolve to the most specific class through the label registry (`async_/query.py:142-182`; `test/async_/test_issue283.py:127`) |
| Q18 | n.a. | — |
| S5 | present | Read vs write transactions route to cluster members (`doc/source/transactions.rst` "Explicit Transactions"; `transaction.py:22` `access_mode`) |
| S6 | absent | Only a class-registry index cache (`_node_class_registry.py:90`) |
| S7 | partial | Delegates to the driver's `max_transaction_retry_time` (`config.py:93`, `async_/connection.py:298`); no chunking beyond the UNWIND bulk ops |
| S8 | absent | Bound to the official `neo4j` driver; no port |
| X6 | absent | — |
| X7 | n.a. | No HTTP layer |
| X8 | absent | — |
| X9 | partial | `db_property` maps the attribute name to the stored key (`properties.rst:165`) |
| X10 | absent | — |
| X11 | absent | — |
| X12 | absent | — |
| X13 | partial | Impersonated user and target database are carried in ContextVars to every query (`connection.py:124-136`, `transaction.py:117`) |
| X14 | absent | — |
| D6 | present | `hooks.py`; `pre_/post_save`, `pre_/post_delete`, `post_create` |
| D7 | present | `bin/make-unasync` generates `sync_/` from `async_/` |
| D8 | partial | CI matrix of Python 3.10–3.14 × Neo4j community/enterprise 4.4–5.x (`.github/workflows/integration-tests.yml:35-37`); one store family, no in-memory store |
| D9 | absent | — |
| RAD1 | absent | Admin and CRUD UI only via the external `django_neomodel` |
| RAD2 | n.a. | — |
| O3–O7 | n.a. | No ontology layer |
| A2 | n.a. | — |
| A3 | absent | Only reserved-name guards (`node.py:46-63`) |
| O2 (refined) | n.a. | — |
| X4 (refined) | present | `pydantic_schema()` / `to_pydantic_model()` → JSON Schema (`contrib/pydantic.py:159-282`); there are no RDF-term types |
| X5 (refined by X12) | partial | Hooks only; no change-set format |
| D2 (refined by D7) | present | `adb` / `Async*` API |

### Proposed new features (round 2)

- **Q19 Vector / semantic similarity search:** `vector_index` plus `VectorFilter` (`properties.py:71`, `semantic_filters.py`). RDF analogue: an embedding index over literals.
- **D10 Model diagram generation:** `scripts/neomodel_generate_diagram.py` (PlantUML/arrows from model classes).
- **I5 Hashable entity equality by persistent id:** `__eq__`/`__hash__` on the DB id, with object identity for unsaved entities (`node.py:171-200`). The minimum identity contract when there is no identity map.

## Round 3

### (a) v2 cross-check

| Id | Status | Evidence |
|---|---|---|
| M16 | partial | `__optional_labels__` let a node carry extra labels (`doc/source/extending.rst:46-49`); behaviour comes from one Python class (MRO), and labels resolve to a single class through the registry (`async_/query.py:171`) |
| M17 | present | `NodeMeta.__new__` rejects reserved names `id/element_id/deleted` and warns on single-member exclusion groups (`async_/node.py:46-104`); `Property.__init__` rejects `required`+`default` and `unique_index`+`index` (`properties.py:146-153`); relationship class redefinition raises `RelationshipClassRedefined` (`exceptions.py:136`) |
| I5 | absent | — |
| I6 | present | `__eq__`/`__hash__` by `element_id`, object identity when unsaved (`async_/node.py:171-200`) |
| P16 | absent | `delete()` is a hard `DETACH DELETE` (`node.py:640`) |
| P17 | absent | — |
| P18 | partial | `pre_save` hooks can mutate properties before the write (`hooks.py`); there is no write-path transformation on the generated query |
| P19 | absent | — |
| Q19 | present | `__regex`, `__iregex`, `__contains`, `__startswith`, `__istartswith` lookups (`async_/match.py:162-171` `_SPECIAL_OPERATOR_REGEX`) |
| Q20 | present | `vector_index` plus `VectorFilter` (`properties.py:71`, `semantic_filters.py`, `match.py:533`) |
| S9 | absent | Single driver (multi-database by name only) |
| S10 | n.a. | — |
| S11 | partial | Schema admin: `install_all_labels`, `drop_constraints`, `remove_all_labels` (`async_/schema.py:99-203`, `scripts/neomodel_remove_labels.py`); no backup or optimise |
| S12 | absent | One Cypher per call; `bulk_*` batch writes via UNWIND (P7/P14) |
| S13 | present | Async iteration streams records (`async_/match.py:1355-1371` → `_stream_cypher_query`, `query.py:362-397`) |
| S14 | present | Slow-query log with timing and redacted parameters (`async_/query.py:81`, `:100-115`; `config.cypher_debug`, `slow_queries`) |
| X15 | n.a. | — |
| X16 | n.a. | — |
| D10 | present | `scripts/neomodel_generate_diagram.py` (PlantUML, arrows) |

### (b) Developer experience: the "loved OGM" benchmark

- **Shortest complete CRUD:** about 14 lines from `doc/source/getting_started.rst`: config (`:9-12`, 2 lines), a class with 2–3 properties (`:43-53`), then `:168-172` `Person(name='Jim', age=3).save()` / `jim.age = 4; jim.save()` / `Person.nodes.get(name='Jim')` / `jim.delete()`. Add `neomodel_install_labels` once for constraints.
- **Concepts to learn:** about eight: `StructuredNode`, `Property` types plus options, `RelationshipTo/From/Relationship`, cardinality classes, `.nodes` / `NodeSet` lookups (`field__op`), `db` vs `adb` (sync/async), `db.transaction`, and `install_labels`. All of them are Django-familiar.
- **Concrete API choices that make it pleasant** (worth copying):
  1. **Declare once, in the class body:** properties and relationships are class attributes, and the metaclass gathers them (`node.py:36-125`). There is no separate mapping file.
  2. **Manager on the class:** `Person.nodes` returns a lazy, chainable, **generic-typed** `NodeSet[Person]`. `get`, `get_or_none`, `first`, `first_or_none`, `filter`, `exclude`, `order_by`, slicing, `len` and `in` follow Python and Django idioms (`match.py:1650-2105`).
  3. **Lookups as kwargs:** `filter(age__gt=3, lives_in__name="Paris")` crosses relationships without joins, and `Q()` handles OR/NOT (`match_q.py:165`).
  4. **Per-class exceptions:** `Person.DoesNotExist` is created by the metaclass (`node.py:39-41`), so `except Person.DoesNotExist` reads naturally.
  5. **Relationship managers with verbs:** `jim.country.connect(de)`, `.disconnect`, `.reconnect`, `.replace`, `.is_connected`, `.single()` (`relationship_manager.py:128-364`, `cardinality.py:136`).
  6. **One transaction object, three styles:** context manager, decorator and manual, with `read_`/`write_` variants and a `timeout=` option (`transaction.py:19-91`).
  7. **Async without a second mental model:** names are prefixed `Async*`, and the sync API is generated (`bin/make-unasync`).
  8. **An escape hatch that returns models:** `db.cypher_query(q, params, resolve_objects=True)` (`query.py:242`).
  9. **Explicit schema install** rather than implicit migrations (`schema.py:203`).
  10. **Typed property access** (v7): `node.name` is `str` in the IDE, and mypy runs in CI (Changelog 7.0.0).
- **Real errors:**
  - `CardinalityViolation: Expected: {rel_manager}, got: {actual}.` (`exceptions.py:33-36`).
  - `Attempting to deflate property '{name}' on {obj} of class '{cls}': {msg}` (`exceptions.py:196`).
  - `Node with labels {labels} does not resolve to any of the known objects` followed by the full registry dump (`exceptions.py:117`). These are actionable messages that include the model context.
- **Docs:** about 4,000 lines on RTD, including getting started, topic guides, full sync and async API reference, and a full worked example.
- **Footguns:**
  1. There is no identity map, so the same node fetched twice gives two objects and the last `save()` wins.
  2. Lazy relationship access invites N+1 queries unless you use `traverse()`.
  3. `post_create` is not called by `get_or_create`/`create_or_update` (`hooks.rst`).
  4. A global `db` singleton plus module config makes DI and test isolation awkward. Tests need a live Neo4j (`test/conftest.py`).
  5. Cardinality checks are client-side read-then-write and can race.
  6. `save()` rewrites all properties.
  7. 7.0 made API-moving breaking changes (`match()` return type, bulk ops moved).
- **DX score: 5/5.** It is the reference for the shape of a Pythonic graph-persistence API. Its footguns are architectural (Active Record, no UoW), not ergonomic.

### (c) Authorization seams

- **neomodel has no ACL concept.** It runs everything as the connection user (credentials in `database_url`).
- **Its one seam is identity propagation:** `db.impersonate(user=…)` as a context manager or decorator (`async_/transaction.py:117` `ImpersonationHandler`, impersonated user in a ContextVar, `connection.py:133`). With it, the **store** becomes the PEP and PDP: Neo4j Enterprise RBAC grants `TRAVERSE` / `READ {prop}` / `MATCH` / `WRITE` / `SET PROPERTY` / `CREATE` / `DELETE` per database, label, relationship type and property, plus property-based access control. All of these are enforced server-side, so queries silently return less data for unprivileged users. Impersonation is Enterprise-only.
- **Other seams:** hooks (`pre_save`/`pre_delete`) can call a PDP, but they are per object and bypassed by raw Cypher and `bulk_*`, so they are not a reliable PEP. A repository wrapper over `NodeSet` is the natural application-level PEP.
- **Lesson for rdf-persistence (DEC-8):** the "impersonate / forward the end-user identity to a store that enforces policy natively" pattern carries over directly. RDF analogues are GraphDB or Stardog per-graph RBAC, Virtuoso graph-level security, or an authorising SPARQL proxy that receives the user's JWT. The persistence layer only has to carry the identity in a ContextVar and attach it to each request.

### (d) Layer coverage and codegen fit

- **Layers:** **L1** (domain and persistence, Active Record) and **L2** (Neo4j store, transactions); **L0** partially (constraint install, reverse engineering, diagrams); **L6** weakly (hooks only). L3 is limited to store impersonation. L4 and L5 are absent; the Pydantic bridge feeds L4.
- **Codegen from LinkML:** LinkML has no neomodel generator, but one is easy to write as a custom Jinja generator, about 200 LOC.
  - Mapping: class becomes `StructuredNode` (`is_a` gives inheritance and labels); a slot with a scalar `range` becomes a `Property` subclass (`required`, `identifier` → `unique_index=True`, enums → `choices`); a slot with a class `range` becomes `RelationshipTo` with a cardinality from `required`/`multivalued`; `inverse` becomes `RelationshipFrom`.
  - The reverse direction already exists (`contrib/pydantic.py` node → pydantic).
- **For rdf-persistence, the better route** is to keep the domain as **LinkML `gen-pydantic` classes** (no persistence code, DEC-6/cosmic-python) and offer the neomodel-*like* API (`Repository[T].nodes`-style manager, lookups, transactions) as a separate persistence layer that reads LinkML slot metadata (`slot_uri`, `range`, `multivalued`, `inverse`) at runtime. The declaration convenience comes from the model instead of Active Record classes. **Fit: medium-high** for the API ideas, **low** for reusing neomodel's code, which is Neo4j-only.

### (e) C9 and C10

| # | Score | Justification | Evidence |
|---|---|---|---|
| C9 Composability | 1 | Neo4j/Bolt/Cypher only, no SPARQL, JSON-LD, SHACL or RDF/JS. Composes with pydantic and JSON Schema (`contrib/pydantic.py`) and with Django (external). Not swappable behind a port | `pyproject.toml` (`neo4j~=6.1.0`); `async_/connection.py` |
| C10 Maintainability | 4 | Strict semver since 6.0, a detailed Changelog, mypy, CodeQL, Sonar and Codecov in CI, a matrix over Python 3.10–3.14 × Neo4j 4.4–5.x, and a god-object refactor behind a stable facade. Breaking changes in 7.0, and the sync/async duplication needs generator tooling | `Changelog`; `.github/workflows/integration-tests.yml:35-37`; `bin/make-unasync` |

### (f) Proposed new features (round 3)

- **AZ4 End-user identity propagation to the store:** impersonation or delegated credentials carried in context-local state and attached to every store call, so store-native policies apply (`transaction.py:117`, `connection.py:133`).
- **D12 Per-model exception types:** `Model.DoesNotExist` and `MultipleNodesReturned`, generated per class (`node.py:39-41`).
- **D13 Model-aware error messages:** errors include the model, property and registry context (`exceptions.py:117`, `:196`).
- **G3 LinkML → OGM declaration generator:** generate persistence-layer declarations (or runtime mapping metadata) from LinkML slot metadata. A gap shared by every library reviewed here.

## Round 4

### (a) v3 cross-check (102 features)

Every "absent" was confirmed by grep over `neomodel/` for these terms, all with 0 hits: `If-Match|ETag`, `outbox|publish`, `patch`, `cursor`, `graphql`, `openapi`, `jsonld|@context`, `as_of|history`, `idempot`, `savepoint`, `audit`, `401|403`, `sudo|bypass`. The `redact|mask` hits are the Cypher *log* redaction hook (`config.py:158-166`), not data masking. GitNexus shows no publish, outbox or event process; the only flows are config and CLI. Round-3 proposals map as AZ4→AZ19, D12→D12, D13→D13, G3→G2.

| Id | Status | Evidence |
|---|---|---|
| AZ1, AZ2 | absent | No store-port decorator; no filter injection into `QueryBuilder` (`async_/match.py:575`) |
| AZ3 | n.a. | No SPARQL; the Cypher `QueryAST` is string fragments (`match.py:520`) |
| AZ4–AZ18 | absent | Neo4j Enterprise RBAC (label, property and relationship privileges) is store configuration that neomodel neither manages nor maps |
| AZ19 | present | `db.impersonate(user=…)` with the user in a ContextVar on every query (`async_/transaction.py:117`, `connection.py:133`); Enterprise-only |
| AZ20–AZ29 | absent | — |
| G1–G5, G7–G18, G21–G27 | absent | Active Record classes are hand-written (`node.py:148`). The only generation is reverse (`scripts/neomodel_inspect_database.py`), diagrams (`neomodel_generate_diagram.py`) and node → pydantic (`contrib/pydantic.py:159`), none of which is a v3 G feature. The `bin/make-unasync` async → sync generation is D7 (v1) |
| G6, G19, G20 | n.a. | No language-tagged strings or OWL in the labelled property graph |
| T1 | n.a. | Real server transactions exist; `bulk_save` uses at most two UNWIND round-trips (Changelog 7.0.0) |
| T2 | absent | — |
| T3 | present | Explicit multi-statement Bolt transactions with begin, commit and rollback (`transaction.py:19-91`, `database.py:241-256`) |
| T4 | absent | — |
| T5 | present | Reads inside `db.transaction` run on the same open transaction (`connection.py` `_active_transaction`, `:393`) |
| T6 | partial | Only the driver's `max_transaction_retry_time` (`config.py:93`, `connection.py:298`); explicit `begin()` transactions are not auto-retried |
| T7 | partial | A capability check for the parallel runtime warns and falls back (`transaction.py:34-41` `parallel_runtime_available`); there is no general capability descriptor |
| T8–T11 | absent | T10: rollback does not reset in-memory node objects (`transaction.py:51-53` rolls back the DB only) |
| E1–E9 | absent | Hooks only (`hooks.py`); no event transport |
| U1–U10 | n.a. | No HTTP or UI layer |
| RAD3, RAD4 | n.a. | — |
| X17–X22 | n.a. | No HTTP layer |
| D11 | present | Driver errors propagate; uniqueness violations are translated to `UniqueProperty(message)` (`transaction.py:55-60`) |
| D12 | present | `Model.DoesNotExist` per class (`node.py:39-41`) |
| D13 | present | `exceptions.py:117`, `:196`, `:265` |
| S15–S18 | absent | — |
| S19 | partial | A commit returns bookmarks (a transaction id, `transaction.py:63` `last_bookmarks`); no message, author or digest |

**Counts (102):** present 6, partial 3, absent 70, n.a. 23.

### Purpose and origin

- **Built for:** giving Django-era Python web developers an ORM-like experience over Neo4j: class-declared nodes, a `.nodes` query manager, relationships as managers, and Django integration (`django_neomodel`).
- **Who and context:** Robin Edwards started it in 2013 (`LICENSE`, `pyproject.toml` author). It lives in the **neo4j-contrib** organisation (community-contributed, not an official Neo4j product), with 30+ contributors in `AUTHORS.txt` and current maintainers Marius Conjeaud, Antoine Nguyen and Athanasios Anastasiou. Releases are regular, with strict semver since 6.0.
- **Design angle:** developer-experience-first and store-specific. Active Record over the official driver, and parity between async and sync APIs.
- **Where it fits:** nowhere as a component, since it is a labelled property graph with Cypher only, not RDF. As a **design benchmark** it shapes the rdf-persistence **L1** API (declaration convenience, query sets, transactions, errors) and the L2 transaction ergonomics. It passes DEC-5 (1.1k stars, active), but its store is out of scope, so it is ideas only.

### Variant fit

| Candidate | V1 | V2 | V3 | V4 | V5 | A | B | C |
|---|---|---|---|---|---|---|---|---|
| neomodel | ideas: the rdf-persistence API style (manager / query set / `with session.begin()`, per-model errors, async-first plus unasync) | ideas only | ideas: impersonation-style identity forwarding maps onto Fluree identities (AZ19) | ideas: impersonation maps onto GraphDB user-scoped requests; its T3 explicit-transaction API is the ergonomic model for the RDF4J/GraphDB transaction adapter | n.a. | **supports** the runtime-mapper approach as a model: a neomodel-like manager reading LinkML `slot_uri`/`range` at runtime | possible (generate neomodel-style declarations or mapping metadata, G2), but would conflict with persistence-free domain classes if done as Active Record | n.a. |

Adopting neomodel itself would **block** every variant, because all of them assume an RDF store.

### Corrections to the integrated docs

- `catalogue.adoc` (neomodel row), Origin "Neo4j community": more precisely the **neo4j-contrib** community organisation, started by Robin Edwards in 2013, with named maintainers (`pyproject.toml`). It is not maintained by Neo4j, Inc. as a product.
- `catalogue.adoc` (neomodel row), Layers "L1": should be **L1 plus L2** (Neo4j transactions), L0 partial (constraint install, reverse engineering, diagrams) and L6 weak (hooks), consistent with `libraries/neomodel.adoc:14`.
- `index.adoc` patterns, "Identity … equality by IRI … neomodel": neomodel's equality is by the database `element_id`, not an IRI (`node.py:171-200`). The pattern carries over as "equality by persistent id" (I6), so the wording is fine if read as an analogy.

### Proposed new features (round 4)

- **D14 Parameter redaction in query logs:** a pluggable redaction hook masks sensitive parameters in logged queries (`config.py:158-166`, `async_/query.py:81` `_redact_params`). It complements S14 observability without leaking secrets.

## Round 5

### (a) v4 cross-check (77 features)

Absences were confirmed by grep over `neomodel/` for these terms, all with 0 hits: `opentelemetry|traceparent|span`, `outbox`, `If-Match|ETag`, `mcp`, `CURIE`. `migrat` matches only an `id` → `element_id` deprecation notice (`async_/node.py:228`). GitNexus shows no event or publish process.

| Id | Status | Evidence |
|---|---|---|
| B1, B2 | absent | No aggregate or ownership declaration |
| B3 | partial | `traverse()` / `resolve_subgraph()` load a subgraph in one query (`async_/match.py:1934`, `:2000`); relationships are otherwise lazy and there is no boundary |
| B4–B6, B8, B9, B11–B13, B16 | absent | Active Record per node. `post_save` runs inside the transaction, not after commit (`node.py:801` `@hooks`). `delete` = `DETACH DELETE` (`node.py:640`) |
| B7, B10 | n.a. | SPARQL/RDF-specific |
| B14 | partial | Database-specific labels and the target database name per context (`doc/source/extending.rst`, "Database specific labels"; `connection.py:130`) |
| B15 | n.a. | No unit of work |
| PG1 | absent | `QueryAST` holds Cypher string fragments with one renderer (`match.py:520`, `:1116` `build_query`) |
| PG2 | absent | No LinkML-driven projection |
| PG3 | partial | Edge properties through `StructuredRel` (`async_/relationship.py:51`); not driven by a model |
| PG4 | partial | Partitions by database name and labels (`connection.py:130`); not shared with authorization |
| EV1–EV9 | absent | `install_labels` applies constraints and indexes and is not a migration runner (`schema.py:203`) |
| AZ30–AZ32, AZ34 | n.a. | Store-policy features (Neo4j RBAC is outside neomodel) |
| AZ33, AZ35, AZ36 | absent | — |
| G28, G30–G32, G34 | n.a. | No LinkML or OWL generation chain |
| G29, G33, G35, G36 | absent | Lookups are untyped kwargs strings (`filter(age__gt=3)`); no field metamodel or TypedDicts |
| T12 | n.a. | — |
| T13 | partial | `read_transaction` opens a READ-mode transaction, so the server refuses writes (`database.py:243-248` `access_mode`; `transaction.py:22`) |
| T14 | absent | — |
| S20 | n.a. | — |
| S21 | absent | — |
| S22 | partial | Uniqueness constraints installed from the model are enforced by Neo4j in the write transaction and surfaced as `UniqueProperty` (`schema.py:346`, `transaction.py:55-60`); no shapes |
| S23 | partial | Schema admin only (`schema.py:99-203`, `scripts/neomodel_remove_labels.py`); no backup, restore or statistics |
| X23, E10, I7 | n.a. | — |
| X24, I8, P20 | absent | — |
| U11–U13 | n.a. | — |
| D14, D16, D22, D25, D28 | n.a. | No append-only writes, HTTP contract or IRIs; arrays are ordered lists |
| D15 | present | `cypher_log_redaction_hook` and `_redact_params` (`config.py:158-166`, `async_/query.py:81`) |
| D17 | partial | `AsyncQueryBuilder.build_query()` (`match.py:1116`) is internal; the debug or slow-query log shows the query and timing (`query.py:100-115`) |
| D18 | absent | Relationship managers query lazily on access |
| D19–D21 | absent | Tests need a live Neo4j (`test/conftest.py`); docs are not executed |
| D23 | partial | A "Did you mean" hint only for single-member exclusion groups (`async_/node.py:101`) |
| D24, D27, D29 | absent | — |
| D26 | present | `test/test_typing.py` with `assert_type`, checked by mypy in CI (Changelog 7.0.0) |

**Counts (77):** present 2, partial 9, absent 41, n.a. 25.

### (b) Page review: `libraries/neomodel.adoc`

1. **Line 21**, "30+ contributors in `AUTHORS.txt`": wrong. `AUTHORS.txt` has **15** entries (`wc -l` = 15). My own round-4 raw text (neomodel.md, Purpose and origin) has the same error. **Fix:** "15 contributors listed in `AUTHORS.txt` (GitHub shows more)".
2. **Line 99**, "Hooks as a security boundary: they are bypassed by raw Cypher and `bulk_*`": partly wrong. `bulk_save` **runs** `pre_save`/`post_save` (`async_/node.py:542-606`), and `bulk_create` runs `post_create` unless `lazy` (`node.py:451-453`). **Fix:** "bypassed by raw Cypher, `lazy` bulk creation, and `get_or_create`/`create_or_update` (no `post_create`); `bulk_create` skips `pre_save`/`post_save`."
3. **Line 38**, "`bulk_*` take at most two round-trips": only `bulk_save` is "at most two"; `bulk_create` is one `UNWIND` query. **Fix:** "`bulk_create` is one UNWIND query; `bulk_save` at most two round-trips."
4. **Line 89**, "Slow-query log": add the missing caveat that it only logs when `config.cypher_debug` is on and the query exceeds `slow_queries` (`query.py:107-108`).
5. **Line "Round-4 proposal (no id yet)" (Feature coverage section):** it now has v4 id **D15**. **Fix:** "…now v4 D15 (present)."
6. **`index.adoc:154`** (shared with Prez): neomodel is correctly credited for identity forwarding (AZ19).

### (c) Final verdict and three things to remember

**Verdict: ideas.**

1. neomodel is the **developer-experience benchmark**: declare once, a lazy generic `Model.nodes` query set with `field__op` lookups and `Q`, one transaction object usable three ways, per-model `DoesNotExist`, async-first with a generated sync API, and typing regression tests. Copy the **API shape**, reading the mapping from LinkML metadata.
2. **Do not copy its core:** Active Record (persistence inside domain classes), no identity map, no unit of work, save rewrites every property, and client-side cardinality checks that race.
3. Its one authorization lesson, **forward the end-user identity to a store that enforces policy** (`db.impersonate`), carries over directly to RDF stores and proxies (AZ19). Any policy in hooks is bypassable.

### (e) New features

None.
