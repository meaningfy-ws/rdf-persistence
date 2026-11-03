# Prez

- **Repo:** https://github.com/RDFLib/prez (clone `/home/lps/work/repos/prez`, origin RDFLib/prez; the GitHub page says active development has moved to `kurrawong/prez`, yet this clone has commits up to 2026-10-06)
- **Commit analysed:** `0366b22` (main, 2026-10-06), version 4.7.5 (`pyproject.toml`)
- **Licence:** BSD-3-Clause (`LICENSE`, "Copyright (c) 2022, RDFLib Team")
- **Size:** `prez/` 62 Python files, 17,703 LOC; `tests/` 19,876 LOC, 406 `def test_` functions; 47 `.ttl`/`.rq` reference-data files (profiles, endpoints, prefixes)
- **GitNexus index:** `prez`, 431 files, 3,236 symbols, 6,823 edges, 100 clusters, 255 processes (indexed at `0366b22`)
- **Docs read:** `README.md`, `docs/custom_endpoints.md`, `docs/` listing (4,385 lines of design notes and feature docs), `prez/reference_data/profiles/prez_default_profiles.ttl`, https://github.com/RDFLib/prez. No published docs site exists; the README is the only user documentation.

## Summary

Prez is a FastAPI application, not a library. It publishes a **read-only** Linked Data HTTP API over a knowledge graph. *Profiles* (RDF/SHACL descriptions of which triples to return for a class) and *Content Negotiation by Profile* (W3C dx-connegp) decide what each request returns. It generates SPARQL CONSTRUCT queries from SHACL node shapes using a typed SPARQL grammar AST (`sparql-grammar`, a pydantic model of the SPARQL grammar). Three interchangeable backends sit behind one `Repo` port: a remote SPARQL endpoint, in-memory or on-disk pyoxigraph, and oxrdflib. It does **not** support writes. It is a strong benchmark for the HTTP, content-negotiation and query-generation side of rdf-persistence and is irrelevant to the ORM, session and transaction side.

## Architecture (from GitNexus)

The GitNexus community labels are generic ("Prez", "Tests", "Renderers"), so the layering below comes from the processes and symbol contexts.

- **Entrypoints:** FastAPI routers in `prez/routers/` (`base_router.py`, `ogc_features_router.py`, `cql_router.py`, `sparql.py`, `identifier.py`, `management.py`). Routes can also be generated at runtime from RDF endpoint definitions (`custom_endpoints.py:206`, `router.add_api_route`).
- **Services:** `prez/services/` contains `listings.py:388` `listing_function`, `objects.py:46` `object_function`, `connegp_service.py:97` `NegotiatedPMTs` and the `query_generation/` package (19 modules: `umbrella.py`, `shacl.py`, `cql.py`, `facet.py`, `count.py`, `search_*`).
- **Repository port:** `prez/repositories/base.py:16-80` `Repo(ABC)`. GitNexus `context(Repo)` shows exactly four subclasses: `OxrdflibRepo`, `PyoxigraphRepo`, `RemoteSparqlRepo`, and the test double `FakeLuceneListingRepo` (`tests/test_cql_lucene.py`). It has five methods, all for reading: `rdf_query_to_rdflib_graph`, `rdf_query_to_oxigraph_store`, `tabular_query_to_table`, `send_queries` (an `asyncio.gather` fan-out), and `sparql` (passthrough).
- **Composition root:** `prez/dependencies.py:124-148` `get_data_repo` uses FastAPI `Depends` to pick the backend from `settings.sparql_repo_type` (`config.py:15-23`, `SparqlRepoType` = `remote | pyoxigraph_persistent | pyoxigraph_memory | oxrdflib`). A separate *system repo* (pyoxigraph) holds profiles and endpoint definitions.
- **Renderers:** `prez/renderers/renderer.py` serialises with rdflib to Turtle, N-Triples, RDF/XML and JSON-LD, plus "annotated" (`+anot`) variants that add labels and descriptions, and GeoJSON (`rdf2geojson`).
- **Representative processes (GitNexus):** `proc_42_listings`, `Listings → get_data_repo → Get_pyoxi_persistent_store`, and `proc_39_listings_post` (the same flow for POST/CQL bodies).

## Implementation principles

- **Mapping:** there are no domain classes. Data stays as RDF graphs from end to end, rdflib `Graph` or pyoxigraph `Store` (`base.py:36-75`). "Mapping" is the choice of which triples to CONSTRUCT, driven by profile NodeShapes (`shacl.py:135` `NodeShape`, `:184` `to_grammar`, `:256` `PropertyShape` with `minCount`/`maxCount`/`sh:in` and property-path parsing at `:403`).
- **Query generation:** `umbrella.py:64` `PrezQueryConstructor(ConstructQuery)` builds `CONSTRUCT { profile triples } WHERE { { SELECT ?focus_node ... ORDER BY ... LIMIT ... OFFSET } profile patterns }`. It composes typed grammar objects (`TriplesSameSubjectPath`, `GraphPatternNotTriples`, `Var`, `IRI` from `sparql_grammar`), not strings. CQL2 JSON filters compile to SPARQL in `query_generation/cql.py`.
- **Pagination:** `models/query_params.py:131-260` `ListingQueryParams` accepts `page`, `limit` (1..10000) and `offset`/`startindex`, rejects conflicting combinations with a 400, and caps counts with `listing_count_limit`, returning ">N" (`docs/result_counting.md`).
- **Content negotiation:** `connegp_service.py:97` `NegotiatedPMTs` reads `_profile`/`_mediatype` query parameters first and the `Accept`/`Accept-Profile` headers second (`:219-230`). It resolves the best profile with a SPARQL SELECT over the system graph that ranks by class distance through `rdfs:subClassOf*` (`:358-441`), and emits `Link` alternate-profile headers (`:304`).
- **Identity:** resources are addressed by CURIE path segments (`curie_functions.py`), and IRIs come from the data. There is no minting.
- **Sessions and transactions:** none. The repos are stateless per request.
- **Writes:** none. `RemoteSparqlRepo.sparql` (`remote_sparql.py:272-336`) forwards only `query=`. The `/sparql` router (`routers/sparql.py:24-35`) declares a `query` Form field, commented "Pydantic validation prevents update queries (the Form would need to be 'update')". `settings` documents `sparql_endpoint` as "Read-only SPARQL endpoint" (`config.py:27`). The POST routes in `base_router.py:110-239` take CQL search bodies, not mutations.

## Patterns catalogue

| Pattern | Where |
|---|---|
| Repository / port-and-adapters (read side) | `repositories/base.py:16` `Repo` plus 3 adapters |
| Dependency injection / composition root | `dependencies.py:124` `get_data_repo` (FastAPI `Depends`) |
| Query Object (typed SPARQL AST) | `services/query_generation/umbrella.py:64` `PrezQueryConstructor` on `sparql-grammar` |
| Specification-as-data (profiles as SHACL) | `reference_data/profiles/*.ttl`, `services/query_generation/shacl.py` |
| Content negotiation by profile | `services/connegp_service.py:97` |
| Configuration-driven routing (endpoints defined in RDF) | `routers/custom_endpoints.py:206`, `docs/custom_endpoints.md` |
| Test double for a port | `tests/test_cql_lucene.py` `FakeLuceneListingRepo(Repo)` |
| Parallel fan-out of queries | `base.py:36` `send_queries`, `asyncio.gather` |

## Docs vs code

- "data-configurable Linked Data API … profiles … Content Negotiation by Profile" (README:8): **confirmed** (`connegp_service.py`, profiles TTL).
- `SPARQL_REPO_TYPE` with remote / pyoxigraph / oxrdflib: **confirmed** (`config.py:15-23`, `dependencies.py:124-148`).
- GitHub page: "if the SPARQL endpoint is enabled … it accepts POST requests, so users … could update the store": **not backed by code**. The POST handler accepts only a `query` form field and forwards `query=` (`routers/sparql.py:24-35`, `remote_sparql.py:295`). A SPARQL Update cannot pass through Prez.
- "Prez does not make any updates to the remote repository": **confirmed**. No `Repo` method writes (GitNexus `context(Repo)`).
- JSON-LD output: **confirmed** (`MediaType.json_ld`, `connegp_service.py:75`; rdflib `serialize(format="json-ld")`, `renderer.py:754`).

## Scores C1–C8

| # | Score | Justification | Evidence |
|---|---|---|---|
| C1 Feature coverage | 1 | Read, query and pagination only. No create/update/delete, relations as objects, transactions or identity map. JSON-LD out, no JSON-LD in. | `repositories/base.py:16-80`; `routers/sparql.py:24-35` |
| C2 Design patterns | 3 | Clean Repo port with injected adapters and a typed Query Object, but persistence patterns (UoW, Data Mapper, Identity Map) do not apply | `base.py`, `dependencies.py:124`, `umbrella.py:64` |
| C3 Developer friendliness | 2 | Configured through RDF and env vars, not a programming API. README only, no published docs site. Good OpenAPI from FastAPI | README; `docs/*.md` are design notes |
| C4 Ease of adoption | 2 | Heavy app: 16 runtime deps, including two git-pinned ones (`sparql-grammar`, `rdf2geojson`). Works with in-memory and remote stores out of the box | `pyproject.toml:21-40` |
| C5 Reuse of foundations | 4 | rdflib, pyoxigraph, oxrdflib, pydantic, httpx, pyld. Writes its own HTTP SPARQL client instead of using SPARQLWrapper (deliberate, for async) | `pyproject.toml`; `remote_sparql.py:60` |
| C6 Data-centric / DDD | 2 | Strongly data-centric (SHACL profiles drive everything) but has no domain objects. Its service layer is cosmic-python-shaped (routers → services → repos) | `services/`, `repositories/` |
| C7 SPARQL 1.1 portability | 4 | Plain SPARQL 1.1 Protocol queries to any endpoint. Optional Jena-specific search (Lucene/FTS) is isolated in its own modules. Query side only, no Update or GSP | `remote_sparql.py:70`; `search_jena_lucene.py`, `search_fuseki_fts.py` |
| C8 Health | 4 | 406 tests, CI (`pr.yaml`, `release.yaml`), recent commits (2026-10), BSD-3, three named authors. The shallow clone hides contributor history | `.github/workflows/`; `pyproject.toml:4` |

## Feature inventory

| Id | Status | Evidence |
|---|---|---|
| M1 | absent | No domain classes; data stays as graphs |
| M2 | present (as profiles) | SHACL NodeShapes in `reference_data/profiles/*.ttl` drive the response shape |
| M3 | partial | Queries (not code) are generated from SHACL (`shacl.py:184` `to_grammar`); OpenAPI generated from routes |
| M4 | partial | Profile selection honours `rdfs:subClassOf*` with constraint distance (`connegp_service.py:358-441`) |
| M5 | absent | No validation on load; the README points to external SHACL validators |
| I1 | absent | IRIs come from the data |
| I2 | partial | Blank-node depth through `BNodeDepth` paths (`shacl.py:459`) |
| I3 | absent | — |
| R1 | partial | Multi-valued properties come back as graph triples, without set/list semantics |
| R2 | partial | Parent→child endpoint hierarchies are defined in RDF (`docs/custom_endpoints.md`) |
| R3 | partial | Depth controlled by profile paths and `BNodeDepth` |
| R4 | absent | — |
| L1 | present | Passed through as RDF terms (rdflib/pyoxigraph) |
| L2 | present | Passed through; language-aware label annotation in `services/annotations.py` |
| P1 | partial | Read only |
| P2–P5 | absent | — |
| P6 | partial | Separate system store for configuration; no named-graph selection in query generation |
| P7 | partial | Streaming SPARQL passthrough (`remote_sparql.py:38` `_TimedSparqlStream`) |
| Q1 | present | `/object?uri=`, CURIE routes (`routers/identifier.py`) |
| Q2 | present | CQL2 JSON → SPARQL (`query_generation/cql.py`), facets (`facet.py`) |
| Q3 | partial | `/sparql` passthrough returns raw RDF, not mapped objects |
| Q4 | present | page/limit/offset, ordering, capped counts (`query_params.py:131-260`, `count.py`) |
| Q5 | present | SHACL property paths → SPARQL paths (`shacl.py:403`) |
| S1 | present | pyoxigraph memory/persistent, oxrdflib (`config.py:15-23`) |
| S2 | partial | Query only (`remote_sparql.py`) |
| S3 | absent | — |
| S4 | present | `Repo` ABC plus DI selector |
| X1 | present | JSON-LD out (`MediaType.json_ld`), annotated JSON-LD |
| X2 | present | Turtle, N3, N-Triples, RDF/XML (`connegp_service.py:71-90`) |
| X3 | present | REST / OGC API Features / OGC Records-style API (`ogc_features_router.py`) |
| X4 | partial | OpenAPI from FastAPI; OGC "queryables" JSON schema (`services/generate_queryables.py`) |
| X5 | absent | — |
| D1 | partial | Typed Python internally; no typed client API |
| D2 | present | Fully async repos and services |
| D3 | present | FastAPI |
| D4 | partial | README plus design notes; no tutorial or reference site |
| D5 | present | Fake Repo subclass; pyoxigraph in-memory test store; testcontainers |
| O1, O2 | absent | — |
| A1 | absent (noted) | — |

### Proposed new features

- **X6 Content negotiation by profile:** the same resource is served in several shapes or profiles, chosen with `Accept-Profile` or `?_profile` (`connegp_service.py:97`).
- **X7 Annotated representations:** labels and descriptions for referenced IRIs are added to responses for UI consumption (`+anot` media types, `services/annotations.py`).
- **Q6 Typed SPARQL AST builder:** queries are composed as typed grammar objects rather than strings (`sparql-grammar`), which makes them safe to compose and inject into.
- **Q7 Standard filter language:** an external filter language (OGC CQL2 JSON) compiles to SPARQL (`query_generation/cql.py`).
- **Q8 Faceted search and capped counts:** facet counts plus a "count up to N" guard for large stores (`facet.py`, `count.py`).

## JS-friendliness

Good on the read side. It offers a REST API with OpenAPI (FastAPI), JSON-LD and GeoJSON responses, OGC API Features/Records conventions, CQL2 JSON filters and `Link` headers for alternate profiles, and a separate Prez UI (Vue) consumes it. It does not generate TS types and has no write API.

## Reuse verdict for rdf-persistence: **borrow ideas** (do not adopt or depend on it)

Ideas to borrow:
1. **`Repo` port with three adapters** (remote SPARQL / pyoxigraph / oxrdflib) selected in one DI function. This maps directly onto a cosmic-python `AbstractRepository`/`AbstractStore` port. rdf-persistence must add the write half (`update`, GSP).
2. **A typed SPARQL AST** (`sparql-grammar`) instead of string templates for query building. Evaluate it as a dependency or a design reference for Q2.
3. **Profiles as SHACL NodeShapes** that state which triples make up a resource "view". This is the RDF analogue of an aggregate boundary and could define the CONSTRUCT used by `get()` and the triple set that `delete()` must remove.
4. **The CONSTRUCT { … } WHERE { { SELECT ?focus … LIMIT/OFFSET } … } pattern** for paginated object listings (`umbrella.py:64`). LDkit uses the same pattern, which confirms it.
5. **Content negotiation by profile** for the later JSON-LD middleware: the same object served as JSON-LD, Turtle or annotated JSON-LD, chosen by header.
6. **Pagination contract** (`page`/`limit`/`offset`, mutual exclusion, capped count) for the HTTP layer.

## Risks / anti-patterns observed

- It is an application, not a library: the code imports `settings` globals everywhere (`remote_sparql.py:286`), so pieces cannot be reused in isolation.
- Two runtime dependencies are pinned to git revisions (`pyproject.toml:33-34`), which is a supply-chain and packaging risk if we depend on `sparql-grammar` directly.
- Project governance is ambiguous (RDFLib versus Kurrawong forks).
- Search features are tied to particular stores (Jena Lucene/FTS) through config. They are isolated, but they show how store lock-in creeps in.

## Round 2 cross-check (taxonomy v1)

Checked against `docs/modules/ROOT/pages/architecture/soa/feature-taxonomy.adoc` (v1). Prez is read-only, so every write-side feature is absent. That was confirmed in round 1 with GitNexus `context(Repo)`, which found only five query methods. Each "absent" below was also confirmed with a grep over `prez/` (searches for skolem/genid, retry/backoff, hydra, jsonapi, find_by_, owl:imports, infer, readonly and diff found no implementation; the only hits were annotation TTL text).

| Id | Status | Evidence |
|---|---|---|
| M6 | absent | No domain classes; data stays as rdflib/pyoxigraph graphs (`repositories/base.py:36-75`) |
| M7 | absent | No object fields to derive predicates from |
| M8 | absent | JSON-LD is only an output format (`renderers/renderer.py:754`, rdflib serialize); it is not a mapping |
| M9 | absent | — |
| M10 | absent | — |
| M11 | absent | No import path |
| M12 | absent | Class membership via `rdf:type` / `rdfs:subClassOf*` only (`services/connegp_service.py:428`) |
| M13 | absent | Consumes SHACL profiles; emits no shapes or indexes. The OGC queryables JSON (`services/generate_queryables.py`) is an API description, not a constraint |
| M14 | absent | — |
| M15 | absent | — |
| I4 | absent | grep `skolem|genid|well-known` finds only TTL annotation text |
| R5 | absent | `PropertyShape.minCount/maxCount` (`services/query_generation/shacl.py:284-295`) shape queries; they are not enforced |
| R6 | absent | — |
| R7 | absent | — |
| R8 | partial | Endpoint and profile relations can be traversed in either direction (`create_tssp_alt_or_alt_inverse`, `services/query_generation/cql_functions.py:44`); configured, not automatic |
| L3 | absent | Terms pass through untyped (`repositories/pyoxigraph.py:214-223`, a term→JSON-type dict only) |
| P8–P12 | absent | Read-only (`routers/sparql.py:24-35`; GitNexus `context(Repo)`) |
| P13 | partial | Only a per-query timeout parameter (`config.py:78-79`, `repositories/remote_sparql.py:76`); no transactions |
| P14 | absent | Read-only |
| P15 | n.a. | Stateless per-request repos |
| Q6 | partial | Queries are composed from a typed AST (`sparql_grammar`) and Lucene/SPARQL escaping (`services/query_generation/sparql_escaping.py:1`); no prepared-query binding API |
| Q7 | present | `services/query_generation/umbrella.py:64` `PrezQueryConstructor(ConstructQuery)` on `sparql-grammar` |
| Q8 | absent | grep `find_by_` finds nothing |
| Q9 | present | One CONSTRUCT per listing, with the paged inner SELECT plus profile patterns (`umbrella.py:64-90`); parallel fan-out (`base.py:36` `send_queries`) |
| Q10 | present | Pagination over focus nodes (groups) in the inner SELECT, then the full graph per node (`umbrella.py:72-84`) |
| Q11 | partial | `/sparql` passthrough accepts only `query`, so updates are rejected (`routers/sparql.py:29`); no result-integrity checks |
| Q12 | partial | Store-specific Jena Lucene/FTS (`search_jena_lucene.py`, `search_fuseki_fts.py`) plus a portable regex default (`search_default.py`) |
| Q13 | absent | CQL "custom functions" are a fixed list of operators (`cql_functions.py:31-44`); none can be registered |
| Q14 | present | CQL2 JSON → SPARQL (`services/query_generation/cql.py`, `routers/cql_router.py`) |
| Q15 | present | Capped counts ">N" (`services/query_generation/count.py:70-98`); facets (`facet.py`, `reference_data/facet_profiles`) |
| Q16 | absent | — |
| Q17 | partial | Profile and class matching over `rdfs:subClassOf*` with constraint distance (`connegp_service.py:358-441`); listings are by class or endpoint |
| Q18 | partial | Blank-node closure to a configurable depth via `BNodeDepth` paths (`shacl.py:459-461`) |
| S5 | absent | Single `sparql_endpoint`, documented as read-only (`config.py:27`) |
| S6 | partial | aiocache tbox/annotation (label) cache with a purge endpoint (`routers/management.py:73-89`, `services/curie_functions.py:5`); data is not cached |
| S7 | partial | Only a startup health-check retry (`services/app_service.py:77`); no retries on queries |
| S8 | absent | Its own `Repo` ABC (`repositories/base.py:16`), not the rdflib `Store` interface (the oxrdflib adapter wraps an rdflib Graph internally) |
| X6 | absent | grep `jsonapi` finds nothing; it uses an OGC API style instead |
| X7 | present | `services/connegp_service.py:97` `NegotiatedPMTs` (media type plus profile) |
| X8 | absent | grep `hydra` finds no Python code |
| X9 | absent | — |
| X10 | partial | Profiles are read projections over one graph (`reference_data/profiles/*.ttl`); there is no write model to separate from |
| X11 | present | `+anot` media types, `services/annotations.py` |
| X12 | absent | — |
| X13 | partial | `x-request-id` is bound to a ContextVar and logged (`middleware.py:21`, `services/prez_logging.py:38-52`) but not forwarded to the store (`remote_sparql.py:79`, only the `Accept` header) |
| X14 | absent | — |
| D6 | absent | — |
| D7 | absent | Async only |
| D8 | present | In-memory pyoxigraph test store plus a Jena Fuseki testcontainer (`tests/integration/jena-lucene-cql/test_jena_lucene_cql_integration.py:216`) |
| D9 | absent | — |
| RAD1 | partial | Read-only API endpoints generated from RDF endpoint definitions (`routers/custom_endpoints.py:206-218`) |
| RAD2 | present | Declarative routes in RDF (`docs/custom_endpoints.md`; `/configure-endpoints` form, `routers/management.py:193`) |
| O3–O7 | absent | grep `owl:imports|infer` finds only annotation TTL text |
| A2 | present | Data queries do not use GRAPH clauses (no GRAPH patterns in `services/query_generation/`), so they work behind an auth proxy |
| A3 | absent | — |
| O2 (refined) | absent | No reasoner |
| X4 (refined) | partial | FastAPI OpenAPI plus OGC queryables JSON schema; no Pydantic/JSON-Schema export of RDF-term-typed models |
| X5 (refined by X12) | absent | — |
| D2 (refined by D7) | present | Async only |

### Proposed new features (round 2)

- **X15 Standard API profile conformance:** the server implements an external API standard and declares conformance classes (OGC API Features/Records, a `/conformance` endpoint) (`routers/conformance.py:8`, `routers/ogc_features_router.py`).
- **S9 Query observability:** query fingerprints and timing are logged per store call (`remote_sparql.py:21` `_query_fingerprint`, `_TimedSparqlStream`).

### Upstream note

The README (`README.md:6`) says active development moved to `kurrawong/prez`. That repository is **not publicly reachable** on 2026-11-03: `gh api repos/kurrawong/prez` and `git ls-remote https://github.com/kurrawong/prez` both return "not found", and the Kurrawong organisation's public repos list only themes, stacks and `prez-lite`, not `prez` itself. It is probably private. So its stars and last commit could not be measured, and **whether it differs materially, including whether it supports writes, cannot be verified**. The public RDFLib/prez is not archived and not a fork, has 40 stars and 13 forks, and was last pushed 2026-10-06 (`gh api repos/RDFLib/prez`). It is therefore the only analysable upstream and remains the reference for this review.

## Round 3

### (a) v2 cross-check

| Id | Status | Evidence |
|---|---|---|
| M16 | absent | No object model |
| M17 | absent | No mapping classes; profiles are not validated at load (README "Data Validation" points to external SHACL validators) |
| I5 | absent | — |
| I6 | n.a. | No entities |
| P16–P19 | absent | Read-only; local RDF is loaded once at startup (`app.py:138` `load_local_data_to_oxigraph`), with no change detection |
| Q19 | present | Default search uses SPARQL `REGEX` (`services/query_generation/search_default.py:188-227`) |
| Q20 | absent | — |
| S9 | absent | Single data repo (`dependencies.py:124-148`) |
| S10 | absent | — |
| S11 | absent | The pyoxigraph persistent store is opened but not administered; only the tbox cache can be purged (`routers/management.py:73`) |
| S12 | present | `Repo.send_queries` runs RDF and tabular queries in one call through `asyncio.gather` (`repositories/base.py:36-75`) |
| S13 | present | Streamed SPARQL passthrough (`repositories/remote_sparql.py:38` `_TimedSparqlStream`, `:312` `send(..., stream=True)`) |
| S14 | present | Query fingerprint and timing in structured logs (`remote_sparql.py:21`, `:86-100`) |
| X15 | absent | — |
| X16 | present | `/conformance` (`routers/conformance.py:8`), OGC API Features router |
| D10 | absent | — |

### (b) Developer experience

- **Configure-and-serve path (README.md:27-50, :218-226):** about 4 commands: `git clone …`, `poetry install`, set `SPARQL_ENDPOINT=…` (or `SPARQL_REPO_TYPE=pyoxigraph_memory` plus `LOCAL_RDF_DIR`), then `poetry run python main.py`. Alternatively `docker compose up` in `demo/` (Prez, Prez UI and Fuseki), or `ghcr.io/rdflib/prez` with semver tags (README:234-246). There are no code lines: Prez is customised entirely through env vars and RDF.
- **Concepts to learn:** profiles (prof/altr-ext/SHACL), connegp (`_profile`, `_mediatype`, `Accept-Profile`), endpoint definitions (`ont:ListingEndpoint`/`ObjectEndpoint` hierarchies in TriG), CURIEs and the CURIE separator, the system graph versus data graph split, the `+anot` media types, CQL2 queryables and facets, and about 60 `Settings` fields (`config.py`, 64 class/field lines). That is a steep curve for an app developer and natural for a linked-data publisher.
- **Typing/IDE:** none applies to users; customisation happens in Turtle. Developers extending Prez get typed pydantic models and FastAPI OpenAPI.
- **Real errors:** `No classes found for {uri}. Prez can only display information for instances of classes` (`exceptions/model_exceptions.py:13`); `Mutually exclusive pagination parameters provided: page, offset. Use only one of: page, offset, or startindex.` (`models/query_params.py:260`). Both are clear and returned as JSON 400/404 (`services/exception_catchers.py:18-89`).
- **Docs:** README plus design notes in `docs/`. No tutorial or reference site; profile authoring is learned from `reference_data/profiles/*.ttl` and `docs/examples/`.
- **Footguns:**
  - Nothing renders unless an instance has an `rdf:type` matched by a profile (see the first error above).
  - Settings are global singletons read at import time (`remote_sparql.py:286`).
  - CORS defaults to `allow_origins=["*"]` (`app.py:282-289`).
  - `/sparql` is a raw passthrough to the store when `enable_sparql_endpoint` is set (`app.py:246`).
- **DX score: 2/5.** Excellent if you publish vocabularies and catalogues; opaque for application CRUD.

### (c) Authorization seams

- **Present:**
  - Store credentials: one service account via HTTP basic auth (`dependencies.py:66-75`).
  - A static shared-secret header gate: `required_header` → 400 if the header is missing or wrong (`middleware.py:200-209`, `config.py:107`). This is meant for "only reachable through my proxy" deployments.
  - Request correlation IDs (`middleware.py:21`).
- **No end-user identity** is read, enforced or propagated to the store (`_send_query` sends only `Accept`, `remote_sparql.py:79`).
- **Natural PEP sites** (ACL-agnostic, DEC-8):
  1. **FastAPI dependency or middleware:** validate the OIDC JWT and obtain a decision from an external PDP (OPA, Cedar, Zitadel actions) before the router runs. This is coarse, per endpoint or per resource.
  2. **The `Repo` port** (`get_data_repo`, `dependencies.py:124`): a decorator `PolicyRepo(Repo)` can (a) forward the user's token to an authorising SPARQL proxy or a store with native ACL, or (b) rewrite queries.
  3. **The typed query AST** (`PrezQueryConstructor`, `umbrella.py:64`): because queries are grammar objects, a PEP can inject a `FILTER`/`VALUES`/`GRAPH` restriction on `?focus_node` safely. Such query rewriting is much harder with string templates.
- **Fit with "behind an authorising proxy":** good. Prez's data queries use no GRAPH clauses (A2). The proxy only needs per-user credentials, which Prez cannot forward today, so it is limited to service-level auth. Turning on the `/sparql` passthrough bypasses every Prez-level PEP.

### (d) Layer coverage and codegen fit

- **Layers:** **L4** (data-service/API, read side), **L2** (read adapters for remote/pyoxigraph/oxrdflib, no transactions), and **L5** only through the separate Prez UI. L0, L1, L3 and L6 are absent.
- **Codegen from LinkML:**
  - `gen-shacl` emits NodeShapes with `sh:targetClass` and `sh:property/sh:path`, which is the raw material of Prez profiles (`altr-ext:hasNodeShape`, `shacl.py:135-260`). A thin generator could wrap LinkML classes into `prof:Profile` resources (default plus per-class object and listing profiles).
  - Endpoint hierarchies (`ont:ListingEndpoint`/`ObjectEndpoint`) could come from LinkML class containment (`tree_root`, slots with a class `range` that are inlined/owned).
  - **Fit: medium.** Profiles need annotations LinkML does not hold (formats, default profile) and would need `annotations:` or a side config.

### (e) C9 and C10

| # | Score | Justification | Evidence |
|---|---|---|---|
| C9 Composability | 4 | Speaks SPARQL 1.1 Protocol (query), JSON-LD, Turtle, SHACL-as-profiles, W3C connegp, OGC API and CQL2. Backends are swappable behind `Repo`. It lacks SPARQL Update/GSP and OIDC, and is an app, not a library component | `repositories/base.py:16`; `connegp_service.py:71-90`; `routers/conformance.py:8` |
| C10 Maintainability | 3 | Semver container images and a changelog, OTEL-style JSON logs, a single process. But it has git-pinned deps (`pyproject.toml:33-34`), global settings coupling, a large config surface (about 60 settings), and ambiguous upstream (kurrawong/prez is not public) | README:234-246; `changelog.md`; `docs/2026-09-21-v5-breaking-changes.md` |

### (f) Proposed new features (round 3)

- **AZ1 Trusted-proxy gate:** a static shared-secret header that must be present, so the service only answers through its proxy (`middleware.py:200`).
- **AZ2 Query-rewriting PEP on a typed AST:** policy constraints are injected as grammar nodes into generated queries. Prez shows the enabling seam (`umbrella.py:64`); the PEP itself is not implemented.
- **G1 LinkML → API-profile generation:** derive server response profiles and endpoint hierarchies from the model. Not present anywhere; it is the gap Prez exposes.

## Round 4

### (a) v3 cross-check (102 features)

Every "absent" was confirmed by grep over `prez/` (Python plus non-reference-data files) for these terms, all with 0 hits: `If-Match|ETag|412`, `outbox|publish`, `RDF Patch|N3 Patch|merge-patch`, `cursor`, `graphql`, `as_of|history`, `idempot`, `savepoint`, `redact|mask`, `audit`, `401|403|Forbidden|Unauthorized`, `capabilit`, `sudo|bypass`, `langString`, `designates_type`. GitNexus `context(Repo)` shows only five query methods, so no write path exists. Round-3 proposals map as AZ1→AZ23, AZ2→AZ3, G1→G15.

| Id | Status | Evidence |
|---|---|---|
| AZ1 | absent | Seam only: `get_data_repo` DI (`dependencies.py:124-148`) is where a scoping `Repo` decorator would go |
| AZ2 | absent | Seam: item, listing and count queries all come from the query-generation package (`umbrella.py:64`, `count.py`); no policy is injected |
| AZ3 | absent | Seam only: typed AST (`umbrella.py:64`, `sparql_grammar`) |
| AZ4–AZ18 | absent | No PDP integration, policies or session scope (grep above) |
| AZ19 | absent | One service account via basic auth (`dependencies.py:66-75`); `x-request-id` is not forwarded (`remote_sparql.py:79`) |
| AZ20–AZ22 | absent | The tbox/label cache is global, not partitioned by principal (`routers/management.py:73-89`) |
| AZ23 | present | `required_header` middleware (`middleware.py:200-209`, `config.py:107`) |
| AZ24–AZ29 | absent | No 401/403 contract, masking, audit, tuple sync or model-generated ACL (grep above) |
| G1–G12 | absent | No LinkML, codegen or domain classes. OpenAPI comes from FastAPI routes, not a schema (`app.py`) |
| G13 | partial | OGC queryables (filterable properties) are generated from profile and shape data (`services/generate_queryables.py:8`, `services/listings.py:140`) |
| G14 | partial | Listing and object CONSTRUCT queries generated from SHACL profiles (`shacl.py:184` `to_grammar`); the source is profiles, not the domain model |
| G15 | partial | Endpoint RDF is generated from a JSON form (`services/generate_endpoint_rdf.py:201`, `/configure-endpoints`); profiles are hand-written TTL; nothing comes from a model |
| G16–G27 | absent | — |
| T1–T11 | absent | Read-only |
| E1–E9 | absent | No events or notifications |
| U1–U8, U10 | n.a. | Server; the UI is the separate Prez UI project |
| U9 | absent | — |
| RAD3 | absent | — |
| RAD4 | partial | The whole API is read-only by construction (`routers/sparql.py:24-35`); there is no per-class opt-in |
| X17 | partial | One resource rendered as Turtle, JSON-LD, RDF/XML, annotated variants and GeoJSON, chosen by profile (`connegp_service.py:71-90`, `renderers/renderer.py`); no JSON:API or GraphQL views |
| X18–X22 | absent | page/offset only (`models/query_params.py:131-260`); no writes, preconditions or bundled context |
| D11 | partial | The store error body is read and logged by size only; the raised message holds just the status (`remote_sparql.py:131-152`) |
| D12 | absent | — |
| D13 | partial | Errors name the URI, CURIE or prefix (`exceptions/model_exceptions.py:13-48`) |
| S15–S17, S19 | absent | — |
| S18 | partial | Local RDF is bulk-loaded into pyoxigraph at startup, a load path separate from queries (`app.py:138`); there are no transactional writes |

**Counts (102):** present 1, partial 8, absent 84, n.a. 9 (U1–U8, U10). Grouped rows are counted per feature.

### Purpose and origin

- **Built for:** publishing authoritative vocabularies, catalogues and spatial datasets (Australian government geological surveys and agencies, the OGC/AGLDWG ecosystem) as a read-only Linked Data API that standards-aware clients and the Prez UI consume. README:8 says "data-configurable Linked Data API … Content Negotiation by Profile"; `config.py:85` says "read-only access".
- **Who and context:** the RDFLib team (copyright 2022) with Kurrawong AI (authors Nicholas Car, David Habgood, Lawson Lewis, `pyproject.toml:4`). It is driven by data-publishing projects; the demo stack is Fuseki.
- **Design angle:** publishing-first and configuration over code. Everything about the response shape lives in RDF (profiles, endpoints), and it adheres to standards (connegp, OGC API, CQL2).
- **Where it fits:** only at **L4 read side**, and only as **ideas**. It fails DEC-5 (40 stars < 200), and it has no L1 domain, no writes and no L3 identity. It cannot be the data-management service in any variant. It could at most sit beside one as a public read-only publication endpoint, which would require a DEC-5 exception.

### Variant fit

| Candidate | V1 | V2 | V3 | V4 | V5 | A | B | C |
|---|---|---|---|---|---|---|---|---|
| Prez | ideas: repo port, typed AST, connegp, OGC pagination contract | n.a. (JSON:API dialect) | ideas only; it could read Fluree over SPARQL, but with no policy forwarding it would see all data | ideas only; a single service account defeats GraphDB fine-grained access control | **closest fit** as a read-side publication API on the read replica; blocked by DEC-5 and by no per-user identity forwarding | n.a. | idea: generate profiles and endpoints from LinkML (G15 gap) | conceptually supports C for reads (generic, schema-interpreting at runtime) |

### Corrections to the integrated docs

- `catalogue.adoc` (Prez row, Layers "L4"): should read **L4 (read side) plus L2 read adapters**, as `libraries/prez.adoc:14` already states.
- `index.adoc` patterns, "Authorization … identity forwarded to the store … Prez": Prez forwards **no** identity (one basic-auth service account, `dependencies.py:66-75`). Its contribution is the typed-AST seam (AZ3) and the trusted-proxy gate (AZ23) only.
- Nothing else contradicts my evidence. Scores in `index.adoc:64` match this report.

### Proposed new features (round 4)

- **T12 Read-only mode guard:** the service rejects update forms at the protocol boundary (the `query`-only form field, `routers/sparql.py:24-35`). A cheap safety switch for read replicas in V5.

## Round 5

### (a) v4 cross-check (77 features)

Absences were confirmed by grep over `prez/` for these terms, all with 0 hits: `migrat`, `opentelemetry|traceparent`, `If-Match|ETag`, `outbox`, `version`-guard patterns, `did you mean`, `assert_type`, `mcp`. GitNexus `context(Repo)` again shows a read-only port (five query methods).

| Id | Status | Evidence |
|---|---|---|
| B1, B2 | absent | No aggregate concept |
| B3 | partial | One CONSTRUCT loads the focus node plus its profile-defined closure (`umbrella.py:64-90`); the closure comes from the profile, not an aggregate boundary |
| B4–B16 | absent | Read-only; no unit of work, events, versions or contexts |
| PG1 | absent | The `sparql-grammar` AST renders SPARQL only |
| PG2–PG4 | n.a. | No labelled property graph |
| EV1–EV9 | absent | No migrations or schema versioning (grep `migrat` finds nothing) |
| AZ30–AZ36 | absent | No policy engine. AZ33: unknown resources return 404 for everyone (`exceptions/model_exceptions.py:13-28`), with no policy logic. AZ36: no stripping of internal headers |
| G28–G36 | absent | No generation from a model (`conformsTo` is used only by the OGC `/conformance` endpoint, `routers/conformance.py:11`) |
| T12, T14 | absent | — |
| T13 | present | `/sparql` accepts only the `query` form field (`routers/sparql.py:24-35`); there are no update paths |
| S20–S23 | absent | The admin endpoints are tbox-cache purge and health only (`routers/management.py:73-104`) |
| X23, X24 | absent | JSON-LD is serialised by rdflib with no strict mode (`renderer.py:754`); no MCP |
| E10 | absent | — |
| I7 | partial | Reversible CURIE ↔ IRI for path identifiers (`services/curie_functions.py:99`, `:127`); this applies to URLs, not minting |
| I8, P20 | absent | — |
| U11–U13 | n.a. | Server |
| D14 | n.a. | No writes |
| D15 | absent | The query fingerprint is logged and parameters are not (no redaction needed) |
| D16 | partial | The OGC API conformance test suite runs against the app in tests (`tests/test_ogc.py`, `ogctests` dev dependency); there is no formal access-contract model |
| D17 | partial | Per-query fingerprint and timing logs (`remote_sparql.py:21`, `:86-100`); no `to_sparql()` API |
| D18 | n.a. | No objects |
| D19–D21 | absent | Internal fixtures only; nothing shipped; docs are not executed |
| D22 | present | CURIEs in routes, identifiers and errors (`curie_functions.py`; `model_exceptions.py:28` `URI for curie "…" not found`) |
| D23–D28 | absent | — |
| D29 | partial | Structured JSON logs with fingerprint, timing and request IDs (`middleware.py:21`, `services/prez_logging.py`); no OpenTelemetry spans or `traceparent` |

**Counts (77):** present 2, partial 5, absent 62, n.a. 8.

### (b) Page review: `libraries/prez.adoc`

1. **Line 21**, "Its users are Australian government geological surveys and agencies and the OGC/AGLDWG ecosystem": overstated and too narrow. Kurrawong's public Prez UI theme and stack repos include Australian agencies (GSQ, GSWA, ICSM, AGLDWG) **and the British Geological Survey** (`Kurrawong/bgs-prez-ui-theme`, `prez-stack-ansible-bgs`, from the `gh search repos prez --owner kurrawong` listing). These repos are deployment evidence, not a user list. **Fix:** "Deployed for geological surveys and government agencies (Australian ones such as GSQ, GSWA and ICSM, and the British Geological Survey) and the OGC/AGLDWG ecosystem, judging by Kurrawong's public Prez UI themes."
2. **Line 110**, V5 "enables": overstated given the same row's two blockers (DEC-5 fail, no per-user identity forwarding). **Fix:** "conditional (ideas)". It enables V5 only as a *public* read-only publication endpoint where every reader may see all data.
3. **Line 138**, "Proposed in round 4: a read-only guard …": now taxonomy **T13**. **Fix:** "…now v4 T13 (present)."
4. **Line 75**, "Query observability: fingerprint and timing per store call": add the missing caveat that there are no OpenTelemetry spans or `traceparent` (D29 partial).
5. **Line 9**: correct as is (the upstream is unreachable).
6. **Elsewhere, `index.adoc:154`**, the Authorization pattern ("… identity forwarded to the store …") credits **Prez**, and still does after round 4. Prez forwards no identity. **Fix:** credit Prez only for the typed-AST seam (AZ3) and the trusted-proxy gate (AZ23), and add **LDkit** (AZ19 present via `fetch`) to the "identity forwarded" credit.

### (c) Final verdict and three things to remember

**Verdict: ideas.**

1. Prez is a **read-only publishing app**, not a library. It can never be the data-management service or carry writes, and it fails DEC-5 (40 stars).
2. What is worth taking is **design**: a `Repo` port with three adapters, the typed SPARQL AST (the safest place for a query-rewriting PEP), CONSTRUCT around a paged SELECT, connegp by profile, and capped counts and facets.
3. Prez has **no per-user identity** (one basic-auth service account; CORS `*`; the optional `/sparql` passthrough bypasses Prez). Behind any authorising design it must be treated as "sees everything".

### (e) New features

None. The taxonomy covers everything observed.
