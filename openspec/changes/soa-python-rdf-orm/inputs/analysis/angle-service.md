# Angle: L4 data-management service / API layer (the "mu-cl-resources role")

Change: `soa-python-rdf-orm` · Round 3 · Analyst slug `angle-service` · Date 2026-11-03

**Question.** A UI app needs a data-management service over RDF/JSON-LD data. Which API styles exist, what can be *generated* from a LinkML/SHACL model, how do pagination, filters, includes and framing work, where does the PEP sit, how are changes notified, and which style(s) should an rdf-persistence-based service expose so it stays coherent with semantic.works (JSON:API) and with JSON-LD clients?

**Not repeated here.** mu-cl-resources (semantic-works.md §2–4), Prez (prez.md) and OldMan's Hydra/HTTP controller (oldman.md) are already analysed. They appear below only as comparison points.

**Deep dives (4):**
1. API Platform core: `/home/lps/work/repos/api-platform-core` @ `2f4ca71` (2026-11-02). 1,665 PHP files, 183k LOC.
2. Community Solid Server: `/home/lps/work/repos/CommunitySolidServer` @ `628cc42` (2026-11-02), v7.3.0, 505 TS files, 32k LOC. The clone and its GitNexus index already existed (1,228 files, 6,151 symbols, 289 processes). I did not re-index it and only queried it.
3. LinkedDataHub: `/home/lps/work/repos/LinkedDataHub` @ `a0687e4` (2026-11-02). 302 Java files (48.7k LOC) and 80 XSLT files. GitNexus: 7,994 nodes, 19,265 edges, 541 clusters, 300 flows.
4. linkml-store: `/home/lps/work/repos/linkml-store` @ `f19c1d9` (2026-09-20). 19.3k Python LOC. GitNexus: 2,717 nodes, 5,809 edges, 88 clusters, 226 flows.

**api-platform-core index.** `gitnexus analyze` was started but had not finished when this report was written. Its parse workers hit idle timeouts on the large PHP tree. All API Platform evidence below therefore comes from grep and Read on the source.

**Also read locally, without deep-diving:**
- the LinkML generators `openapigen.py`, `graphqlgen.py` and `jsonldcontextgen.py` (`/home/lps/work/repos/linkml` @ `d48b197`);
- the `fluree-db` crate list and `fluree-db-graphql/src/lib.rs` (existing clone `/home/lps/work/repos/fluree-db` @ `807902b`).

**Docs read (WebFetch):**
- api-platform.com/docs/admin/, /docs/create-client/, /docs/core/security/ (the last one only points elsewhere);
- graphdb.ontotext.com/documentation/11.0/graphql.html;
- docs.stardog.com/query-stardog/graphql;
- next.developers.flur.ee/docs/reference/http-api/;
- solidproject.org/TR/notifications-protocol;
- jsonapi.org/ext/atomic/;
- hydra-cg.com/spec/latest/core/;
- github.com/vemonet/rdflib-endpoint;
- github.com/benavlabs/fastcrud.

---

## 1. Landscape (desk scan)

Stars and last push come from `gh api repos/...` on 2026-11-03. Downloads are per month: PyPI from pypistats, npm from api.npmjs.org.

**Columns**
- **DEC-5:** pass means > 200★ and a commit within 12 months. "inh." means the candidate inherits a pass from its org or monorepo.
- **Layers:** L0 modelling, L3 authorization, L4 service/API, L5 JS client/UI, L6 events.

### Generic model-to-API platforms (non-RDF reference designs)

| Candidate | Repo | ★ | Last push | Licence | Lang | Downloads/mo | DEC-5 | Layers | Style |
|---|---|---|---|---|---|---|---|---|---|
| **API Platform core** | api-platform/core (monorepo api-platform/api-platform 9.2k★) | 2,580 | 2026-11-02 | MIT | PHP | – | pass | L0 L3 L4 L6 | JSON-LD+Hydra, JSON:API, HAL, GraphQL, OpenAPI, MCP, Mercure |
| API Platform Admin | api-platform/admin | 515 | 2026-09-10 | MIT | TS | 21.7k npm | pass | L5 | react-admin built from Hydra/OpenAPI docs |
| API Platform create-client | api-platform/create-client | 376 | 2025-12-27 | MIT | TS | 375 npm | pass | L5 | Next/Nuxt/React/Vue/Quasar/Vuetify/RN scaffolds from Hydra/OpenAPI |
| API Platform schema-generator | api-platform/schema-generator | 474 | 2026-06-29 | MIT | PHP | – | pass | L0 | RDF vocab (schema.org) or OpenAPI → PHP classes |
| PostgREST | PostgREST/postgrest | 27.7k | 2026-11-03 | MIT | Haskell | – | pass (pattern only) | L3 L4 | zero-code REST over a DB schema, PEP = DB row-level security |
| Hasura | hasura/graphql-engine | 32.1k | 2026-11-02 | Apache-2.0 | TS/Haskell | – | pass (pattern only) | L3 L4 L6 | zero-code GraphQL, permission rules as row filters, subscriptions |
| Neo4j GraphQL Library | neo4j/graphql | 549 | 2026-11-02 | Apache-2.0 | TS | 92k npm | pass (graph, not RDF) | L4 | SDL type defs → full CRUD GraphQL + `@authorization` directives |
| react-admin | marmelab/react-admin | 27.0k | 2026-11-02 | MIT | TS | – | pass | L5 | data-provider port (REST, JSON:API, GraphQL, Hydra providers) |
| JSON:API spec | json-api/json-api | 7.7k | 2026-10-04 | CC0 | spec | – | n.a. (standard) | L4 | JSON:API 1.1 + Atomic Operations ext |
| WarpDrive (ember-data) | warp-drive-data/warp-drive | 3.2k | 2026-11-02 | MIT | TS | 192k npm (`@warp-drive/core`) | pass | L5 | JSON:API cache/client (what mu-cl-resources targets) |

### Python API generators

| Candidate | Repo | ★ | Last push | Licence | Lang | Downloads/mo | DEC-5 | Layers | Style |
|---|---|---|---|---|---|---|---|---|---|
| FastAPI | fastapi/fastapi | 104k | 2026-11-02 | MIT | Py | – | pass | L4 | OpenAPI from Pydantic (already in MWBv2) |
| FastCRUD | benavlabs/fastcrud | 1,599 | 2026-10-12 | MIT | Py | 138k | pass | L4 | `crud_router` → CRUD endpoints. SQLAlchemy only, offset and cursor pagination, `__gte/__in` filters |
| fastapi-crudrouter | awtkns/fastapi-crudrouter | 1,698 | 2023-11-01 | MIT | Py | 7.6k | **fail** (stale) | L4 | generic CRUD routers per backend |
| FastAPI-JSONAPI | mts-ai/FastAPI-JSONAPI | 138 | 2025-04-07 | MIT | Py | 3.5k | **fail** | L4 | JSON:API on FastAPI + SQLAlchemy |
| Strawberry | strawberry-graphql/strawberry | 4,725 | 2026-11-02 | MIT | Py | – | pass | L4 | code-first GraphQL with Pydantic integration |
| Ariadne | mirumee/ariadne | 2,344 | 2026-10-07 | BSD-3 | Py | – | pass | L4 | schema-first GraphQL (could consume LinkML `gen-graphql` SDL) |
| Graphene | graphql-python/graphene | 8,237 | 2025-09-04 | MIT | Py | – | borderline (last push 14 months ago) | L4 | code-first GraphQL |
| **linkml-store** | linkml/linkml-store (org linkml 680★) | 27 | 2026-10-09 | MIT | Py | 10.4k | **inh. pass** | L1 L4 | generic LinkML collections API over duckdb/mongo/solr/neo4j…, FastAPI web API |
| LinkML generators | linkml/linkml | 680 | 2026-11-02 | Apache-2.0 | Py | – | pass | L0 | `gen-openapi` (components only), `gen-graphql` (types only), `gen-jsonld-context`, `gen-typescript`, `gen-shacl` |
| rdflib-endpoint | vemonet/rdflib-endpoint | 100 | 2026-07-23 | MIT | Py | 4.4k | **fail** | L4 | SPARQL endpoint for rdflib/Oxigraph in FastAPI (`SparqlRouter`), custom functions, no auth |
| Prez | RDFLib/prez | 40 | 2026-10-06 | BSD-3 | Py | – | inh. via RDFLib org? (see prez.md) | L4 | read-only LD API, profiles, CQL2 |
| pyLDAPI | RDFLib/pyLDAPI | 43 | 2025-01-18 | BSD-3 | Py | 78 | fail (stale) | L4 | conneg-by-profile helper (Prez predecessor) |
| grlc | CLARIAH/grlc | 151 | 2026-10-01 | MIT | Py | 130 | **fail** | L4 | SPARQL queries in git → OpenAPI endpoints |
| RAMOSE | opencitations/ramose | 33 | 2026-10-30 | ISC | Py | – | fail | L4 | SPARQL → REST from a config file |
| hydrus | HTTP-APIs/hydrus | 196 | 2023-02-16 | MIT | Py | 404 | **fail** (dormant) | L4 | Hydra server from API doc, SQLAlchemy store |
| hydra-python-core | HTTP-APIs/hydra-python-core | 15 | 2026-04-13 | MIT | Py | – | fail | L0 | Hydra API-doc writer/parser |

### LDP / Solid (standard read-write Linked Data)

| Candidate | Repo | ★ | Last push | Licence | Lang | Downloads/mo | DEC-5 | Layers | Style |
|---|---|---|---|---|---|---|---|---|---|
| **Community Solid Server** | CommunitySolidServer/CommunitySolidServer | 610 | 2026-11-02 | MIT | TS | 27k npm | pass | L2 L3 L4 L6 | LDP + Solid Protocol, WAC/ACP, Solid-OIDC, Solid Notifications |
| Trellis LDP | trellis-ldp/trellis | 110 | 2025-05-19 | Apache-2.0 | Java | – | **fail** (stale, < 200★) | L4 | LDP server (Memento, WebAC) |
| ldp4j | ldp4j/ldp4j | 46 | 2020-12-01 | Apache-2.0 | Java | – | fail | L4 | LDP framework |
| Inrupt solid-client | inrupt/solid-client-js | 244 | 2026-11-02 | MIT | TS | 69k npm | pass | L5 | Solid/LDP client |
| Solid Notifications spec | solid/notifications | 11 | 2026-08-04 | MIT | spec | – | n.a. (standard) | L6 | AS2 JSON-LD notifications, WebSocket/Webhook/StreamingHTTP channels |
| LDO | o-development/ldo | 73 | 2026-10-31 | MIT | TS | 634 | fail | L5 | ShEx → TS typings over Solid/RDF |

### Low-code knowledge-graph apps

| Candidate | Repo | ★ | Last push | Licence | Lang | Downloads/mo | DEC-5 | Layers | Style |
|---|---|---|---|---|---|---|---|---|---|
| **LinkedDataHub** | AtomGraph/LinkedDataHub | 636 | 2026-11-02 | Apache-2.0 | Java/XSLT | – | pass | L3 L4 L5 | GSP document graphs + SPARQL, ontology-driven forms (SaxonJS), WAC ACL as a SPARQL query |
| AtomGraph Processor | AtomGraph/Processor | 67 | 2023-07-10 | Apache-2.0 | Java | – | fail (archived) | L4 | LDT ontology-driven read-write LD server (LDH predecessor) |
| Sparnatural | sparna-git/Sparnatural | 315 | 2026-11-02 | LGPL-3.0 | TS | – | pass | L5 | SHACL-configured visual SPARQL query builder |

### GraphQL over RDF

| Candidate | Repo | ★ | Last push | Licence | Lang | Downloads/mo | DEC-5 | Layers | Style |
|---|---|---|---|---|---|---|---|---|---|
| HyperGraphQL | hypergraphql/hypergraphql | 170 | 2022-07-25 | Apache-2.0 | Java | – | **fail** (dormant) | L4 | GraphQL config → SPARQL, read-only |
| UltraGraphQL | (repo not found on GitHub) | – | – | – | – | – | fail | L4 | HyperGraphQL fork with mutations |
| OBG-gen | LiUSemWeb/OBG-gen | 17 | 2024-03-31 | Apache-2.0 | Py | – | fail | L4 | ontology → GraphQL server (OBDA) |
| GraphQL-LD.js | rubensworks/GraphQL-LD.js | 121 | 2026-08-18 | MIT | TS | – | fail (< 200★; Comunica org would qualify but the repo is personal) | L5 | GraphQL + JSON-LD context → SPARQL, client side |
| graphql-to-sparql.js | rubensworks/graphql-to-sparql.js | 116 | 2026-07-16 | MIT | TS | – | fail | L5 | same algebra translator |
| Stardog GraphQL | proprietary (docs) | – | – | commercial | – | – | n.a. | L3 L4 | schema-less, auto from RDFS/OWL or SHACL, explicit schemas. Mutations not documented on the query page |
| GraphDB GraphQL | proprietary (docs) | – | – | commercial (GraphQL licence for RBAC) | – | – | n.a. | L3 L4 | schema from OWL+SHACL or a "GraphQL SHACL model". RBAC per role controls reads and mutations |
| TopQuadrant SHACL / DASH GraphQL vocab | TopQuadrant/shacl | 247 | 2026-06-30 | Apache-2.0 | Java | – | pass | L0 | `datashapes.org/graphql#`, the shared SHACL→GraphQL curation vocabulary |

### DB-native JSON-LD APIs (the MWBv2 "front-end talks to DB" model)

| Candidate | Repo | ★ | Last push | Licence | Lang | Downloads/mo | DEC-5 | Layers | Style |
|---|---|---|---|---|---|---|---|---|---|
| **Fluree (v4, Rust)** | fluree/db | 477 | 2026-11-02 | **BUSL-1.1** (`Cargo.toml:65`) | Rust | – | pass on stars/activity; **licence is a new reservation** | L2 L3 L4 L6 | JSON-LD FlureeQL + SPARQL query/update + GraphQL (SHACL-tiered) + Cypher + MCP; identity/policy headers |
| Fluree server (Clojure, v3) | fluree/server | 21 | 2026-01-29 | none | Clojure | – | fail | L4 | legacy HTTP server |

### Hydra / JSON-LD clients (L5, for the contract choice)

| Candidate | Repo | ★ | Last push | Licence | Lang | Downloads/mo | DEC-5 | Layers |
|---|---|---|---|---|---|---|---|---|
| jsonld.js | digitalbazaar/jsonld.js | 1,817 | 2026-03-04 | BSD-3 | JS | 1.2M | pass | L5 |
| Alcaeus | hypermedia-app/Alcaeus | 65 | 2026-03-25 | MIT | TS | 1.5k | fail | L5 |
| LDflex | LDflex/LDflex | 196 | 2026-10-26 | MIT | JS | 1.7k | fail (just under) | L5 |
| Comunica | comunica/comunica | 620 | 2026-11-02 | MIT* | TS | 47k (`query-sparql`) | pass | L5 |

**Not deep-dived but relevant:**
- Ontop (1,009★) is a virtual KG with SPARQL only; it has no API generation.
- Zazuko Trifid (102★) and kopflos (16★) fail DEC-5. kopflos is a Hydra-driven API framework and is an idea source only.
- hey-api/openapi-ts (5.6k★) and graphql-code-generator (11.3k★) are the TS client generators a contract-first service would feed (L5).

---

## 2. API styles and what each costs the JS developer

The second column gives what the JS developer writes or uses. The third column is in-process code. Change notifications are in the last column.

| Style | JS developer writes / uses | Generated client tooling | Filter / page / include | Writes | PEP placement seen | Notifications | Cost to JS dev |
|---|---|---|---|---|---|---|---|
| **JSON:API** (mu-cl-resources, API Platform `JsonApi/`) | plain JSON. `type/id/attributes/relationships`; `included` is normalised | ember-data/WarpDrive, react-admin JSON:API providers, OpenAPI → TS | `filter[...]` (grammar is server-defined), `sort`, `include`, `fields[type]`, `page[...]`, links | POST/PATCH/DELETE per resource, relationship endpoints, **Atomic ext** for multi-op transactions with `lid` (jsonapi.org/ext/atomic) | proxy (mu) or per-operation (API Platform) | none in spec (mu: deltas + cache-clear) | **Lowest.** No RDF knowledge needed. IDs are opaque (UUID), not IRIs |
| **JSON-LD + Hydra** (API Platform default, OldMan) | JSON with `@id/@type/@context`; collections `hydra:member/totalItems/view/search` | api-doc-parser → **API Platform Admin** (react-admin) and **create-client** (7 frameworks), Alcaeus | `hydra:search` IriTemplate advertises filters (`CollectionFiltersNormalizer.php:115`), `PartialCollectionView` first/next/last, cursor variant (`PartialCollectionViewNormalizer.php:85-93`) | POST/PUT/PATCH (merge-patch+json)/DELETE | per-operation expression | Mercure SSE (`PublishMercureUpdatesListener.php:101-131`) | **Low.** Readable as JSON if the context is compact. IRIs are the IDs. Hydra docs drive generated UIs |
| **LDP / Solid** (CSS, Trellis) | documents and containers; RDF bodies (Turtle/JSON-LD); PATCH as N3 Patch or SPARQL Update | Inrupt solid-client, LDO (ShEx → TS) | containment listing only, **no server-side filter/sort/page** | PUT/POST/PATCH/DELETE on documents, `If-Match` ETags (`storage/conditions/BasicETagHandler.ts`) | HTTP handler before the store (`AuthorizingHttpHandler.ts:70-86`), WAC/ACP as data | **Solid Notifications** (AS2 JSON-LD over WebSocket/Webhook/StreamingHTTP; `server/notifications/*Channel2023`) | **High** for CRUD apps: the client must parse RDF and join documents itself. Good for personal-data pods |
| **GSP + SPARQL** (LinkedDataHub, Fuseki) | graph documents (GSP) for writes, SPARQL for lists and search | none generated; LDH ships its own XSLT client | SPARQL (the client writes queries) | GSP PUT/POST/PATCH(SPARQL Update)/DELETE with ETag/If-Match (`DocumentHierarchyGraphStoreImpl.java:518-948,1810`) | request filter evaluating a **SPARQL ACL query** over WAC data (`AuthorizationFilter.java:85-194`, `web.xml:61-104`) | none (LDH) | **High.** Needs SPARQL skills; a SPARQL client lib (Comunica, LDkit) moves the ORM into JS |
| **SPARQL-direct** (rdflib-endpoint, store endpoints) | SPARQL strings or a JS query builder | Comunica, LDkit, GraphQL-LD (client-side) | in the query | SPARQL Update | must be a **SPARQL-rewriting proxy** (sparql-parser) or store-native | store-specific | **Highest** server-side flexibility, highest JS cost, hardest to secure |
| **GraphQL** (Neo4j lib, Hasura; RDF: Stardog, GraphDB, Fluree v4, HyperGraphQL) | GraphQL documents | graphql-code-generator → TS types/hooks | `where`, `orderBy`, `limit/first/skip` (vendor-specific args) | mutations (GraphDB, Fluree "curated" tier only), not in HyperGraphQL | store RBAC (GraphDB), field directives (Neo4j), DB policy (Fluree) | subscriptions (Hasura, API Platform GraphQL via Mercure `GraphQl/Subscription/SubscriptionManager.php:33`) | **Low–medium.** Excellent TS DX, but no RDF standard for the schema except the DASH `graphql:` vocabulary; argument grammars differ per vendor |
| **FlureeQL-like JSON-LD query** (Fluree) | JSON-LD query/transaction documents (`select`, `where`, `insert/upsert/update`) | none; hand-written | in the query JSON | `insert/upsert/update` with JSON-LD bodies | **in-DB policy** keyed by `fluree-identity`/JWT headers (HTTP API docs) | ledger history | **Low–medium.** JSON-native, nested `@id` joins, but vendor lock-in (BUSL) and FE→DB coupling |

**Take-aways**
1. **JSON:API is cheapest for the JS developer, and it is what semantic.works speaks.**
2. **JSON-LD+Hydra is nearly as cheap** and is the only style with mature generic *generated* UIs from an RDF-aware contract (API Platform Admin, create-client).
3. **LDP/GSP/SPARQL push RDF work into the browser.**
4. **GraphQL has the best TS tooling but no portable RDF binding.** The DASH `graphql:` vocabulary is the closest thing: Fluree v4's `lib.rs:14-15` says it is "shared with TopBraid EDG and GraphDB".

---

## 3. Deep dive — API Platform core (contract reference)

### Architecture and implementation principles (evidence)

**Metadata is the single source.** PHP attributes `ApiResource`, `ApiProperty` and operations (`Get`, `GetCollection`, `Post`, `Put`, `Patch`, `Delete`, GraphQL `Query`/`Mutation`) are built into a resource metadata collection. Every format is a *projection* of that one metadata:
- `JsonLd/ContextBuilder.php:53-82` generates `@context` with `@vocab` pointing to the API docs and the `hydra:` prefix;
- `Hydra/Serializer/DocumentationNormalizer.php` produces `hydra:ApiDocumentation`;
- `OpenApi/`, `JsonSchema/` and `JsonApi/JsonSchema/SchemaFactory.php` generate the OpenAPI document and JSON Schemas;
- `GraphQl/Type/` builds the GraphQL types;
- `Mcp/` exposes MCP tools.

Properties can carry `jsonldContext` and `genId` (`Metadata/ApiProperty.php:115,211`), so a property can map to an RDF predicate IRI.

**State ports.** These are the key idea for rdf-persistence. The whole HTTP and GraphQL pipeline talks to persistence through two interfaces:
- `ProviderInterface::provide(Operation, uriVariables, context)` (`State/ProviderInterface.php`);
- `ProcessorInterface::process(data, Operation, uriVariables, context)` (`State/ProcessorInterface.php`).

Doctrine ORM/ODM, Elasticsearch and Laravel Eloquent are adapters. The request pipeline is a **decorator chain of providers and processors**:
- providers: `ContentNegotiationProvider → ReadProvider → DeserializeProvider → ParameterProvider → SecurityParameterProvider` (`State/Provider/`);
- processors: `WriteProcessor → SerializeProcessor → AddLinkHeaderProcessor → RespondProcessor` (`State/Processor/`).

An RDF backend would be one Provider and one Processor that delegate to an rdf-persistence repository. No such adapter exists in core (C7 = 0).

**PEP: four hook points, all in the service layer.** `Symfony/Security/State/AccessCheckerProvider.php` decorates the provider and evaluates an expression per operation at four stages:
- `security`, before or after the read;
- `securityPostDenormalize`, with `object` and `previous_object`;
- `securityPostValidation`;
- `securityAfterResolver`, for GraphQL.

It delegates to `ResourceAccessCheckerInterface`, the Symfony voters. `pre_read` is skipped when the expression does not use `object` (`ObjectVariableCheckerInterface`).

**Row-level filtering** is a *query extension*, not a post-filter: `Doctrine/Orm/Extension/QueryCollectionExtensionInterface::applyToCollection(QueryBuilder, …)` (`QueryCollectionExtensionInterface.php:26-33`) lets a policy add WHERE clauses before pagination and count. The MCP layer gets its own `Mcp/Security/PolicyAccessChecker.php`.

**Pagination**
- The default is cursor-or-page according to operation metadata (`State/Pagination/Pagination.php:199`), with the `itemsPerPage` parameter (l.39).
- Hydra `PartialCollectionView` gives first/last/prev/next or cursor links (`PartialCollectionViewNormalizer.php:53-93`).
- JSON:API uses `page[...]`, `include` and `fields[type]`. `JsonApi/State/JsonApiProvider.php:110-130` notes that "fields[TYPE] takes a resource TYPE while include takes a relation NAME". Sparse fieldsets are in `JsonApi/Filter/SparseFieldset.php`.

**Filters** are declared per resource (`ApiFilter`/`QueryParameter`) and advertised to clients as a `hydra:search` `IriTemplate` with mappings (`CollectionFiltersNormalizer.php:115-147`). Generated UIs therefore discover filters at runtime.

**Notifications: Mercure.** `PublishMercureUpdatesListener` hooks Doctrine `onFlush`/`postFlush` (l.101, 131) and publishes the serialised resource to topics, which are the resource IRI or expressions (`evaluateTopics` l.268-293). `private` updates are authorised by the Mercure hub's JWT (l.50-53, 322-324). GraphQL subscriptions ride on the same hub (`GraphQl/Subscription/SubscriptionManager.php`).

**JS side.** `@api-platform/api-doc-parser` reads Hydra or OpenAPI. Admin generates list/create/show/edit views, field types, required-field validation, pagination, filters, related records and Mercure live updates (api-platform.com/docs/admin/). create-client scaffolds 7 front-end frameworks from the same docs (api-platform.com/docs/create-client/).

### Patterns

| Pattern | Where |
|---|---|
| Metadata-driven multi-format projection | `Metadata/*` → `JsonLd/`, `Hydra/`, `JsonApi/`, `OpenApi/`, `GraphQl/`, `Mcp/` |
| Ports (Provider/Processor) + decorator pipeline | `State/ProviderInterface.php`, `State/Provider/*`, `State/Processor/*` |
| Policy-as-expression PEP at pipeline stages | `Symfony/Security/State/AccessCheckerProvider.php` |
| Query extension for row-level security (filter before paginate/count) | `Doctrine/Orm/Extension/QueryCollectionExtensionInterface.php` |
| Self-describing API (Hydra docs, `hydra:search`) → generic UI | `Hydra/Serializer/DocumentationNormalizer.php`, `CollectionFiltersNormalizer.php` |
| Outbox-like publish after flush | `PublishMercureUpdatesListener.php:101-131` |

### Scores (service angle)

| # | Score | Justification | Evidence |
|---|---|---|---|
| C1 | 5 | CRUD, relations, filters, pagination (page and cursor), JSON-LD in/out, validation, GraphQL, subscriptions | dirs above |
| C2 | 5 | clean ports, decorator pipeline, metadata as SSoT | `State/*Interface.php` |
| C3 | 4 | attributes + docs; heavy framework | docs site |
| C4 | 1 (for us) | PHP/Symfony; cannot be embedded in a Python stack | – |
| C5 | 3 | builds on Symfony Serializer, Doctrine, JSON Schema libs; no RDF library | `composer.json` |
| C6 | 4 | resource ≠ entity possible (DTOs, `ObjectMapper` providers) | `State/Provider/ObjectMapperProvider.php` |
| C7 | 0 | no SPARQL/RDF-store adapter | `ls src` (Doctrine, Elasticsearch, Laravel only) |
| C9 | 5 | JSON-LD, Hydra, JSON:API, HAL, OpenAPI 3.1, GraphQL, Mercure, MCP, Problem+JSON | `src/` top-level dirs |
| C10 | 4 | semver, monorepo split packages; large surface (183k LOC) | – |
| C8 | 5 | 2.6k★ (9.2k distribution), 326 `*Test.php` in `src/**/Tests`, daily commits | `find … -name '*Test.php'` |

**JS-friendliness:** best in class (Hydra plus OpenAPI → Admin and create-client).

**Verdict: borrow ideas (the contract) + integrate its JS tooling.** If an rdf-persistence service emits Hydra API docs, Hydra collections and an OpenAPI document shaped like API Platform's, Admin and create-client work against it unchanged. This was not tested; the claim rests on api-doc-parser's documented inputs.

---

## 4. Deep dive — Community Solid Server (LDP/Solid reference)

### Architecture and evidence

**Store chain.**
- The `ResourceStore` port (`storage/ResourceStore.ts:28-68`) has `getRepresentation`, `setRepresentation`, `addResource`, `deleteResource` and `modifyResource`. Each takes optional `Conditions`, so ETag/If-Match concurrency is built in (`storage/conditions/BasicETagHandler.ts`).
- GitNexus cypher on IMPLEMENTS/EXTENDS shows a decorator chain:
  - `PassthroughStore` is extended by `RepresentationConvertingStore`, `ReadOnlyStore`, `PatchingStore`, `IndexRepresentationStore` and `BinarySliceResourceStore`;
  - `MonitoringStore` (emits change events), `RoutingResourceStore` and `DataAccessorBasedStore` implement `ResourceStore`;
  - `DataAccessor` has five implementations: `SparqlDataAccessor`, `FileDataAccessor`, `InMemoryDataAccessor`, `PassthroughDataAccessor` and `SimpleDataAccessor`.
- The whole server is wired with Components.js JSON configs (`package.json` `componentsjs ^5.5.1`).

**SPARQL backend** (`storage/accessors/SparqlDataAccessor.ts`)
- One **named graph per LDP document**: `getData` CONSTRUCTs from `GRAPH <docIRI>` (l.70-76), metadata goes into `GRAPH <meta:docIRI>` (l.181), and containment triples sit in the parent's graph.
- Writes are DELETE-graph + INSERT built with **sparqljs `Generator`** (an AST, not strings; l.15) and sent through `fetch-sparql-endpoint` (l.3).
- It rejects quads outside the default graph (l.131-134): "Only triples in the default graph are supported". It works against any SPARQL 1.1 Query+Update endpoint.

**PEP pipeline.** `AuthorizingHttpHandler.ts:70-86` runs `credentialsExtractor` (Solid-OIDC/DPoP) → `modesExtractor` (which access modes the operation needs; there are dedicated `SparqlUpdateModesExtractor` and `N3PatchModesExtractor`) → `permissionReader` (`WebAclReader`, `AcpReader`, `OwnerPermissionReader`, `UnionPermissionReader`, `PathBasedReader`) → `authorizer` (`PermissionBasedAuthorizer`). Policies are RDF data: WAC `.acl` or ACP resources. This is the cleanest separation of PEP, PIP and PDP in this survey.

**PATCH:** N3 Patch and SPARQL Update (`storage/patch/N3Patcher.ts`, `SparqlUpdatePatcher.ts`).

**Notifications** (`server/notifications/`)
- `ActivityEmitter` + `ListeningActivityHandler` turn store `ChangeMap`s into AS2 activities.
- `generate/` produces Activity, Add/Remove, Delete and State notifications; `serialize/JsonLdNotificationSerializer.ts` serialises them.
- Channels: `WebSocketChannel2023`, `WebhookChannel2023` and `StreamingHttpChannel2023`.
- The spec features `startAt/endAt/state/rate/accept` (solidproject.org/TR/notifications-protocol) are confirmed by the `NotificationChannel.ts` fields. I checked the file list only.

**Gaps for a CRUD UI:** there are no typed resources, no server-side query, filter, sort or page over a class, and no schema/model. LDP is document-centric.

### Scores (service angle)

| # | Score | Justification | Evidence |
|---|---|---|---|
| C1 | 3 | document CRUD, PATCH, conditions, notifications; no class-level listing, filter or pagination; no validation by shape | `ResourceStore.ts`, `http/ldp/*Handler.ts` |
| C2 | 5 | ports + decorators + DI; PEP/PIP/PDP separated | GitNexus cypher above; `AuthorizingHttpHandler.ts` |
| C3 | 2 | operating it is easy; customising it means Components.js JSON graphs, a steep learning curve | `config/` |
| C4 | 2 | Node service; configuration-heavy | – |
| C5 | 5 | N3.js, sparqljs, fetch-sparql-endpoint, RDF/JS types | `SparqlDataAccessor.ts:1-15` |
| C6 | 1 | no domain model; documents not aggregates (though "document = aggregate" is a usable analogy) | – |
| C7 | 3 | any SPARQL 1.1 endpoint, but graph-per-document and default-graph-only content | `SparqlDataAccessor.ts:131-134` |
| C9 | 5 | LDP, Solid Protocol, WAC/ACP, Solid-OIDC, Notifications, RDF/JS | – |
| C10 | 3 | v7.3.0 semver, active; large config surface | `package.json:3` |
| C8 | 5 | 610★, 27k npm/mo, large unit and integration test suite, Inrupt/imec backing | `test/` |

**Verdict: borrow ideas; integrate only when a Solid pod interface is itself a requirement.** Ideas to borrow:
1. the credentials → modes → permission readers → authorizer pipeline, as the shape of the rdf-persistence PEP hook;
2. ETag/If-Match `Conditions` on every write, to answer P5;
3. Solid Notifications as an *open-standard* notification contract (L6), fed by X12 deltas;
4. N3 Patch as a standard RDF patch body.

---

## 5. Deep dive — LinkedDataHub (low-code KG app platform)

### Architecture and evidence

- **Writes are GSP on document graphs.** `server/model/impl/DocumentHierarchyGraphStoreImpl.java` implements GET/POST/PUT/PATCH(SPARQL `UpdateRequest`)/DELETE (l.347-948) against the dataspace's Graph Store (`GraphStoreClient`, l.26, 232, 465), and `SPARQLEndpointImpl.java` serves queries.
- **Concurrency.** ETags and `If-Match` follow RFC 9110 (l.409, 456, 586, `evaluatePreconditions` l.1810). The README "Formal verification" section claims "A write guarded by `If-Match` loses no update", with models under `formal/http/` and `formal/acl/`. The models exist; I did not check them.
- **Validation.** `server/io/ValidatingModelProvider.java` checks incoming RDF with SPIN constraints (l.50-54, 210-244). jena-shacl is a dependency (README l.401), and three Java files reference SHACL.
- **The PEP is a JAX-RS request filter whose policy is a SPARQL query over ACL data.** `AuthorizationFilter.java:85-194` loads `aclQuery`, a `DESCRIBE ?auth` over WAC `acl:Authorization` triples (`acl:accessTo`, `acl:default`, `acl:accessToClass` with `rdfs:subClassOf*`, `acl:agent`, `acl:agentGroup`, `acl:agentClass`). The query is configured in `WEB-INF/web.xml:61-104`, with a "fail-closed default" `VALUES` row (l.101-103). A grant of `acl:Write` covers `acl:Append` (`AuthorizationFilter.java:247`).
- **Identity and other features.** Authentication uses WebID/client certificates and OIDC (Google, ORCID; `resource/oauth2/`). Admin and end-user dataspaces are split, and Memento versioning is provided.
- **UI.** The client is ontology-driven: XSLT templates run in SaxonJS (`static/.../xsl/*.xsl`, 80 files) and render forms from class/constructor definitions. I did not trace how a form is derived from an ontology class. GitNexus query "authorization filter ACL query agent" returns the `Authorize → SolutionMapToMultivaluedMap` flow and HTTP tests such as `authorizationCountsOnlyInItsOwnDocument`.

### Scores

| # | Score | Justification | Evidence |
|---|---|---|---|
| C1 | 4 | CRUD on documents, SPARQL, ETag, validation, versioning, ACL; no JSON-friendly typed API | `DocumentHierarchyGraphStoreImpl.java` |
| C2 | 4 | filters, GSP resource, config-as-SPARQL | `AuthorizationFilter.java` |
| C3 | 2 | XSLT/SaxonJS is a niche skill for JS teams | `static/**/*.xsl` |
| C4 | 2 | Docker stack (Tomcat, Fuseki-like store, nginx, secrets) | `docker-compose.yml`, README l.63 |
| C5 | 4 | Apache Jena, jena-shacl | README l.401 |
| C6 | 3 | ontology-driven, but document-centric and no codegen | – |
| C7 | 4 | GSP + SPARQL 1.1 against the dataspace service (claimed portable; only `GraphStoreClient` and a Sesame-protocol client were seen) | `AuthorizationFilter.java:280` |
| C9 | 4 | GSP, SPARQL, WAC, WebID, OIDC, Memento; no JSON:API/OpenAPI | – |
| C10 | 3 | single-vendor (AtomGraph), active; formal models are a plus | README l.371-380 |
| C8 | 4 | HTTP test suite + formal CI; small team | `tests/http`, `formal/` |

**Verdict: borrow ideas.** The strongest DEC-8-shaped idea in this angle is **ACL as RDF data (WAC vocabulary) + a declarative SPARQL policy query evaluated by the PEP, configurable and fail-closed**. That is exactly the "SPARQL-like, data-centric policy language" preference. Also borrow:
- GSP document-graph CRUD as the low-level write contract;
- ETag/If-Match semantics;
- formal models of the HTTP and ACL contract.

Do not adopt the XSLT UI.

---

## 6. Deep dive — linkml-store (the LinkML-native API generator)

### Architecture and evidence

- The **port is `Client → Database → Collection`**. `api/collection.py` provides `insert` (l.197), `upsert` (234), `delete` (297), `delete_where` (330), `update` (362), `query` (375), `query_facets` (400), `find` (460) and `find_iter` (506).
- Backends live in `api/stores/`: chromadb, dremio, duckdb, filesystem, hdf5, ibis, mongodb, neo4j and solr. `grep -i "sparql|oxigraph|rdflib"` over `src/` finds **no RDF or SPARQL backend**. RDF appears only as an import format (`utils/format_utils.py:37-38, 261` uses lightrdf).
- **The web API is generic, not per class.** `webapi/main.py` exposes `/databases/{db}/collections/{c}/objects` (GET with `where` JSON, `limit` 1..100 and `offset`, l.321-390), objects by id, search, facets, attributes, schema, and POST insert (l.709-725).
- It has **no PUT, PATCH or DELETE routes** and **no auth dependency**: the only `Depends` are `get_client`/`get_database`, l.120-144.
- Each listing response carries HAL-like `links` (self/prev/next/first/last/parent) and `meta.item_count`. The total is computed with a full `collection.find({})` (l.351), which is costly on large stores.
- GitNexus processes: `Import_database → Insert / Delete_where / Create_collection`.

### Scores

| # | Score | Justification | Evidence |
|---|---|---|---|
| C1 | 2 | generic CRUD in Python; HTTP is read + insert only; no relations/includes | `webapi/main.py` routes |
| C2 | 3 | adapter-per-backend port | `api/stores/*` |
| C3 | 4 | LinkML-native, CLI and docs | – |
| C4 | 4 | pip install, FastAPI | – |
| C5 | 4 | LinkML runtime, pydantic, FastAPI | – |
| C6 | 4 | schema-first collections | – |
| C7 | 0 | no SPARQL backend | grep result |
| C9 | 2 | no JSON-LD out, no OpenAPI shaping beyond FastAPI defaults, no auth | `main.py:120-144` |
| C10 | 3 | 27★ (inherits LinkML org), 10k downloads/mo | – |
| C8 | 3 | 25 test files | `tests/` |

**Verdict: borrow ideas; optional integration later.** A `sparql`/`rdf-persistence` store adapter for linkml-store would give LinkML users a uniform Python API over RDF at low cost. But linkml-store's HTTP API is not a model for the UI service: it is generic, insert-only and has no auth.

---

## 7. What can be GENERATED from LinkML / SHACL today (and what is missing)

| Artifact | Generator today | State | Evidence |
|---|---|---|---|
| Pydantic domain classes | `gen-pydantic` | mature | linkml `generators/pydanticgen/` |
| JSON-LD `@context` (API field names ↔ IRIs) | `gen-jsonld-context` | mature, 621 LOC | `jsonldcontextgen.py` |
| JSON Schema → OpenAPI `components` | `gen-openapi` | **components only.** "composes a user-provided OpenAPI template (containing … paths/endpoints, and security schemes)" | `openapigen.py:96-120` |
| GraphQL SDL | `gen-graphql` | **types only** (121 LOC); no Query/Mutation, filter inputs or pagination | `graphqlgen.py` |
| TypeScript interfaces | `gen-typescript` | weak (MWBv2 digest: no enums, `uri`→string) | `typescriptgen.py` (340 LOC) |
| SHACL shapes | `gen-shacl` | mature | `shaclgen.py` |
| CRUD routes / JSON:API resource config / Hydra API doc | **none** in LinkML | gap | – |
| GraphQL schema from SHACL | Stardog, GraphDB, Fluree v4 (`datashapes.org/graphql#` curation tier enables mutations) | vendor | Fluree `fluree-db-graphql/src/lib.rs:1-24` |
| UI (admin) from API docs | API Platform Admin (Hydra/OpenAPI), react-admin | mature | api-platform.com/docs/admin/ |
| TS client from OpenAPI | hey-api/openapi-ts, openapi-generator | mature | – |

**Implication.** The missing link in the MWBv2 chain is a **LinkML → service generator**. It should emit the routes (JSON:API and JSON-LD/Hydra profiles), the filter/sort/include grammar per class, the relationship endpoints and the API docs (OpenAPI with paths, Hydra `ApiDocumentation`, optionally mu `domain.json`). It is configured by LinkML annotations: exposed classes, read-only slots and filterable slots. The ingredients exist in pieces: FastAPI's OpenAPI, `gen-jsonld-context` and `gen-pydantic`.

---

## 8. Patterns catalogue (angle)

| Pattern | Seen in | Use for rdf-persistence |
|---|---|---|
| **Model metadata → many projections** (one resource model; JSON:API, JSON-LD/Hydra, OpenAPI, GraphQL as views) | API Platform | the generated service builds one resource registry from LinkML and renders several profiles |
| **Provider/Processor ports** between the HTTP pipeline and persistence | API Platform `State/` | the service calls rdf-persistence repositories through exactly two ports; easy to fake in tests |
| **Decorator store chain** (converting, patching, read-only, monitoring, routing) | CSS `storage/` | wrap the repository/store with monitoring (deltas), read-only and auth-filter decorators |
| **PEP at the HTTP edge** (credentials → required modes → permissions → decision) | CSS `AuthorizingHttpHandler`, LDH `AuthorizationFilter` | a FastAPI dependency that asks a pluggable PDP (DEC-8: borrowed engine) |
| **Policy as data + declarative query** | LDH `aclQuery` (WAC + SPARQL), Fluree policies, GraphDB RBAC | strongest DEC-8 fit; PDP evaluates SPARQL ASK/DESCRIBE over ACL graphs |
| **Policy as pre-pagination query filter** | API Platform `QueryCollectionExtensionInterface`, PostgREST/Hasura row rules, sparql-parser graph rewrite | a **query-filter hook** on rdf-persistence listing queries; post-filtering breaks counts and pages |
| **PEP as SPARQL-rewriting proxy** | semantic.works sparql-parser | ACL-agnostic mode: the service forwards request context (X13) and the proxy decides |
| **Self-describing API → generic UI** | Hydra docs + `hydra:search` → API Platform Admin | emit Hydra docs so Admin/create-client work |
| **Conditional writes (ETag/If-Match)** | CSS `conditions/`, LDH GSP | optimistic concurrency at the API (P5) |
| **Multi-operation atomic request with local ids** | JSON:API Atomic ext (`lid`) | maps 1:1 onto a rdf-persistence Unit of Work commit |
| **Publish-after-flush** | API Platform Mercure listener | emit notifications from the UoW commit (outbox), not from handlers |
| **Standard notification envelope** | Solid Notifications (AS2 JSON-LD), Mercure SSE, mu deltas | one internal delta (X12) rendered to 1+ channels |
| **Tiered schema exposure** (inferred → shaped → curated; mutations only when curated) | Fluree v4 GraphQL | a safe default for generated APIs: read-only unless the model opts in |

---

## 9. How each option plugs into the MWBv2 chain and an ACL-agnostic rdf-persistence

MWBv2 chain: UML → model2owl → **LinkML** → generated Python (domain + persistence + authz) → **generated data-management service** → TS UI (JSON-LD).

| Option | Plugs in at | ACL-agnostic? | Notes |
|---|---|---|---|
| Own **Python resource service** (FastAPI) generated from LinkML, using rdf-persistence repositories through Provider/Processor-like ports | L4 | yes. PEP is a FastAPI dependency calling a pluggable PDP; query-filter hook for row level; context headers (X13) for proxy mode | the recommended core; borrows the API Platform shape and the mu-cl-resources dialect |
| API Platform Admin / create-client | L5, reading our Hydra + OpenAPI | n.a. | integrate (no code from us beyond emitting docs) |
| react-admin / WarpDrive | L5, reading JSON:API | n.a. | integrate |
| semantic.works sparql-parser + delta-notifier | below rdf-persistence (L3/L6) | yes (proxy) | compatible if rdf-persistence does not rely on GRAPH clauses (A2) |
| CSS | beside, as a Solid pod | own WAC/ACP | only for pod use cases; borrow notifications and conditions |
| LDH | beside, as a low-code admin | own WAC + SPARQL policy | idea source for the PDP policy language |
| Fluree v4 | L2 store + L3 policy + L4 API in one | no: the policy is DB-native, so the persistence code ties itself to Fluree headers | **BUSL-1.1** is a new reservation on top of the MWBv2 digest; SPARQL query/update now exists (`fluree-db-server/src/extract/credential.rs:90,168`), which softens the old "no SPARQL" loss. Verify separately |
| GraphDB/Stardog GraphQL | L4 by the store | store RBAC | commercial licence; GraphQL schema from SHACL; not portable |
| rdflib-endpoint | L4 (SPARQL-direct, dev/test) | no auth | fails DEC-5; acceptable as a dev fixture or idea |

---

## 10. Architecture variants enabled

**V-S1 "semantic.works-compatible Python resources"**
- Shape: browser → identifier/dispatcher (or any gateway with OIDC) → **generated Python resource service (JSON:API, mu dialect)** → rdf-persistence → sparql-parser (PEP + deltas) → triplestore.
- Ember/WarpDrive or react-admin front-ends work unchanged.
- The authorization lives entirely in the proxy, so the service is ACL-agnostic.

**V-S2 "API-Platform-shaped standalone service"**
- Shape: browser → gateway (Zitadel/OIDC) → generated FastAPI service exposing **JSON-LD+Hydra** (default) and **JSON:API** (profile), with an in-process PEP (FastAPI dependency → PDP) and a query-filter hook → rdf-persistence → any SPARQL 1.1 store.
- Notifications: UoW deltas → Mercure/SSE or Solid Notifications.
- API Platform Admin gives a zero-code back office.

**V-S3 "DB-native JSON-LD"** (MWBv2 runbook model): the TS UI talks to Fluree (FlureeQL/GraphQL) through a thin proxy. It is fastest to start but brings lock-in, a BUSL licence, and rdf-persistence is bypassed for the UI path.

**V-S4 "SPARQL-direct + JS ORM":** the UI uses LDkit/Comunica against a SPARQL endpoint behind a SPARQL-rewriting PEP. It needs the least server code and the most JS/RDF skill, and the backend domain rules are bypassed.

**V-S5 "Solid pod":** CSS with a SPARQL backend; document-centric, for personal-data scenarios only.

---

## 11. Recommendation (API styles to expose)

1. **Primary: JSON:API in the mu-cl-resources dialect**: `filter[...]` with `:exact:/:gt:/:id:/:uri:/:has:`, `sort`, `include`, `fields`, `page[number|size]`, `meta.count`. This keeps it coherent with semantic.works and is the cheapest contract for JS developers (WarpDrive, react-admin). Add the **JSON:API Atomic Operations** extension mapped to one rdf-persistence Unit of Work. It is the only standard multi-resource transactional write found in this angle.
2. **Second representation: JSON-LD**, selected by content negotiation on the *same* routes (`application/ld+json`, optional `profile=`).
   - Use a compact form with the LinkML-generated `@context`, IRIs as `@id`, and optional framing per resource "view" (Prez/OldMan ideas).
   - Wrap collections in **Hydra** `Collection`/`PartialCollectionView`/`search`, and publish a Hydra `ApiDocumentation` plus a full OpenAPI.
   - This is what JSON-LD clients and API Platform Admin/create-client expect, at small extra cost because both views come from one resource registry.
3. **SPARQL 1.1 protocol**: offer it as a *read* escape hatch behind the same PEP, or proxy-rewritten. Do not offer a generated write API over SPARQL.
4. **GraphQL: defer.** If it is needed, generate it from the same registry, following the DASH `graphql:` curation vocabulary (shared by TopBraid, GraphDB and Fluree), so a later move to a store-native GraphQL stays possible. Python runtime: Strawberry or Ariadne (both pass DEC-5).
5. **LDP/Solid: do not expose.** Borrow ETag/If-Match and the Solid Notifications envelope.
6. **Notifications:** emit internal deltas from the UoW commit (X12 format) and render them as (a) mu delta POSTs for semantic.works compatibility and (b) SSE/Mercure-compatible or Solid WebSocket/Webhook channels for browsers. Authorise subscriptions with the same PEP.
7. **PEP placement** (DEC-8, ACL-agnostic). Offer three seams and implement none of the policy logic:
   - (a) a request-context pass-through (X13) for proxy mode;
   - (b) an endpoint-level PEP hook (pre-read, post-denormalize, post-validate) calling an external PDP;
   - (c) a **listing-query filter hook** so row- or graph-level policies are applied before pagination and count.

---

## Feature inventory (deep-dived candidates, service-relevant ids)

Values: Y present · P partial · N absent · n.a. not applicable.

| Id | API Platform | CSS | LDH | linkml-store | Evidence |
|---|---|---|---|---|---|
| P1 CRUD | Y | Y (documents) | Y (documents) | P (no HTTP update/delete) | §3–6 |
| P4 transactions | P (Doctrine flush per request) | N | N | N | – |
| P5 optimistic concurrency | P (HttpCache/ETag; not traced) | Y `conditions/` | Y `If-Match` l.586 | N | – |
| P6 named graphs | n.a. | Y graph per document | Y graph per document | N | `SparqlDataAccessor.ts:181` |
| Q4 pagination | Y page+cursor | N | via SPARQL | Y offset | `Pagination.php:199`; `main.py:321` |
| Q14 standard filter language | P (own filters, advertised via `hydra:search`) | N | SPARQL | P (`where` JSON) | `CollectionFiltersNormalizer.php:115` |
| Q15 totals/counts | Y `hydra:totalItems` | N | N | Y (full scan) | `main.py:351` |
| Q9 includes / N+1 avoidance | Y (JSON:API include, eager loading ext) | N | N | N | `JsonApiProvider.php:121` |
| X1 JSON-LD in/out | Y | Y | Y | N | `JsonLd/` |
| X3 HTTP API | Y | Y (LDP) | Y (GSP) | Y | – |
| X4 schema export | Y OpenAPI, JSON Schema, Hydra, GraphQL | P (storage description) | N | P (FastAPI OpenAPI) | – |
| X5/X12 change notifications | Y Mercure | Y Solid Notifications | N | N | §3, §4 |
| X6 JSON:API contract | Y | N | N | N | `JsonApi/` |
| X7 content negotiation | Y | Y | Y | N | – |
| X8 hypermedia (Hydra) | Y | N | N | P (links) | `Hydra/` |
| X16 standard API profile conformance | Y (JSON:API, Hydra) | Y (Solid, LDP) | Y (GSP, Memento) | N | – |
| A1 authorization hooks | Y expression PEP at 4 stages | Y full PEP/PDP | Y SPARQL ACL query | N | §3–5 |
| A2 auth-proxy compatible | n.a. | N (expects own graphs) | N | n.a. | – |
| A3 field-level access | Y (property `security`, not traced) | N | N | N | – |

### Proposed new features

| Proposed id | Area | Feature | Seen in |
|---|---|---|---|
| RAD1 | RAD | Zero-code resource service generated from the model (confirms semantic-works RAD1) | mu-cl-resources, API Platform, Neo4j GraphQL |
| RAD3 | RAD | **Generic admin UI from self-describing API docs** (Hydra/OpenAPI → react-admin CRUD screens) | API Platform Admin |
| RAD4 | RAD | **Front-end scaffold generation** from API docs (Next/Nuxt/React/Vue…) | API Platform create-client |
| RAD5 | RAD | **Tiered exposure**: read-only by default, mutations only for curated/opted-in classes | Fluree v4 GraphQL tiers |
| G1 | Generation | **LinkML → service routes** (paths, operations, relationship endpoints), not just components | gap (LinkML `openapigen.py` needs a hand-written template) |
| G2 | Generation | **LinkML → Hydra `ApiDocumentation`** (supportedClass/Property/Operation, `hydra:search` templates) | API Platform `DocumentationNormalizer` |
| G3 | Generation | **SHACL/LinkML → GraphQL schema with queries, filters and mutations** using the DASH `graphql:` vocabulary | Fluree v4, GraphDB, Stardog, TopBraid |
| G4 | Generation | **Per-class filter/sort/include grammar** generated from slot annotations (filterable, sortable, includable) | API Platform `ApiFilter`, mu-cl-resources |
| G5 | Generation | **TS client generation from the service contract** (OpenAPI → TS, GraphQL → TS) | hey-api, graphql-code-generator |
| X17 | Interop | **Multi-profile rendering from one resource registry** (JSON:API + JSON-LD/Hydra + OpenAPI + GraphQL views of the same metadata) | API Platform |
| X18 | Interop | **Atomic multi-operation write** with client-local ids (JSON:API Atomic ext) mapped to one UoW | jsonapi.org/ext/atomic |
| X19 | Interop | **Conditional requests** (ETag / If-Match / 412) on resource writes | CSS, LDH |
| X20 | Interop | **Standard notification channels** (Solid Notifications AS2 JSON-LD over WebSocket/Webhook/SSE; Mercure) — channel for X12 | CSS, API Platform |
| X21 | Interop | **Publish-after-commit** (notifications emitted only after successful flush/commit; outbox) | API Platform Mercure listener |
| X22 | Interop | **Cursor pagination** alongside page/offset | API Platform, FastCRUD |
| X23 | Interop | **RDF patch bodies** (N3 Patch, SPARQL Update, JSON merge-patch) on resources | CSS, LDH, API Platform |
| AZ-S1 | Access | **Staged PEP hooks** (pre-read, post-read, post-denormalize, post-validate) in the service pipeline | API Platform `AccessCheckerProvider` |
| AZ-S2 | Access | **Listing-query policy filter hook** (policy adds patterns before pagination/count; no post-filtering) | API Platform Doctrine extensions, Hasura, PostgREST, sparql-parser |
| AZ-S3 | Access | **ACL as RDF data with a declarative SPARQL policy query, fail-closed** | LinkedDataHub `aclQuery`, CSS WAC/ACP |
| AZ-S4 | Access | **Separated PEP/PIP/PDP pipeline** (credentials → required modes → permission readers → authorizer) | CSS `AuthorizingHttpHandler` |
| E-S1 | Events | **Authorised subscriptions** (private topics/channels checked by the same PEP/JWT) | Mercure `private`, Solid Notifications |

---

## Open questions

1. Should the JSON:API profile use **UUID ids** (mu dialect, `mu:uuid`) or **IRIs as ids**? IRIs would keep it aligned with JSON-LD, but existing semantic.works front-ends would break.
2. Is **API Platform Admin compatibility** a goal? If so, how far should the Hydra output follow API Platform's quirks (`@vocab` pointing to the API doc, `hydra:` prefix toggle)?
3. **Fluree v4**: BUSL-1.1 licence, the new SPARQL Update and SHACL-tiered GraphQL. Does this change the MWBv2 "accepted with reservations" verdict? A separate check is needed: the local clone shows the crates, but I did not test them.
4. **Row-level policies.** Does the chosen PDP (another angle) return a *filter* (query patterns or graph list) or only allow/deny? Only a filter supports correct paginated listings (AZ-S2).
5. **Notification channel.** Mercure (SSE, a simple hub, JWT) or Solid Notifications (standard, heavier) for the browser? And should mu delta POSTs be kept for back-end services?
6. Is GraphQL needed in MWBv2 at all, given that the runbook asked for "GraphQL-like freedom"? JSON:API `include` + `fields` may cover it.

**Not checked**
- I ran no candidate code (per brief).
- The api-platform-core GitNexus index was still building.
- I did not trace API Platform property-level `security` or HttpCache ETags.
- I did not read the LDH form-generation XSLT in detail.
- CSS notification feature fields were checked only from the file listing.
- I did not visit the GraphDB/Stardog mutation docs pages beyond the overview.
- Fluree claims come from crate names, `lib.rs` and HTTP-API docs only.

---

## Round 4

Analyst: angle-service · 2026-11-03 · Brief: `BRIEF-round4.md`.

**Columns and evidence roots**
- AP = API Platform core (`/home/lps/work/repos/api-platform-core/src`), GitNexus repo name **`core`**. The index is up to date at `2f4ca71` (`gitnexus status`).
- CSS = Community Solid Server (`.../CommunitySolidServer/src`), GitNexus `CommunitySolidServer`.
- LDH = LinkedDataHub (`.../LinkedDataHub/src/main/java/com/atomgraph/linkeddatahub`), GitNexus `LinkedDataHub`.
- LS = linkml-store (`.../linkml-store/src/linkml_store`), GitNexus `linkml-store`.
- Values: **Y** present · **P** partial · **N** absent · **n.a.** not applicable (the tool is not that kind of component).
- Absences were confirmed with grep or GitNexus where noted.

### (0) Round-3 code claims re-checked with the finished `core` index

**Confirmed**
- *ProviderInterface implementers.* GitNexus cypher (IMPLEMENTS `ProviderInterface`) lists persistence adapters only for Doctrine ORM, Doctrine ODM, Elasticsearch and Laravel Eloquent (`src/Doctrine/{Orm,Odm}/State/{Item,Collection}Provider.php`, `src/Elasticsearch/State/*`, `src/Laravel/Eloquent/State/*`). There is **no RDF/SPARQL provider**, so C7 = 0 stands. `docs/guides/hook-a-persistence-layer-with-a-processor.php` and `provide-the-resource-state.php` show that a custom backend is a supported extension point.
- *ProcessorInterface implementers* include `WriteProcessor`, `SerializeProcessor`, `RespondProcessor`, `AddLinkHeaderProcessor`, `HydraLinkProcessor`, `MercureLinkProcessor`, `Doctrine/Common/State/{Persist,Remove}Processor`, `GraphQl/State/Processor/SubscriptionProcessor` and `Mcp/State/StructuredContentProcessor`. The two-port claim is confirmed.
- *Access checkers.* `ResourceAccessCheckerInterface` has exactly two implementations: Symfony and Laravel `ResourceAccessChecker`. `AccessCheckerProvider` exists in both stacks.
- *Property-level security.* It exists: `Serializer/AbstractItemNormalizer.php:527-540` `canAccessAttribute` evaluates `ApiProperty::security`/`policy` with the object. `isCacheKeySafe` (l.548-551) disables normaliser caching when a property is secured.
- *Test count.* There are 387 more `*Test.php` files under the top-level `tests/`, in addition to the 326 under `src/**/Tests`. C8 = 5 stands.

**Corrected**
1. **Row-level security is a hook, not a feature.** GitNexus lists exactly five implementers of `QueryCollectionExtensionInterface` in core: `FilterExtension`, `OrderExtension`, `EagerLoadingExtension`, `FilterEagerLoadingExtension` and `ParameterExtension`. **None is a security extension.** The row-level policy filter is a *documented user pattern*: `CurrentUserExtension` implementing `QueryCollectionExtensionInterface` + `QueryItemExtensionInterface` (api-platform.com/docs/core/extensions/). The round-3 sentence "row-level filtering is a query extension" is right about the *seam* only.
2. **There are no write preconditions.** `HttpCache/State/AddHeadersProcessor.php:34,66` only *emits* a response ETag (`xxh3` of the body, opt-in). grep for `If-Match` / `PreconditionFailed` / `isNotModified` in `src/` (excluding tests) finds nothing else. API Platform core has no optimistic-concurrency check on PUT/PATCH; Doctrine `@Version` would be the backend's job.
3. **No JSON:API Atomic Operations.** grep for `atomic` / `ext/atomic` in `src/` finds nothing. API Platform's JSON:API covers include, fields, page and filter only (`JsonApi/State/JsonApiProvider.php:110-130`).

### (a) v3 cross-check

| Id | AP | CSS | LDH | LS | Evidence |
|---|---|---|---|---|---|
| AZ1 store-boundary scope decorator | N | N | N | N | AP: PEP in the State pipeline, not the store (GitNexus: only `AccessCheckerProvider` decorates). CSS: `AuthorizingHttpHandler.ts:70-86` at the HTTP edge; stores undecorated (GitNexus store chain has no auth store). LDH: JAX-RS `AuthorizationFilter.java:65`. LS: no auth (`webapi/main.py:120-144`) |
| AZ2 policy injected before pagination/count | P | n.a. | N | N | AP: hook only (`Doctrine/Orm/Extension/QueryCollectionExtensionInterface.php:26-33`; user `CurrentUserExtension` per docs). CSS: no listings. LDH: SPARQL endpoint not rewritten (`SPARQLEndpointImpl.java:72`, queries only) |
| AZ3 rewriting PEP on typed AST | P | N | N | N | AP: extensions add to a typed Doctrine `QueryBuilder` (DQL, not SPARQL) |
| AZ4 PDP list/plan integration | N | N | N | N | no PDP client in any (grep `openfga|spicedb|cerbos|opa`: none) |
| AZ5 write authz on the changeset | P | P | P | N | AP: `securityPostDenormalize` with `object` + `previous_object` (`AccessCheckerProvider.php`). CSS: modes derived from patch content (`authorization/permissions/SparqlUpdateModesExtractor.ts`, `N3PatchModesExtractor.ts`, `IntermediateCreateExtractor.ts`). LDH: Append vs Write by method (`AuthorizationFilter.java:247`) |
| AZ6 staged PEP hooks | Y | P | N | N | AP: pre_read / post_denormalize / post_validate / after_resolver (`Symfony/Security/State/AccessCheckerProvider.php`). CSS: one stage |
| AZ7 PEP/PIP/PDP pipeline | P | Y | P | N | AP: expression + voters. CSS: credentials → modes → readers → authorizer. LDH: `AuthenticationFilter` → `AuthorizationFilter` → `AuthorizationContext` (`:142`) |
| AZ8 triple-level targeting | P | N | P | N | AP: per property (`AbstractItemNormalizer.php:536`). LDH: per document class `acl:accessToClass` + `rdfs:subClassOf*` (`web.xml:74-81`) |
| AZ9 SPARQL conditions with pre-bound vars | P | N | P | N | AP: expression language with `object`, `previous_object`, `request`, URI vars (not SPARQL). LDH: `$agent`, `$base`, `?Target` bound into one global ACL query |
| AZ10 policy-as-data, SPARQL, fail-closed | N | Y | Y | N | CSS: `WebAclReader.ts`, `AcpReader.ts`. LDH: `web.xml:61-104`, fail-closed `VALUES` l.101-103 |
| AZ11 combining algorithm / default deny | P | Y | P | N | AP: `AccessDecisionAwareResourceAccessCheckerInterface` decision object. CSS: ACP `allOf/anyOf/noneOf` (`AcpUtil.ts:55-57`). LDH: allow-only WAC + fail-closed default |
| AZ12 SPARQL-defined group membership | N | P | P | N | CSS: `access/AgentGroupAccessChecker.ts` (vcard groups). LDH: `foaf:member` resolved inside `aclQuery` (`web.xml:85-89`) |
| AZ13 parameterised graph templates | n.a. | N | N | N | graph = document IRI in CSS/LDH |
| AZ14 quad → graph write policy | n.a. | N | N | N | – |
| AZ15 caller (client) scopes | N | P | N | N | CSS: ACP `client` / `issuer` matchers (`AcpUtil.ts:38-39`) |
| AZ16 privileged bypass | N | P | N | N | CSS: `OwnerPermissionReader.ts:16` (pod owner gets control) |
| AZ17 non-widenable governed session | n.a. | n.a. | N | n.a. | LDH public SPARQL endpoint is a document under ACL, not a scoped session |
| AZ18 IdP claim → policy selector | P | P | P | N | AP: Symfony roles in expressions. CSS: Solid-OIDC WebID, ACP issuer. LDH: ID token → agent via `agentQuery` by `foaf:mbox` (`web.xml:107-118`) |
| AZ19 per-request identity to the store | N | N | N | N | CSS: one `SparqlEndpointFetcher` (`SparqlDataAccessor.ts:3`). LDH: one client per dataspace |
| AZ20 token propagation across hops | N | N | N | N | – |
| AZ21 principal threaded into field checks | Y | N | N | N | AP `AbstractItemNormalizer.php:527-540` |
| AZ22 caches partitioned by principal | P | n.a. | N | n.a. | AP `isCacheKeySafe` (`AbstractItemNormalizer.php:548`) |
| AZ23 trusted-proxy shared secret | N | N | Y | N | LDH `PROXY_SECRET` (README l.63) |
| AZ24 401/403 error contract | Y | Y | Y | N | AP `AccessDeniedException` in `AccessCheckerProvider`. CSS `PermissionBasedAuthorizer.ts:5-7`. LDH `ForbiddenExceptionMapper.java`; README l.376 "reveals nothing" |
| AZ25 read masking | P | N | N | N | AP hides secured properties, does not mask |
| AZ26 policy-aware explain/stats | N | N | N | N | – |
| AZ27 decision audit trail | N | N | N | N | – |
| AZ28 tuple sync from events | n.a. | n.a. | n.a. | n.a. | no ReBAC engine |
| AZ29 ACL inputs from the model | P | N | N | N | AP: `security` declared on resource/property metadata |
| G1 generated classes carry RDF mapping | P | n.a. | n.a. | n.a. | AP: `ApiResource(types: …)`, `ApiProperty(iris:, jsonldContext:)` (`Metadata/ApiProperty.php:115`), hand-written or schema-generator |
| G2 separate mapper layer | P | n.a. | n.a. | N | AP `State/Provider/ObjectMapperProvider.php` (resource ↔ entity) |
| G3 overridable templates | P | n.a. | n.a. | n.a. | create-client custom generators (docs) |
| G4 per-module generation | n.a. | n.a. | n.a. | n.a. | – |
| G5 IRI-typed fields | N | n.a. | n.a. | N | – |
| G6 language-tagged strings | N | n.a. | n.a. | N | AP: no `rdf:langString` (grep `langString`: none) |
| G7 JSON-LD context (and frames) generated | P | N | N | N | AP `JsonLd/ContextBuilder.php:53-97` (context, no frames) |
| G8 twin projections | P | n.a. | n.a. | N | AP: classes + generated context, context not used as the mapping |
| G9 OpenAPI generation | Y | N | N | P | AP `src/OpenApi/` (`OpenApiProvider` in GitNexus). LS: FastAPI default OpenAPI of generic routes |
| G10 route generation per resource | Y | n.a. | N | N | AP operations metadata → routes. LDH/LS generic routes |
| G11 Hydra ApiDocumentation | Y | N | N | N | `Hydra/Serializer/DocumentationNormalizer.php` |
| G12 GraphQL with queries/filters/mutations | P | N | N | N | AP `GraphQl/Type/` from resource metadata (not SHACL/DASH) |
| G13 per-class filter/sort/include grammar | Y | N | N | N | `ApiFilter`, `CollectionFiltersNormalizer.php:115-147` |
| G14 read-model query generation | N | N | N | N | – |
| G15 response profiles from the model | P | N | N | N | AP serialization groups per operation |
| G16 client-side model generation | Y | N | N | N | create-client (TS interfaces) |
| G17 shapes/vocab → schema import | P | N | N | N | AP schema-generator (RDF vocab → PHP, separate repo) |
| G18 UML → OWL/SHACL | n.a. | n.a. | n.a. | n.a. | – |
| G19 reasoner gate | n.a. | n.a. | n.a. | n.a. | – |
| G20 inference materialisation | n.a. | n.a. | n.a. | n.a. | – |
| G21 data-quality SPARQL generation | n.a. | n.a. | n.a. | n.a. | – |
| G22 RML generation | n.a. | n.a. | n.a. | n.a. | – |
| G23 type-designator polymorphism | P | n.a. | n.a. | N | AP: `@type` per subclass via Doctrine inheritance |
| G24 enum values as IRIs | P | n.a. | n.a. | N | AP `State/Provider/BackedEnumProvider.php` exposes enums as resources with IRIs |
| G25 standalone bindings | n.a. | n.a. | n.a. | n.a. | – |
| G26 inheritance-safe config | P | n.a. | n.a. | n.a. | AP `Metadata/CascadeFromResource.php` (resource → operation cascade) |
| G27 build-time regeneration | n.a. | n.a. | n.a. | n.a. | runtime metadata, nothing generated |
| T1 single-request atomic flush | n.a. | P | P | N | CSS: one Update with delete + insert ops per resource (`SparqlDataAccessor.ts:216-254`). LDH: one GSP request per document |
| T2 guarded update / CAS | N | P | P | N | CSS: ETag check under `LockingResourceStore` (not in WHERE). LDH: If-Match before write (`DocumentHierarchyGraphStoreImpl.java:586`) |
| T3 vendor transaction adapter | N | N | N | N | – |
| T4 compensating rollback | N | N | N | N | – |
| T5 read-your-writes | n.a. | n.a. | n.a. | n.a. | – |
| T6 retry on conflict | N | N | N | N | – |
| T7 capability descriptor | N | N | N | N | – |
| T8 savepoints | N | N | N | N | – |
| T9 idempotent writes | P | P | P | N | PUT semantics only; LDH "appending nothing is a no-op" (`:456`); no idempotency key anywhere |
| T10 rollback resets cache | n.a. | n.a. | n.a. | n.a. | – |
| T11 write-batch limits | N | N | N | N | LDH `ContentLengthLimitFilter.java` limits the request size only |
| E1 publish-after-commit / outbox | P | P | N | N | AP `PublishMercureUpdatesListener.php:101,131` (after flush, not transactional). CSS `MonitoringStore` → `ActivityEmitter` (in memory) |
| E2 RDF Patch wire format | N | N | N | N | CSS accepts N3 Patch as input only |
| E3 head-moved + pull | N | P | N | N | CSS notifications carry topic + `state`; client re-GETs |
| E4 authorised feeds | Y | Y | N | N | AP Mercure `private` (`:50-53,322-324`). CSS `NotificationSubscriber.ts:36-67` (permissionReader + authorizer) |
| E5 ordered, resumable sequence | P | N | N | N | AP: Mercure update `id` (`buildUpdate` l.322-324) enables `Last-Event-ID` |
| E6 delta-only virtual graphs | N | N | N | N | – |
| E7 call-id loop prevention | N | N | N | N | – |
| E8 coalesced notifications | P | P | N | N | AP collects per flush (`storeObjectToPublish` l.160). CSS `rate` (`NotificationChannel.ts:37`) |
| E9 standard channels | Y | Y | N | N | Mercure; WebSocket/Webhook/StreamingHTTP 2023 |
| U1 generated typed SDK | Y | N | N | N | create-client |
| U2 IRI-keyed client cache | P | N | N | N | Admin through react-admin |
| U3 push-to-cache | Y | N | N | N | Admin + Mercure (api-platform.com/docs/admin/) |
| U4 shape-driven forms | P | N | P | N | AP Admin from Hydra/OpenAPI. LDH ontology-driven XSLT forms (`xsl/client/functions.xsl`; derivation not traced) |
| U5 schema-introspected admin | Y | N | Y | P | AP Admin; LDH generic UI; LS `/pages` HTML (`main.py:794`) |
| U6 validation report on fields | Y | N | P | N | AP `Hydra/Serializer/ConstraintViolationListNormalizer.php`. LDH SPIN violations (`ValidatingModelProvider.java:210-244`) |
| U7 client UoW by graph diff | N | N | N | N | – |
| U8 generated mocks | N | N | N | N | – |
| U9 capability hints per user | N | Y | Y | N | CSS `WacAllowHttpHandler.ts:28,55` (WAC-Allow). LDH `Link rel=acl:mode` (`filter/response/ResponseHeadersFilter.java:113-114`). AP Hydra `supportedOperation` is static |
| U10 shape-driven search UI | P | N | N | N | AP Admin filters from `hydra:search` |
| RAD3 front-end scaffold | Y | N | N | N | create-client |
| RAD4 tiered exposure | P | N | N | N | AP operations opt-in per resource, `Metadata/NotExposed.php` |
| X17 multi-profile rendering | Y | P | P | N | CSS/LDH: RDF serialisation conneg (+ HTML in LDH) |
| X18 atomic multi-op with lid | N | N | N | P | AP: grep `atomic` none. LS: list insert in one POST (`main.py:709-725`), no lid |
| X19 conditional requests | P | Y | Y | N | AP response ETag only (`AddHeadersProcessor.php:34,66`). CSS `storage/conditions/*`. LDH `evaluatePreconditions` `:1810` |
| X20 cursor pagination | Y | N | N | N | `State/Pagination/Pagination.php:199`; `PartialCollectionViewNormalizer.php:85-93` |
| X21 RDF patch bodies | P | Y | P | N | AP merge-patch JSON (`Metadata/ApiResource.php`). CSS N3 + SPARQL Update. LDH SPARQL Update (`:689-691`) |
| X22 bundled client context | N | N | N | N | AP serves the context by URL (`ContextBuilder.php:97`) |
| D11 store errors surfaced | n.a. | P | n.a. | N | CSS `createErrorMessage` (`SparqlDataAccessor.ts:22`) |
| D12 per-model exceptions | n.a. | n.a. | n.a. | N | – |
| D13 model-aware errors | Y | N | P | N | AP violations with `propertyPath`. LDH violations with paths |
| S15 time travel | N | N | Y | N | LDH Memento TimeGate/TimeMap (`ResponseHeadersFilter.java:97`, README l.375) |
| S16 branching | N | N | N | N | – |
| S17 diff-load / sync | n.a. | P | P | P | CSS/LDH: PUT replaces the document graph. LS `upsert` (`api/collection.py:234`) |
| S18 bulk loader path | N | N | Y | Y | LDH `imports/ImportExecutor.java`. LS `import_database` (GitNexus process `Import_database → Insert`) |
| S19 commit metadata | N | N | P | N | LDH `server/util/GraphVersioningService.java` (best-effort GitHub mirror commits) |

**Counts over the 102 v3 features** (Y / P / N / n.a.):

| Tool | Y | P | N | n.a. |
|---|---|---|---|---|
| API Platform core | 18 | 32 | 34 | 18 |
| Community Solid Server | 9 | 15 | 53 | 25 |
| LinkedDataHub | 8 | 17 | 55 | 22 |
| linkml-store | 1 | 4 | 81 | 16 |

### (b) Purpose and origin

**Deep-dived candidates**

- **API Platform core.**
  - *Built for:* PHP developers who want a hypermedia/REST and GraphQL API from their classes in minutes.
  - *Origin:* Les-Tilleuls.coop (Lille, France), started by Kévin Dunglas (2015). Today Antoine Bluchet (`soyuka`, 2,853 commits) leads and Dunglas follows (1,868; `gh api …/contributors`). It is a commercial-cooperative open source project.
  - *Design angle:* API-first and standards-first (JSON-LD/Hydra was the founding format). The resource model is metadata, persistence is pluggable, and security is per operation.
  - *Fit:* the reference **contract** for L4. Its JS tooling (Admin, create-client) fits L5 as integrations. It does not fit L1/L2: PHP, no RDF store.
- **Community Solid Server.**
  - *Built for:* a modular research and reference implementation of the Solid Protocol, used to test the specification and to host pods.
  - *Origin:* imec / IDLab, Ghent University (Joachim Van Herwegen, Ruben Verborgh; README l.86, 101), with Inrupt funding.
  - *Design angle:* Web-standard-first, every behaviour a swappable Components.js component.
  - *Fit:* L3 and L6 *patterns* (the PEP pipeline, notifications) and conditional writes. As a deployable, only for personal-data/pod products. It does not fit as the UI's data-management service, because it has no class-level queries.
- **LinkedDataHub.**
  - *Built for:* a low-code platform for building and publishing knowledge-graph apps without programming.
  - *Origin:* AtomGraph (Copenhagen, Denmark; `pom.xml:17-23`, GitHub org location), essentially one author, Martynas Jusevičius. It descends from AtomGraph Processor and the Linked Data Templates research.
  - *Design angle:* app-platform-first and RDF-all-the-way (ACL, config and UI templates are RDF/XSLT), with formal verification of the HTTP/ACL contract.
  - *Fit:* L3 policy-as-data idea and L4 GSP semantics. As a stand-alone back office it could sit *next to* a V1/V2 deployment over the same store, provided its document-graph layout is acceptable. It does not fit inside the Python stack.
- **linkml-store.**
  - *Built for:* LinkML users who want one Python API over many data backends (DuckDB, MongoDB, Solr, Neo4j, vector stores), including LLM-assisted search and inference.
  - *Origin:* the LinkML organisation (top contributor `cmungall`, 118 commits; LBNL / Monarch ecosystem). The `pyproject.toml` author field is a placeholder.
  - *Design angle:* schema-driven-store-first, research data management.
  - *Fit:* an approach-C (generic service) *reference* and a possible place to plug an rdf-persistence store adapter. It does not fit as the UI service: no RDF backend, insert-only HTTP, no auth.

**Desk-scan candidates**

| Tool | Purpose and origin (short) | Where it could fit |
|---|---|---|
| API Platform Admin / create-client | react-admin back office / front-end scaffolds from Hydra or OpenAPI; Les-Tilleuls.coop | L5 integrate if we emit Hydra/OpenAPI |
| API Platform schema-generator | PHP classes from schema.org or OpenAPI; Les-Tilleuls.coop | L0 idea only |
| PostgREST | zero-code REST over PostgreSQL; started by Joe Nelson, now community | L3/L4 pattern: DB enforces policy |
| Hasura | zero-code GraphQL with permission rules as row filters; Hasura Inc. | L3/L4 pattern (AZ2) |
| Neo4j GraphQL Library | SDL → CRUD GraphQL with `@authorization`; Neo4j Inc. | L4 pattern for G12 |
| react-admin / WarpDrive | admin UI over data providers (Marmelab) / JSON:API client (Ember community) | L5 integrate / compatible |
| JSON:API spec | JSON resource API; born in the ember-data community (Klabnik, Katz) | L4 contract (V2, V1) |
| FastAPI | Python APIs with OpenAPI from Pydantic; Sebastián Ramírez | L4 dependency |
| FastCRUD | CRUD routers over SQLAlchemy; Benav Labs | idea for the G10 router generator |
| fastapi-crudrouter, FastAPI-JSONAPI | generic CRUD / JSON:API routers over SQL; one author / MTS AI | ideas; fail DEC-5 |
| Strawberry, Ariadne, Graphene | Python GraphQL (code-first / schema-first / code-first) | L4 integrate if GraphQL is wanted (Graphene borderline) |
| rdflib-endpoint | SPARQL endpoint for rdflib/Oxigraph in FastAPI; Vincent Emonet (academic) | dev/test fixture; fails DEC-5 |
| pyLDAPI, Prez | conneg-by-profile publishing APIs; RDFLib / Kurrawong | L4 ideas (read side) |
| grlc, RAMOSE | SPARQL-query-as-REST; CLARIAH / OpenCitations research infrastructures | ideas for "named queries" endpoints; fail DEC-5 |
| hydrus, hydra-python-core | Hydra server/doc tooling from GSoC student projects (HTTP-APIs) | G11 doc model idea; dormant |
| Trellis LDP | LDP server with Memento/WebAC; Aaron Coburn (then Amherst College, later Inrupt) | none (stale) |
| ldp4j | Java LDP framework; Center for Open Middleware (`pom.xml` `<organization>`) | none (stale since 2020) |
| HyperGraphQL | read-only GraphQL over SPARQL; Semantic Integration Ltd., now "developed and maintained by Epeirogenic AB" (README) | none (dormant) |
| UltraGraphQL | HyperGraphQL successor with bootstrapping and insert/delete mutations; RWTH Aachen i5 (git.rwth-aachen.de/i5/ultragraphql, archived, last commit 2020-10) | none |
| OBG-gen | ontology → GraphQL server (OBDA); Linköping University | idea only |
| Stardog / GraphDB GraphQL | vendor GraphQL generated from OWL/SHACL; Stardog Union / Ontotext | V4 (GraphDB) only |
| DASH `graphql:` vocab | SHACL annotations for GraphQL exposure; TopQuadrant | L0 compatible, for G12 |
| Fluree v4 | ledger DB with JSON-LD, SPARQL, GraphQL and policies; Fluree PBC | V3 only (BUSL-1.1) |
| Solid Notifications | standard notification protocol; W3C Solid CG | L6 compatible (E9) |
| Sparnatural | SHACL-configured SPARQL query UI; Sparna | L5 integrate (V5) |
| GraphQL-LD.js | GraphQL + JSON-LD context → SPARQL in the browser; Ruben Taelman | V5 idea; fails DEC-5 |
| jsonld.js, Comunica, LDflex, Alcaeus, LDO | JSON-LD processing / SPARQL engine / path DSL / Hydra client / ShEx-typed Solid objects | L5; see angle-jsclient |

### (c) Variant fit

V1 Portable Python core · V2 semantic.works-compatible · V3 Fluree · V4 GraphDB · V5 Graph-direct reads. Development approaches: A runtime mapper · B generated mapper and routes · C generic service. Each cell says whether the tool **supports**, **enables** or **blocks** the variant, or is **–** (irrelevant).

| Tool | V1 | V2 | V3 | V4 | V5 | A | B | C |
|---|---|---|---|---|---|---|---|---|
| API Platform core (design) | enables (contract blueprint) | supports (JSON:API) | – | – | – | – | enables (metadata → routes, G10/G11/G13) | enables (runtime metadata) |
| API Platform Admin / create-client | supports (if Hydra/OpenAPI emitted) | – (JSON:API only) | – | supports | – | – | supports (U1, RAD3) | supports (U5) |
| Community Solid Server | – (ideas: AZ7, X19, E9) | – | – | – | blocks (no class-level query) | – | – | – |
| LinkedDataHub | supports as a side back office over the same store (graph-per-document layout) | – | – | supports (Jena/GSP) | supports (SPARQL endpoint + ACL) | – | – | enables (low-code, ontology-driven) |
| linkml-store | – (no RDF backend) | – | – | – | – | – | – | enables (generic-service reference) |
| FastAPI | supports (dependency) | supports | supports | supports | supports (read endpoint) | supports | supports | supports |
| FastCRUD | – (SQL) | – | – | – | – | – | enables (router-generation pattern) | – |
| Strawberry / Ariadne | supports (optional GraphQL view) | – | supports | supports | – | – | supports (G12) | supports |
| JSON:API spec + Atomic ext | supports | **required** | supports | supports | – | – | supports | supports |
| WarpDrive / react-admin | supports | supports (WarpDrive) | supports | supports | – | – | – | – |
| rdflib-endpoint | dev fixture | – | – | – | idea (FastAPI SPARQL mount) | – | – | – |
| grlc / RAMOSE | – | – | – | – | idea (named queries instead of free SPARQL) | – | – | supports (config-only) |
| Stardog / GraphDB GraphQL | – | – | – | supports (GraphDB) | supports (vendor read API) | – | – | supports (zero code) |
| Fluree v4 GraphQL / FlureeQL | – | – | supports (UI-to-DB path) | – | supports | – | – | supports |
| Solid Notifications / Mercure | supports (E9) | – (uses mu deltas) | – | supports | supports | – | – | – |
| HyperGraphQL / UltraGraphQL / OBG-gen / hydrus / Trellis / ldp4j | – (dormant) | – | – | – | – | – | – | – |

**Headline**
- Nothing in this angle *blocks* V1–V4.
- V1 + approach B gets the most direct help: API Platform design, FastAPI, the Admin/create-client integration and the JSON:API contract.
- V2 is defined by the JSON:API contract.
- V5 has only vendor or dormant read APIs (GraphDB/Stardog/Fluree GraphQL, LDH's SPARQL endpoint). CSS actively blocks it.
- Approach C has references (linkml-store, LDH, mu-cl-resources) but no RDF-capable reusable implementation.

### (d) Corrections to the integrated docs (not edited)

1. **`angles/service.adoc:113` and `building-blocks.adoc:81-83`** read as if API Platform *applies* row-level filters before pagination. Correct wording: "API Platform provides the *hook* (`QueryCollectionExtensionInterface`/`QueryItemExtensionInterface`); the policy extension is written by the application (docs: `CurrentUserExtension`); core ships only filter, order, eager-loading and parameter extensions" (GitNexus `core`).
2. **`index.adoc` patterns table, row "Service contract"**, lists API Platform among the sources of "conditional writes (ETag/If-Match)". API Platform only *emits* ETags (`HttpCache/State/AddHeadersProcessor.php:34,66`) and checks no precondition on writes. Attribute X19 to CSS and LinkedDataHub only.
3. **`catalogue.adoc`, linkml-store row:** "Generic-service variant (E) reference" uses a retired variant letter. It should read "approach C (generic service) reference". Not my candidate: the row at l.259, "Route skeletons from an OpenAPI contract (variant D)", has the same stale-letter problem.
4. **`catalogue.adoc`, Origin cells:**
   - **HyperGraphQL:** "Origin not recorded" → "Semantic Integration Ltd.; README now says developed and maintained by Epeirogenic AB".
   - **UltraGraphQL:** "repository not found" → "RWTH Aachen, Databases and Information Systems (i5), git.rwth-aachen.de/i5/ultragraphql; archived, last commit 2020-10".
   - **ldp4j:** "Origin not recorded" → "Center for Open Middleware (per `pom.xml`)".
   - **Trellis LDP:** "trellis-ldp project" → "Aaron Coburn (top contributor; Amherst College, later Inrupt)".
   - **API Platform:** "Kévin Dunglas" is right as founder. Add "maintained today mainly by Antoine Bluchet (soyuka)".
   - **LinkedDataHub:** add "Martynas Jusevičius".
   - **linkml-store:** add "Chris Mungall (main author)".
   - **Community Solid Server:** confirmed (imec – Ghent University).
5. **`angles/service.adoc` landscape:** "API Platform schema-generator … none" disagrees with the catalogue's "ideas". The catalogue is right, because schema-generator is a vocabulary → classes precedent.

### (e) Proposed new features (round 4)

| Proposed id | Area | Feature | Seen in |
|---|---|---|---|
| AZ30 | Authorization | **Side-channel minimisation in metadata:** validators and headers (ETag, Last-Modified, existence, counts) withheld from callers who may not read; denial reveals nothing about existence | LDH `ResponseHeadersFilter.java:99-108`, README l.376 |
| X23 | Interop | **MCP projection of the resource registry:** the same resources and operations exposed as MCP tools/resources for AI agents, under the same security | AP `src/Mcp/` (`ToolProvider`, `PolicyAccessChecker`) |
| E10 | Events | **Subscription channel features:** rate limit, state-on-connect, validity window (`startAt`/`endAt`), accepted media type | CSS `NotificationChannel.ts:22-37`; Solid Notifications spec |
| S20 | Stores | **Named-graph mirroring to version control** (graph → file, best-effort commits per change) | LDH `GraphVersioningService.java` |
| D14 | DevEx | **Formal model of the HTTP/ACL contract checked in CI** (theorems, replayed against the running server) | LDH `formal/`, README l.371-380 |

**Not checked in round 4**
- The LDH form derivation; the GraphDB/Stardog mutation pages.
- The `fluree-db` index (named `db`). That belongs to the stores/authz angles, and my Fluree statements are unchanged.

---

## Round 5

Analyst: angle-service · 2026-11-03 · Brief: `BRIEF-round5.md`.

Columns, evidence roots and values are the same as in Round 4 (AP, CSS, LDH, LS; Y/P/N/n.a.). Taxonomy **v4**.

### (a) v4 cross-check

| Id | AP | CSS | LDH | LS | Evidence |
|---|---|---|---|---|---|
| B1 aggregate declaration | N | n.a. | n.a. | N | AP: Doctrine cascade options are ORM config, not aggregate roots. CSS/LDH: the document is the only unit |
| B2 boundary validation at generation | N | n.a. | n.a. | N | – |
| B3 whole-aggregate load | n.a. | P | P | N | CSS `getData` CONSTRUCTs the whole document graph (`SparqlDataAccessor.ts:70-76`). LDH GSP GET of the document graph |
| B4 whole-aggregate save, diffed | n.a. | P | P | N | PUT replaces the document graph without a diff (CSS `sparqlUpdateDeleteAll` + insert; LDH PUT `:518-520`) |
| B5 typed cross-aggregate refs | N | n.a. | n.a. | N | AP relations are IRIs in JSON-LD but objects in PHP |
| B6 aggregates-per-commit policy | N | N | N | N | – |
| B7 single conjunctive guarded op | N | N | N | N | CSS/LDH check the ETag *before* the update; it is not inside WHERE |
| B8 inspectable change-set | N | P | N | N | CSS: every write returns a `ChangeMap` (`ResourceStore.ts:15`); this is a post-write effect map, not a pre-commit value |
| B9 domain events via outbox | N | N | N | N | – |
| B10 aggregate storage strategy | n.a. | P | P | N | graph per document is the only strategy (CSS `:181`, LDH `DocumentHierarchyGraphStoreImpl`) |
| B11 version kept by mapper, exposed as ETag | N | P | P | N | AP ETag = hash of the body (`AddHeadersProcessor.php:66`). CSS `BasicETagHandler.ts` (from metadata). LDH ETag = hash of the graph (`:409`) |
| B12 after-commit hooks | P | P | N | N | AP Doctrine `postFlush` listener (`PublishMercureUpdatesListener.php:131`). CSS `MonitoringStore` events |
| B13 boundary-aware delete | n.a. | P | N | N | CSS: `DeleteParentExtractor.ts` (deleting needs rights on the parent container) |
| B14 bounded-context partitioning | n.a. | n.a. | P | N | LDH admin vs end-user dataspaces (`AuthorizationFilter.java:335`) |
| B15 no-autoflush contract | n.a. | n.a. | n.a. | N | – |
| B16 saga / process manager | N | N | N | N | – |
| PG1 query AST with pluggable renderers | P | N | N | Y | AP: one filter API with per-backend implementations (Doctrine ORM/ODM, Elasticsearch, Eloquent; GitNexus provider list). LS: `api/queries.py:16` `Query`, executed by each store in `api/stores/*` |
| PG2 LPG projection config | n.a. | n.a. | n.a. | P | LS `api/stores/neo4j/` (collection → label); no IRI-based naming |
| PG3 edge-property mapping | N | N | N | N | – |
| PG4 partition scope abstraction | N | N | N | P | LS `Database`/`Collection` scope over all backends |
| EV1 migration runner with RDF log | n.a. | P | P | N | CSS `init/migration/V6MigrationInitializer.ts` (internal storage). LDH `migrations/6.0-*.ru.template` (2 files, no applied-log) |
| EV2 migration integrity | n.a. | N | N | N | – |
| EV3 schema diff → update skeletons | N | N | N | N | – |
| EV4 down migrations | N | N | N | N | – |
| EV5 object-level transformation | N | N | N | N | – |
| EV6 post-migration SHACL gate | N | N | N | N | – |
| EV7 schema version stamped and checked | N | P | N | N | CSS `init/ModuleVersionVerifier.ts` (stored server version checked at startup) |
| EV8 staged bulk load | N | N | N | N | LDH `imports/ImportExecutor.java` loads directly |
| EV9 migration rehearsal | N | N | N | N | – |
| AZ30 graph-aware class targeting | n.a. | n.a. | N | N | LDH resolves `acl:accessToClass` against the **union graph** (`web.xml:79-80` `GRAPH <urn:x-arq:UnionGraph>`), the opposite of AZ30 |
| AZ31 ACL inheritance down a hierarchy | N | Y | Y | N | CSS `authorization/ParentContainerReader.ts` + WAC `acl:default`. LDH `acl:default` on a container above (`web.xml:70-73`) |
| AZ32 predicate-coverage fast path | N | N | N | N | – |
| AZ33 existence-hiding denial | N | P | Y | N | CSS: 404 is shown only to agents with Read; others get 401/403 (`PermissionBasedAuthorizer.ts:56-72`). LDH: denial "reveals nothing else, not even whether the document exists" (README l.376); HEAD drops Last-Modified for non-readers (`ResponseHeadersFilter.java:99-108`) |
| AZ34 lagging policy configuration | N | N | N | N | – |
| AZ35 policy-filter equivalence test | N | N | N | N | LDH `formal/acl/` proves other properties (no cross-document widening), not count equivalence |
| AZ36 edge sanitisation of internal headers | N | N | P | N | LDH `PROXY_SECRET` (README l.63) proves the request came through nginx; no header allow-list seen |
| G28 contract hygiene | n.a. | n.a. | n.a. | N | LS publishes FastAPI defaults |
| G29 importer lossiness report | n.a. | n.a. | n.a. | N | – |
| G30 cross-path equivalence gate | n.a. | n.a. | n.a. | n.a. | – |
| G31 toolchain prerequisites check | n.a. | n.a. | n.a. | n.a. | – |
| G32 reasoner profile choice | n.a. | n.a. | n.a. | n.a. | – |
| G33 generated-metadata completeness | n.a. | n.a. | n.a. | n.a. | – |
| G34 `dcterms:conformsTo` link | N | N | N | N | grep `conformsTo` in LDH Java: none |
| G35 typed field metamodel | n.a. | n.a. | n.a. | N | – |
| G36 typed filter/input types per class | P | n.a. | n.a. | N | AP per-operation input JSON Schema + filter parameters in OpenAPI (`src/JsonSchema/`, `OpenApi/`) |
| T12 read-tracked optimistic commit | N | N | N | N | – |
| T13 read-only mode guard | N | Y | P | N | CSS `storage/ReadOnlyStore.ts`. LDH snapshot/TimeMap views read-only (`ResponseHeadersFilter.java:97`) |
| T14 cross-store unit of work | n.a. | P | N | N | CSS `RoutingResourceStore` routes per path to different stores; no unit of work, no atomicity |
| S20 per-named-graph store config | N | N | N | N | – |
| S21 named graphs mirrored to VCS | N | N | Y | N | LDH `server/util/GraphVersioningService.java` |
| S22 store-side shape enforcement on write | n.a. | N | P | N | CSS validators are quota only (`storage/validators/QuotaValidator.ts`). LDH SPIN/SHACL check in the app before write (`ValidatingModelProvider.java`) |
| S23 ops admin port | N | N | N | N | – |
| X23 strict JSON-LD processing | N | N | N | n.a. | not found (grep `safe` / strict-mode options: none) |
| X24 MCP projection of the registry | Y | N | N | N | AP `src/Mcp/` (`State/ToolProvider`, `Security/PolicyAccessChecker.php`). grep `mcp` in LS/LDH sources: none |
| E10 subscription channel options | P | Y | N | N | AP Mercure `retry`/`type`/`id`/`private` (`PublishMercureUpdatesListener.php:322-324`). CSS `NotificationChannel.ts:22-37` |
| I7 reversible IRI minting | Y | n.a. | n.a. | N | AP `IriConverterInterface::getResourceFromIri` / `getIriFromResource` (`Metadata/IriConverterInterface.php:57`) |
| I8 deferred IRI minting | P | n.a. | n.a. | N | AP: IRI derived from the backend id after persist (Doctrine) |
| P20 reference-aware flush ordering | n.a. | n.a. | n.a. | N | delegated to Doctrine in AP |
| U11 Web Components | N | N | N | N | – |
| U12 desktop/notebook editor | N | N | N | N | – |
| U13 bulk operations in one batch | N | N | N | P | the v4 table already records the gap in api-platform/admin. LS list insert (`webapi/main.py:709-725`) |
| D14 stale-write warning | n.a. | n.a. | n.a. | N | – |
| D15 parameter redaction in logs | N | N | N | N | – |
| D16 formal HTTP/ACL model in CI | N | N | Y | N | LDH `formal/`, README l.371-380 |
| D17 inspectable compiled query | n.a. | N | N | N | – |
| D18 explicit-loading sentinel | n.a. | n.a. | n.a. | N | – |
| D19 test kit | P | P | N | P | AP `src/Symfony/Bundle/Test/` (API test case and client). CSS `InMemoryDataAccessor`. LS in-memory DuckDB |
| D20 real-store test fixtures | N | N | N | N | LDH HTTP tests run against its docker-compose stack, not shipped fixtures |
| D21 tested documentation | Y | N | N | N | AP `.github/workflows/guides.yml` runs `docs/guides/*.php` |
| D22 CURIEs everywhere | N | N | N | N | – |
| D23 "did you mean" | N | N | N | N | – |
| D24 stable error codes + doc page | P | N | N | N | AP Problem+JSON `type` URIs (`src/Problem/`) |
| D25 deterministic multi-value order | N | N | N | N | – |
| D26 typing regression tests | N | n.a. | n.a. | N | – |
| D27 fault-injection tests | N | N | N | N | – |
| D28 contract fuzzing | N | N | N | N | – |
| D29 store-port observability | P | N | N | N | AP `State/StopwatchAwareInterface.php` (profiler timing), no OpenTelemetry |

**Counts over the 77 v4 features** (Y / P / N / n.a.):

| Tool | Y | P | N | n.a. |
|---|---|---|---|---|
| API Platform core | 3 | 8 | 43 | 23 |
| Community Solid Server | 3 | 12 | 41 | 21 |
| LinkedDataHub | 4 | 9 | 45 | 19 |
| linkml-store | 1 | 4 | 67 | 5 |

### (b) Page review — `angles/service.adoc` and the L4/L6 parts of `building-blocks.adoc`, `variants.adoc`, `index.adoc`

The page already carries the round-4 corrections (row-filter hook, no `If-Match`, no Atomic ext, origins). Remaining items:

1. **`angles/service.adoc:258-264`** says "Round-4 proposals, not yet in the taxonomy:". They are now in v4. Fix: "Round-4 proposals, merged as AZ33 (existence-hiding denial), X24 (MCP projection), E10 (channel options), S21 (graph mirroring to VCS), D16 (formal contract model)."
2. **`angles/service.adoc:168`**: "Works against any SPARQL 1.1 endpoint." This is an overstatement. Add the caveat: "…that supports SPARQL 1.1 Update with `GRAPH`; one named graph per document, default-graph content only, so existing data in other layouts is not visible (`SparqlDataAccessor.ts:131-134`)."
3. **`angles/service.adoc:308`**, recommended contract "plus the *Atomic Operations* extension mapped to one unit of work". Add the caveat: "an extension of the mu dialect: mu-cl-resources does not implement it (no `atomic` in its README), and API Platform does not either. Existing Ember front ends will not send it."
4. **`angles/service.adoc:49` vs `catalogue.adoc`**: the page says WarpDrive is "integrate" and Strawberry/Ariadne "dependency (if GraphQL is needed)" (l.55). The catalogue says "compatible" and "integrate". Fix: align on the catalogue values (WarpDrive *compatible*, Strawberry/Ariadne *integrate*), or the reverse, but use one.
5. **`angles/service.adoc:166`**, CSS "ETag/If-Match is built in". This is correct, but add the AZ33 nuance that CSS reveals non-existence (404) only to readers (`PermissionBasedAuthorizer.ts:56-72`). It is a pattern worth citing next to LinkedDataHub's.
6. **`index.adoc:157-160`**, patterns row "conditional writes with ETag/If-Match (Community Solid Server)". Add LinkedDataHub, the stronger example: formally modelled, RFC 9110 (`DocumentHierarchyGraphStoreImpl.java:586,1810`).
7. **`building-blocks.adoc:103`** (L6): "no single standard." This is an overstatement. Fix: "no RDF-*store* standard for change feeds; for resource-level notifications to clients there is the Solid Notifications Protocol (W3C Solid CG; Community Solid Server implements it) and Mercure (IETF draft, used by API Platform)."

No errors found in `variants.adoc` or `design-implications.adoc` about L4. `variants.adoc:16` (V1 service generated from LinkML with JSON-LD + Hydra, JSON:API, OpenAPI) matches the evidence.

### (c) Final verdicts and what to remember

| Candidate | Final verdict |
|---|---|
| API Platform core | **ideas** (the contract design); its JS tooling (`@api-platform/admin`, create-client) is **integrate** |
| Community Solid Server | **ideas** (deployable only for pod products) |
| LinkedDataHub | **ideas** |
| linkml-store | **ideas** (optional later integration: an rdf-persistence store adapter) |

**Three things a system architect must remember**
1. **Copy API Platform's shape, not its guarantees.** One resource registry projected to JSON:API, JSON-LD+Hydra, OpenAPI (and MCP); persistence behind exactly two ports; security at fixed pipeline stages. But it ships *no* row-level policy filter, no `If-Match` and no Atomic Operations. We must build those seams ourselves: AZ2, X19, X18.
2. **The listing-query filter decides whether authorization is correct.** Every reviewed service either enforces per document or request (CSS, LinkedDataHub: fine for documents, unusable for class-level lists) or leaves the row filter to the application (API Platform). Only a policy injected *before* pagination and count gives correct totals. Pick a PDP that returns a filter, or stay graph-level.
3. **Documents vs resources.** LDP/GSP servers (CSS, LinkedDataHub) model "one named graph per document". That gives clean ETags, ACL inheritance and whole-graph PUT, but no server-side query, filter or page. A UI-facing service needs class-level resources (JSON:API/Hydra) over rdf-persistence. Borrow the document servers' concurrency and ACL ideas, not their storage layout.

### (d) Purpose and origin, variant fit

Already written in Round 4 (b) and (c). Nothing changed.

### (e) New features

None proposed. The taxonomy covers this angle.

**Not checked in round 5**
- I did not open the LDH `formal/` models.
- I did not run the AP guides workflow (inferred from `guides.yml`).
- I did not re-read the CSS notification channel implementations beyond the field list.
