# sparqlmodel

- **Repo:** https://github.com/eddiethedean/sparqlmodel — clone `/home/lps/work/repos/sparqlmodel` (shallow clone, single squashed commit)
- **Commit analysed:** `90183cd` "Release 0.13.1" (2026-06-01), version 0.13.1, PyPI status "Beta"
- **Licence:** MIT (`LICENSE`, `pyproject.toml`)
- **Size:** 33 source files, 6,526 Python LOC in `src/` (largest: `compiler.py` 898, `session_core.py` 595, `stores/http_common.py` 475); 51 test files, 10.4k test LOC, **685 `test_` functions**. Docs: 15 Markdown files, about 3.8k lines (`docs/`), plus a 538-line CHANGELOG.
- **GitNexus index:** repo `sparqlmodel`, 130 files, 2,612 nodes, 5,842 edges, 62 communities, 226 processes, indexed at HEAD (not stale).
- **Author / cadence:** one author (commits signed "Odo Matthews"; `pyproject` says "SparqlModel Contributors"). 0.1.0 shipped 2026-05-16 and 0.13.1 shipped 2026-06-01: about 25 releases in 16 days (CHANGELOG.md:10–519). No later activity was visible at analysis time (2026-11-03).
- **Docs read:** `README.md`, `CHANGELOG.md`, `docs/SPECS.md` (grep), `docs/ROADMAP.md` (grep), `docs/ECOSYSTEM.md` (grep), `docs/PRODUCTION.md` (grep), `docs/PLAN.md` (grep); https://sparqlmodel.readthedocs.io/en/latest/ (landing page and table of contents).

## Summary

sparqlmodel is a SQLModel-style ORM. Its entities are `SPARQLModel` classes, which are Pydantic v2 models that subclass `triplemodel.TripleModel`. `SPARQLSession` provides `add/put/get/delete/query/execute`, an identity map and a "pending queue". A string-based compiler turns operator-overloaded filter expressions into SPARQL `SELECT`. Two store families exist: an in-memory pyoxigraph `MemoryStore`, and `HttpStore`/`AsyncHttpStore`, which send SPARQL 1.1 `INSERT DATA`/`DELETE DATA` over httpx while keeping a **local pyoxigraph mirror** that drives `get`, cascade and orphan logic. The code has no real transactions, no named graphs, no SHACL and no LinkML. It is a well-tested and ergonomic prototype of the developer experience we want, but the persistence semantics are fragile at their core (a client-side mirror and a single-writer assumption).

## Architecture (GitNexus + code)

- **Clusters (GitNexus communities):** "Sparqlmodel" core (78, 60, 32 and 27 symbols: session/state, model/fields, compiler, hydration), "Stores", "Fastapi" (13), and many "Tests" communities. Leiden labels are coarse, so the structure below comes from reading the code.
- **Layers (by module):**
  - **model:** `model.py` (`SPARQLModel`, `SPARQLModelMetaclass`), `fields.py` (`Field`, `Relationship`, `SPARQLFieldMetadata`) and `types.py` (`IRI`, `NamespaceRegistry`).
  - **mapping bridge:** `rdf_bridge.py` (`model_to_graph`, `load_from_graph`), which delegates to triplemodel.
  - **unit of work:** `session.py` / `async_session.py` are thin facades over `session_core.py` (shared sync/async logic) and `session_state.py` (`SessionState`: identity map, hydration cache, pending list).
  - **cascade:** `graph.py` (`cascade_subjects_for_removal`, `orphaned_embedded_targets`, `owned_triples_for_subject`).
  - **query:** `expressions.py` (AST) → `query_common.py` (`QueryState`) → `compiler.py` (`compile_where`); `query.py` / `async_query.py` hold the fluent API.
  - **stores:** `stores/base.py` (`StoreProtocol`), `memory.py`, `http.py`, `async_http.py`, `http_common.py`, `sparql_json.py`.
  - **integration:** `fastapi/` (`SessionDep`, lifespan helpers, `negotiated_response`).
- **Key execution flows (GitNexus processes / CALLS):**
  - `get_impl` → `_sync_store_generation` → `_pull_subject_for_read_sync` → `HttpStore.pull_subjects_into_mirror` (`CONSTRUCT … VALUES ?s`) → `hydrate_one` → `set_identity` / `set_hydration` (GitNexus CALLS on `get_impl`, `session_core.py:239`).
  - `SPARQLSession.flush` → `_put_impl` → `session_core.put_impl` → `cascade_subjects_for_removal` → `owned_triples_for_subjects` → `model_to_graph` → `store.update_graph(add, remove)` (`session.py:136–150`, `session_core.py:196–210`).
  - `Query.all` → `QueryState.compile` → `compile_where` → `session.execute` (remote SELECT) → `hydrate_bindings_impl` → `get_impl` once per row (`query.py:89–98`, `session_core.py:294–325`).
  - `HttpStore.update_graph` → `build_update_chunks` (all DELETE chunks, then all INSERT chunks) → `_post_update`, one HTTP POST per chunk → the mirror is patched only after every chunk succeeds (`stores/http.py:287–298`, `http_common.py:92–110`).
  - GitNexus processes `proc_74/157/158 compile_not`, `proc_86 execute_select → is_retryable_status`, `proc_172 http_store_lifespan`, `proc_8/78/162 expunge_impl`.

## Implementation principles (how it actually works)

- **Mapping:** declarative. `name: str = Field("schema:name")` stores a `SPARQLFieldMetadata` in Pydantic `json_schema_extra` (`fields.py:26–33, 80–116`). `Relationship(..., cascade=False)` becomes a triplemodel `ref_field` (a by-IRI reference), and `cascade=True` means composition (`fields.py:119–175`). `__init_subclass__` derives a triplemodel `Rdf` config class from `rdf_type` and `__prefixes__` (`model.py:57–68, 194–216`). One predicate per field is enforced (`model.py:79–96`). Triple generation and parsing are delegated to triplemodel `sync_to_graph` / `from_graph` (`rdf_bridge.py`).
- **Query expressions:** a metaclass `__getattr__` returns `FieldRef` objects, so `Person.name == "x"` builds an AST (`model.py:25–38`, `expressions.py:44–110`).
- **Identity / IRI minting:** `id: IRI | None`. If it is absent, `ensure_id()` mints `urn:uuid:<uuid4>` (`model.py:144–149`). Compact IRIs (CURIEs) are expanded with the class prefixes. The identity-map key is `(model class, expanded IRI)` (`session_state.py:13–29`), so the same IRI loaded as two different classes produces two objects.
- **Session / unit of work:** `put(model)` defaults to `flush=True` and **writes immediately**. Only `put(..., flush=False)` queues the model (`session.py:250–263`). `flush()` replays the queue model by model; on failure it re-queues the remainder, but writes already made stay in place (`session.py:136–150`). `__exit__` flushes on success and discards the queue on error (`session.py:176–202`). The class docstring itself says "Already-flushed writes are not rolled back … Full transactional rollback may be added in a future release" (`session.py:39–41`). Autoflush runs before reads (`_maybe_autoflush`).
- **Update strategy:** `put` = delete the "owned triples" (`rdf:type` plus declared predicates) of the root and of every cascaded or orphaned subject, then insert the newly generated graph (`session_core.py:196–210`, `graph.py:249–287`). Triples on predicates that are not mapped are preserved. `add` only inserts, and warns with `StaleTripleWarning` (`session_core.py:213–236`).
- **Cascade / orphans:** `iter_nested_models` walks the composition tree (`graph.py:124–150`). Orphan detection scans the **whole mirror graph** for each candidate object (`_object_referenced_from_outside`, `graph.py:153–167`): O(N) per object, and correct only if the mirror is complete.
- **Remote stores:** `HttpStore` holds a local `triplemodel.Store`. Reads such as `get` and cascade use the mirror, while `query`/`execute` hit the remote endpoint (`http.py:24–47`). The mirror can be refreshed in three ways: lazily by per-subject CONSTRUCT (`pull_subjects_into_mirror`, `http.py:242–285`), by `mirror_mode="remote_authoritative"`, which always pulls, or by `sync_mirror()`, which runs a GSP GET of the default graph and **replaces the whole mirror** (`http.py:165–186`). Writes use `INSERT DATA`/`DELETE DATA` with no `GRAPH` clause (`http_common.py:290–301`); `grep GRAPH` over `src/` returns nothing. Retries with backoff cover 502/503/504 (`http_common.py:59–71, 135–165`). Results are parsed with pyoxigraph `parse_query_results` (`sparql_json.py:20–41`), not with SPARQLWrapper.
- **Querying:** `compile_where` builds `SELECT DISTINCT ?root` (or `COUNT(DISTINCT)`) by string concatenation. It uses `OPTIONAL` for nullable hops, `NOT EXISTS` for `!=`, `FILTER(EXISTS…||…)` for OR, `VALUES`, polymorphic `rdf:type` alternatives, `ORDER BY`, `LIMIT` and `OFFSET` (`compiler.py:773–898`). Literal escaping is in `sparql_escape.py` and IRI validation in `rdf_n3.validate_iri_token`. Hydration is **N+1**: one `get_impl` per row, and each one may trigger a CONSTRUCT over HTTP (`session_core.py:309–324`).
- **Serialisation:** `model_dump_jsonld()` hand-builds a compact JSON-LD dict whose `@context` is the prefix map, with cascade embeds nested (`serializers.py`, `model.py:159–178`). Full RDF formats (Turtle, JSON-LD, TriG and others) go through triplemodel or pyoxigraph serialisers. FastAPI `negotiated_response` picks Turtle or JSON-LD from `Accept` (`fastapi/__init__.py:72–149`).
- **Async:** parallel `AsyncSPARQLSession`, `AsyncHttpStore` and `AsyncMemoryStore` share `session_core` logic (`async_session.py`, `session_core.py:478–595`).

## Patterns catalogue

| Pattern | Where |
|---|---|
| Data Mapper (entity is a Pydantic model; mapping held in field metadata, not in save/load methods on the object) | `fields.py:26`, `rdf_bridge.py:164` |
| Session / Unit of Work (partial: a pending queue, no change tracking or dirty detection) | `session.py:29`, `session_state.py:31` |
| Identity Map | `SessionState.get_identity/set_identity` (`session_state.py:40–53`) |
| Query Object + Interpreter (operator-overloaded AST → SPARQL) | `expressions.py`, `query_common.QueryState`, `compiler.compile_where` |
| Repository | **absent** (the session is the only gateway) |
| Lazy loading | **absent**; eager loading with an explicit `depth` of 0–2 (`hydration.validate_depth`) |
| Strategy / Protocol for stores | `StoreProtocol` (`stores/base.py:10–21`), `AsyncStoreProtocol` |
| Read-through cache / client-side replica | `HttpStore` mirror and `mirror_generation` (`http.py:157–186`, `session_core._sync_store_generation`) |
| Composition cascade (aggregate-like ownership) | `graph.cascade_subjects_for_removal` (`graph.py:211`) |
| Retry with exponential backoff | `http_common.request_with_retry` (`http_common.py:135`) |
| Dependency injection (FastAPI) | `fastapi/deps.py:76–160` |

## Docs vs code

| Claim (source) | Verdict |
|---|---|
| "`SPARQLSession` is the unit of work … roll back the pending queue on error" (README) | Confirmed, but it is a pending queue, not a UoW with change tracking. `put()` writes immediately by default (`session.py:250–255`). |
| Identity map; `merge/refresh/expunge` (README) | Confirmed (`session.py:204–229`, `session_state.py`). |
| Query DSL: `&`, `\|`, `in_`, comparisons, multi-hop, `count`, `order_by`, property paths, `not_`, `VALUES`, polymorphic (README, 0.13) | Confirmed (`expressions.py`, `compiler.py`, `query.py`). |
| "`put` may send `DELETE DATA` followed by `INSERT DATA` in one SPARQL Update request" (`docs/SPECS.md:349`) | **Contradicted by code**: each chunk is a separate POST (`http.py:290–291`, `http_common.py:92–110`), so put is **not atomic** remotely even on endpoints that support atomic requests. |
| SHACL validation via `triplemodel[shacl]` (`docs/ECOSYSTEM.md:86,113`, `SPECS.md:478`) | **Claimed, not found in code.** triplemodel removed SHACL and the `[shacl]` extra in 0.11 (triplemodel `docs/MIGRATION_0.11.md:11–20`). Roadmapped for 0.14, not shipped. |
| Named graphs (`ROADMAP.md:235,578`) | Correctly listed as not yet available ("post-0.15"). Code is default-graph only. |
| "Transactions: Partial (no remote txn)" (`ROADMAP.md:602`) | Accurate. |
| GSP `sync_mirror()` (README, 0.12) | Confirmed, but GET only and default graph only. The code has no GSP PUT/POST/DELETE for writes. |
| "Validation … before bad triples reach the store" (README) | Confirmed for Pydantic validation only (`validate_assignment=True`, `model.py:44–49`). |
| RTD site says "SHACL / LinkML / named graphs not mentioned" | Consistent with the code. The RTD docs are more conservative than the in-repo ECOSYSTEM/SPECS. |

## Scores C1–C8

| # | Score | Justification | Evidence |
|---|---|---|---|
| C1 Feature coverage | 3 | Full CRUD, cascade, identity map, query builder, lang strings and multi-valued fields. Missing: real transactions, named graphs, SHACL, optimistic locking. n-m relations only via `set[IRI/ResourceRef]`, and `list[SPARQLModel]` is unsupported (README "Known limitations"). | `session.py`, `compiler.py`, `http_common.py:290–301`, README L231 |
| C2 Approach & patterns | 3 | Clear Data Mapper + Session + Identity Map + Query Object, with sync/async sharing `session_core`. But the UoW is degenerate (immediate writes, no dirty tracking), and the client-side mirror conflates cache with source of truth. | `session.py:39–41`, `http.py:36–43` |
| C3 Developer friendliness | 4 | SQLModel-like happy path in about 10 lines, typed `py.typed` package, FastAPI deps, RTD guides, API reference and troubleshooting, real-world examples. Downsides: semantics are subtle (`add` vs `put`, mirror modes, NE semantics toggles). | README quickstart, `fastapi/deps.py`, https://sparqlmodel.readthedocs.io/en/latest/ |
| C4 Ease of adoption | 3 | Small dependency set (pydantic, pyoxigraph, triplemodel, plus httpx optional) and in-memory by default. Remote use requires understanding the mirror and a single-writer assumption, and the API churns fast (13 minors in 16 days). | `pyproject.toml` deps, `http.py:36–43` |
| C5 Reuse of foundations | 3 | Reuses pydantic, pyoxigraph (store, parsers, SPARQL JSON results) and triplemodel. But it hand-rolls the SPARQL HTTP client (httpx + retry + chunking) instead of SPARQLWrapper, builds SPARQL by string concatenation, and has no rdflib interoperability (`session.graph` is not an rdflib Graph). | `http_common.py`, `compiler.py`, README "Known limitations" |
| C6 Data-centric & DDD fit | 2 | Model-first in Python classes only (no LinkML or ontology → model path). Entities must subclass `SPARQLModel` (inheritance-based, persistence-aware base class with `model_dump_jsonld`), so plain domain objects are not possible. No repository layer, though one could be written over the session. | `model.py:41`, `schema_registry.py` |
| C7 SPARQL 1.1 portability | 3 | Uses only standard SPARQL 1.1 Query/Update and GSP GET, with no vendor API; tested against Fuseki. But writes target only the default graph, and read correctness depends on the client mirror (stale under concurrent writers). | `http.py`, `tests/conftest_fuseki.py` |
| C8 Health | 3 | CI on Python 3.10–3.13 with ruff, ty and `--cov-fail-under=100`; 685 tests; MIT. Against that: a single author, a release burst followed by ~5 months of silence, and coverage-chasing test files (`test_coverage.py`, `test_013_coverage.py`). | `.github/workflows/ci.yml:58`, `CHANGELOG.md` |

## Feature inventory

| Id | Status | Evidence |
|---|---|---|
| M1 | present | `SPARQLModel` Pydantic classes (`model.py:41`) |
| M2 | absent | No LinkML, SHACL or ShEx input. `SchemaRegistry` is an alias of triplemodel `OntologyRegistry` for inverse/subclass hints only (`schema_registry.py:9`). |
| M3 | absent | None in sparqlmodel (triplemodel has an experimental OWL→stub CLI) |
| M4 | partial | Subclasses with their own `rdf_type`; `.polymorphic()` query matches subtypes (`compiler._polymorphic_type_patterns`, 0.13) |
| M5 | partial | Pydantic on construct, assignment and load; no SHACL |
| I1 | present | Explicit `id: IRI` (CURIE or absolute) or auto `urn:uuid` (`model.py:144`); no configurable minting policy |
| I2 | partial | Blank-node ids tolerated (`_:` keys in `session_state.py:19`); bnode embed is via triplemodel `embed="bnode"`, but sparqlmodel forces `embed="iri"` (`model.py:211`) |
| I3 | present | `SessionState` keyed `(cls, iri)` (`session_state.py:13–53`) |
| R1 | present | `set[...]` multi-valued, `list[...]` as `rdf:List` (via triplemodel); `test_query_lists.py`, `test_multivalue_roundtrip.py` |
| R2 | partial | 1-1/1-n via `Relationship`; n-m via `set[IRI]`/`ResourceRef`; inverse via `inverse=` (import-only) and `back_populates` (`fields.py:119`); `list[SPARQLModel]` unsupported (README L231) |
| R3 | partial | Eager with `depth=0..2`, no lazy proxies (`hydration.validate_depth`) |
| R4 | present | Composition cascade plus orphan cleanup on put/delete; `cascade=False` for references (`graph.py:211`) |
| L1 | present | XSD mapping via triplemodel; `literal_datatype=` (`fields.py:84`) |
| L2 | present | `lang=`, `LangString`, `MultiLangString` (`fields.py:82`, README) |
| P1 | present | `add/put/get/delete` (`session.py:235–288`) |
| P2 | present | Delete owned triples + insert (replace per owned predicate set) (`session_core.py:196–210`) |
| P3 | partial | Pending queue + `flush()` + autoflush; no dirty tracking (`session.py:136`) |
| P4 | absent | No atomic commit or rollback, locally or remotely (`session.py:39–41`; separate POST per chunk, `http.py:290`) |
| P5 | absent | None |
| P6 | absent | Default graph only; no `GRAPH` in generated SPARQL (grep) |
| P7 | partial | Chunked updates (`max_triples_per_update`); `from_rdf_file`; no streaming export API in sparqlmodel |
| Q1 | present | `session.get(Model, iri, depth=)` |
| Q2 | present | Operator DSL → SPARQL (`compiler.py:773`) |
| Q3 | partial | `execute(sparql)` returns SELECT bindings as dicts; `hydrate_bindings` maps to objects only when the variable equals the lowercased class name (`session_core.py:306–315`) |
| Q4 | partial | `limit/offset/order_by/count`; no group-by or aggregates beyond count |
| Q5 | present | Multi-hop `Person.works_for.located_in.name`, `property_path()` (`expressions.py:254`) |
| S1 | present | `MemoryStore` on pyoxigraph (`stores/memory.py`) |
| S2 | present | `HttpStore`/`AsyncHttpStore`, split read/write endpoints, auth, retries |
| S3 | partial | GSP GET for `sync_mirror` only (`http.py:165`) |
| S4 | present | `StoreProtocol` structural protocol (`stores/base.py:10`) |
| X1 | present | `model_dump_jsonld/model_validate_jsonld`, `serialize(format="json-ld")` |
| X2 | present | Via triplemodel/pyoxigraph (Turtle, TriG, N-Triples, N-Quads, RDF/XML) |
| X3 | partial | FastAPI deps + content negotiation; no generated REST/JSON:API routes |
| X4 | partial | Pydantic JSON Schema comes for free; no TS types |
| X5 | absent | None |
| D1 | present | Typed, `Typing :: Typed`, `ty` in CI |
| D2 | present | `AsyncSPARQLSession`, `AsyncHttpStore` |
| D3 | present | FastAPI (`sparqlmodel.fastapi`) |
| D4 | present | RTD guides, API reference, examples (`examples/realworld/`) |
| D5 | partial | `MemoryStore` as an in-memory fake; Fuseki conftest; no shipped fixtures |
| O1 | absent | None |
| O2 | absent | None |
| A1 | partial | HTTP auth (Basic/Bearer) only; no ACL hooks (noted only) |

### Proposed new features

| Proposed id | Area | Feature | Seen here |
|---|---|---|---|
| S5 | Stores | Client-side mirror / read-through cache of remote data with invalidation (generation counter) | `HttpStore` mirror, `mirror_mode`, `mirror_generation` |
| S6 | Stores | HTTP resilience: retries/backoff, split read/write endpoints, chunked updates | `http_common.py` |
| P8 | Persistence | Ownership model: only mapped predicates are "owned" and replaced; foreign triples preserved | `owned_triples_for_subject` (`graph.py:265`) |
| P9 | Persistence | Orphan cleanup for dropped composition children (with shared-reference protection) | `orphaned_embedded_targets` (`graph.py:170`) |
| Q6 | Query | Configurable open-world semantics for negation/optional (NOT EXISTS vs `!=`, OPTIONAL on nullable hops) | `use_not_exists_for_ne`, `use_optional_for_comparisons` |
| Q7 | Query | Polymorphic query over subclasses | `.polymorphic()` |
| D6 | DevEx | Content negotiation helpers (Accept → Turtle/JSON-LD response) | `fastapi.negotiated_response` |

## JS-friendliness

Moderate. FastAPI integration produces Pydantic-derived OpenAPI/JSON Schema for request and response bodies, and `negotiated_response` serves Turtle or JSON-LD. `model_dump_jsonld()` emits compact JSON-LD with a prefix-only `@context`, which is not a curated term context, so JS clients see CURIE keys. There are no TS types, no JSON:API or GraphQL, and no generated routes.

## Reuse verdict for rdf-persistence: **borrow ideas, avoid as a dependency**

Do not adopt or extend it. It is a single-author project whose release burst ended about five months ago. Its persistence core rests on a client-side mirror with a single-writer assumption. It has no transactions or named graphs, re-implements the SPARQL HTTP client (against DEC-4 in spirit), and is coupled to triplemodel/pyoxigraph with no rdflib interoperability. It has no LinkML path and requires inheriting from a persistence base class, which conflicts with our model-first, cosmic-python goal. **Ideas worth borrowing:**
1. The SQLModel-style DX: `with Session() as s`, `put/get/delete`, `Model.field == x` expressions via metaclass `FieldRef`, and `.where().order_by().limit().all(depth=n)`.
2. "Owned predicates" update semantics: on update, delete only mapped predicates plus `rdf:type`, and leave foreign triples alone.
3. Composition (`cascade=True`) vs reference (`cascade=False`) as the aggregate boundary, plus orphan cleanup that protects shared references. This maps cleanly onto DDD aggregates.
4. Explicit `depth` eager loading instead of lazy proxies, which keeps it predictable over HTTP.
5. Sync and async facades over one shared core (`session_core`).
6. Explicit open-world query switches (NOT EXISTS vs `!=`).
7. FastAPI `SessionDep` and Accept-based RDF content negotiation, as a seed for the later JSON-LD middleware.

**Do differently:** build a real UoW (track new, dirty and removed objects, then emit one `DELETE {…} INSERT {…} WHERE` or a single multi-operation update request per commit); scope writes to named graphs; never treat a local cache as truth for orphan detection; batch hydration in a single CONSTRUCT instead of N+1; use a SPARQL algebra or builder (rdflib) or SPARQLWrapper instead of string concatenation and a hand-rolled httpx client.

## Risks / anti-patterns observed

- **Non-atomic remote writes:** DELETE chunks and INSERT chunks go as separate POSTs, so a failure in the middle leaves the remote half-updated. The mirror is not updated, so it then diverges (`http.py:287–298`).
- **Mirror as source of truth** for `get`, cascade and orphan detection. Data from other writers is invisible unless pulled, and `sync_mirror()` replaces the whole default graph in memory, which does not scale (`http.py:165–186`).
- **N+1 hydration:** one `get_impl`, and potentially one CONSTRUCT HTTP call, per result row (`session_core.py:309–324`).
- **O(N) full-graph scan** per orphan candidate (`graph.py:153–167`).
- **String-built SPARQL** (about 900 LOC compiler) with custom escaping: a correctness and injection risk surface, mitigated by `validate_iri_token`.
- **Datatype loss** in `MemoryStore.query` bindings (`str(term.value)`, `memory.py:100`), which differs from `HttpStore` (`term.value`, `sparql_json.py:53`). The two stores do not return the same types.
- **Identity map keyed by class:** the same IRI under a parent and a subclass yields two instances (`session_state.py:22`).
- **Docs drift:** SPECS claims single-request DELETE+INSERT, and ECOSYSTEM points to a `triplemodel[shacl]` extra that no longer exists.
- **Release burst / probably generated code:** about 25 releases in 16 days, tests named for coverage targets, a 100% coverage gate. Treat API stability claims sceptically.

## Round 2 cross-check (taxonomy v1)

Checked against `docs/modules/ROOT/pages/architecture/soa/feature-taxonomy.adoc` (v1). Paths are relative to `src/sparqlmodel/`. Absences were confirmed by grep over `src/` (case-insensitive) and by reading the module where the feature would live.

**Counts:** 10 present, 7 partial, 45 absent, 1 n.a. (63 v1 features).

| Id | Status | Evidence |
|---|---|---|
| M6 | absent | Would live in `model.py`. Classes are always hand-declared; grep for `create_model` / dynamic `type(` returns nothing. |
| M7 | absent | `iter_sparql_fields` maps only fields carrying `Field("pred")` metadata (`model.py:108–116`). There is no namespace + field-name convention. |
| M8 | absent | The only `@context` is *emitted* from prefixes in `serializers.model_to_jsonld`; JSON-LD is never used as the mapping source. |
| M9 | absent | Explicitly forbidden: `_validate_unique_predicates` raises when two fields share a predicate (`model.py:79–96`). |
| M10 | absent | No per-RDF-class behaviour binding; methods are plain Python on the class. |
| M11 | absent | The underlying triplemodel supports `strict_import`, but `_apply_rdf_config` injects an `Rdf` without it (`model.py:207–215`), so it is not exposed. |
| M12 | absent | The injected `Rdf` has no `instance_of`; type is always `rdf_type` (`model.py:207–215`). |
| M13 | absent | No SHACL, index or install emission. Only generic Pydantic JSON Schema exists. |
| M14 | absent | No codegen in sparqlmodel. |
| M15 | absent | No external model-file loader. |
| I4 | absent | No skolemisation (grep `skolem` returns nothing). Embeds are forced to `embed="iri"` (`model.py:211`). |
| R5 | partial | Cardinality comes only from Pydantic typing (`X \| None`, `set[...]`, required). It is checked at validation, not on connect (`fields.field_cardinality_for`, `fields.py:201`). |
| R6 | absent | No exclusivity constraint in `fields.py`. |
| R7 | absent | No reification or RDF-star support (grep `reif\|rdf-star` returns nothing). |
| R8 | absent | Query paths follow forward predicates only (`compiler._follow_path`, `compiler.py:161`); reverse requires `inverse=` / `back_populates`. |
| L3 | present | Inherited: conversion goes through triplemodel's `LiteralRegistry`, and `register_literal_type` applies (triplemodel `terms/registry.py:134`). |
| P8 | present | `owned_triples_for_subject` deletes only `rdf:type` and mapped predicates (`graph.py:265–287`). |
| P9 | absent | No snapshot or dirty tracking in `SessionState` (`session_state.py:31–111`); `put` always deletes and reinserts the owned set (`session_core.py:196–210`). |
| P10 | absent | No `$add` / `$remove` operators; multi-valued fields are replaced wholesale. |
| P11 | present | `orphaned_embedded_targets` with shared-reference protection (`graph.py:153–208`). |
| P12 | absent | No graph placement at all (default graph only; grep `GRAPH` returns nothing). |
| P13 | absent | No transactions (`session.py:39–41`). |
| P14 | absent | No bulk upsert or get-or-create API. Grep hits for `upsert` are docstrings of `put`. |
| P15 | absent | "Not thread-safe; use one session per thread" (`session.py:43`). No concurrency modes. |
| Q6 | partial | The compiler escapes literals and validates IRIs (`sparql_escape.py`, `rdf_n3.validate_iri_token`), but raw `execute(sparql)` has no parameter binding (`session.py:331–339`). |
| Q7 | absent | Has an ORM expression AST (`expressions.py`), but SPARQL is produced by string concatenation (`compiler.py:773–898`). There is no SPARQL algebra or AST. |
| Q8 | absent | No method-name-derived queries. |
| Q9 | partial | Eager loading via `depth=0..2`, but hydration is N+1: one `get_impl` per row and one CONSTRUCT per missing subject (`session_core.py:309–324`). |
| Q10 | absent | `hydrate_bindings` uses only the root variable and re-fetches each object (`session_core.py:306–323`); rows are not grouped. |
| Q11 | partial | Only a query-form check (`http_common.is_select_query`, `http.py:219`; `MemoryStore` result-type check, `memory.py:71`). |
| Q12 | absent | No text-search operator in `expressions.CompareOp` (grep `regex\|CONTAINS` returns nothing). |
| Q13 | absent | None. |
| Q14 | absent | None. |
| Q15 | partial | `Query.count()` gives a total (`query.py:84–87`). No facets, and counts are not embedded in paginated responses. |
| Q16 | present | `use_not_exists_for_ne` / `use_inequality_for_ne` / `use_optional_for_comparisons` (`query_common.py:31–42, 133–151`). |
| Q17 | present | `.polymorphic()` → `_polymorphic_type_patterns` (`query.py:43`, `compiler.py:675`). |
| Q18 | absent | `pull_subjects_into_mirror` is a one-hop `CONSTRUCT ?s ?p ?o`, not a CBD (`stores/http.py:250`). |
| S5 | present | `read_endpoint` / `write_endpoint` (`stores/http.py:53–54, 112–116`). |
| S6 | present | Mirror with `mirror_mode` and `mirror_generation` invalidation (`stores/http.py:143–163`, `session_core._sync_store_generation`). |
| S7 | present | Retries and backoff (`http_common.py:59–71, 135–165`); chunked updates (`http_common.py:92–110`). |
| S8 | absent | `StoreProtocol` is a custom 3-method protocol (`stores/base.py:10–21`), not the rdflib `Store` or RDF/JS interface. |
| X6 | absent | The FastAPI module has deps and response helpers only (`fastapi/`). No JSON:API. |
| X7 | present | Media-type negotiation for Turtle and JSON-LD (`fastapi/__init__.py:72–149`). No profile negotiation. |
| X8 | absent | No Hydra. |
| X9 | absent | API model = storage model. |
| X10 | absent | No separate read models. |
| X11 | absent | No label annotation of referenced IRIs. |
| X12 | absent | No delta or change-set output. |
| X13 | absent | No request-context propagation; FastAPI deps only inject the session (`fastapi/deps.py:76–160`). |
| X14 | absent | Only an internal `graphs_isomorphic` contract check (`rdf_bridge.py:373–383`). Not a public diff API. |
| D6 | absent | No hooks. The grep hit is a docstring at `session.py:50`. |
| D7 | partial | Sync and async are hand-written facades over the shared `session_core` (`session.py`, `async_session.py`), not one source with generated sync. |
| D8 | partial | In-memory tests plus Fuseki integration (`tests/conftest_fuseki.py`, `integration` marker, `pyproject.toml`). No Oxigraph-server leg. |
| D9 | absent | No scaffold. |
| RAD1 | absent | No generated CRUD routes; users write FastAPI endpoints themselves (README FastAPI section). |
| RAD2 | n.a. | Out of library scope. |
| O3 | absent | No OWL support (grep `owl` returns nothing in `src/`). |
| O4 | absent | None. |
| O5 | absent | None. |
| O6 | absent | None. |
| O7 | absent | None. |
| A2 | present | Incidentally: generated SPARQL never uses `GRAPH` clauses (`http_common.py:290–301`; grep `GRAPH` returns nothing). |
| A3 | absent | No readonly or writeonly field modes. A generic Pydantic `frozen` field would only guard Python assignment. |

**Re-marked v0 features:**

| Id | Status | Evidence |
|---|---|---|
| O2 | absent | No reasoner in any mode. |
| X4 | partial | Pydantic JSON Schema exists, but `IRI` is a plain `str_schema()` with no `format: uri` (`types.py:39–45`). No TS types. |
| X5 | absent | No events or deltas (see X12). |
| D2 | present | `AsyncSPARQLSession` / `AsyncHttpStore` / `AsyncMemoryStore` (refined by D7: partial). |

### Proposed new features (round 2)

| Proposed id | Area | Feature | Seen here |
|---|---|---|---|
| M16 | Modelling | Mapping validation at class-definition time (predicate IRIs resolvable, unique predicates, inverse pairs consistent) | `model.py:79–96`; triplemodel `fields/validation.py:39`, `fields/back_populates.py:169–299` |

## Round 3

### (a) v2 cross-check

Paths are relative to `src/sparqlmodel/`. Absences were confirmed by grep over `src/` and by reading the module where the feature would live.

**Counts:** 1 present, 2 partial, 16 absent.

| Id | Status | Evidence |
|---|---|---|
| M16 | absent | One `rdf_type` per class (`model.py:51, 59–60`). The identity key is `(class, iri)` (`session_state.py:22`), so one IRI with two types gives two unrelated objects. |
| M17 | present | `_validate_unique_predicates` (`model.py:79–96`), `_ensure_id_field_has_iri_id` (`model.py:181–191`), `register_back_populates` validation (`model.py:75–77`, triplemodel `fields/back_populates.py:169–299`). |
| I5 | absent | No rename API in `session.py` / `session_core.py`. |
| I6 | absent | Pydantic value equality (`BaseModel.__eq__`), not by IRI. Grep finds no `__hash__`/`__eq__` override in `model.py`. The identity map gives one instance per IRI only *inside* a session. |
| P16 | absent | `delete` removes triples irreversibly (`session.py:265–276`). |
| P17 | absent | None. |
| P18 | absent | `update_graph(add, remove)` is a pass-through. The only transformation seam is a custom `StoreProtocol` wrapper (`stores/base.py:20`). |
| P19 | absent | `from_rdf_file` always parses (`session.py:74–118`). |
| Q19 | partial | `.str()`, `.lower()`, `.upper()` on IRI refs with `==` / `!=` / `in_` (`expressions.py:59–135`). No regex or substring operator (grep `regex\|CONTAINS` returns nothing). |
| Q20 | absent | None. |
| S9 | absent | None. |
| S10 | absent | The model is not dereferenced by IRI. File loading only (`from_rdf_file`). |
| S11 | absent | `MemoryStore` has no admin API (`stores/memory.py`). Would come from triplemodel `store/ops.py`. |
| S12 | absent | One HTTP call per query, and per-row hydration (`session_core.py:309–324`). |
| S13 | absent | `parse_sparql_json_bindings` materialises the whole result list (`stores/sparql_json.py:33–41`). |
| S14 | absent | No `logging` anywhere in `src/` (grep `getLogger` returns nothing). |
| X15 | partial | Cascade composition puts the embedded subjects of a root into one `put`/`delete` (`graph.py:211–246`). They are separate IRIs, not fragment IRIs under one document. |
| X16 | absent | None. |
| D10 | absent | None. |

### (b) Developer experience deep-dive

**Shortest complete CRUD** (14 lines, assembled from the docs and tests):
- model: `tests/models.py:23–28`
- create/read: `tests/test_session_crud.py:7–11`
- update: `:33–39`
- delete: `:21–24`
- query: `docs/getting-started.md`

```python
class Person(SPARQLModel):
    rdf_type = "schema:Person"
    __prefixes__ = {"schema": "https://schema.org/"}
    name: str = Field("schema:name")

with SPARQLSession() as session:
    odos = Person(name="Odos")             # id minted as urn:uuid on put
    session.put(odos)                       # create
    loaded = session.get(Person, odos.id)   # read
    odos.name = "Odos M."; session.put(odos)  # update
    found = session.query(Person).where(Person.name == "Odos M.").all()  # query
    session.delete(odos)                    # delete
```

**Concepts to learn (about 12):**
- for the happy path: `SPARQLModel`, `rdf_type`, `__prefixes__`, `IRI`/`id`, `Field`, `Relationship(cascade=)`, `SPARQLSession`, `put` vs `add`, `depth`, `FieldRef` query expressions;
- for remote use: the pending queue / `flush`, plus stores and mirror modes.

The public surface is small: 28 names in `__all__`.

**Typing / IDE:**
- Good: a typed package (`Typing :: Typed`), `ty` in CI, and Pydantic models give completion on instances.
- Weak spot: class-level `Person.name` is produced by a metaclass `__getattr__` (`model.py:28–38`), so type checkers see `str`, not `FieldRef`. `Person.works_for.name` chains are untyped for the IDE. (SQLModel has the same problem.)

**Error messages are actionable.** Real examples:
- `RuntimeError: Cannot close SPARQLSession with 2 pending put(s); call flush() or rollback_pending() first` (`session.py:163–166`).
- `ConfigurationError: Person maps multiple fields to the same predicate: name, label -> https://schema.org/name` (`model.py:91–96`).
- `StaleTripleWarning: add() on Person subject … may leave stale triples for predicate 'schema:name'; use put() for upsert.` (`session_core.py:228–233`).

**Docs:** a good getting-started page, guides (models, sessions, queries, FastAPI, real-world), an API reference, a troubleshooting page that lists real failure modes, and a frank "Known limitations" section. Against that, in-repo SPECS and ECOSYSTEM drift from the code (see Docs vs code).

**Surprises / footguns:**
- `with SPARQLSession()` *looks* transactional, but `put()` writes immediately, and on error only the `flush=False` queue is discarded.
- `add` silently duplicates literals (warning only).
- `.first()` ignores `.limit/.offset`.
- `.in_("x")` with a bare string is rejected.
- Default `!=` includes resources with no value.
- `Person.id` is not queryable through the metaclass (`model.py:36` excludes `id`).
- `execute()` results map back to objects only if the variable is named after the lowercased class.
- `HttpStore` reads can be stale (mirror).
- Memory and HTTP stores return different literal value types (`memory.py:100` vs `sparql_json.py:53`).

**DX score: 4/5.** Developers will love the SQLModel feel. They will hate the transaction and mirror semantics once they go remote.

### (c) Authorization seams (DEC-8)

- **Behind an authorizing SPARQL proxy (semantic.works sparql-parser / mu-authorization, Fluree policy endpoint): partly feasible.**
  - Write semantics are proxy-friendly. Writes are plain `INSERT DATA`/`DELETE DATA`, and reads are plain `SELECT`/`CONSTRUCT`, with **no `GRAPH` clauses anywhere** (`http_common.py:290–301`; grep `GRAPH` returns nothing). A proxy that rewrites or dispatches quads into graphs, sparql-parser style, breaks nothing in the SPARQL text. `rdf:type` travels in the same `INSERT DATA`, so type-based graph dispatch works for creates.
  - Identity propagation is possible: `HttpStore(headers=…, bearer_token=…, client=httpx.Client)` (`stores/http.py:57–61, 88–104`) can carry a `mu-session-id`, a JWT or Fluree credentials.
- **Blockers:**
  1. **The shared mirror leaks data across users.** FastAPI lifespan helpers share one `HttpStore`, and with it one mirror, across all requests (`fastapi/deps.py:85–92`). `get()`, cascade and orphan detection read that mirror (`session_core.py:94–106`, `graph.py:153–167`). Triples pulled under user A's authorisation can be served to user B, and an ACL-filtered (partial) view makes the "owned triples" delete set wrong.
  2. **Non-atomic multi-POST writes.** A proxy that denies one chunk leaves a partial update behind (`stores/http.py:290–291`).
  3. Identity headers are fixed per store instance, not per request, unless a per-request store or client is built (the FastAPI deps do not do this).
- **Where a PEP would go:** the cleanest seam is the **store adapter**. Wrapping `StoreProtocol.query/update_graph` (`stores/base.py:10–21`) to rewrite or filter the SPARQL text and deltas is possible because the compiler emits a plain string. A repository-level filter could also be injected into `QueryState.expressions` (`query_common.py:31`). Both seams are bypassed by the mirror reads, so for ACL-agnostic use **`mirror_mode="remote_authoritative"` with one store per request** would be mandatory, and it is still not airtight because cascade reads the local mirror.
- **Verdict:** the idea of ACL-agnostic SPARQL is borrowable (GRAPH-free, default-graph statements). The mirror architecture is incompatible with DEC-8 as it stands.

### (d) Layer coverage & codegen fit

- **Layers covered:**
  - **L1** domain and persistence: full (models, session, cascade).
  - **L2** stores and transactions: partial (memory and HTTP stores, no transactions).
  - **L4** data-management service / API: partial (FastAPI deps, content negotiation, no generated CRUD routes).
  - **L0**: no codegen. **L3, L5, L6**: none.
- **Generating models from LinkML: feasible with a custom generator or template.** The mapping is fully declarative and static: `rdf_type` ← `class_uri`, `Field("pred")` ← `slot_uri`, `Relationship(model=…, cascade=)` ← range class plus `inlined: true/false`, `__prefixes__` ← schema `prefixes`, `X | None` ← `required`, `set[...]` ← `multivalued`, and subclassing ← `is_a`.
- **What is missing or awkward for codegen:**
  1. Entities must subclass `SPARQLModel`, so linkml's stock `pydantic` generator output cannot be reused unchanged.
  2. `list[...]` means `rdf:List`, whereas LinkML multivalued slots usually mean repeated triples, so the generator must emit `set[...]`.
  3. `list[SPARQLModel]` (inlined multivalued objects) is unsupported (README "Known limitations").
  4. LinkML `identifier` / IRI minting patterns (`id_prefixes`, `structured_pattern`) have no hook; the only options are `urn:uuid` or a caller-supplied id.
  5. Enums with `meaning:` IRIs, language-tagged slots and `mixins` have no direct mapping.
  6. There is no SHACL hook, so LinkML-generated shapes cannot be enforced.

### (e) C9 and C10

| # | Score | Justification | Evidence |
|---|---|---|---|
| C9 Composability / ecosystem fit | 2 | Speaks SPARQL 1.1 Query/Update and GSP GET and emits JSON-LD (prefix context only). The store port is a custom 3-method protocol, not rdflib `Store` or RDF/JS. Hard-wired to triplemodel and pyoxigraph (no rdflib graph interop). No SHACL, LinkML or JSON-LD framing. OIDC/JWT only as raw headers. | `stores/base.py:10–21`, `pyproject.toml` deps, `serializers.model_to_jsonld` |
| C10 Maintainability & operability | 2 | Small export surface (28 names), but subtle semantics (mirror modes, NE toggles, `add` vs `put`). About 25 releases in 16 days and then dormant, with a single maintainer. No logging or observability. Operating `HttpStore` requires understanding mirror staleness and the single-writer assumption. | `__init__.py`, `CHANGELOG.md`, grep `logging` returns nothing, `stores/http.py:36–43` |

### (f) Proposed new features (round 3)

| Proposed id | Area | Feature | Seen here |
|---|---|---|---|
| AZ1 | Authorization | Per-request identity propagation to the store (session/JWT header injected per call, not per store instance) | absent here; `HttpStore(headers=, bearer_token=)` is per instance (`stores/http.py:57–61`) |
| AZ2 | Authorization | Shared client-side caches partitioned by principal (or disabled) to avoid cross-user leakage behind an authorizing proxy | anti-pattern seen: shared mirror (`fastapi/deps.py:85–92`) |
| G1 | Generation | Generator-friendly declarative mapping (all RDF mapping expressible as static class attributes, so a LinkML template can emit it) | `rdf_type`, `__prefixes__`, `Field`, `Relationship` (`model.py`, `fields.py`) |

## Round 4

### (a) v3 cross-check

Checked against `feature-taxonomy.adoc` (v3, 102 features). Paths are relative to `src/sparqlmodel/`. Absences were confirmed by grep over `src/` (`policy`, `permission`, `acl`, `outbox`, `event`, `etag`, `If-Match`, `cursor`, `version`, `savepoint`, `transaction`, `logging` all return no hits outside docstrings) and by reading the module where the feature would live (`session.py`, `session_core.py`, `stores/`, `fastapi/`).

My round-3 proposals map to v3 ids as follows: AZ1 → **AZ19**, AZ2 → **AZ22**, G1 → **G1**.

| Id | Status | Evidence |
|---|---|---|
| AZ1 | absent | No decorator on the store port. `StoreProtocol` (`stores/base.py:10–21`) is *wrappable*, but mirror reads bypass it (`session_core.py:94–106`). |
| AZ2 | absent | No policy injection in `compile_where` (`compiler.py:773–898`). `count()` compiles separately (`query.py:84–87`). |
| AZ3 | absent | No typed SPARQL AST; the compiler output is a string (`compiler.py:893`). |
| AZ4 | absent | None. |
| AZ5 | absent | No changeset is computed; `put` deletes and inserts directly (`session_core.py:196–210`). |
| AZ6 | absent | FastAPI deps only yield a session (`fastapi/deps.py:76–160`). |
| AZ7 | absent | None. |
| AZ8 | absent | None. |
| AZ9 | absent | None. |
| AZ10 | absent | None. |
| AZ11 | absent | None. |
| AZ12 | absent | None. |
| AZ13 | absent | No named graphs at all (grep `GRAPH` returns nothing). |
| AZ14 | absent | None. |
| AZ15 | absent | None. |
| AZ16 | absent | None. |
| AZ17 | absent | None. |
| AZ18 | absent | None. |
| AZ19 | absent | Headers and bearer token are fixed per `HttpStore` instance (`stores/http.py:57–61, 88–104`). The FastAPI store is shared across requests (`fastapi/deps.py:85–92`). This is my round-3 gap. |
| AZ20 | absent | None. |
| AZ21 | absent | None. |
| AZ22 | absent | Anti-pattern: one shared mirror for all requests (`fastapi/deps.py:85–92`, `stores/http.py:83`). |
| AZ23 | absent | None. |
| AZ24 | absent | HTTP 401/403 surface as a generic `QueryError(f"{operation} failed: {exc}")` (`http_common.py:159–161`). |
| AZ25 | absent | None. |
| AZ26 | absent | None. |
| AZ27 | absent | None. |
| AZ28 | absent | None. |
| AZ29 | absent | None. |
| G1 | partial | Classes carry static mapping metadata (`rdf_type`, `Field(pred)`, `Relationship`; `model.py:51–55`, `fields.py:26–33`), but they are **not persistence-free**: they subclass `SPARQLModel`, which adds `model_dump_jsonld`, `ensure_id` and a metaclass (`model.py:41–178`). |
| G2 | absent | The mapper is generic; no generated mapper or repository. |
| G3 | absent | No generator. |
| G4 | absent | No generator. |
| G5 | partial | `IRI` type exists, but its schema is plain `str_schema()` with no `format: uri` (`types.py:35–51`). |
| G6 | partial | `LangString` / `MultiLangString` exist at runtime (README), but there is no schema or generation side. |
| G7 | absent | `model_dump_jsonld` builds a prefix-only `@context` (`serializers.model_to_jsonld`). No frames. |
| G8 | absent | None. |
| G9 | absent | FastAPI derives OpenAPI from *hand-written* routes. Nothing is generated from a schema. |
| G10 | absent | None. |
| G11 | absent | None. |
| G12 | absent | None. |
| G13 | absent | None. |
| G14 | absent | None. |
| G15 | absent | None. |
| G16 | absent | None. |
| G17 | absent | None. |
| G18 | absent | None. |
| G19 | absent | None. |
| G20 | absent | None. |
| G21 | absent | None. |
| G22 | absent | None. |
| G23 | partial | Polymorphism by `rdf:type` (`.polymorphic()`, `compiler._polymorphic_type_patterns`, `compiler.py:675`; resolve-subclass hydration). There is no designator slot. |
| G24 | absent | None. |
| G25 | absent | None. |
| G26 | partial | `__prefixes__` is inherited from the nearest base (`model.py:61–67`), and `rdf_type` is a plain class attribute, so it is inherited. Each class's triplemodel `Rdf` is re-derived (`model.py:194–216`), so it does not suffer from triplemodel's replace-on-subclass problem. Not a general config merge. |
| G27 | absent | None. |
| T1 | absent | Each DELETE/INSERT chunk is a separate POST (`stores/http.py:290–291`, `http_common.py:92–110`). |
| T2 | absent | None. |
| T3 | absent | None. |
| T4 | absent | None. |
| T5 | absent | The pending queue is autoflushed before reads (`session.py:231–233`), so reads see writes only after flushing them. |
| T6 | absent | Retries cover only transient HTTP 502/503/504 (`http_common.py:59–71`), not conflicts. |
| T7 | absent | No capability descriptor. The session docstring admits there is no rollback (`session.py:39–41`). |
| T8 | absent | None. |
| T9 | absent | Retries re-POST updates without an idempotency key (`http_common.py:135–165`). |
| T10 | absent | `rollback_pending` only clears the queue; object state is not reset (`session.py:152–155`). |
| T11 | present | `max_triples_per_update` chunking, ordered as all DELETEs then all INSERTs, with no atomicity across chunks (`http_common.py:92–110`, `stores/http.py:65`). |
| E1 | absent | None. |
| E2 | absent | None. |
| E3 | absent | None. |
| E4 | absent | None. |
| E5 | absent | None. |
| E6 | absent | None. |
| E7 | absent | None. |
| E8 | absent | None. |
| E9 | absent | None. |
| U1 | n.a. | Python server-side library; no JS client. |
| U2 | n.a. | Same. |
| U3 | n.a. | Same. |
| U4 | n.a. | Same. |
| U5 | n.a. | Same. |
| U6 | n.a. | Same. |
| U7 | n.a. | Same. |
| U8 | n.a. | Same. |
| U9 | n.a. | Same. |
| U10 | n.a. | Same. |
| RAD3 | n.a. | No API description to scaffold from. |
| RAD4 | absent | No generated API, so no exposure tiers. |
| X17 | absent | Only RDF media-type negotiation (Turtle / JSON-LD), counted as X7 (`fastapi/__init__.py:72–149`). |
| X18 | absent | None. |
| X19 | absent | None. |
| X20 | absent | `limit` / `offset` only (`query.py:65–75`). |
| X21 | absent | None. |
| X22 | absent | None. |
| D11 | absent | `httpx` status errors are wrapped as `QueryError(f"{operation} failed: {exc}")`; the response body is not included (`http_common.py:159–161`). |
| D12 | absent | `get()` returns `None` (`session.py:278–288`). Exceptions are `ConfigurationError`, `QueryError`, `StaleTripleWarning` (`exceptions.py`). |
| D13 | present | Errors name the model and predicate: `"{cls} maps multiple fields to the same predicate: …"` (`model.py:91–96`) and `"add() on {Model} subject … predicate …"` (`session_core.py:228–233`). |
| S15 | absent | None. |
| S16 | absent | None. |
| S17 | absent | `put` deletes all owned triples and reinserts them; it does not compute a minimal difference (`session_core.py:196–210`). |
| S18 | partial | `SPARQLSession.from_rdf_file` loads a file into a `MemoryStore` outside the write path (`session.py:74–118`). There is no bulk path to remote stores. |
| S19 | absent | None. |

**Counts (102):** 2 present, 6 partial, 83 absent, 11 n.a.

### (b) Purpose and origin

- **Built for:** giving Python application developers a **SQLModel-like ORM over RDF**: Pydantic entities, a `with Session()` workflow, a fluent query builder and FastAPI helpers. The README tagline is "The SQLModel of SPARQL", and the targets are "knowledge-graph and metadata apps".
- **Who and in what context:**
  - One author: GitHub `eddiethedean`, commits signed "Odo/Odos Matthews", pyproject author "SparqlModel Contributors".
  - Released 2026-05-16 → 06-01 in a roadmap-driven burst (version milestones in `docs/ROADMAP.md`, a "1.3 GA gate" checklist in `SPECS.md`).
  - Built on the same author's triplemodel and tested against Fuseki (`tests/conftest_fuseki.py`).
  - Desk scan: 0 stars, 1 contributor, about 61 PyPI downloads a month.
- **Design angle:** developer-experience-first and app-centric. The model lives in Python code; it is a single-process, single-writer design whose client-side mirror stands in for transactions and server round-trips. It is not model-driven: there is no LinkML or ontology input, and it is not standards-driven (no SHACL, no named graphs).
- **Where it fits:** it would be **L1** (domain and persistence) with partial **L2** and **L4**. As a *dependency* it fits nowhere: it fails DEC-5 (0 stars, dormant), the mirror conflicts with DEC-8, and it does not build on rdflib (DEC-4). As an *idea source* it fits our L1 API surface (session, query DSL, depth loading, composition vs reference) and our L4 FastAPI glue.

### (c) Variant fit

| Variant / approach | Fit | Why |
|---|---|---|
| V1 Portable Python core | ideas only | The API ergonomics are exactly the V1 developer experience. The write path (non-atomic, mirror) and the DEC-5 failure block it as a dependency. |
| V2 semantic.works-compatible | blocks as-is | Its GRAPH-free statements suit `sparql-parser`, but per-instance identity headers and the shared mirror leak across users behind the proxy. |
| V3 Fluree | blocks | No per-request policy identity. Plain SPARQL Update only, with no Fluree transaction or commit semantics. |
| V4 GraphDB | blocks benefit | Would run as plain SPARQL but cannot use GraphDB transactions (no T3 adapter). |
| V5 Graph-direct reads (CQRS) | n.a. / blocks | Hydration reads the local mirror, not the read endpoint, so it is not a read-model layer. |
| A Runtime mapper | ideas | It is a runtime mapper, but over its own base class rather than LinkML-generated Pydantic classes. |
| B Generated mapper and routes | enables (template target) | Static, declarative mapping (G1 partial) that a LinkML template could emit. No routes are generated. |
| C Generic service | blocks | Classes must exist in code; there is no runtime model materialisation (M6 absent). |

### (d) Corrections to the integrated docs

1. `catalogue.adoc` lists sparqlmodel layers as "L1, L4". Its own library page (`libraries/sparqlmodel.adoc`, "Layers") and this report give "L1 full · **L2 partial** · L4 partial". The catalogue omits L2 (`MemoryStore` / `HttpStore`).
2. `index.adoc`, Identity row ("… skolem IRIs for blank nodes; equality by IRI", sources "sparqlmodel, OldMan, semantic.works, neomodel"): sparqlmodel contributes only the identity map keyed by `(class, IRI)` and UUID minting. It has **no skolemisation** (round 2, I4 absent) and **no equality by IRI** (round 3, I6 absent: Pydantic value equality). The row should not suggest otherwise.
3. `index.adoc` anti-pattern "SPARQL built by string concatenation": correct for sparqlmodel. Note that sparqlmodel escapes literals and validates IRIs (`sparql_escape.py`, `rdf_n3.validate_iri_token`), so the risk is in correctness and maintainability more than demonstrated injection. Raw `execute()` has no parameter binding.

### (e) Proposed new features (round 4)

| Proposed id | Area | Feature | Seen here |
|---|---|---|---|
| D14 | DevEx | Stale-write warning when an append-only write may leave duplicate values (guides users from `add` to upsert) | `StaleTripleWarning` (`session_core.py:213–236`) |

## Round 5

### (a) v4 cross-check

Checked against `feature-taxonomy.adoc` (v4, 77 features). Paths are relative to `src/sparqlmodel/`. Absences were confirmed by grep over `src/` and `tests/` (`version`, `etag`, `outbox`, `event`, `on_commit`, `migration`, `saga`, `cypher`, `assert_type`, `testcontainers`, `opentelemetry`, `logging`, `did you mean`, `error code` give no hits) and by reading `session.py`, `session_core.py`, `graph.py` and `stores/`.

| Id | Status | Evidence |
|---|---|---|
| B1 | partial | `Relationship(cascade=True)` declares owned (composed) slots and `cascade=False` declares references (`fields.py:119–175`). There is no aggregate-root declaration, and nothing comes from LinkML. |
| B2 | partial | Embed cycles are rejected at `put` / `model_to_graph` time (`rdf_bridge.assert_no_embed_cycles`, `rdf_bridge.py:37`). The check happens at run time, not at generation time, and single owner and no outside references to non-root entities are not checked. |
| B3 | absent | Loading walks `depth` with one `get_impl` per object, plus a CONSTRUCT per missing subject (`session_core.py:239–325`). Not one query. |
| B4 | partial | `put` replaces the owned subtree, including orphans (`session_core.py:196–210`, `graph.py:211–246`). There is no snapshot diff. |
| B5 | partial | `works_for: Organization \| IRI` and `ResourceRef` with `cascade=False` hold IRIs (`tests/models.py:28`). Not a typed `Ref[T]`, and resolution happens implicitly through `depth`. |
| B6 | absent | None. |
| B7 | absent | DELETE DATA and INSERT DATA are sent as separate POSTs with no WHERE guard (`http_common.py:92–110, 290–301`). |
| B8 | absent | `update_graph(add, remove)` stores are built internally and sent immediately. There is no inspectable change-set or dry run. |
| B9 | absent | None. |
| B10 | absent | Default graph only. |
| B11 | absent | None. |
| B12 | absent | None. |
| B13 | partial | Cascade delete inside composition (`session.py:265–276`). Shared targets referenced from outside are kept, but only on `put` orphan cleanup (`graph.py:153–208`). Inbound references are not refused on `delete`. |
| B14 | absent | None. |
| B15 | absent | The opposite design: `autoflush=True` by default (`session.py:58`, `_maybe_autoflush` at `session.py:231–233`). It can be disabled, but there is no warning. |
| B16 | absent | None. |
| PG1 | absent | The compiler renders SPARQL strings only (`compiler.py`). |
| PG2 | absent | None. |
| PG3 | absent | None. |
| PG4 | absent | None. |
| EV1 | absent | None. |
| EV2 | absent | None. |
| EV3 | absent | None. |
| EV4 | absent | None. |
| EV5 | absent | None. |
| EV6 | absent | None. |
| EV7 | absent | None. |
| EV8 | absent | None. |
| EV9 | absent | None. |
| AZ30 | n.a. | A policy-engine feature; sparqlmodel is a client library with no policy engine. |
| AZ31 | n.a. | Same. |
| AZ32 | n.a. | Same. |
| AZ34 | n.a. | Same. |
| AZ33 | absent | FastAPI routes are hand-written; the README example returns 404 for a missing item but has no policy logic. |
| AZ35 | absent | `count()` and `all()` compile separately with no policy filter (`query.py:84–98`). |
| AZ36 | n.a. | A gateway feature. |
| G28 | n.a. | No generator. |
| G29 | n.a. | No generator. |
| G30 | n.a. | No generator. |
| G31 | n.a. | No generator. |
| G32 | n.a. | No generator. |
| G33 | n.a. | No generator. |
| G34 | absent | No `dcterms:conformsTo` handling (grep returns nothing). |
| G35 | partial | Class-level `Person.name` yields a `FieldRef` through the metaclass (`model.py:25–38`), with `.str()`, `.lower()`, `.in_()` and `.is_()` (`expressions.py`). It is not generated, not statically typed, and the domain class is not persistence-free. |
| G36 | absent | None. |
| T12 | absent | None. |
| T13 | absent | No read-only switch. |
| T14 | absent | One store per session (`session.py:62`). |
| S20 | absent | None. |
| S21 | absent | None. |
| S22 | absent | None. |
| S23 | absent | `HttpStore` has no admin operations. |
| X23 | absent | The opposite: `model_from_jsonld` reads only known mapped keys and ignores the rest silently. It keeps only string-valued `@context` entries (prefixes) and drops term definitions (`serializers.py:165–215`). |
| X24 | absent | None. |
| E10 | absent | None. |
| I7 | n.a. | `id` *is* the IRI (CURIE or absolute; `model.py:55`), so there is no separate id to recover. |
| I8 | absent | `ensure_id` mints a permanent `urn:uuid` immediately (`model.py:144–149`). |
| P20 | absent | `flush` replays the queue in insertion order (`session.py:136–150`). |
| U11 | n.a. | Python server-side library. |
| U12 | n.a. | Same. |
| U13 | n.a. | Same. |
| D14 | present | `StaleTripleWarning` from `add()` (`session_core.py:213–236`). Seen first here. |
| D15 | absent | No query logging at all. |
| D16 | absent | None. |
| D17 | partial | `Query._compile()` exists but is private (`query.py:77–82`, used by tests). There is no public `to_sparql()` and no logging. |
| D18 | absent | Unloaded relationships at `depth=0` look like `None`, so "not loaded" cannot be told apart from "absent" (`hydration.validate_depth`, `session_core.depth_satisfied`). |
| D19 | partial | `SPARQLSession()` defaults to a fresh `MemoryStore` (`session.py:62`), and tests have conftest fixtures. Nothing is shipped as a plugin, there is no fake-instance builder, and isomorphism checks are internal only (`rdf_bridge.graphs_isomorphic`). |
| D20 | absent | `tests/conftest_fuseki.py` needs an external `FUSEKI_BASE_URL`. No testcontainers. |
| D21 | partial | The CI "examples" job runs the four real-world scripts (`.github/workflows/ci.yml`, examples job). Docs snippets are not executed. |
| D22 | partial | CURIEs are accepted for ids, `get` and predicates through `expand_iri` (`types.py:62–90`, `session_state.identity_key_for_iri`). `repr` and errors are not CURIE-aware. |
| D23 | absent | None. |
| D24 | absent | None. |
| D25 | absent | Multi-valued fields are `set[...]` (unordered). |
| D26 | absent | Grep `assert_type` returns nothing. |
| D27 | partial | Mocked-transport failure tests, e.g. `test_http_store_update_mirror_unchanged_on_mid_batch_failure` (`tests/test_http_store.py:889`). Not run against a real store. |
| D28 | absent | None. |
| D29 | absent | None. |

**Counts (77):** 1 present, 11 partial, 50 absent, 15 n.a.

### (b) Page review: `docs/modules/ROOT/pages/architecture/soa/libraries/sparqlmodel.adoc`

1. **Line 65** (C7): "Standard Query, Update and GSP GET only, *tested on Fuseki*"
   - **Problem:** Fuseki tests are opt-in (`integration` marker, `FUSEKI_BASE_URL`; `pyproject.toml`, `tests/conftest_fuseki.py`). CI runs no Fuseki service; its jobs are test, docs and examples.
   - **Fix:** "Fuseki integration tests exist but are opt-in (not run in CI)".
2. **Line 76:** "orphan cleanup that protects shared references (`graph.py:153–208`)"
   - **Problem (missing caveat):** protection is computed by scanning the *local mirror* (`graph.py:153–167`), so it is correct only when the mirror holds every referrer. Behind `HttpStore`, an external referrer can be missed and the child deleted.
   - **Fix:** add "(computed from the local graph; incomplete under HttpStore)".
3. **Line 88:** "String-built SPARQL … a correctness and injection surface"
   - **Problem (missing caveat):** literals are escaped and IRIs validated (`sparql_escape.py`, `rdf_n3.validate_iri_token`). The real exposure is raw `execute()`, which has no parameter binding.
   - **Fix:** add that caveat.
4. **Line 92:** "`docs/SPECS.md:349` *claims* one-request DELETE+INSERT"
   - **Problem:** SPECS says `put` "*may* send DELETE DATA followed by INSERT DATA in one SPARQL Update request". The code always sends separate POSTs.
   - **Fix:** "describes a possible one-request DELETE+INSERT that the code never does".
5. **Line 124:** "V4 GraphDB | blocks"
   - **Problem (overstatement):** it runs against GraphDB as plain SPARQL 1.1. It only cannot use GraphDB transactions.
   - **Fix:** "neutral (no transaction benefit)".
6. **Line 151** (G1 partial): correct. Add I8 and X23 to the notable gaps: JSON-LD input silently drops unknown keys and context term definitions (`serializers.py:165–215`), which conflicts with the strict JSON-LD processing that V1 and V5 need.

### (c) Final verdict

**ideas** — borrow the session/query developer experience and the composition-vs-reference cascade; never depend on it.

Three things a system architect must remember:
1. Its `with SPARQLSession()` **is not a transaction**: `put` writes immediately, and remote writes are several non-atomic POSTs.
2. `HttpStore`'s **shared local mirror is treated as truth**. It leaks data across users behind an authorizing proxy and makes cascade and orphan logic wrong under other writers.
3. Its best idea is the **API shape**: `Model.field == x` expressions, explicit `depth`, owned-predicate `put`, and `cascade=True/False` as the aggregate boundary. We should re-implement that shape over a persistence-free LinkML model and a single-request atomic store port.

### (d) Not applicable

I am a library analyst, not an angle analyst; Purpose and origin and the variant-fit table were written in round 4.

### (e) New features

None proposed. The taxonomy covers everything observed here, including D14, which came from this report.
