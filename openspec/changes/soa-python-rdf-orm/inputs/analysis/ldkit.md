# LDkit

- **Repo:** https://github.com/karelklima/ldkit (clone `/home/lps/work/repos/ldkit`), npm package `ldkit`, docs https://ldkit.io/
- **Commit analysed:** `09fc801` (main, 2026-10-13); the version is set at publish time (`scripts/dnt.ts:38`)
- **Licence:** MIT (`LICENSE`, "Copyright (c) 2021-present Karel Klima")
- **Size:** `library/` 33 TS files, 3,889 LOC (largest: `lens/lens.ts` 557, `lens/query_builder.ts` 355, `encoder.ts`/`decoder.ts` 240 each); `scripts/` (schema generators) 2,456 LOC; `tests/` 8,539 LOC, 316 `Deno.test` cases (unit tests plus e2e tests on Comunica over an in-memory N3 store)
- **GitNexus index:** `ldkit`, 227 files, 1,594 symbols, 3,741 edges, 79 clusters, 119 processes
- **Docs read:** `README.md`, `docs/table-of-contents.json`, `docs/components/schema-generators.md`, https://ldkit.io/docs/components/lens, https://ldkit.io/docs/features/query-with-comunica, https://github.com/karelklima/ldkit. Paper: Klíma, Taelman, Nečaský, "LDkit: Linked Data Object Graph Mapping Toolkit for Web Applications", ISWC 2023 (CITATION.cff).

## Summary

LDkit is a small TypeScript object-graph mapper for the browser, Deno and Node. A schema is a JSON-LD-like literal object (`{"@type": …, name: {"@id": …, "@type": xsd.string, "@optional": true}}`). Its type is inferred with TS conditional types, so entities are fully typed without code generation. A `Lens` built on a schema exposes `find / findOne / findByIri(s) / count / insert / update / delete` plus raw `insertData / deleteData`. Each call compiles to a single SPARQL 1.1 Query or Update string and goes to an RDF/JS `StringSparqlQueryable` engine. The default is LDkit's own `fetch`-based SPARQL Protocol client, about 160 LOC; Comunica is optional. There are no sessions, transactions or identity map: every call is one round-trip. It is the reference for what a JS client of rdf-persistence will look like and expect.

## Architecture (from GitNexus)

The clusters "Lens", "Sparql", "Engine" and "Scripts" match the folders:

- **`library/schema/`**: the type-level schema DSL (`schema.ts`: `Property` with `@id @type @schema @optional @array @multilang @inverse @enum`), `data_types.ts` (xsd → JS type map, extensible through the `CustomDataTypes` interface), and `interface.ts`/`search.ts` (the derived `SchemaInterface<T>`, `SchemaUpdateInterface<T>`, `SchemaSearchInterface<T>`).
- **`library/lens/`**: `lens.ts:86-556` `Lens<T>` (the facade), `query_builder.ts:34-354` `QueryBuilder`, `update_helper.ts:11-200` `UpdateHelper`, `search_helper.ts` `SearchHelper`. GitNexus `context(QueryBuilder)` shows it is only constructed by `Lens.constructor`, and every Lens method calls exactly one builder method (`count→countQuery`, `find→getQuery/getSearchQuery`, `findByIris→getByIrisQuery`, `insert→insertQuery`, `update→updateQuery`, `delete→deleteQuery`).
- **`library/sparql/`**: a tagged-template SPARQL builder (`sparql_tag.ts`, `sparql_query_builders.ts` with `SELECT/CONSTRUCT…LIMIT/OFFSET`, `sparql_update_builders.ts` with `INSERT DATA / DELETE DATA / DELETE…INSERT…WHERE / WITH`).
- **`library/engine/`**: `query_engine.ts` `QueryEngine` (POSTs `application/sparql-query` or `application/sparql-update`), `query_engine_proxy.ts`, `query_resolvers.ts` (bindings, boolean or quads from SPARQL JSON and RDF responses). The engine contract `IQueryEngine = RDF.StringSparqlQueryable<…>` (`engine/types.ts`) is the RDF/JS standard interface, so Comunica can be swapped in.
- **`encoder.ts` / `decoder.ts`**: convert entities to and from RDF/JS quads.
- **`cli.ts` + `scripts/`**: `context-to-schema`, `shexc/shexj-to-schema`, `shacl-to-schema`, `schema-to-script`, `schema-to-package` (all marked experimental).
- **GitNexus processes:** `proc_10_update`, `Update → UpdateHelper → ParseArrayUpdateConfig`, and `proc_113_queryvoid`, `QueryVoid → GetSparqlEndpoint`.

## Implementation principles

- **Mapping:** the schema is data and its TS type is computed from it. `expandSchema` normalises shorthand. `encode()` (`encoder.ts`) walks the expanded schema and emits quads. Nested objects without `$id` become blank nodes (`encoder.ts:136`). `decode()` (`decoder.ts`) rebuilds objects from the CONSTRUCT graph. `@multilang` gives a `{lang: value}` map, and otherwise the value in the preferred `options.language` is picked (`decoder.ts:137-212`).
- **Read query shape:** `getQuery`/`getSearchQuery` (`query_builder.ts:245-300`) produce `CONSTRUCT { ?iri a ldkit:Resource . <shape> } WHERE { { SELECT DISTINCT ?iri WHERE { required shape + filters } LIMIT n OFFSET m } <full shape with OPTIONALs> }`. Optional fetch-only properties are put in a `UNION` inside one `OPTIONAL` to avoid cartesian blow-up (issue #175, comments at `:118-124`). Filters on optional properties are placed after the OPTIONAL block (issue #170). `findByIris` uses `VALUES ?iri {…}`.
- **Filters:** `$equals $not $in $notIn $lt $lte $gt $gte $contains $strStarts $strEnds $regex $langMatches $filter` (`lens/search_helper.ts`), compiled to SPARQL `FILTER`s.
- **Insert:** `INSERT DATA { quads }` (`query_builder.ts:312-319`). There is no existence check, so inserting the same `$id` twice merges triples.
- **Update:** one `DELETE {old} INSERT {new} WHERE {old pattern}` per call (`query_builder.ts:344-354`, `update_helper.ts`). Single-valued properties are replaced; optional ones are wrapped in `OPTIONAL` in WHERE. Arrays support `$set` (replace) and `$add`/`$remove` (patch) (`update_helper.ts:161-189` `parseArrayUpdateConfig`). This is a per-property delete-insert patch, not a whole-graph replace.
- **Delete:** `DELETE { ?s ?p ?o } WHERE { ?s ?p ?o . VALUES ?s {…} }` (`query_builder.ts:331-339`). Only the subject's own triples are removed, so nested blank nodes and inverse links are left behind.
- **Named graphs:** a single `options.defaultGraph` wraps reads in `GRAPH <g>` and writes in `WITH <g>` or quads in `g` (`query_builder.ts:57-80`, `:321-329`). There is no per-entity graph.
- **Identity:** the caller supplies `$id` (an IRI). There is no minting strategy. The decoder caches nodes per decode call (`decoder.ts:23`), so there is no session-wide identity map.
- **Transactions:** none. One Lens call is one SPARQL request, so a multi-entity `insert(...entities)` or `update(...entities)` is atomic only because it is a single Update request.
- **Pagination:** `find({ where, take, skip })` with default `take` 1000 (`lens.ts:246-256`, `options.ts`). `count({ where, max })` uses `COUNT(DISTINCT ?iri)` with an optional cap (`query_builder.ts:222`).

## Patterns catalogue

| Pattern | Where |
|---|---|
| Data Mapper (schema-driven encode/decode; entities are plain objects) | `encoder.ts`, `decoder.ts` |
| Repository-like collection facade ("Lens") | `lens/lens.ts:86` |
| Query Object / builder (tagged templates) | `sparql/sparql_tag.ts`, `sparql_query_builders.ts`, `sparql_update_builders.ts` |
| Schema-as-value with type inference (no codegen needed) | `schema/interface.ts` |
| Strategy / pluggable engine (RDF/JS `StringSparqlQueryable`) | `engine/types.ts`, `engine/query_engine.ts` |
| Patch semantics for collections (`$set/$add/$remove`) | `lens/update_helper.ts:161` |
| Code generation from SHACL/ShEx/JSON-LD context | `cli.ts`, `scripts/*_to_schema.ts` |
| In-memory fake store for tests (Comunica + N3.Store) | `tests/test_utils.ts:105-134` |

## Docs vs code

- "Compatible with Comunica query engine": **confirmed** (`engine/types.ts` uses the `@comunica/types` context; the e2e tests use Comunica). Our brief's wording "CRUD over SPARQL endpoints **via Comunica**" is **inaccurate**: the default engine is LDkit's own fetch client (`query_engine.ts`), and Comunica is optional (docs page "Query with Comunica").
- "Runs in browser, Deno and Node": consistent with the dnt build (`scripts/dnt.ts`, `npm-publish.yml`). Runtime environments were not tested here.
- Schema generators from JSON-LD context, ShEx and SHACL: **confirmed** in `cli.ts` and `scripts/`. The docs mark them experimental.
- No claims of transactions, validation or JSON-LD output were found, and none exist in the code (`grep transaction|jsonld` over `library/` finds nothing).

## Scores C1–C8

| # | Score | Justification | Evidence |
|---|---|---|---|
| C1 Feature coverage | 3 | CRUD, filters, pagination, count, inverse and nested properties, lang-tagged and typed literals, one default graph. No transactions, identity map, validation, JSON-LD I/O or cascade delete | `lens.ts:155-557`, `query_builder.ts` |
| C2 Design patterns | 4 | Clean Data Mapper: plain objects, schema-driven codec, a builder per operation, a pluggable engine. No Unit of Work or session | `encoder.ts`, `query_builder.ts:34`, `engine/types.ts` |
| C3 Developer friendliness | 5 | Fully inferred TS types from one schema literal, a short happy path, a docs site with tutorial, components, features and API, and 7 examples (React, Next) | `schema/interface.ts`; ldkit.io; `examples/` |
| C4 Ease of adoption | 5 | About 3.9k LOC with a single endpoint URL as config. The default engine has no heavy dependencies. Comunica is optional for files, Solid and in-memory N3 | `options.ts`, `query_engine.ts` |
| C5 Reuse of foundations | 4 (JS ecosystem) | RDF/JS data model and interfaces, N3, optional Comunica. Writes its own small SPARQL builder and HTTP client, on purpose for bundle size. Python foundations n.a. | `rdf.ts`, `engine/` |
| C6 Data-centric / DDD | 4 | Schema-first, with SHACL/ShEx/JSON-LD-context codegen. Entities carry no persistence code. A Lens per type works as a repository | `scripts/shacl_to_schema.ts`, `lens.ts` |
| C7 SPARQL 1.1 portability | 5 | Plain SPARQL 1.1 Query and Update over the Protocol (POST `application/sparql-query` / `sparql-update`). No store-specific API. No GSP | `query_engine.ts` (`query()`), `sparql_update_builders.ts` |
| C8 Health | 4 | 316 tests, CI (fmt, lint, test, dnt build), commits to 2026-10, MIT, peer-reviewed paper, 83 stars. Essentially a single maintainer | `.github/workflows/deno-test.yml`; GitHub page |

## Feature inventory

| Id | Status | Evidence |
|---|---|---|
| M1 | present | TS schema literal plus inferred interface (`schema/schema.ts`, `interface.ts`) |
| M2 | present | The schema literal is JSON-LD-context-like |
| M3 | present (experimental) | `cli.ts` with context/ShEx/SHACL → schema → script or package |
| M4 | partial | `@type` arrays; no polymorphic decode by subclass |
| M5 | partial | Only TS compile-time typing and `@enum`; no runtime validation |
| I1 | absent | Caller supplies `$id` |
| I2 | present | Nested objects without `$id` become blank nodes (`encoder.ts:136`) |
| I3 | absent | Cache only within one decode call (`decoder.ts:23`) |
| R1 | partial | `@array` = unordered set; no `rdf:List` in the Lens schema (the context generator maps `@list`) |
| R2 | present | Nested `@schema` and `@inverse` (`query_builder.ts:160-185`) |
| R3 | partial | Always eager to the schema's declared depth; depth = schema nesting |
| R4 | absent | Delete removes only the subject's triples (`query_builder.ts:331-339`) |
| L1 | present | xsd → JS map plus custom datatypes (`schema/data_types.ts`) |
| L2 | present | `@multilang` and `options.language` (`decoder.ts:137-212`) |
| P1 | present | `lens.ts:155-557` |
| P2 | present | Per-property DELETE/INSERT/WHERE patch; arrays use `$set/$add/$remove` (`update_helper.ts`) |
| P3 | absent | — |
| P4 | absent | Only single-request atomicity |
| P5 | absent | — |
| P6 | partial | One `defaultGraph` per Lens (`query_builder.ts:57-80`) |
| P7 | partial | `insertData/deleteData` with raw quads; no streaming |
| Q1 | present | `findByIri(s)` with `VALUES` |
| Q2 | present | `where` with `$`-operators (`search_helper.ts`) |
| Q3 | present | `Lens.query(sparql)` maps a CONSTRUCT result back through the schema (`lens.ts:205`) |
| Q4 | partial | take/skip, count with max; no order-by or aggregation API |
| Q5 | partial | Via nested schemas; no property-path syntax |
| S1 | partial | Through Comunica plus N3.Store (JS side) |
| S2 | present | `query_engine.ts` |
| S3 | absent | — |
| S4 | present | `IQueryEngine` = RDF/JS `StringSparqlQueryable` |
| X1 | absent | Plain JSON objects, no `@context` emitted |
| X2 | partial | Through the RDF/JS quad APIs (`rdf.ts` re-exports N3) |
| X3 | n.a. | Client library |
| X4 | present | TS types inferred, or generated through `schema-to-package` |
| X5 | absent | — |
| D1 | present | — |
| D2 | present | All promise-based |
| D3 | present | React / Next / React Query examples (`examples/`) |
| D4 | present | ldkit.io plus `docs/` plus `examples/` |
| D5 | present | Comunica plus N3.Store in-memory fixture (`tests/test_utils.ts`) |
| O1, O2 | absent | — |
| A1 | absent | — |

### Proposed new features

- **M6 Type-inferred schema:** host-language types are derived from a schema value with no codegen step (TS conditional types; a Python analogue would be pydantic `create_model` or LinkML-generated pydantic).
- **P8 Collection patch operators:** `$set` / `$add` / `$remove` on multi-valued properties, compiled to a minimal DELETE/INSERT.
- **Q9 Engine-standard interface:** the store or engine port is an existing community interface (RDF/JS `StringSparqlQueryable`), which allows a drop-in federated engine.
- **Q10 Cartesian-safe optional fetch:** optional properties are fetched in UNION branches to avoid result explosion (`query_builder.ts:118-124`).

## JS-friendliness

LDkit is the JS client. What it needs from a backend is **only a standards-compliant SPARQL 1.1 Protocol endpoint**: POST `application/sparql-query` returning `application/sparql-results+json` or an RDF CONSTRUCT serialisation, and POST `application/sparql-update`. It does not consume REST, JSON:API or OpenAPI. That gives an rdf-persistence HTTP contract two options for LDkit-style clients:

1. **Expose a SPARQL 1.1 Protocol endpoint** (query plus update) backed by the same store (pyoxigraph or a remote endpoint), so LDkit works unchanged. Authorisation and validation then cannot be enforced per object, which is a reason to put a policy layer on the update route or keep it disabled.
2. **Expose an entity contract** (a REST or JSON-LD resource per aggregate) and publish the model as an **LDkit schema / TS package**. LinkML → SHACL → `ldkit shacl-to-schema` is already a working pipeline, and a direct LinkML → LDkit-schema generator is a small, well-defined target. Entities would be exchanged as JSON-LD whose compacted keys equal the LDkit property names, so the same schema serves both sides.

Recommendation for the brief: offer (1) for read-heavy RAD and (2) for writes with server-side validation and transactions, generating the LDkit schema from the same LinkML model.

## Reuse verdict for rdf-persistence: **borrow ideas** (and target as a client)

1. The **Lens API surface** (`find({where, take, skip})`, `findByIri(s)`, `count`, `insert`, `update`, `delete`, `insertData`, `deleteData`, raw `query`) is a proven minimal repository interface; mirror it in Python for symmetry with JS.
2. The **CONSTRUCT-around-paginated-SELECT** read query and the **UNION-in-OPTIONAL** trick for optional fields.
3. **Per-property DELETE/INSERT/WHERE patch updates** and the `$set/$add/$remove` array semantics as the P2 strategy.
4. **The schema as a JSON-LD-context-like value with `@optional/@array/@multilang/@inverse`**: a compact mapping vocabulary to compare with LinkML slot metadata (`required`, `multivalued`, `inverse`, `range`).
5. **A pluggable engine behind a standard interface**: the Python analogue is a store port with rdflib-Graph / pyoxigraph / SPARQLWrapper adapters.
6. **Do not copy** delete semantics (orphaned blank nodes, dangling inverse links), the missing transactions, or the missing runtime validation.

## Risks / anti-patterns observed

- `delete()` leaves nested blank-node subtrees and incoming references behind, and does not respect aggregate boundaries.
- `insert()` uses `INSERT DATA` with no existence check: a duplicate `$id` silently merges.
- `update()` puts required-property patterns in WHERE, so updating an entity with a missing required triple silently matches nothing (inferred from `update_helper.ts:60-77`, where a required pattern goes into WHERE without OPTIONAL; not tested here).
- Any SPARQL Update endpoint exposed to browsers is an open write surface; LDkit assumes the endpoint enforces access.
- Bus factor: one primary maintainer.

## Round 2 cross-check (taxonomy v1)

Checked against `docs/modules/ROOT/pages/architecture/soa/feature-taxonomy.adoc` (v1). Each "absent" was confirmed with a grep over `library/`: skolem/genid, retry/backoff, cache (only the decoder's per-call cache), fulltext, owl:imports, infer, hydra, jsonapi, request-id, find_by_, facet and timeout all return nothing relevant.

| Id | Status | Evidence |
|---|---|---|
| M6 | present | TS types are inferred from the schema value at compile time, with no codegen step (`schema/interface.ts`); objects are plain |
| M7 | absent | Every property needs an explicit `@id` (`schema/schema.ts:9`); `createNamespace` only helps spell IRIs |
| M8 | partial | The schema is a JSON-LD-context-like value (`@id/@type/@inverse/@multilang`); real contexts are converted offline by `context-to-schema` (`cli.ts`, `scripts/context_to_schema.ts`) |
| M9 | partial | `@multilang` exposes all language variants of one property as a `{lang: value}` map (`decoder.ts:137-162`); there is no "one attribute per language" |
| M10 | absent | Entities are plain objects |
| M11 | absent | Unmapped triples are never fetched; CONSTRUCT covers the schema shape only (`lens/query_builder.ts:245-300`) |
| M12 | absent | `rdf:type` is hard-coded as the discriminator (`query_builder.ts:49`, `:118`) |
| M13 | absent | Generates TS from SHACL; emits no shapes or indexes |
| M14 | present | Schema generated from SHACL / ShEx / JSON-LD context (`cli.ts`, `scripts/shacl_to_schema.ts`, `shex_to_schema.ts`); experimental |
| M15 | absent | — |
| I4 | absent | Blank nodes are created for nested objects (`encoder.ts:136`) with no skolemisation |
| R5 | partial | Cardinality only as compile-time typing (`@optional`, `@array`); there is no runtime check |
| R6 | absent | — |
| R7 | absent | — |
| R8 | absent | Inverse navigation needs a declared `@inverse` (`query_builder.ts:160-185`) |
| L3 | present | `registerDataHandler(dataType, {fromRdf, toRdf})` (`translator.ts:48`) plus the type-level `CustomDataTypes` (`schema/data_types.ts`) |
| P8 | partial | `update()` deletes and inserts only the mapped properties it is given, so foreign triples survive (`lens/update_helper.ts:60-77`); `delete()` removes every `?s ?p ?o` (`query_builder.ts:331-339`) |
| P9 | absent | No tracking; the caller passes a partial entity (`lens/types.ts` `DeepPartial`) |
| P10 | present | `$set / $add / $remove` (`update_helper.ts:161-189`) |
| P11 | absent | Nested blank nodes are orphaned on delete (`query_builder.ts:331-339`) |
| P12 | absent | One `defaultGraph` option per Lens (`query_builder.ts:57-80`) |
| P13 | absent | — |
| P14 | absent | `INSERT DATA` only (`query_builder.ts:317`) |
| P15 | absent | — |
| Q6 | present | All values go through the tagged-template builder as RDF/JS terms and literals are escaped (`sparql/stringify.ts:3`, `:23`) |
| Q7 | partial | Tagged-template builders over RDF/JS terms (`sparql/sparql_query_builders.ts`, `sparql_update_builders.ts`); not a full grammar AST |
| Q8 | absent | — |
| Q9 | present | One CONSTRUCT per `find`, with UNION-in-OPTIONAL for optional fields (`query_builder.ts:118-124`, `:245-300`) |
| Q10 | present | The CONSTRUCT graph is decoded into nested objects (`decoder.ts`); paginated over `?iri` in the inner SELECT (`query_builder.ts:251-258`) |
| Q11 | absent | `Lens.query()` runs any CONSTRUCT unchecked (`lens/lens.ts:205-211`) |
| Q12 | partial | `$contains/$regex/$strStarts` via FILTER (`lens/search_helper.ts`); no text index |
| Q13 | absent | `$filter` injects a raw expression only |
| Q14 | absent | Its own Mongo-style `$`-operators, not a standard language (`search_helper.ts`) |
| Q15 | partial | `count({where, max})` with a cap (`query_builder.ts:222-232`); no facets |
| Q16 | partial | Negative operators deliberately tolerate unbound optional values (`search_helper.ts:33`, `:143-146`); fixed, not configurable |
| Q17 | absent | — |
| Q18 | absent | Fetch is limited to the schema shape, not CBD |
| S5 | absent | One source for query and update (`engine/query_engine.ts` `getSparqlEndpoint`) |
| S6 | absent | Cache only within one decode call (`decoder.ts:23`) |
| S7 | absent | `fetch` once; it throws on a non-OK status (`query_engine.ts` `queryAndResolve`) |
| S8 | present | `IQueryEngine = RDF.StringSparqlQueryable` (`engine/types.ts`) |
| X6 | absent | — |
| X7 | partial | Client side: `Accept` lists the media types per result kind (`engine/query_resolvers.ts:131-143`) |
| X8 | absent | — |
| X9 | partial | Schema keys (API names) map to predicate IRIs (`schema/schema.ts:9`); one level |
| X10 | partial | Several Lenses (schemas) can project the same data differently; there is no write/read split |
| X11 | absent | — |
| X12 | absent | — |
| X13 | absent | Only a custom `fetch` via the context (`query_engine.ts` `getFetch`) |
| X14 | absent | — |
| D6 | absent | — |
| D7 | n.a. | JS is promise-only |
| D8 | partial | Comunica plus an in-memory N3 store, and a live DBpedia e2e test (`tests/test_utils.ts:105`, `tests/e2e/dbpedia.test.ts`) |
| D9 | partial | `schema-to-package` scaffolds an npm package from a schema (`scripts/schema_to_package.ts`) |
| RAD1 | absent | — |
| RAD2 | n.a. | Client library |
| O3–O7 | absent | — |
| A2 | present | GRAPH/WITH are emitted only when `defaultGraph` is set (`query_builder.ts:57-80`, `:321-329`) |
| A3 | absent | (TS `readonly` hits are compiler modifiers) |
| O2 (refined) | absent | — |
| X4 (refined) | present | TS types inferred or generated (`schema-to-script`/`schema-to-package`); no JSON Schema |
| X5 (refined by X12) | absent | — |
| D2 (refined by D7) | present | Promise-based API |

### Proposed new features (round 2)

None: every LDkit behaviour found maps to an existing v0 or v1 id.

## Round 3

### (a) v2 cross-check

| Id | Status | Evidence |
|---|---|---|
| M16 | partial | `@type` can be an array; all types are asserted and required (`schema/schema.ts:24-26`, `query_builder.ts:110-121`); no resolution order (objects have no methods) |
| M17 | partial | Compile-time only: TS `as const` schema typing and `parseArrayUpdateConfig` runtime checks (`lens/update_helper.ts:161-189`); no check for unique predicates or inverse pairs |
| I5 | absent | — |
| I6 | n.a. | Plain objects, compared by `$id` by the user |
| P16 | absent | — |
| P17 | absent | — |
| P18 | absent | Quads are built inside `QueryBuilder` with no hook (`query_builder.ts:50-55` `entitiesToQuads`) |
| P19 | absent | — |
| Q19 | present | `$regex`, `$contains`, `$strStarts`, `$strEnds` (`lens/search_helper.ts`) |
| Q20 | absent | — |
| S9 | absent | One source per engine (`engine/query_engine.ts` `getSparqlEndpoint`, which rejects more than one source) |
| S10 | partial | Only through Comunica (link traversal and Solid sources, per the docs page "Query with Comunica"); not in the default engine |
| S11 | absent | — |
| S12 | absent | One SPARQL request per Lens call |
| S13 | partial | The engine returns `RDF.ResultStream` (`engine/query_resolvers.ts:12-13`) but `Lens` collects it into a full graph before decoding (`lens.ts` `decode(graph)`) |
| S14 | partial | `options.logQuery(query)` callback on every query (`options.ts:22`, `lens/lens.ts:108`); no timing or fingerprint |
| X15 | absent | — |
| X16 | n.a. | Client library |
| D10 | absent | — |

### (b) Developer experience

- **Shortest complete CRUD:** `docs/getting-started/index.md:18-85`, about 45 code lines covering the import, a 9-line schema literal, options `{ sources: [endpoint] }`, `createLens`, then `find()`, `count()`, `findByIri(iri)`, `insert({$id, …})`, `update({$id, name})` and `delete(iri)`. Each operation is one line. This is the shortest complete CRUD of the three libraries.
- **Concepts to learn:** five. Schema (`@type`, `@id`, `@optional`, `@array`, `@multilang`, `@inverse`), `Lens`, `Options` (source, language, take, defaultGraph), namespaces, and `$id`. Search operators come later.
- **Typing/IDE:** the best seen. `person.birthDate` is typed `Date` straight from the schema literal, with no build step (`schema/interface.ts`). `update()` accepts `SchemaUpdateInterface<T>`, and `where` gets operator completion.
- **Real errors:**
  - `Invalid query response status '${status} ${statusText}'` (`engine/query_engine.ts:95`): terse, and the endpoint's error body is discarded, so SPARQL syntax errors from the store are invisible.
  - `Invalid array update query, expected an array, or an object with $add, $set, or $remove properties` (`lens/update_helper.ts:169-171`): clear.
  - `No data source defined in Options` (`options.ts:83`).
- **Docs:** a good docs site (getting started, components, features, API reference), a peer-reviewed paper, and 7 runnable examples, including React and Next.
- **Footguns:**
  1. Properties are required by default. Entities missing any non-`@optional` property silently drop out of `find()`, because required patterns sit in the paged inner SELECT (`query_builder.ts:233-243`, `getShape(Flags.ExcludeOptional | IncludeTypes)`).
  2. `insert` with an existing `$id` merges triples silently (`INSERT DATA`, `query_builder.ts:317`).
  3. `delete` orphans nested blank nodes (`:331-339`).
  4. The getting-started mutation examples omit `await` (`docs/getting-started/index.md:71-84`), which invites floating promises.
  5. The default `take` of 1000 truncates silently (`options.ts`).
  6. Store error bodies are swallowed (above).
- **DX score: 4/5.** It is loved for type inference and brevity, and loses a point for silent-data footguns and opaque errors.

### (c) Authorization seams

- **No PEP inside LDkit.** It is a client, so authorization must be enforced server-side, which is consistent with DEC-8.
- **Credential seam:** a custom `fetch` in the options or query context (`docs/components/options.md:30`, `engine/query_engine.ts` `getFetch`). This is where an OIDC access token is attached (`Authorization: Bearer …`) and refreshed, for example by wrapping `fetch` with an oidc-client-ts token getter. Each Lens can carry its own context, so different tokens per resource are possible.
- **Behind an authorising proxy:** LDkit sends plain SPARQL 1.1 Protocol POSTs (`application/sparql-query` / `sparql-update`). Any proxy that checks the JWT and then (a) filters by graph, (b) rewrites queries, or (c) delegates to a store with native ACLs works without LDkit changes. A2 holds: no GRAPH clause is emitted unless `defaultGraph` is set.
- **Risk:** LDkit writes need a raw **SPARQL Update** endpoint exposed to browsers. Per-entity or per-field policy on arbitrary updates is hard, because the proxy must parse DELETE/INSERT WHERE.
- **Recommendation for rdf-persistence:** give LDkit-style clients a **read** SPARQL endpoint behind the proxy, and route writes through entity endpoints (L4), where the Python PEP and validation run. A server-side update rewriter would otherwise need to recognise LDkit's fixed update shapes (`query_builder.ts:331-354`).

### (d) Layer coverage and codegen fit

- **Layers:** **L5** (JS client and object mapper) primarily. **L0** through the schema generators (`cli.ts`). **L1** on the client side (encode/decode). **L2** via pluggable engines (no transactions). L3, L4 and L6 are absent.
- **Codegen from LinkML:** works today as a two-step pipeline. **Fit: high.** LinkML slot metadata (`required`, `multivalued`, `inverse`, `range`, `slot_uri`, `class_uri`) maps almost one-to-one onto LDkit's `@optional`, `@array`, `@inverse`, `@type`/`@schema` and `@id`.
  - (1) `gen-shacl` → `ldkit shacl-to-schema` gives namespaces, NodeShapes, cardinalities and nested shapes (`docs/components/schema-generators.md`, `scripts/shacl_to_schema.ts`, 598 LOC).
  - (2) `gen-jsonld-context` → `ldkit context-to-schema` gives types, `@language` (to `@multilang`), `@set`/`@list` and `@reverse`. Every property becomes required, because contexts carry no cardinality, so the SHACL route is better.
  - A direct `gen-ldkit` LinkML generator (about 200–300 LOC of Jinja) would remove the "experimental" step and keep `@optional`/`@array` exact.
  - `schema-to-package` then publishes the generated schema as an npm package for UI teams.

### (e) C9 and C10

| # | Score | Justification | Evidence |
|---|---|---|---|
| C9 Composability | 5 | SPARQL 1.1 Protocol query and update, the RDF/JS interfaces (`StringSparqlQueryable`, data model), Comunica as a drop-in engine, and schema import from SHACL, ShEx and JSON-LD context. Auth stays orthogonal via `fetch`. No lock-in | `engine/types.ts`; `cli.ts`; `options.md:30` |
| C10 Maintainability | 4 | Small (3.9k LOC core), plain TS, CI with fmt, lint, test and an npm build (dnt), versioned npm releases. Bus factor of 1, and the generators are marked experimental | `deno.json`; `.github/workflows/deno-test.yml`, `npm-publish.yml` |

### (f) Proposed new features (round 3)

- **AZ3 Pluggable credential injection per request:** a custom `fetch` or token getter on the store client, for OIDC bearer forwarding (`options.md:30`).
- **G2 LinkML → JS client-schema generator:** generate a typed client mapping (LDkit schema / TS package) from the same model as the backend. Today it is reachable through SHACL; a direct generator is a gap.
- **D11 Store error-body surfacing:** propagate the store's error message to the developer. LDkit lacks this (`query_engine.ts:95`), so it is listed as a needed DX feature.

## Round 4

### (a) v3 cross-check (102 features)

Every "absent" was confirmed by grep over `library/` for these terms, all with 0 hits: `If-Match|ETag|412`, `outbox|publish`, `RDF Patch|merge-patch`, `cursor`, `graphql`, `openapi`, `jsonld|@context`, `frame`, `as_of|history`, `idempot`, `savepoint`, `redact|mask`, `audit`, `401|403`, `capabilit`. GitNexus `context(QueryBuilder)` shows exactly one builder method per Lens call, with no hook or policy stage. Round-3 proposals map as AZ3→AZ19, G2→G16, D11→D11.

| Id | Status | Evidence |
|---|---|---|
| AZ1–AZ18 | absent | Client library; no PEP, PDP or policy model (grep above) |
| AZ19 | present | Custom `fetch` per Lens or global options injects a bearer token on every call (`docs/components/options.md:30`, `engine/query_engine.ts` `getFetch`) |
| AZ20, AZ21 | absent | — |
| AZ22 | n.a. | No client cache (`decoder.ts:23` caches within one decode call only) |
| AZ23–AZ29 | absent | — |
| G1 | partial | Mapping lives in a static schema value separate from plain objects (`schema/schema.ts`); it is hand-written or CLI-generated, not LinkML |
| G2 | partial | The mapper (`Lens` + `QueryBuilder`) is separate from the types (`lens/lens.ts:86`); it is not generated |
| G3, G4 | absent | `schema_to_script.ts` has fixed templates; it emits a single file |
| G5 | partial | `ldkit.IRI` maps to the `IRI` type alias (string), not a branded type (`schema/data_types.ts`) |
| G6 | present | `rdf:langString` plus `@multilang` round-trip, with a preferred `language` option (`schema/data_types.ts`, `decoder.ts:137-212`, `encoder.ts`) |
| G7–G15 | absent | — |
| G16 | partial | TS schema and npm package generated from SHACL, ShEx or a JSON-LD context (`cli.ts`, `scripts/schema_to_package.ts`); no LinkML source |
| G17 | partial | Shapes → schema import (`scripts/shacl_to_schema.ts`, `shex_to_schema.ts`); multi-file merge not seen |
| G18–G23 | absent | — |
| G24 | partial | `@enum` restricts string values, which may be IRIs (`schema/schema.ts:16`); no concept binding |
| G25 | partial | Standalone generated package (`schema-to-package`) with a pluggable codec (`translator.ts:48` `registerDataHandler`); no object-set identity |
| G26, G27 | absent | — |
| T1 | partial | A multi-entity `insert`/`update`/`delete` is one SPARQL Update request (`lens/lens.ts:400-515`); there is no unit of work across calls |
| T2–T11 | absent | No version guards, transactions, retries or idempotency (grep above) |
| E1–E9 | absent | — |
| U1 | absent | Not generated from a service contract |
| U2 | partial | No built-in cache; integration shown with TanStack Query (`examples/react-query-todo-app`) |
| U3–U10 | absent | U7: `update()` takes caller-stated changes, no graph diff (`lens/update_helper.ts`) |
| RAD3 | absent | — |
| RAD4 | n.a. | Client |
| X17 | n.a. | Client |
| X18 | absent | — |
| X19 | absent | No preconditions sent (`query_engine.ts` `query()` headers: accept and content-type only) |
| X20 | absent | take/skip only (`lens.ts:246-256`) |
| X21 | partial | Writes are sent as SPARQL Update bodies (`application/sparql-update`, `query_engine.ts`); this is the client side of the feature |
| X22 | absent | — |
| D11 | absent | The body is cancelled and only the status is reported (`engine/query_engine.ts:93-96`) |
| D12, D13 | absent | Generic `Error`s (`options.ts:83`, `update_helper.ts:169`) |
| S15–S19 | absent | — |

**Counts (102):** present 2, partial 10, absent 87, n.a. 3.

### Purpose and origin

- **Built for:** letting web developers read and write Linked Data as typed plain JS objects without learning SPARQL, against any SPARQL endpoint, from the browser, Deno or Node (README; ISWC 2023 paper title "Linked Data Object Graph Mapping Toolkit for Web Applications").
- **Who and context:** Karel Klíma, with co-authors Ruben Taelman (the Comunica author) and Martin Nečaský (`CITATION.cff`), in an academic-plus-open-source setting. CITATION version 2.4.0 (2025-05-21); repo activity to 2026-10.
- **Design angle:** client-first and zero-backend. The browser talks SPARQL directly, schema types are inferred and the bundle is small (its own ~160-LOC engine).
- **Where it fits:** **L5**, and only for **graph-direct reads (V5)**. Because it assumes a raw SPARQL Update endpoint, it does not fit any variant where domain rules and authorization run in the backend for writes. It fails DEC-5 (83 stars), so it is integrated behind a replaceable seam or used for ideas only.

### Variant fit

| Candidate | V1 | V2 | V3 | V4 | V5 | A | B | C |
|---|---|---|---|---|---|---|---|---|
| LDkit | not needed: the UI uses the generated OpenAPI client; mirror the Lens API in Python | n.a.: the UI speaks JSON:API / ember-data | supports reads through Fluree's SPARQL endpoint behind a thin proxy, with store-native policy and the identity forwarded via `fetch`; **blocks** domain rules if used for writes | supports reads on GraphDB with FGAC (token → user via proxy); same write caveat | **enables** graph-direct reads (its design point); needs a policy-filtered read endpoint plus a DEC-5 exception or a replaceable seam | neutral | **supports**: generate the LDkit schema from LinkML via `gen-shacl` → `shacl-to-schema` (or a direct generator, G16) | fits the spirit (one schema value interpreted at runtime), client side only |

### Corrections to the integrated docs

- `catalogue.adoc` and `libraries/ldkit.adoc:9`, "Karel Klíma (Charles University)": the affiliation is **not stated** in the repo (`CITATION.cff` lists names only). Verify it against the ISWC paper or drop it.
- `catalogue.adoc` LDkit fit "integrate" versus `angles/codegen.adoc`/`jsclient.adoc` "ideas": these are inconsistent. Given DEC-5 fail (83 stars), "integrate behind a replaceable seam (V5 only), otherwise ideas" should be stated in one way everywhere.
- Confirmed: `angles/jsclient.adoc:192` "LDkit … send no preconditions" (headers only accept and content-type).

### Proposed new features (round 4)

None. The new behaviours seen map to AZ19, G6, G16, G25, T1 and X21.

## Round 5

### (a) v4 cross-check (77 features)

Absences were confirmed by grep over `library/` for these terms, all with 0 hits: `migrat`, `version`, `If-Match|ETag`, `outbox`, `opentelemetry|traceparent`, `redact`, `did you mean`, `CURIE`, `mcp`. GitNexus `context(QueryBuilder)` shows one builder method per Lens call: no change-set value object, hooks or session.

| Id | Status | Evidence |
|---|---|---|
| B1, B2 | absent | Nesting (`@schema`) has no ownership semantics |
| B3 | partial | Root plus nested schemas are loaded in one CONSTRUCT and never lazily (`query_builder.ts:83-205` recursive `getShape`); the depth is the schema's, not an aggregate's |
| B4–B16 | absent | No unit of work, version, events, after-commit hooks or boundary-aware delete (`delete` removes `?s ?p ?o` only, `query_builder.ts:331-339`) |
| PG1 | absent | The tagged-template builder emits SPARQL only |
| PG2–PG4 | n.a. | — |
| EV1–EV9 | absent | — |
| AZ30–AZ36 | n.a. | Client library; enforcement is server-side (seam: AZ19 `fetch`) |
| G28 | n.a. | — |
| G29–G35 | absent | The generators document their supported subsets (`docs/components/schema-generators.md`) but emit no lossiness report |
| G36 | present | Typed filter and partial-update types are inferred per schema: `SchemaSearchInterface<T>`, `SchemaUpdateInterface<T>` (`schema/interface.ts`, `schema/search.ts`) |
| T12, T14 | absent | — |
| T13 | n.a. | Client |
| S20–S23 | absent | — |
| X23 | n.a. | No JSON-LD processing |
| X24 | absent | — |
| E10, I7, I8, P20 | absent | `$id` is caller-supplied and there is no flush ordering |
| U11 | absent | — |
| U12 | n.a. | — |
| U13 | partial | `insert(...entities)` / `update(...)` / `delete(...)` send one request for many entities (`lens/lens.ts:400-515`), but with no per-item results |
| D14 | absent | `insert` on an existing `$id` silently appends (`INSERT DATA`, `query_builder.ts:317`), which is exactly the hazard D14 should warn about |
| D15, D16 | absent | `logQuery` receives the full query including literal values (`options.ts:22`) |
| D17 | partial | `logQuery` callback shows the compiled SPARQL (`lens/lens.ts:108`); there is no compile-without-execute API |
| D18 | partial | On `update`, `undefined` means "not given" and `null` means "delete" for optional properties (`lens/update_helper.ts:47-77`); there is no load-side sentinel |
| D19–D25 | absent | Fixtures (Comunica + N3) are internal to `tests/` |
| D26 | present | Type-level assertions `assertTypeSafe<Equals<…>>` (`tests/schema.test.ts:210-211`) |
| D27 | absent | — |
| D28 | n.a. | — |
| D29 | absent | — |

**Counts (77):** present 2, partial 4, absent 56, n.a. 15.

### (b) Page review: `libraries/ldkit.adoc`

1. **Line 9**, "Ruben Taelman (the Comunica author)": the repo does not state this. Taelman is Comunica's lead developer, but "the author" overstates a multi-author project. **Fix:** "(lead developer of Comunica; not stated in the repo)".
2. **Line 135**, "M1 typed classes": misleading, because LDkit has **no classes**. The model is a TS schema literal with inferred interfaces. **Fix:** "M1 host-language model (TS schema literal, inferred types; no classes)".
3. **Missing caveat (variant fit V5, line 117):** the default engine **always POSTs** queries (`application/sparql-query` body, `engine/query_engine.ts` `query()`) and supports only **one source** (`getSparqlEndpoint` throws on more than one). The policy-filtered read endpoint or proxy for V5 must therefore parse POST bodies, and must not merely filter GET `?query=`. **Fix:** add to the V5 row: "the read proxy must accept and police POST `application/sparql-query` bodies; one endpoint per Lens."
4. **Missing caveat (line 87, "What to avoid"):** `Lens.find()` buffers the whole CONSTRUCT result before decoding (no streaming to the app), and `logQuery` exposes literal values, so it can leak personal data into logs. **Fix:** add both bullets.
5. **Line 15** (the verdict) and **line 107** (the integrate-for-V5 rule) match my evidence and the new uniform rule.

### (c) Final verdict and three things to remember

**Verdict: integrate for V5 graph-direct reads only, behind a replaceable seam (needs a DEC-5 exception); ideas otherwise.**

1. LDkit assumes a **raw SPARQL endpoint**. Use it for **reads** behind a policy-filtering proxy or store-native ACLs, and never for writes that must pass backend domain rules and validation.
2. **Silent-data footguns:** required-by-default properties drop entities from `find()`, `insert` merges duplicates, `delete` orphans blank nodes, the store's error body is discarded, and `take` defaults to 1000.
3. Its schema **can be generated from our LinkML model** (`gen-shacl` → `shacl-to-schema`, or a small direct generator). Its Lens API (`find/findByIri/count/insert/update/delete`, `$set/$add/$remove`) is the shape to mirror in Python.

### (e) New features

None.
