# rdfproxy

- **Repo:** https://github.com/acdh-oeaw/rdfproxy · clone `/home/lps/work/repos/rdfproxy`
  (ACDH-OEAW, Austrian Academy of Sciences)
- **Commit analysed:** `76aac6a` (2026-10-26, branch `main`; shallow clone, last author Lukas Plank)
- **Licence:** **GPL-3.0** (`LICENSE`)
- **Version:** 0.11.0 (release-please CHANGELOG, 0.8.0 → 0.11.0 over 2025-07 … 2026-08)
- **Size:**
  - Library: 1,875 LOC in 15 modules; the core is `mapper.py` 357, `constructor.py` 249,
    `utils/utils.py` 248, `utils/_types.py` 132, `utils/sparql_utils.py` 126, `adapter.py` 120.
  - Tests: 5,163 LOC, 72 test functions plus heavy `pytest.mark.parametrize` (67 uses). Adapter
    tests are parametrised ×3 targets.
  - Examples: 5 FastAPI/Wikidata examples.
- **Runtime deps:**
  - `pydantic>=2.9.2,<3`, `pandas>=2.2.3,<3`, `rdflib>=7.3`.
  - `sparqlx>=0.10`, the same author's httpx-based SPARQL client, imported as
    `from sparqlx import SPARQLWrapper` (adapter.py:9). It is **not** the `SPARQLWrapper`
    package.
  - Python ≥3.12.
- **GitNexus:** 83 files, 1,514 symbols, 2,303 edges, 31 clusters, 69 processes. The main flows
  are `Base_route → _compvalue_to_dict` (7 steps), `Base_route → _calculate_offset`, and
  `Base_route → _left_wrapper` (examples' FastAPI routes → `get_page` → query constructor
  pipeline), plus `Person_detail → _get_item_filter_clause` (`get_item`).
- **Docs read:**
  - `README.md`, `CHANGELOG.md`, `docs/{index,concept,tutorial,reference}.md`.
  - https://acdh-oeaw.github.io/rdfproxy/. The site has Welcome, Concept, Tutorial and Reference
    pages; in-repo `concept.md` and `tutorial.md` are **empty (0 lines)**, and Reference is
    mkdocstrings autodoc.

## Summary

rdfproxy is a **read-only "SPARQL SELECT → nested Pydantic" adapter** for building REST APIs over
SPARQL endpoints:
- The developer writes a SELECT query and a Pydantic model.
- `SPARQLModelAdapter(target, query, model)` rewrites the query for pagination, counting or
  single-item lookup.
- It runs the query through sparqlx (against a remote endpoint URL **or** an rdflib `Graph`), loads
  the flat bindings into a pandas DataFrame, then groups and aggregates them into nested models.
- Grouping is driven by `ConfigDict(group_by=...)` and `list[...]` fields.

Results come back as a FastAPI-ready `Page[Model]`. There is no write path at all. It is the most
mature of the three libraries analysed here (tests against rdflib, Oxigraph and Fuseki
containers, coverage, release automation), but it solves a different problem: read projections,
not persistence.

## Architecture (GitNexus + source)

- **Clusters.** GitNexus finds four `Rdfproxy` production clusters:
  - adapter/constructor;
  - mapper (`_ModelConstructor` / `UngroupedModelConstructor` / `GroupedModelConstructor` /
    `_ModelBindingsMapper`);
  - type/model utils (`FieldsBindingsMap`, `ModelSPARQLMap`, `CurryModel`);
  - checkers (`check_query`, `check_model`, `check_key`, `check_item_model`).
  The rest are test and example clusters.
- **Key classes:**
  - `SPARQLModelAdapter` (adapter.py:22) — facade; `get_page`, `get_item`, deprecated `query`.
  - `_PageQueryConstructor` and `_ItemQueryConstructor` (constructor.py:97, 28) — query
    rewriting.
  - `_ModelBindingsMapper` (mapper.py:293) — bindings → models.
  - `Page` / `QueryParameters` (utils/models.py:12, 29) — FastAPI I/O models.
- **Execution flow (`get_page`)** (adapter.py:80-109):
  1. `_PageQueryConstructor.get_count_query()` → `replace_query_select_clause` with
     `count(*)` or `count(distinct ?group)` (constructor.py:151-168).
  2. `get_items_query()`, ungrouped: `inject_into_query` (filter stub) →
     `add_solution_modifier(order by, limit, offset)` (constructor.py:204-218). Grouped: build a
     subquery `select distinct ?group … order/limit/offset` and inject it into the original query
     so pagination counts *groups*, not rows (constructor.py:181-202).
  3. `sparqlwrapper.queries(items, count, convert=True)` (adapter.py:93-94).
  4. `_ModelBindingsMapper(model, bindings).get_models()` → DataFrame → `groupby` → recursive
     constructors (mapper.py:317-341).
- **Execution flow (`get_item`)** (adapter.py:55-78): `check_key`, then append a
  `filter(str(?k) = "v")` / `^^xsd` / `@lang` clause before the final `}` (constructor.py:70-94),
  then map, then `check_item_model` (exactly one result expected).

## Implementation principles

- **Mapping = projection.** Model fields bind to SPARQL variables by name, or by
  `Annotated[T, SPARQLBinding("var")]` (utils/_types.py:26-43; `FieldsBindingsMap`,
  utils/utils.py:22).
  - There is no predicate mapping, rdf:type or IRI identity. The *query* defines the shape and
    the model defines the nesting.
  - Nested `BaseModel` fields are built from the same row. `list[Model]` with the nested model's
    `group_by` aggregates rows (mapper.py:189-226).
  - `model_bool` config decides when an all-empty nested model collapses to its default
    (mapper.py:68-93, 229-251).
- **Data-integrity guard.** `_check_grouping_consistency` raises `InconsistentGroupingException`
  (or warns) if a non-aggregated field has distinct values within a group (mapper.py:253-290).
  This is the "Non-Aggregated Field Sameness" assumption made explicit.
- **SPARQL handling.**
  - Queries are parsed with rdflib's `parseQuery` for validation: SELECT only, and no top-level
    solution modifiers (utils/checkers/query_checker.py:12-56).
  - Projection extraction also uses `parseQuery` (sparql_utils.py:105-126).
  - Query *modification* is **regex/string surgery**: `select … where` replacement, injection
    before the last `}`, prefix stripping for subqueries (sparql_utils.py:14-81). The code
    documents the prefix limitation itself (sparql_utils.py:36-39).
  - Item keys are escaped via rdflib `Literal._quote_encode()` (constructor.py:76-78), a private
    API. `xsd_type` and `lang_tag` are interpolated unescaped.
- **Filtering.** `_compute_filter_clause` is a stub that always returns `None`
  (constructor.py:229-231), so the generic query builder does not exist yet. Ordering comes from
  `QueryParameters.order_by`, validated against the model through a dynamic `StrEnum`
  (utils/models.py:60-68).
- **Store access.** Everything goes through sparqlx: a URL or an rdflib `Graph` target, httpx
  under the hood, `aclient_config` passthrough (adapter.py:39-53). Tests run the same adapter
  suite against an in-memory rdflib Graph, an Oxigraph container and a Fuseki container
  (tests/conftest.py:103-112). That is real SPARQL 1.1 Query portability.
- **Persistence, transactions, Update.** None. A read-only adapter by design.
- **Validation.** Pydantic validation of each built model; `CurryModel` validates fields
  incrementally (utils/utils.py:210-248). There is no SHACL.

## Patterns catalogue

| Pattern | Where |
|---|---|
| Adapter / Facade over a SPARQL endpoint | `SPARQLModelAdapter`, adapter.py:22 |
| Query rewriting pipeline (function composition) | `compose_left` + `QueryConstructorComponent`, constructor.py:188-218; utils/utils.py:153-187 |
| Builder / Strategy for model construction (ungrouped vs grouped) | `_ModelConstructor._get_constructor_type`, mapper.py:58-66 |
| Projection / read-model (CQRS query side) | the whole library: SELECT → DTO |
| Declarative config on the model (`group_by`, `model_bool`) | `ConfigDict`, utils/_types.py:55-60 |
| Fail-fast checkers at construction | `check_query`, `check_model`, adapter.py:47-48 |
| Page object (fastapi-pagination style) | `Page`, utils/models.py:12 |
| *Absent:* Repository-for-writes, Unit of Work, Identity Map, Session, lazy loading | — |

## Docs vs code

| Claim | Verdict |
|---|---|
| "building REST APIs on top of SPARQL endpoints" (README, docs site) | Confirmed for **read** APIs: `Page` + `QueryParameters` + FastAPI examples (examples/full_static_fastapi_example.py). |
| Grouping/aggregation of scalars and nested models via `group_by` + `list` (README) | Confirmed: mapper.py:189-226, extensive parametrised tests. |
| Default page size 100 (adapter docstring) | Confirmed: utils/models.py:30. |
| Concept and Tutorial pages (docs site nav) | **Empty**: docs/concept.md and docs/tutorial.md are 0 lines. |
| Filtering | Not claimed; a stub in code (constructor.py:229). |
| "aclient_config option for internal SPARQLWrapper" (CHANGELOG 0.10.0) | Confirmed, passed through to sparqlx (adapter.py:52); the public API is still sync. |
| Coverage badge (coveralls) | CI runs pytest-cov + coveralls (.github/workflows/tests.yml:32-37); the percentage was not checked. |

## Scores

| # | Score | Justification | Evidence |
|---|---|---|---|
| C1 Feature coverage | 1 | Read-only: fetch-by-key, pagination and ordering; no create/update/delete, transactions, identity or JSON-LD | adapter.py:55-109 |
| C2 Approach & patterns | 4 | Clear read-model adapter; grammar-on-the-model for grouping; composable query pipeline; strong checkers. Query surgery by regex is the weak point | constructor.py; sparql_utils.py:14-81 |
| C3 Developer friendliness | 3 | Typed generics (`Page[T]`), FastAPI-native, good custom exceptions; but query-writing is manual, docs are thin (empty concept/tutorial), and group_by semantics have a learning curve | utils/models.py; docs/ |
| C4 Ease of adoption | 3 | Works with a URL or an rdflib Graph at once; pandas plus a niche client (sparqlx) add weight; Python ≥3.12; GPL-3.0 is restrictive for a library dependency | pyproject.toml; LICENSE |
| C5 Reuse of foundations | 3 | Reuses rdflib's SPARQL parser, Pydantic and pandas; the client is the author's own sparqlx rather than SPARQLWrapper; query modification is hand-rolled regex instead of algebra or a builder | adapter.py:9; sparql_utils.py |
| C6 Data-centric & DDD fit | 2 | Models are plain Pydantic DTOs (no persistence code), good for read models; no ontology/schema input, no aggregates, shape defined by SELECT queries | utils/_types.py:26 |
| C7 SPARQL 1.1 portability | 4 | Standard SELECT over HTTP; tested against rdflib, Oxigraph and Fuseki; no Update/GSP | tests/conftest.py:59-112 |
| C8 Health | 4 | Strong CI (tests, coverage, ruff, deptry, gitlint, release-please, docs deploy), Docker integration tests, active 2026-10, institutional backing; single dominant maintainer; GPL-3.0 | .github/workflows/; CHANGELOG.md |

## Feature inventory

| Id | Status | Evidence |
|---|---|---|
| M1 host-language classes | present | Pydantic models as projection targets |
| M2 schema language | absent | — |
| M3 codegen | absent | — |
| M4 inheritance → rdf:type | absent | (model unions: first model wins, mapper.py:68-93) |
| M5 validation on load | present | Pydantic via `CurryModel`, utils/utils.py:210 |
| I1 IRI minting | n.a. | read-only |
| I2 blank nodes | partial | bindings converted by sparqlx; no special handling |
| I3 identity map | absent | dedup of nested models by equality only, mapper.py:229-251 |
| R1 single/multi-valued | present | `list[str]` / `list[Model]` aggregation, mapper.py:194-199 |
| R2 references | partial | nesting via joins in the user's query; no IRI references |
| R3 lazy/eager | partial | eager, depth = query shape |
| R4 cascade | n.a. | read-only |
| L1 typed literals | partial | Python conversion by sparqlx `convert=True`; `xsd_type` key filter, constructor.py:83-84 |
| L2 lang tags | partial | `lang_tag` for item-key filter only; values lose the tag |
| P1 CRUD | partial | Read only |
| P2–P5 update/UoW/tx/versioning | absent | — |
| P6 named graphs | absent | (only inside the user's query) |
| P7 bulk | absent | — |
| Q1 fetch by key | present | `get_item(**key)`, by any bound field, not only the IRI; adapter.py:55 |
| Q2 query builder | absent | filter stub, constructor.py:229 |
| Q3 raw SPARQL → objects | present | the core feature |
| Q4 pagination/order/aggregation | present | `Page`, `QueryParameters`, group-aware LIMIT/OFFSET subquery, constructor.py:181-202 |
| Q5 property paths | partial | whatever the user's SPARQL contains |
| S1 in-memory | present | rdflib Graph target, tests/conftest.py:110 |
| S2 remote endpoint | partial | Query yes, Update no |
| S3 GSP | absent | — |
| S4 pluggable store | partial | URL or Graph via sparqlx; no port abstraction |
| X1 JSON-LD | absent | plain JSON |
| X2 other formats | absent | — |
| X3 HTTP API | partial | FastAPI-ready `Page`/`QueryParameters`; the user wires routes, examples/ |
| X4 schema export | present | via Pydantic/FastAPI OpenAPI; `QueryParameters[Model]` exposes the order_by enum |
| X5 events | absent | — |
| D1 static typing | present | generics `SPARQLModelAdapter[T]`, `Page[T]` |
| D2 async | absent | sync API; sparqlx async used internally via `aclient_config` |
| D3 framework integration | present | FastAPI |
| D4 docs | partial | README + autodoc; concept/tutorial empty |
| D5 testing support | partial | testcontainer fixtures for Oxigraph/Fuseki in its own tests (not shipped) |
| O1/O2 OWL/reasoner | absent | — |
| A1 ACL | absent | (out of scope) |

### Proposed new features

- **Q8 Grouped/aggregated result mapping**: flat SELECT rows → nested objects by group key, with
  pagination over groups (subquery over `distinct ?group`). Evidence: constructor.py:181-202,
  mapper.py:189-226.
- **Q9 Query safety checks**: parse-validate user SPARQL (form, forbidden modifiers) before
  rewriting. Evidence: utils/checkers/query_checker.py.
- **Q10 Result-integrity checks**: detect data loss when aggregating (non-aggregated field
  sameness). Evidence: mapper.py:253-290.
- **X8 Read-model / projection DTOs**: query-defined view models separate from the write model
  (CQRS read side). Evidence: the library as a whole.
- **D6 Multi-store integration test matrix**: the same suite against in-memory, Oxigraph and
  Fuseki via testcontainers. Evidence: tests/conftest.py:59-112.

## JS-friendliness

Good for reads. Endpoints return plain JSON `Page{items,page,size,total,pages}`, and FastAPI
generates OpenAPI from the Pydantic models, including an `order_by` enum per model
(utils/models.py:60-68). There is no JSON-LD context, no IRIs as `@id`, and no write contract.

## Reuse verdict for rdf-persistence: **borrow ideas** (do not depend on it, given GPL-3.0)

- **Borrow:**
  - The **read side**: query-defined Pydantic projections with group-by aggregation and
    group-aware pagination. This fits a cosmic-python "views" module and the later HTTP
    middleware.
  - The fail-fast query/model checkers.
  - The `Page`/`QueryParameters` contract.
  - The three-target testcontainers matrix (rdflib / Oxigraph / Fuseki) as our own conformance
    test setup.
- **Do not depend on it:**
  - The GPL-3.0 licence would infect a library dependency.
  - pandas is a heavy dependency for row grouping.
  - Regex-based query rewriting is fragile. Prefer rdflib algebra or a structured query builder.
- **sparqlx** (same author, httpx-based, sync and async) should be looked at as a candidate
  SPARQL client alongside SPARQLWrapper. Its licence and maturity are not checked here.

## Risks / anti-patterns observed

- **Regex query surgery.** `select … where` replacement, injection before the last `}` and prefix
  stripping can break on nested selects, comments, `FROM` clauses or prefix-dependent subqueries.
  The code admits the prefix issue itself (sparql_utils.py:36-39).
- **Private rdflib API** `Literal._quote_encode` (constructor.py:76-78); `xsd_type` and
  `lang_tag` are interpolated unescaped (constructor.py:84-86).
- **Fragile grouping assumption.** Grouping relies on "Non-Aggregated Field Sameness" and uses
  only the first row of a group for scalars (mapper.py:95-110). This is guarded by the
  consistency check, but by default it raises.
- **Repeated full-query scans.** The count query is a SELECT-clause replacement over the full
  user query; pagination with OFFSET over large endpoints may be slow.
- **Heavy dependency for a light job.** pandas is a runtime dependency only for groupby.

## Round 2 cross-check (taxonomy v1)

This round checks rdfproxy against taxonomy v1
(`docs/modules/ROOT/pages/architecture/soa/feature-taxonomy.adoc`).

How the evidence was gathered:
- `rdfproxy/` was re-read. Line numbers are file-relative.
- Every "absent" was confirmed by a grep over `rdfproxy/` for skolem, cache, retry, async, hook,
  json-ld, lang, owl, subClassOf, delete, insert, update, named, describe, diff and
  content-type. The hits are only:
  - `lang_tag` (constructor.py:39-86);
  - checker "hooks" (model_utils.py:16-56). These are model-validation visitors, not lifecycle
    hooks.
- GitNexus processes cover only `get_page` and `get_item` (e.g. `Person_detail →
  _get_item_filter_clause`, `Base_route → _calculate_offset`). There is no write flow.

rdfproxy is read-only by design (adapter.py:22-120), so write-side features are marked **n.a.**

| Id | Status | Evidence |
|---|---|---|
| M6 runtime model materialisation | absent | Models are user-defined Pydantic classes. `QueryParameters[Model]` creates only a parameter model (utils/models.py:60-68). |
| M7 convention-based predicates | n.a. | There is no predicate mapping. The equivalent convention is field name = SPARQL variable, with a `SPARQLBinding` override (utils/_types.py:26; utils/utils.py:22). |
| M8 JSON-LD context as mapping | absent | — |
| M9 attribute ≠ property | partial | Several fields can bind to different variables, which the user's query can derive from one predicate (e.g. per-language `FILTER`). The library has no explicit support. |
| M10 behaviour bound to schema classes | absent | No RDF classes. |
| M11 strict / warn on unmapped import | absent | Extra bindings are ignored. The nearest check is the grouping-consistency check, which covers a different concern (Q11). |
| M12 alternative type discriminator | n.a. | No type mapping. |
| M13 constraint emission | absent | — |
| M14 reverse engineering | absent | — |
| M15 external model-file compatibility | absent | — |
| I4 skolemisation policy | absent | BNode bindings pass through as-is (utils/_types.py:118). |
| R5 cardinality on relations | partial | `list[...]` versus scalar fields plus Pydantic validation. `check_item_model` enforces exactly one result for `get_item` (utils/checkers/item_checker.py:40). |
| R6 mutually exclusive relations | partial | Model-union fields instantiate the first model that passes `model_bool` (mapper.py:68-93). This is not true xone. |
| R7 relations with properties | partial | A nested model can carry edge attributes from the same row, but only if the user's query projects them. There is no RDF-star or reification support. |
| R8 inverse navigation | n.a. | Navigation is whatever the user's query does. |
| L3 pluggable literal registry | partial | Conversion goes through sparqlx `convert=True` and rdflib `toPython` (adapter.py:71, 94; utils/_types.py:118). The library adds no registry of its own. |
| P8–P15 (write-side persistence) | n.a. | Read-only; no write API (grep delete/insert/update: 0 hits). |
| Q6 injection-safe binding | partial | Key values are escaped via `Literal._quote_encode` (constructor.py:76-78), and `order_by` is validated against a model enum (utils/models.py:60-68). `xsd_type` and `lang_tag` are interpolated raw (constructor.py:84-86). |
| Q7 typed SPARQL AST builder | absent | Rewriting is regex and string based (sparql_utils.py:14-81). `parseQuery` is used for checks only. |
| Q8 derived query methods | absent | — |
| Q9 eager loading / N+1 avoidance | present | One flat SELECT fetches the whole nested graph and is grouped client-side. The items and count queries are sent concurrently in one `queries()` call (adapter.py:93-94; mapper.py:323-341). |
| Q10 grouped result mapping | present | `group_by` with `list[Model]`, and pagination over a `distinct ?group` subquery (constructor.py:181-202; mapper.py:189-226). |
| Q11 query safety / integrity checks | present | `check_query` allows SELECT only with no top-level modifiers (query_checker.py:12-56). `_check_grouping_consistency` guards aggregation (mapper.py:253-290). |
| Q12 full-text search | absent | — |
| Q13 user-defined SPARQL functions | absent | — |
| Q14 standard filter language | absent | `_compute_filter_clause` is a stub that returns None (constructor.py:229-231). |
| Q15 totals / facets / capped counts | partial | `Page.total` and `pages` come from a count query (constructor.py:151-168; utils/models.py:12). There are no facets or caps. |
| Q16 open-world semantics config | absent | — |
| Q17 polymorphic query over subclasses | absent | — |
| Q18 CBD extraction | absent | SELECT only (query_checker.py:19). |
| S5 read/write endpoint split | n.a. | Read-only, one `target` (adapter.py:39). |
| S6 client-side cache | absent | — |
| S7 HTTP resilience | partial | Delegated to sparqlx/httpx. `raise_for_status` was added in 0.8.0 (CHANGELOG), and `aclient_config` passes through to httpx, where a transport with retries can be configured (adapter.py:44-53). rdfproxy has no retry logic of its own. |
| S8 store port is a community standard | partial | Accepts a SPARQL 1.1 Protocol URL or an `rdflib.Graph` (adapter.py:41). There is no port abstraction of its own. |
| X6 JSON:API contract | absent | Uses its own `Page{items,page,size,total,pages}` shape (utils/models.py:12). |
| X7 content negotiation | absent | — |
| X8 Hydra hypermedia | absent | — |
| X9 API ↔ storage vocabulary mapping | partial | `SPARQLBinding` maps API field names to SPARQL variables (utils/_types.py:26-43). |
| X10 read models / projections | present | This is the whole library: SELECT → Pydantic DTO (adapter.py:22). |
| X11 annotated representations | absent | Labels appear only if the user's query projects them. |
| X12 delta / change-set format | absent | — |
| X13 request-context propagation | absent | — |
| X14 graph / model diff API | absent | — |
| D6 lifecycle hooks | absent | The `model_bool` and checker visitors (model_utils.py) are not lifecycle hooks. |
| D7 single-source sync/async | absent | Sync API only. sparqlx's async is used internally (adapter.py:51-53). |
| D8 multi-store test matrix | present | The `target` fixture runs rdflib, Oxigraph and Fuseki via testcontainers (tests/conftest.py:59-112). |
| D9 scaffold | absent | — |
| RAD1 zero-code CRUD service | absent | Read routes are hand-wired (examples/). |
| RAD2 declarative routing | absent | — |
| O3–O7 (OWL class expressions, inferred views, closure, SWRL, imports) | absent | No owl in `rdfproxy/`. |
| A2 auth-proxy compatibility | present | The library generates no GRAPH clauses; only the user's query decides (constructor.py, sparql_utils.py). |
| A3 field-level access modes | absent | — |
| *v0 re-marks* | | |
| O2 reasoner integration | absent | — |
| X4 schema export with RDF-term types | partial (was present) | FastAPI/Pydantic JSON Schema and OpenAPI exist, but IRIs are plain `str` unless the user types them; there are no RDF-term types. |
| X5 change notifications | absent | — |
| D2 async API | absent | See D7. |

### Proposed new features (round 2)

- **S9 Concurrent multi-query dispatch.** Independent queries (e.g. items and count) are sent in
  parallel through one client call (adapter.py:93-94, via sparqlx `queries()`).
- **S10 Streaming result sets.** Incremental consumption of large SELECT/CONSTRUCT results
  (sparqlx `query_stream` / `aquery_stream`). This is not used by rdfproxy itself.

### sparqlx note

- **Repo:** https://github.com/lu-pl/sparqlx, by Lukas Plank, the rdfproxy author.
- **Health:** about 6 stars. Last push 2026-10-29. Latest PyPI release 0.11.0, uploaded
  2026-10-26; rdfproxy pins `>=0.10`. Single maintainer.
- **Licence:** GPL-3.0, per the GitHub API. The PyPI metadata has no licence and the placeholder
  summary "Add your description here".
- **What it offers:**
  - SPARQL Query **and Update** over the SPARQL Protocol, built on httpx (now `httpx2>=2.10`).
  - Sync and asyncio APIs: `query` / `aquery`, plus a concurrent `queries()`.
  - Streaming: `query_stream` / `aquery_stream`.
  - Accepts an `rdflib.Graph` target as well as an endpoint URL.
  - `convert=True` maps results to rdflib terms: a list of dicts for SELECT, a bool for ASK, a
    Graph for CONSTRUCT/DESCRIBE.
  - Auth and other client settings via `aclient_config`.
  - No Graph Store Protocol and no retries are mentioned in its README (fetched 2026-11-03).
- **Verdict:**
  - Technically the best fit seen so far for D7 (sync and async from one client), S1 with S2
    (one API for in-memory and remote) and S10 (streaming).
  - But **GPL-3.0, one maintainer, ~6 stars and a 0.x API that has had breaking changes** rule
    it out as a dependency of an Apache/MIT-style library under DEC-4.
  - Recommendation: borrow its design (a thin port over httpx plus an rdflib-Graph target) and
    keep SPARQLWrapper (or plain httpx) as the default client behind our own store port. Revisit
    if it is relicensed.

## Round 3

### (a) v2 cross-check

| Id | Status | Evidence |
|---|---|---|
| M16 multi-typed instances | n.a. | There is no type mapping; the shape comes from the query. |
| M17 mapping validation at definition time | present | `check_model` runs when the adapter is constructed (adapter.py:48). It validates `group_by` targets, `model_bool` references, union defaults and grouping-consistency config (utils/checkers/_model_checks.py:18-154). `check_query` validates the query form (adapter.py:47). `check_key` validates item keys against the query projection (item_checker.py:15-35). |
| I5 IRI renaming | n.a. | Read-only. |
| I6 equality by identity | partial | Pydantic value equality, used to deduplicate nested models (mapper.py:229-251). There is no identity concept. |
| P16–P19 (soft delete, offloading, write hooks, reload) | n.a. | Read-only. |
| Q19 regex/substring filters | absent | The filter stub always returns None (constructor.py:229-231). |
| Q20 vector search | absent | — |
| S9 multi-backend replication | n.a. | Single read target. |
| S10 LD dereferencing store | absent | — |
| S11 embedded-store admin | absent | — |
| S12 batched queries | present | `self._sparqlwrapper.queries(items_query, count_query, convert=True)` sends both in one call; sparqlx runs them concurrently (adapter.py:93-94). |
| S13 streaming results | absent | Uses `queries(..., convert=True)`, which materialises everything into a pandas DataFrame (mapper.py:303-315). sparqlx streaming is not used. |
| S14 query observability | partial | Every generated query is logged at DEBUG as JSON through `StructuredMessage`: the input query, bindings map and generated query (constructor.py:57-66, 136-148, 160-166; utils/structlog.py). There is no timing and no fingerprint. |
| X15 document-centric grouping | absent | — |
| X16 API profile conformance | absent | `Page` is its own shape, not OGC API or JSON:API (utils/models.py:12). |
| D10 model diagram generation | absent | — |

### (b) Developer experience deep-dive

- **Shortest complete example.** `examples/wikidata_ungrouped_person_fastapi_example.py`,
  **30 non-blank lines**: a SPARQL query, two models, an adapter and a FastAPI route returning
  `Page[Person]`. It is a complete paginated REST endpoint, the shortest "useful thing" among the
  three libraries.
- **Concepts to learn: about 8.**
  1. `SPARQLModelAdapter`, with `get_page` / `get_item`.
  2. Field-name = SPARQL-variable binding, and `SPARQLBinding`.
  3. `ConfigDict(group_by=...)` together with `list[...]` aggregation.
  4. The `model_bool` rule for empty nested models.
  5. The grouping-consistency rule (`enforce_grouping_consistency`).
  6. `Page` / `QueryParameters[Model]`.
  7. Query restrictions: SELECT only, no top-level modifiers.
  8. `get_item` key semantics (`xsd_type` / `lang_tag`).
  Concepts 3–5 are the learning curve: you must design the SELECT and the model together.
- **Typing and IDE.** Good. `SPARQLModelAdapter[T]` and `Page[T]` are generics, and
  `QueryParameters[Model]` produces an `order_by` enum that shows up in OpenAPI. Mapping errors
  are runtime-only but fail fast when the adapter is built.
- **Real error messages** (specific, and name the model and binding):
  - `UnprojectedKeyBindingException: SPARQL binding 'gnd' for model field 'Author.gnd' not in query projection.`
    (utils/checkers/item_checker.py:33-35)
  - `GroupByException: Model 'Work' has a list-annotated field but  does not specify 'group_by' in its model_config.`
    (utils/checkers/_model_checks.py:31-33; the double space is in the source)
  - `UnsupportedQueryException: Solution modifiers for top-level queries are currently not supported.`
    (query_checker.py:39-41)
  - Quirk: `NoResultsFound`, `MultipleResultsFound`, `UnprojectedKeyBindingException` and
    `InconsistentGroupingException` do **not** inherit `RDFProxyBaseException`
    (utils/exceptions.py:51-64). A blanket `except RDFProxyBaseException` misses them.
- **Docs.** The README is a strong worked example with input table, models and JSON output.
  The docs site's Concept and Tutorial pages are empty. The reference is autodoc, and the
  examples folder is good.
- **Footguns.**
  - A user query with ORDER BY, LIMIT or GROUP BY is rejected.
  - Prefixes are stripped from grouped subqueries.
  - Regex rewriting can break unusual queries.
  - Grouping-consistency errors appear at request time when the data changes.
  - `get_item` filters on `str(?k)`, so typed keys need `xsd_type`.
  - pandas `dtype=object` quirks with `None` versus `NaN` are handled in the code but subtle.
- **What developers would love:** a paginated FastAPI endpoint over any SPARQL endpoint in about
  30 lines. **What they would hate:** hand-writing every SELECT, opaque grouping rules, no writes
  and no filtering.
- **DX score: 3/5.**

### (c) Authorization seams — rdfproxy as a PEP site

- **Behind an authorizing SPARQL proxy: yes, but only with fixed credentials.**
  - The target is a SPARQL Protocol URL. Headers and auth go through `aclient_config`, passed
    once in the constructor to sparqlx and httpx (adapter.py:39-53).
  - Adapters are built at module level in every example (examples/*.py). Per-user tokens
    therefore cannot flow through without either building an adapter per request or a custom
    `httpx.Auth` that reads a contextvar. X13 (request-context propagation) is absent.
  - Because rdfproxy never adds GRAPH clauses (A2), a graph-filtering proxy behaves the same as
    a direct endpoint.
- **PEP sites, three candidates:**
  1. **FastAPI layer** (route dependencies in the user's app; examples/). This is the natural
     place for authn and coarse authz: may this caller use this endpoint or projection. It is
     fully outside rdfproxy and works today.
  2. **Query-rewriting pipeline.** `_PageQueryConstructor._compute_filter_clause` is an
     explicit stub (constructor.py:229-231), already wired into both items-query paths through
     `inject_into_query` (constructor.py:188-218). It is exactly where a policy-derived
     `FILTER` / `VALUES` row filter would go. Three defects make it unsafe as a PEP today:
     - (a) **The count query ignores the filter.** `get_count_query` rewrites only the SELECT
       clause of the raw query (constructor.py:151-168). Totals would leak the size of data the
       caller cannot see.
     - (b) **In grouped models the filter only reaches the subquery.** The filter is injected
       into the paging subquery that selects group keys. The outer query, which fetches the
       group members, is unfiltered (constructor.py:188-202). Row or field filtering inside a
       group would leak.
     - (c) **`get_item` uses a separate constructor** (`_ItemQueryConstructor`,
       constructor.py:28-94) with no filter hook at all.
     A sound PEP needs one policy-injection point applied to *every* generated query: items,
     count, item, and both outer and sub queries. Ideally it works on a parsed algebra rather
     than with regex. This is proposed as AZ1.
  3. **Post-mapping filtering of `Page.items`.** This is too late: it breaks `total` and
     `pages` and wastes queries. It is acceptable only for field-level redaction (A3) through
     Pydantic serialisation.
- **Verdict:** rdfproxy is ACL-agnostic behind a proxy with static credentials. For
  rdf-persistence, borrow the *location* of the seam (the query-construction pipeline plus the
  FastAPI dependency layer) but not its implementation, and add per-request credential
  propagation.

### (d) Layer coverage and codegen fit

- **Layers:**
  - L4 partial: read-only REST building blocks (`Page`, `QueryParameters`, FastAPI-ready).
  - L1 partial: the read side only (projections, X10).
  - L2 partial: SPARQL Query through sparqlx (URL or rdflib Graph); no Update or transactions.
  - L5 indirect: through FastAPI's OpenAPI.
  - L0, L3, L6: none.
- **LinkML fit: partial.** Any Pydantic model works as a projection target, so gen-pydantic
  classes can be used as-is for flat or nested reads. What is missing:
  1. **Queries are not generated.** rdfproxy needs a hand-written SELECT whose variable names
     match the field names. A generator would have to derive the SELECT from `class_uri` and
     `slot_uri`: OPTIONAL per optional slot, joins per object-range slot.
  2. Grouping metadata — `ConfigDict(group_by=<identifier slot>)` on every class with
     multivalued slots — must be added by a template.
  3. The identifier slot must be projected as a variable.
  4. LinkML write models (full aggregates) rarely equal API read projections, so in an MWBv2
     chain rdfproxy-style models fit best as *generated views* derived from the schema,
     generated alongside the write model.

### (e) C9 and C10

| # | Score | Justification | Evidence |
|---|---|---|---|
| C9 Composability | 3 | Works against any SPARQL 1.1 Query endpoint or an rdflib Graph (tested on three stores), and speaks Pydantic / FastAPI / OpenAPI. No Update, GSP, JSON-LD or SHACL. Hard-wired to sparqlx, which is not behind a port. GPL-3.0 limits embedding. | adapter.py:9, 51; tests/conftest.py:103-112 |
| C10 Maintainability & operability | 3 | release-please semver, a CHANGELOG with BREAKING notes, structured DEBUG logging, deptry and gitlint in CI. But 0.x with breaking changes (0.10.0), heavy pandas plus niche sparqlx dependencies, Python ≥3.12 only, fragile regex rewriting, one dominant maintainer. | CHANGELOG.md; .github/workflows/; sparql_utils.py:14-81 |

### (f) Proposed new features (round 3)

- **AZ1 Uniform policy-injection point.** One PEP hook applied to *every* generated query —
  item, page items, count, and outer plus sub queries — so that totals, groups and lookups
  cannot leak filtered data. Evidence of the gap: constructor.py:151-168, 188-202, 229-231.
- **G1 Schema → query/projection generation.** Derive SELECT/CONSTRUCT queries and read-model
  classes (with grouping keys) from LinkML `class_uri` / `slot_uri` / `multivalued`, instead of
  hand-writing them. Evidence of the gap: rdfproxy requires a hand-written query (adapter.py:46).

## Round 4

### (a) v3 cross-check

The table below checks every "v3 features" row of `feature-taxonomy.adoc`.

How absences were confirmed:
- A grep over the library source for these indicators: auth, polic, permission, token,
  transaction, commit, rollback, etag, if-match, event, notif, outbox, patch, savepoint,
  idempot, cursor, history, branch, openapi, graphql, hydra, frame, @context, mock, enum,
  langstring, anyurl. Hits are cited in the table; otherwise there were 0 relevant hits.
- The GitNexus symbol and process lists from round 1, which hold no such symbols.

Relation to my round-3 proposals: AZ1 became **AZ2**, and G1 became **G14** (per the Id-mapping
appendix).

| Id Feature | Status | Evidence |
|---|---|---|
| AZ1 Access-scope / PEP port at the store boundary: a decorator on the store port … | absent | sparqlx is called directly (adapter.py:51-53, 71, 93); there is no store-port decorator. |
| AZ2 Uniform policy injection into every generated query — item, page, count, … | absent | Only a seam stub: `_compute_filter_clause` returns None (constructor.py:229-231). It reaches only the items queries (constructor.py:188-218). The count query (constructor.py:151-168) and the item query (constructor.py:28-94) bypass it, and grouped models filter only the paging subquery. |
| AZ3 Query-rewriting PEP on a typed SPARQL AST (policy constraints injected as … | absent | Rewriting is regex-based (sparql_utils.py:14-81). `parseQuery` is used only for checks (query_checker.py:46-56). |
| AZ4 List-filter integration: a PDP list / plan call (ListObjects, … | absent | Not in `rdfproxy/` (indicator grep: 0 relevant hits; GitNexus: no such symbol). |
| AZ5 Write authorization on the changeset: the unit of work computes the delta … | n.a. | Read-only. |
| AZ6 Staged PEP hooks in the service pipeline (pre-read, post-read, … | absent | No staged hooks. Pre- and post-read logic lives in the user's FastAPI route (examples/*.py). |
| AZ7 Separated PEP / PIP / PDP pipeline (credentials → required modes → … | absent | Not in `rdfproxy/` (indicator grep: 0 relevant hits; GitNexus: no such symbol). |
| AZ8 Triple-level policy targeting by property, class (with RDFS entailment) or … | absent | Not in `rdfproxy/` (indicator grep: 0 relevant hits; GitNexus: no such symbol). |
| AZ9 SPARQL-condition policies with pre-bound `$this` / `$identity` / `$value` / … | absent | Not in `rdfproxy/` (indicator grep: 0 relevant hits; GitNexus: no such symbol). |
| AZ10 Policy-as-data: policies stored, versioned and queried as RDF, evaluated by … | absent | Not in `rdfproxy/` (indicator grep: 0 relevant hits; GitNexus: no such symbol). |
| AZ11 Combining algorithm and default-deny (required gates, deny-overrides, … | absent | Not in `rdfproxy/` (indicator grep: 0 relevant hits; GitNexus: no such symbol). |
| AZ12 SPARQL-defined group membership: a group is a SELECT over session data; … | absent | Not in `rdfproxy/` (indicator grep: 0 relevant hits; GitNexus: no such symbol). |
| AZ13 Parameterised graph templates: graph IRI = base + token parameters … | absent | Not in `rdfproxy/` (indicator grep: 0 relevant hits; GitNexus: no such symbol). |
| AZ14 Type / predicate-pattern write policy deciding which graphs a quad may land in | n.a. | Read-only. |
| AZ15 Caller scopes: grants restricted to a calling service identity | absent | Not in `rdfproxy/` (indicator grep: 0 relevant hits; GitNexus: no such symbol). |
| AZ16 Privileged bypass ("sudo") with explicit per-service opt-in | absent | Not in `rdfproxy/` (indicator grep: 0 relevant hits; GitNexus: no such symbol). |
| AZ17 Non-widenable governed session: the scope is bound to the handle and query … | absent | Not in `rdfproxy/` (indicator grep: 0 relevant hits; GitNexus: no such symbol). |
| AZ18 IdP claim → policy selector mapping (roles / organisations → graph … | absent | Not in `rdfproxy/` (indicator grep: 0 relevant hits; GitNexus: no such symbol). |
| AZ19 Per-request end-user identity propagation to the store: token or delegated … | absent | `aclient_config` is fixed when the adapter is constructed (adapter.py:44-53). Adapters are module-level in every example, so there is no per-request identity. |
| AZ20 Access-token propagation and caching across hops (allowed groups computed … | absent | Not in `rdfproxy/` (indicator grep: 0 relevant hits; GitNexus: no such symbol). |
| AZ21 Principal or trust level threaded through write calls into field-level checks | n.a. | Read-only. |
| AZ22 Client-side caches partitioned by principal, or disabled, behind an … | n.a. | No client cache. |
| AZ23 Trusted-proxy gate: a shared-secret header required so the service answers … | absent | Not in `rdfproxy/` (indicator grep: 0 relevant hits; GitNexus: no such symbol). |
| AZ24 Declared authorization error contract mapped to HTTP 401 / 403 | absent | Not in `rdfproxy/` (indicator grep: 0 relevant hits; GitNexus: no such symbol). |
| AZ25 Read masking / redaction of sensitive properties (instead of hiding them) | absent | Not in `rdfproxy/` (indicator grep: 0 relevant hits; GitNexus: no such symbol). |
| AZ26 Policy-aware explain and statistics (no cardinality leak to scoped callers) | absent | Not in `rdfproxy/` (indicator grep: 0 relevant hits; GitNexus: no such symbol). |
| AZ27 Authorization decision audit trail (call id, groups or policies used, on the … | absent | Not in `rdfproxy/` (indicator grep: 0 relevant hits; GitNexus: no such symbol). |
| AZ28 Authorization-tuple sync from domain events (ReBAC tuples kept consistent … | n.a. | Read-only. |
| AZ29 ACL configuration or policy inputs generated from the model (classes and … | absent | Not in `rdfproxy/` (indicator grep: 0 relevant hits; GitNexus: no such symbol). |
| G1 Persistence-free generated domain classes that carry the RDF mapping … | absent | Not in `rdfproxy/` (indicator grep: 0 relevant hits; GitNexus: no such symbol). |
| G2 Generated mapper / repository layer kept separate from the domain classes … | absent | Not in `rdfproxy/` (indicator grep: 0 relevant hits; GitNexus: no such symbol). |
| G3 Overridable generator templates and injected base classes / fields | absent | Not in `rdfproxy/` (indicator grep: 0 relevant hits; GitNexus: no such symbol). |
| G4 Per-module (split) generation following schema imports | absent | Not in `rdfproxy/` (indicator grep: 0 relevant hits; GitNexus: no such symbol). |
| G5 IRI-typed fields in generated code (Pydantic `AnyUrl` or constrained str, … | partial | `AnyUrl` is accepted as a SPARQL-bound field type (utils/_types.py:122); the user chooses it. IRIs come back as `URIRef` / str. |
| G6 Language-tagged string type in the schema, the generated code and the round-trip | absent | Not in `rdfproxy/` (indicator grep: 0 relevant hits; GitNexus: no such symbol). |
| G7 JSON-LD context and frames generated from the schema, one frame per … | absent | Not in `rdfproxy/` (indicator grep: 0 relevant hits; GitNexus: no such symbol). |
| G8 Twin projections: typed host classes and the JSON-LD context generated … | absent | Not in `rdfproxy/` (indicator grep: 0 relevant hits; GitNexus: no such symbol). |
| G9 API contract generation (OpenAPI) from the schema plus an operations template | partial | OpenAPI comes indirectly from FastAPI over `Page[T]` / `QueryParameters[T]` (utils/models.py:12-68), not from a schema. |
| G10 API route / handler generation per aggregate (paths, operations, … | absent | Not in `rdfproxy/` (indicator grep: 0 relevant hits; GitNexus: no such symbol). |
| G11 Hydra `ApiDocumentation` generated from the model (supportedClass / Property … | absent | Not in `rdfproxy/` (indicator grep: 0 relevant hits; GitNexus: no such symbol). |
| G12 GraphQL schema with queries, filters and mutations generated from SHACL / … | absent | Not in `rdfproxy/` (indicator grep: 0 relevant hits; GitNexus: no such symbol). |
| G13 Per-class filter / sort / include grammar generated from slot annotations | partial | A per-model `order_by` enum is generated from the model's SPARQL-bound fields (utils/models.py:60-68). This is the sort grammar only; there are no filters or includes. |
| G14 Read-model query and projection generation (SELECT / CONSTRUCT and grouping … | absent | Not in `rdfproxy/` (indicator grep: 0 relevant hits; GitNexus: no such symbol). |
| G15 Server response profiles and endpoint hierarchies generated from the model | absent | Not in `rdfproxy/` (indicator grep: 0 relevant hits; GitNexus: no such symbol). |
| G16 Client-side model generation from the same model (TS types, client mapping … | absent | Not in `rdfproxy/` (indicator grep: 0 relevant hits; GitNexus: no such symbol). |
| G17 Shapes / ontology → schema import with multi-file merge — refines M14 | absent | Not in `rdfproxy/` (indicator grep: 0 relevant hits; GitNexus: no such symbol). |
| G18 UML → OWL / SHACL / context with a modelling-conventions report gate | absent | Not in `rdfproxy/` (indicator grep: 0 relevant hits; GitNexus: no such symbol). |
| G19 Reasoner-based model quality gate: the build fails on inconsistency or … | absent | Not in `rdfproxy/` (indicator grep: 0 relevant hits; GitNexus: no such symbol). |
| G20 Inference materialisation as a build artefact (inferred triples exported to … | absent | Not in `rdfproxy/` (indicator grep: 0 relevant hits; GitNexus: no such symbol). |
| G21 Generated data-quality SPARQL check queries | absent | Not in `rdfproxy/` (indicator grep: 0 relevant hits; GitNexus: no such symbol). |
| G22 Generated mapping rules (YARRRML / RML) from the schema | absent | Not in `rdfproxy/` (indicator grep: 0 relevant hits; GitNexus: no such symbol). |
| G23 Polymorphic instance typing via a type-designator slot | absent | Not in `rdfproxy/` (indicator grep: 0 relevant hits; GitNexus: no such symbol). |
| G24 Enum values bound to concept IRIs, serialised as IRIs | absent | Not in `rdfproxy/` (indicator grep: 0 relevant hits; GitNexus: no such symbol). |
| G25 Standalone generated bindings with object-set identity and a pluggable … | absent | Not in `rdfproxy/` (indicator grep: 0 relevant hits; GitNexus: no such symbol). |
| G26 Inheritance-safe mapping configuration (per-class config merges with the … | absent | Not in `rdfproxy/` (indicator grep: 0 relevant hits; GitNexus: no such symbol). |
| G27 Build-time regeneration: generated code never edited, generator version … | absent | Not in `rdfproxy/` (indicator grep: 0 relevant hits; GitNexus: no such symbol). |
| T1 Single-request atomic flush: the unit of work sends all changes as one … | n.a. | Read-only (no write path, adapter.py:22-120). |
| T2 Guarded update / compare-and-swap in WHERE on a per-aggregate version … | n.a. | Read-only (no write path, adapter.py:22-120). |
| T3 Vendor multi-request transaction adapter (begin / operations / commit / … | n.a. | Read-only (no write path, adapter.py:22-120). |
| T4 Compensating rollback / undo log when the store cannot do an atomic … | n.a. | Read-only (no write path, adapter.py:22-120). |
| T5 Read-your-writes inside a transaction without flushing | n.a. | Read-only (no write path, adapter.py:22-120). |
| T6 Automatic retry of a transactional function on conflict | n.a. | Read-only (no write path, adapter.py:22-120). |
| T7 Store capability descriptor (atomic per request, multi-request transactions, … | n.a. | Read-only (no write path, adapter.py:22-120). |
| T8 Savepoints inside a transaction | n.a. | Read-only (no write path, adapter.py:22-120). |
| T9 Idempotent writes / idempotency key for safe client retry | n.a. | Read-only (no write path, adapter.py:22-120). |
| T10 Rollback that also resets cached object state | n.a. | Read-only (no write path, adapter.py:22-120). |
| T11 Write-batch size limits (max quads / characters per update) with ordering … | n.a. | Read-only (no write path, adapter.py:22-120). |
| E1 Transactional outbox / publish-after-commit: events written in the same … | n.a. | Read-only; emits no changes. |
| E2 RDF Patch as the delta wire format (`id` / `prev`, TX / TC) | n.a. | Read-only; emits no changes. |
| E3 Head-moved notification followed by a delta pull | n.a. | Read-only; emits no changes. |
| E4 Authorised, policy-filtered change feeds: subscribers see only facts they … | n.a. | Read-only; no change feed. |
| E5 Ordered, gap-detectable sequence (sequence id, `t`, previous hash) so … | n.a. | Read-only; emits no changes. |
| E6 Delta-only virtual graphs: writes routed to subscribers but never stored | n.a. | Read-only; emits no changes. |
| E7 Call-id trail / loop prevention for event-triggered writes | n.a. | Read-only; emits no changes. |
| E8 Coalesced change notifications (batched per entity and property) | n.a. | Read-only; emits no changes. |
| E9 Standard notification channels (Solid Notifications over WebSocket / Webhook … | n.a. | Read-only; emits no changes. |
| U1 Generated typed client SDK from the service contract (TS types, fetch … | partial | Indirect: the FastAPI OpenAPI output can feed orval or hey-api. Nothing is generated by rdfproxy. |
| U2 Server-state cache keyed by IRI with invalidation and optimistic updates | absent | Not in `rdfproxy/` (indicator grep: 0 relevant hits; GitNexus: no such symbol). |
| U3 Push-to-cache bridge: server events patch the client cache | absent | Not in `rdfproxy/` (indicator grep: 0 relevant hits; GitNexus: no such symbol). |
| U4 Shape-driven forms: edit / view forms generated at runtime from SHACL or … | absent | Not in `rdfproxy/` (indicator grep: 0 relevant hits; GitNexus: no such symbol). |
| U5 Schema-introspected admin: list / show / edit / create screens derived from … | absent | Not in `rdfproxy/` (indicator grep: 0 relevant hits; GitNexus: no such symbol). |
| U6 Server validation report mapped onto form fields by property path | absent | Not in `rdfproxy/` (indicator grep: 0 relevant hits; GitNexus: no such symbol). |
| U7 Client-side unit of work by graph diff, committed as one minimal patch | absent | Not in `rdfproxy/` (indicator grep: 0 relevant hits; GitNexus: no such symbol). |
| U8 Generated mocks for UI tests from the same contract | absent | Not in `rdfproxy/` (indicator grep: 0 relevant hits; GitNexus: no such symbol). |
| U9 Capability hints: the API states which operations the current user may perform | absent | Not in `rdfproxy/` (indicator grep: 0 relevant hits; GitNexus: no such symbol). |
| U10 Shape-driven search and facet UI compiled to SPARQL | absent | Not in `rdfproxy/` (indicator grep: 0 relevant hits; GitNexus: no such symbol). |
| RAD3 Front-end scaffold generation from the API description | absent | Not in `rdfproxy/` (indicator grep: 0 relevant hits; GitNexus: no such symbol). |
| RAD4 Tiered exposure: read-only by default, mutations only for opted-in classes | partial | Read-only by construction; no opt-in mutations exist. |
| X17 Multi-profile rendering from one resource registry (JSON:API, JSON-LD / … | absent | Not in `rdfproxy/` (indicator grep: 0 relevant hits; GitNexus: no such symbol). |
| X18 Atomic multi-operation write with client-local ids, mapped to one unit of work | n.a. | Read-only. |
| X19 Conditional requests / optimistic-concurrency preconditions (ETag, … | n.a. | Read-only. |
| X20 Cursor pagination alongside page / offset | absent | Page and size only (utils/models.py:29-31). |
| X21 RDF patch bodies on resources (N3 Patch, SPARQL Update, JSON merge-patch) | n.a. | Read-only. |
| X22 Bundled generated JSON-LD context: the server's `@context` also ships in the … | absent | Not in `rdfproxy/` (indicator grep: 0 relevant hits; GitNexus: no such symbol). |
| D11 Store error bodies surfaced to the developer | partial | httpx `raise_for_status` surfaces HTTP errors through sparqlx (CHANGELOG 0.8.0). Whether the store's error body reaches the user was not verified. |
| D12 Per-model exception types (`Model.DoesNotExist`) | absent | Not in `rdfproxy/` (indicator grep: 0 relevant hits; GitNexus: no such symbol). |
| D13 Model-aware error messages (model, property, registry context) | present | Errors name the model and the field or binding: `SPARQL binding 'gnd' for model field 'Author.gnd' not in query projection` (item_checker.py:33-35). Also item_checker.py:50-56 and _model_checks.py:31-60. |
| S15 Time travel / as-of queries and per-subject history | absent | Not in `rdfproxy/` (indicator grep: 0 relevant hits; GitNexus: no such symbol). |
| S16 Branching and merging of datasets | absent | Not in `rdfproxy/` (indicator grep: 0 relevant hits; GitNexus: no such symbol). |
| S17 Diff-load / sync: make a graph equal to a document, committing only the … | n.a. | Read-only. |
| S18 Bulk-loader path separate from transactional writes | n.a. | Read-only. |
| S19 Commit metadata (message, author, `t`, digest) on every write | n.a. | Read-only. |

Counts: present 1 · partial 6 · absent 64 · n.a. 31

### (b) Purpose and origin

- **Built for:** exposing SPARQL endpoints as conventional, paginated JSON REST APIs (FastAPI)
  for digital-humanities projects at the Austrian Centre for Digital Humanities (ACDH-OEAW).
  - The examples query Wikidata and GND authors (README).
  - One example is the RELEVEN project's person data (examples/releven_person_example.py).
- **Who:** ACDH-OEAW, principal author Lukas Plank (who also maintains sparqlx). Releases from
  2024 to 2026 under release-please.
- **Design angle:** read-model-first. A curated SELECT plus a Pydantic model gives a typed API
  resource for web front ends that do not want to speak SPARQL. Writes are out of scope by
  design, and identity and mapping to predicates are irrelevant because the query defines the
  shape.
- **Where it could fit:**
  - **L4 read endpoints and the L1 read side (X10 projections)** — the CQRS query side next to
    rdf-persistence's write model.
  - It does not fit L1 writes, L2 transactions, L3 or L6.
  - It fails DEC-5 (7 stars) and is GPL-3.0, so it is ideas only.

### (c) Variant fit

| Variant / approach | Effect | Why |
|---|---|---|
| V1 Portable Python core | supports (read side) | Read-model endpoints over the same SPARQL store. The policy port must cover its generated queries uniformly (AZ2 gap). |
| V2 semantic.works-compatible | neutral | Works behind the authorizing `sparql-parser` with a fixed identity only. Its `Page` JSON is not the JSON:API dialect the Ember frontends expect (X16 absent). |
| V3 Fluree | partially blocks | Standard SELECT works against Fluree's SPARQL endpoint. But Fluree's store-native policies need the *end-user* identity per request, and rdfproxy fixes credentials at adapter construction (adapter.py:44-53; AZ19 absent). Building one adapter per request is the workaround. |
| V4 GraphDB | partially blocks | Same as V3 for per-user fine-grained access control (FGAC). Read-only, so it never touches GraphDB transactions. |
| V5 Graph-direct reads (CQRS) | supports strongly | This is exactly its pattern: a read-only, query-defined projection API. The pattern applies whether the target is a policy-filtered read endpoint or a replica, as long as the proxy enforces policy. |
| A Runtime mapper | complements | Read models are hand-written next to the runtime mapper's write model. |
| B Generated mapper and routes | supports with G14 | Read-model queries and grouping keys generated from LinkML would remove the hand-written SELECTs (absent today). |
| C Generic service | neutral | rdfproxy needs a hand-written query per model. A generic service would have to generate those queries itself. |

### (d) Corrections to the integrated docs

1. **index.adoc:147, "rdfproxy's policy hook would leak totals".** Correct but incomplete.
   - The stub also misses the single-item query (`_ItemQueryConstructor`, constructor.py:28-94,
     no hook).
   - For grouped models it filters only the paging subquery, not the outer query that loads
     group members (constructor.py:188-202). Totals, item lookups *and* nested group rows would
     leak.
2. **catalogue.adoc (sparqlx row), "An async httpx SPARQL client with streaming and batched
   queries".** Incomplete in ways that matter for the reuse decision.
   - It offers **both sync and async** APIs and **SPARQL Update** as well as Query.
   - It accepts an **rdflib `Graph`** target.
   - It is **GPL-3.0** (GitHub API, 2026-11-03).
   - Note from my round 2: about 6 stars, one maintainer, last push 2026-10-29.
   - The licence is the decisive fact and should appear in the row.
3. **libraries/rdfproxy.adoc:12, "4 contributors".** My shallow clone shows one author, so I
   cannot confirm or refute this. The desk-scan figure presumably came from the GitHub API and
   is left as is.

### (e) Proposed new features (round 4)

- **AZ30 Policy-consistent totals and nesting.** A conformance test, not just a design rule: for
  every generated query family (page items, count, item, outer and sub queries), assert that a
  policy-restricted caller gets the same totals and nested rows as a query run directly on the
  restricted dataset. This turns AZ2 into a checkable property. Seen as a gap in rdfproxy:
  constructor.py:151-168, 188-202, 229-231.

## Round 5

### (a) v4 cross-check

The table below checks every "v4 features" row of `feature-taxonomy.adoc` (77 ids).

How absences were confirmed:
- A grep over the library source for migration, opentelemetry/otel, traceparent, redact,
  "did you mean", conformsTo, versionIRI and assert_type/reveal_type (0 hits in all three
  libraries), plus the round-4 indicator set.
- The round-1 GitNexus symbol and process lists.

| Id Feature | Status | Evidence |
|---|---|---|
| B1 Aggregate declaration in the model: root classes and owned slots, from … | absent | No aggregate concept; the nesting is query-defined. |
| B2 Boundary validation at generation time: single owner, no owned cycles, no … | absent | — |
| B3 Whole-aggregate load in one query (root plus owned closure); no lazy loading … | partial | One flat SELECT loads the root plus nested models, and they are assembled client-side (adapter.py:93-101; mapper.py:189-226). The "boundary" is whatever the user's query joins. |
| B4 Whole-aggregate save that replaces the owned subtree, minimised by snapshot … | n.a. | Read-only adapter (adapter.py:22-120); no write, migration or identity path. |
| B5 Typed cross-aggregate references (`Ref[T]` holding an IRI), resolved … | absent | — |
| B6 Aggregates-per-commit policy (strict, warn, allow) | n.a. | Read-only adapter (adapter.py:22-120); no write, migration or identity path. |
| B7 Single conjunctive guarded operation: all version guards in one WHERE with … | n.a. | Read-only adapter (adapter.py:22-120); no write, migration or identity path. |
| B8 Inspectable, backend-neutral change-set: a pure value, unit-testable without … | n.a. | Read-only adapter (adapter.py:22-120); no write, migration or identity path. |
| B9 Domain events collected on aggregates, written to the outbox in the same … | n.a. | Read-only adapter (adapter.py:22-120); no write, migration or identity path. |
| B10 Aggregate storage strategy: shared graph or graph per aggregate (GSP PUT, … | n.a. | Read-only adapter (adapter.py:22-120); no write, migration or identity path. |
| B11 Aggregate version kept by the mapper, not the domain class, and exposed as … | n.a. | Read-only adapter (adapter.py:22-120); no write, migration or identity path. |
| B12 After-commit hooks (`on_commit`) | n.a. | Read-only adapter (adapter.py:22-120); no write, migration or identity path. |
| B13 Boundary-aware delete: cascade inside the boundary; inbound references from … | n.a. | Read-only adapter (adapter.py:22-120); no write, migration or identity path. |
| B14 Bounded-context partitioning: one schema module per context with its own … | absent | — |
| B15 No-autoflush contract: warn when a query runs with pending changes; … | n.a. | Read-only adapter (adapter.py:22-120); no write, migration or identity path. |
| B16 Process manager / saga support: saga state as an aggregate, triggered by … | n.a. | Read-only adapter (adapter.py:22-120); no write, migration or identity path. |
| PG1 Query AST with pluggable renderers; SPARQL is one renderer — refines Q7 | absent | Rewriting is regex-based (sparql_utils.py:14-81); there is no AST or renderers. |
| PG2 LPG projection configuration per LinkML class and slot: node or … | n.a. | Read-only adapter (adapter.py:22-120); no write, migration or identity path. |
| PG3 Edge-property (qualified relationship) mapping: a LinkML class marked as a … | n.a. | Read-only adapter (adapter.py:22-120); no write, migration or identity path. |
| PG4 Scope abstraction for partitions: named graph ↔ database, label or … | absent | Not in the library source (indicator grep for migration/otel/traceparent/redact/did-you-mean/conformsTo/assert_type and the round-4 terms: 0 hits; GitNexus: no such symbol). |
| EV1 Migration runner: ordered, immutable `.sparql` / `.ttl` files, … | n.a. | Read-only adapter (adapter.py:22-120); no write, migration or identity path. |
| EV2 Migration integrity: checksum per applied file, run lock, log written in the … | n.a. | Read-only adapter (adapter.py:22-120); no write, migration or identity path. |
| EV3 Schema diff of two LinkML versions → generated SPARQL Update skeletons … | n.a. | Read-only adapter (adapter.py:22-120); no write, migration or identity path. |
| EV4 Down migrations, written or derived by inverting a mapping specification | n.a. | Read-only adapter (adapter.py:22-120); no write, migration or identity path. |
| EV5 Object-level data transformation between schema versions (split, merge, … | n.a. | Read-only adapter (adapter.py:22-120); no write, migration or identity path. |
| EV6 Post-migration validation gate: data must conform to the new version's … | absent | — |
| EV7 Schema version stamped in the data and checked at startup; refuse to run on … | absent | — |
| EV8 Staged bulk load: temporary graph plus `ADD` / `MOVE`, adaptive batch size | n.a. | Read-only adapter (adapter.py:22-120); no write, migration or identity path. |
| EV9 Migration rehearsal on a branch or snapshot before promotion | n.a. | Read-only adapter (adapter.py:22-120); no write, migration or identity path. |
| AZ30 Graph-aware enforcement: class-targeted policies resolve classes from the … | n.a. | A store- or gateway-side policy feature; rdfproxy is a client. |
| AZ31 Effective-ACL inheritance down a container or graph hierarchy: the nearest … | n.a. | A store- or gateway-side policy feature; rdfproxy is a client. |
| AZ32 Predicate-coverage fast path: skip per-triple policy evaluation for … | n.a. | A store- or gateway-side policy feature; rdfproxy is a client. |
| AZ33 Existence-hiding denial: out-of-scope resources answer 404, not 403, and … | absent | `NoResultsFound` is raised for absent and hidden items alike (item_checker.py:54-56); `Page.total` is always returned (utils/models.py:12-19). There is no policy notion. |
| AZ34 Lagging policy configuration: policy changes take effect from the next … | n.a. | A store- or gateway-side policy feature; rdfproxy is a client. |
| AZ35 Policy-filter equivalence test: for every generated query family (item, … | absent | This is where the gap was seen: count, item and grouped outer queries bypass the filter stub (constructor.py:151-168, 28-94, 188-202, 229-231). |
| AZ36 Edge sanitisation of internal security headers: the gateway removes … | n.a. | A store- or gateway-side policy feature; rdfproxy is a client. |
| G28 Contract hygiene: generator bookkeeping (`linkml_meta`, `x-linkml-*`) … | absent | Not in the library source (indicator grep for migration/otel/traceparent/redact/did-you-mean/conformsTo/assert_type and the round-4 terms: 0 hits; GitNexus: no such symbol). |
| G29 Importer lossiness report: constructs dropped or degraded on import are listed | absent | Not in the library source (indicator grep for migration/otel/traceparent/redact/did-you-mean/conformsTo/assert_type and the round-4 terms: 0 hits; GitNexus: no such symbol). |
| G30 Cross-path equivalence gate: shapes from two generation paths (model2owl … | absent | Not in the library source (indicator grep for migration/otel/traceparent/redact/did-you-mean/conformsTo/assert_type and the round-4 terms: 0 hits; GitNexus: no such symbol). |
| G31 Toolchain prerequisites declared and checked (e.g. a Java runtime for … | absent | Not in the library source (indicator grep for migration/otel/traceparent/redact/did-you-mean/conformsTo/assert_type and the round-4 terms: 0 hits; GitNexus: no such symbol). |
| G32 Reasoner profile choice for the gate (DL consistency or a cheaper EL / RL … | absent | Not in the library source (indicator grep for migration/otel/traceparent/redact/did-you-mean/conformsTo/assert_type and the round-4 terms: 0 hits; GitNexus: no such symbol). |
| G33 Generated-metadata completeness check: every mapped class and slot carries … | absent | Not in the library source (indicator grep for migration/otel/traceparent/redact/did-you-mean/conformsTo/assert_type and the round-4 terms: 0 hits; GitNexus: no such symbol). |
| G34 Conformance link: data carries `dcterms:conformsTo` to its shape, which then … | absent | Not in the library source (indicator grep for migration/otel/traceparent/redact/did-you-mean/conformsTo/assert_type and the round-4 terms: 0 hits; GitNexus: no such symbol). |
| G35 Generated typed field metamodel for queries (`Person_.name`), with RDF … | absent | Not in the library source (indicator grep for migration/otel/traceparent/redact/did-you-mean/conformsTo/assert_type and the round-4 terms: 0 hits; GitNexus: no such symbol). |
| G36 Generated typed filter and input types per class (`TypedDict`) for finders … | absent | Not in the library source (indicator grep for migration/otel/traceparent/redact/did-you-mean/conformsTo/assert_type and the round-4 terms: 0 hits; GitNexus: no such symbol). |
| T12 Read-tracked optimistic commit: blind writes re-base on a moved head; … | n.a. | Read-only adapter (adapter.py:22-120); no write, migration or identity path. |
| T13 Read-only mode guard: the service refuses updates at the protocol boundary … | present | `check_query` rejects every non-SELECT query when the adapter is constructed (`UnsupportedQueryException("Only SELECT queries are applicable.")`, query_checker.py:12-21), so the adapter cannot issue Update. |
| T14 Cross-store unit of work: one session over several stores, flushed per … | n.a. | Read-only adapter (adapter.py:22-120); no write, migration or identity path. |
| S20 Per-named-graph store configuration (policy defaults, SHACL, reasoning, … | n.a. | Read-only adapter (adapter.py:22-120); no write, migration or identity path. |
| S21 Named graphs mirrored to version control (graph → file, best-effort commit … | n.a. | Read-only adapter (adapter.py:22-120); no write, migration or identity path. |
| S22 Store-side shape and uniqueness enforcement in the write transaction, … | n.a. | Read-only adapter (adapter.py:22-120); no write, migration or identity path. |
| S23 Ops admin port per store adapter: backup, restore, compact, statistics — … | absent | — |
| X23 Strict JSON-LD processing: client and server fail when a context drops or … | n.a. | Read-only adapter (adapter.py:22-120); no write, migration or identity path. |
| X24 MCP projection of the resource registry: the same resources and operations … | absent | — |
| E10 Subscription channel options: rate limit, state on connect, validity window, … | n.a. | Read-only adapter (adapter.py:22-120); no write, migration or identity path. |
| I7 Reversible IRI minting: the id can be recovered from the IRI; full IRIs pass … | n.a. | Read-only adapter (adapter.py:22-120); no write, migration or identity path. |
| I8 Deferred IRI minting: temporary IRIs on creation, permanent IRIs minted at flush | n.a. | Read-only adapter (adapter.py:22-120); no write, migration or identity path. |
| P20 Reference-aware flush ordering: the unit of work sorts writes by … | n.a. | Read-only adapter (adapter.py:22-120); no write, migration or identity path. |
| U11 Framework-neutral UI components (Web Components): one widget serves React, … | absent | Not in the library source (indicator grep for migration/otel/traceparent/redact/did-you-mean/conformsTo/assert_type and the round-4 terms: 0 hits; GitNexus: no such symbol). |
| U12 Desktop or notebook ontology instance editor generated from the ontology … | absent | Not in the library source (indicator grep for migration/otel/traceparent/redact/did-you-mean/conformsTo/assert_type and the round-4 terms: 0 hits; GitNexus: no such symbol). |
| U13 Bulk operations sent as one batch with per-item results, not N single … | n.a. | Read-only adapter (adapter.py:22-120); no write, migration or identity path. |
| D14 Stale-write warning when an append-only write may leave duplicate values … | n.a. | Read-only adapter (adapter.py:22-120); no write, migration or identity path. |
| D15 Parameter redaction in query logs (pluggable hook) — complements S14 | absent | DEBUG logs include the full generated query with key values (constructor.py:57-66, 136-148). No redaction hook. |
| D16 Formal model of the HTTP and access contract, checked in CI against the … | absent | Not in the library source (indicator grep for migration/otel/traceparent/redact/did-you-mean/conformsTo/assert_type and the round-4 terms: 0 hits; GitNexus: no such symbol). |
| D17 Inspectable compiled query (`to_sparql()` with bound values) and query … | partial | Generated queries are logged as structured JSON at DEBUG (constructor.py:57-66, 136-148; utils/structlog.py). There is no public `to_sparql()`: the constructors are private (`_PageQueryConstructor`, `_ItemQueryConstructor`). |
| D18 Explicit-loading sentinel: not loaded, absent and empty are distinct; never … | absent | Not in the library source (indicator grep for migration/otel/traceparent/redact/did-you-mean/conformsTo/assert_type and the round-4 terms: 0 hits; GitNexus: no such symbol). |
| D19 Test kit: pytest plugin with an in-memory store per test, a LinkML-driven … | absent | Not in the library source (indicator grep for migration/otel/traceparent/redact/did-you-mean/conformsTo/assert_type and the round-4 terms: 0 hits; GitNexus: no such symbol). |
| D20 Shipped real-store test fixtures (testcontainers wrappers for Oxigraph, … | partial | Testcontainers fixtures for Oxigraph and Fuseki exist in tests/conftest.py:59-112 but are not shipped as a package. |
| D21 Tested documentation: every docs example is a file executed in CI | absent | CI excludes the examples group (`uv sync --no-group examples`, .github/workflows/tests.yml:24); the examples are not executed. |
| D22 CURIEs everywhere: schema prefixes accepted in every id argument, … | absent | Not in the library source (indicator grep for migration/otel/traceparent/redact/did-you-mean/conformsTo/assert_type and the round-4 terms: 0 hits; GitNexus: no such symbol). |
| D23 "Did you mean" suggestions for unknown slots, classes and prefixes | partial | Errors list the valid alternatives (`Applicable values: …`, utils/utils.py:82-84; `applicable_fields_message`, _model_checks.py:58-60). There is no fuzzy "did you mean". |
| D24 Stable error codes with one documentation page per code | absent | Not in the library source (indicator grep for migration/otel/traceparent/redact/did-you-mean/conformsTo/assert_type and the round-4 terms: 0 hits; GitNexus: no such symbol). |
| D25 Deterministic ordering of multi-valued properties on load (stable diffs, … | partial | Deterministic ORDER BY, defaulting to the first projected variable or the group key (constructor.py:237-249). `list[str]` values keep row order via `dict.fromkeys` (mapper.py:197). |
| D26 Typing regression tests (`assert_type` modules checked in CI) | absent | Not in the library source (indicator grep for migration/otel/traceparent/redact/did-you-mean/conformsTo/assert_type and the round-4 terms: 0 hits; GitNexus: no such symbol). |
| D27 Fault-injection tests for store failures (connection dropped mid unit of work) | absent | Not in the library source (indicator grep for migration/otel/traceparent/redact/did-you-mean/conformsTo/assert_type and the round-4 terms: 0 hits; GitNexus: no such symbol). |
| D28 API contract fuzzing from the generated OpenAPI | absent | Not in the library source (indicator grep for migration/otel/traceparent/redact/did-you-mean/conformsTo/assert_type and the round-4 terms: 0 hits; GitNexus: no such symbol). |
| D29 Store-port observability: OpenTelemetry spans with query kind, fingerprint, … | absent | Not in the library source (indicator grep for migration/otel/traceparent/redact/did-you-mean/conformsTo/assert_type and the round-4 terms: 0 hits; GitNexus: no such symbol). |

Counts (77 v4 features): present 1 · partial 5 · absent 34 · n.a. 37

### (b) Page review (`libraries/rdfproxy.adoc`)

1. **Line 12**, "release-please releases 0.8.0 → 0.11.0 over 2025-07 … 2026-08".
   - This understates the history. CHANGELOG.md lists **13 releases, from 0.1.0 (2024-10-23) to
     0.11.0 (2026-08-05)**.
   - **Fix:** "13 releases, 0.1.0 (2024-10) → 0.11.0 (2026-08), via release-please".
2. **Line 82**, "`select … where` replacement and injection before the last `}` break on nested
   selects, comments, `FROM` clauses and prefixes."
   - This overstates nested selects: the regex replaces the first, outer SELECT clause, and no
     breakage was shown for nested selects.
   - It also misses the concrete, verifiable defects:
     - The SELECT-clause pattern `select\s+.*?(?=\s+where)` (sparql_utils.py:16-17) swallows a
       `FROM <g>` clause in the **count** query, so totals are computed over a different dataset
       than the items.
     - A query that omits the optional `WHERE` keyword is rejected
       (`QueryConstructionException`, sparql_utils.py:20-21).
     - Prefixes are stripped from grouped subqueries (sparql_utils.py:36-39).
   - **Fix:** "Regex rewriting can break valid queries: a `FROM` clause is dropped from the count
     query; a query without the optional `WHERE` keyword is rejected; prefixes are stripped from
     grouped subqueries; a trailing comment containing `}` misplaces injected filters."
3. **Line 153**, "Round 4 proposes a policy-filter equivalence test …".
   - This is now merged into taxonomy v4 as **AZ35**.
   - **Fix:** "(merged as AZ35)".

New evidence for the page:
- **T13 present.** `check_query` refuses any non-SELECT query when the adapter is constructed
  (query_checker.py:12-21). The adapter is a structural read-only guard.
- **D21 absent.** CI installs without the examples group (`--no-group examples`,
  .github/workflows/tests.yml:24), so the README and examples are not executed.

The "4 contributors" (line 12) cannot be verified from my shallow clone; it is left to the desk
scan.

### (c) Final verdict and what to remember

**Verdict: ideas.** GPL-3.0, below DEC-5, pandas and regex rewriting rule out dependency.

Three things a system architect must remember:
1. **The read side (X10/Q10) is the transferable idea.** Query-defined Pydantic projections with
   group-aware pagination belong in a cosmic-python "views" module beside the write model. In
   approach B the SELECTs and grouping keys should be generated from LinkML (G14), not
   hand-written.
2. **Policy must be injected into *every* generated query or it leaks.** rdfproxy's filter seam
   misses the count query, the item query and grouped outer queries. A FROM clause is even
   dropped from its count query. Any rdf-persistence PEP needs the AZ35 equivalence test across
   all query families.
3. **Identity must flow per request, not per adapter.** Credentials fixed at construction work
   behind a static-identity proxy (V2) but block per-user store policies (V3 Fluree, V4 GraphDB).
   The store port must take the caller's identity on every call (AZ19).

### (d) Purpose and origin and variant fit

Already given in Round 4 (b) and (c).

### (e) New features

None. The defects above are covered by AZ2, AZ35, Q7 and D21.
