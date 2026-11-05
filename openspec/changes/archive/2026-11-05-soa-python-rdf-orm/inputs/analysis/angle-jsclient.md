# Angle: L5 JS/TS client and UI for JSON-LD from the server (`angle-jsclient`)

Change `soa-python-rdf-orm`, round 3. Analyst brief: `BRIEF-round3.md`. LDkit is already analysed in `ldkit.md`; it is compared here, not redone.

The question this angle answers: the MWBv2 UI app (TypeScript, Cypress + Gherkin E2E) consumes data from a generated Python data-management service. **Which classical, modern JS libraries handle the JSON-LD (or other RDF-backed) contract on the client, and which combination gives a coherent, easy-to-maintain frontend stack for each architecture variant?**

Method: a desk scan of 45 candidates (GitHub API on 2026-11-03, npm weekly downloads on 2026-11-03). Four were deep-dived (shallow clone plus `gitnexus analyze`, code read, docs fetched):

| Clone | Commit | GitNexus index |
|---|---|---|
| `/home/lps/work/repos/jsonld.js` | `7a93609` (2026-03-04) | 733 nodes, 1,799 edges, 72 clusters, 60 flows |
| `/home/lps/work/repos/api-platform-admin` | `ab9239c` (2026-06-22) | 774 nodes, 1,388 edges, 24 clusters, 59 flows |
| `/home/lps/work/repos/shacl-form` | `5f430f5` (2026-10-22) | 890 nodes, 3,736 edges, 61 clusters, 75 flows |
| `/home/lps/work/repos/ldo` | `80fb5ce` (2026-10-23) | 3,255 nodes, 8,622 edges, 191 clusters, 232 flows |

`api-platform/admin` was cloned under the name `api-platform-admin` so that it does not clash with a generic `admin` directory.

Layer tags: L0 modelling & codegen · L1 domain & persistence · L2 stores · L3 identity & authz · L4 data-management API · L5 JS client & UI · L6 events.

---

## 1. Landscape table

DEC-5 means more than 200 stars AND a commit in the last 12 months (after 2025-11-03). Org or monorepo inheritance is noted where it applies.

### 1a. JSON-LD / RDF processing (interop layer)

| Candidate | Repo | Stars | Last push | Licence | Lang | npm/wk | DEC-5 | Layers | Server expectation |
|---|---|---|---|---|---|---|---|---|---|
| **jsonld.js** | digitalbazaar/jsonld.js | 1,817 | 2026-03-04 | BSD-3 (custom text, `LICENSE`) | JS | 436,871 (`jsonld` 9.0.0) | pass | L5 | Any JSON-LD document; remote contexts fetched by the document loader |
| N3.js | rdfjs/N3.js | 797 | 2026-11-02 | MIT | JS | 417,607 | pass | L5 | Turtle/TriG/N-Triples/N3 text; in-memory `Store` (RDF/JS) |
| @rdfjs/types | rdfjs/types | (rdfjs org) | — | MIT | TS | 458,735 | pass (rdfjs org via N3.js) | L5 | Interface-only (RDF/JS Data Model, Stream, Dataset, Queryable) |
| jsonld-streaming-parser | rubensworks/jsonld-streaming-parser.js | 91 | 2026-10-12 | MIT | TS | 173,614 | fail (ideas; it is a Comunica dependency) | L5 | Streaming JSON-LD → RDF/JS quads |
| jsonld-context-parser | rubensworks/jsonld-context-parser.js | 29 | 2026-10-29 | MIT | TS | 267,551 | fail (transitive dependency only) | L5 | — |
| Comunica | comunica/comunica | 620 | 2026-11-02 | MIT | TS | 18,493 (`@comunica/query-sparql`) | pass | L5 (L2 client side) | SPARQL endpoints, TPF, Solid, files, Hydra-paged sources; federation |
| rdflib.js | linkeddata/rdflib.js | 598 | 2026-10-12 | MIT | JS | 20,599 | pass | L5 | LDP/Solid documents, SPARQL Update PATCH |
| rdf-ext | rdf-ext/rdf-ext | 126 | 2026-09-14 | MIT | JS | 28,863 | fail | L5 | — |
| rdf-validate-shacl | zazuko/rdf-validate-shacl | 126 | 2026-04-02 | MIT | TS | 82,007 | fail (ideas; client-side SHACL) | L5 | Shapes + data as RDF/JS |

### 1b. Typed RDF object mappers and clients

| Candidate | Repo | Stars | Last push | Licence | npm/wk | DEC-5 | Layers | Server expectation |
|---|---|---|---|---|---|---|---|---|
| LDkit (see `ldkit.md`) | karelklima/ldkit | 83 | 2026-10 | MIT | 21,910 | fail (ideas / client target) | L5, L0 (SHACL→schema) | **Raw SPARQL 1.1 Query + Update endpoint** |
| **LDO** | o-development/ldo | 73 | 2026-10-31 | MIT | 223 (`@ldo/ldo` 1.0.0-alpha.51) | fail (ideas) | L5, L0 (ShEx/SHACL→TS) | **Solid** pods (LDP + SPARQL-Update PATCH), NextGraph; raw RDF |
| LDflex | LDflex/LDflex | 196 | 2026-10-26 | MIT | 504 | fail (4 stars short) | L5 | SPARQL endpoint or Comunica sources (path expressions → SPARQL) |
| rdf-object | rubensworks/rdf-object.js | 19 | 2026-08-18 | MIT | 74,186 | fail | L5 | RDF/JS quads (untyped object view; Comunica config dependency) |
| @inrupt/solid-client | inrupt/solid-client-js | 244 | 2026-11-02 | MIT | 26,731 | pass | L5, L3 (ACP/WAC helpers) | **Solid** (LDP resources, ACP/WAC) |
| @inrupt/solid-client-authn-browser | inrupt/solid-client-authn-js | 77 | 2026-11-02 | MIT | 24,211 | pass (inrupt org via solid-client) | L3, L5 | Solid-OIDC (DPoP) |
| Soukai / soukai-solid | NoelDeMartin/soukai(-solid) | 31 / 21 | 2026-11-02 / 2025-03 (archived) | MIT | 231 / 669 | fail | L5 | Active Record ODM; Solid engine |
| fdr | kobrixinc/fdr | 11 | 2026-06-17 | MIT | 6 | fail | L5 | SPARQL endpoint |
| Fluree client | fluree/fluree-client | 6 | 2026-03-26 | none | 79 | fail (the Fluree org repo itself passes, but this package is near-dead; Fluree verdict in the MWBv2 digest) | L5, L3 | FlureeQL JSON-LD over HTTP, JWT/JWS-signed requests |
| Alcaeus | hypermedia-app/Alcaeus | 65 | 2026-03-25 | MIT | 361 | fail (ideas) | L5 | **Hydra** API (follows `hydra:apiDocumentation`, operations) |
| shaperone | hypermedia-app/shaperone | 55 | 2025-05-26 | MIT | 239 | fail | L5 (forms) | SHACL shapes + RDF/JS data |
| kopflos (zazuko) | zazuko/kopflos | 16 | 2026-11-01 | MIT | — | fail | L4 (server side) | Hydra/SHACL-driven API server in Node; listed for the Hydra contract |

### 1c. Generic data layers (classical modern JS, backend-agnostic)

| Candidate | Repo | Stars | Last push | Licence | npm/wk | DEC-5 | Layers | Server expectation |
|---|---|---|---|---|---|---|---|---|
| TanStack Query | TanStack/query | 50,520 | 2026-11-03 | MIT | 78,954,917 (`@tanstack/react-query`) | pass | L5 | **Any** (fetcher-agnostic): cache, invalidation, optimistic updates |
| SWR | vercel/swr | 32,492 | 2026-10-16 | MIT | 26,100,690 | pass | L5 | Any |
| react-admin | marmelab/react-admin | 26,981 | 2026-11-02 | MIT | 228,485 | pass | L5 | Any via a `dataProvider` (REST, JSON:API, GraphQL, Hydra); built on TanStack Query |
| **@api-platform/admin** | api-platform/admin | 515 | 2026-09-10 | MIT | 8,532 (+ `api-doc-parser` 10,913) | pass | L5 | **Hydra** (`hydra:apiDocumentation` + compacted JSON-LD collections) or **OpenAPI** |
| refine | refinedev/refine | 35,983 | 2026-09-10 | MIT | 366,564 (`@refinedev/core`) | pass | L5 | Any via a data provider (REST, GraphQL, …); headless |
| ember-data / WarpDrive | warp-drive-data/warp-drive (ex emberjs/data) | 3,160 | 2026-11-02 | MIT | 119,348 (`@ember-data/store`) + 74,887 (`@warp-drive/core`) | pass | L5 | **JSON:API** (default); semantic.works frontend (`semantic-works.md` §"browser (Ember app…)") |
| Orbit.js | orbitjs/orbit | 2,340 | 2026-01-31 | MIT | 2,838 (`@orbit/jsonapi`) | pass | L5 | JSON:API; offline/optimistic sources |
| kitsu | wopian/kitsu | 294 | 2026-11-03 | MIT | 5,128 | pass | L5 | JSON:API |
| jsona | olosegres/jsona | 214 | 2026-06-12 | MIT | 67,403 | pass | L5 | JSON:API (de)serialiser only |
| spraypaint | graphiti-api/spraypaint.js | 111 | 2026-10-30 | MIT | 3,226 | fail | L5 | JSON:API (Graphiti) |
| Apollo Client | apollographql/apollo-client | 19,782 | 2026-11-03 | MIT | — | pass | L5 | GraphQL (LinkML has `graphqlgen`) |
| AdminJS | SoftwareBrothers/adminjs | 8,996 | 2025-07-15 | MIT | — | fail (last push > 12 months ago) | L4/L5 | Node ORM adapters (not HTTP) |
| zustand | pmndrs/zustand | 58,892 | 2026-11-03 | MIT | — | pass | L5 | Client state only |

### 1d. Contract → TS types / clients (codegen for the UI)

| Candidate | Repo | Stars | Last push | Licence | npm/wk | DEC-5 | Layers | Input |
|---|---|---|---|---|---|---|---|---|
| openapi-typescript (+ openapi-fetch) | openapi-ts/openapi-typescript | 8,425 | 2026-09-25 | MIT | 14,172,732 | pass | L0→L5 | OpenAPI 3.x (FastAPI emits it) |
| orval | orval-labs/orval | 6,585 | 2026-11-03 | MIT | 3,639,976 | pass | L0→L5 | OpenAPI → typed client + **TanStack Query hooks** + zod + MSW mocks |
| @hey-api/openapi-ts | hey-api/hey-api | 5,551 | 2026-10-31 | MIT | 6,812,401 | pass | L0→L5 | OpenAPI → SDK, zod, TanStack Query plugins |
| json-schema-to-typescript | bcherny/json-schema-to-typescript | 3,349 | 2026-09-07 | MIT | 5,991,845 | pass | L0→L5 | JSON Schema (LinkML `jsonschemagen`, Pydantic) |
| zod | colinhacks/zod | 44,247 | 2026-10-30 | MIT | 444,545,419 | pass | L5 | Runtime validation of payloads (generated by orval / hey-api) |
| LinkML generators | linkml/linkml | 680 | 2026-11-02 | Apache-2.0 | (PyPI) | pass | L0 | Verified in the repo tree (`packages/linkml/src/linkml/generators/`): `typescriptgen`, `jsonschemagen`, `jsonldcontextgen`, `shaclgen`, `shexgen`, `openapigen`, `graphqlgen`. **Output quality not checked here**; the MWBv2 digest records a weak TS generator (no enums, `uri`→str, dates) |
| linkml-runtime.js | linkml/linkml-runtime.js | 9 | 2023-06-12 | none | — | fail (dead) | L0/L5 | — |

### 1e. Forms and UI from shapes / schemas

| Candidate | Repo | Stars | Last push | Licence | npm/wk | DEC-5 | Layers | Input |
|---|---|---|---|---|---|---|---|---|
| **shacl-form** | ULB-Darmstadt/shacl-form | 93 | 2026-10-22 | MIT | 7,480 | fail (ideas, or vendor-in) | L5 | SHACL shapes + RDF data (Turtle, JSON-LD, RDF/XML) |
| shaperone | hypermedia-app/shaperone | 55 | 2025-05-26 | MIT | 239 | fail | L5 | SHACL + RDF/JS |
| RDForms | MetaSolutionsAB/rdforms | 8 | 2026-10-13 | LGPL-3.0 | not on npm | fail | L5 | RDForms templates (EntryScape) |
| react-jsonschema-form (RJSF) | rjsf-team/react-jsonschema-form | 15,932 | 2026-11-03 | Apache-2.0 | 1,716,647 (`@rjsf/core`) | pass | L5 | JSON Schema + uiSchema |
| JSON Forms | eclipsesource/jsonforms | 2,751 | 2026-10-26 | MIT | 459,497 (`@jsonforms/core`) | pass | L5 | JSON Schema + UI Schema (React/Angular/Vue) |

### 1f. Auth and E2E (supporting the UI stack)

| Candidate | Repo | Stars | Last push | Licence | npm/wk | DEC-5 | Layers | Notes |
|---|---|---|---|---|---|---|---|---|
| oidc-client-ts | authts/oidc-client-ts | 1,968 | 2026-09-01 | Apache-2.0 | 2,907,304 | pass | L3/L5 | OIDC code + PKCE in the browser, token refresh; used by react-oidc-context (1,020,456/wk) |
| @zitadel/react | (zitadel org) | org pass | — | — | 10,577 | pass (org) | L3/L5 | Thin wrapper over oidc-client-ts for Zitadel |
| Cypress | cypress-io/cypress | 51,018 | 2026-11-03 | MIT | — | pass | test | MWBv2 E2E |
| cypress-cucumber-preprocessor | badeball/cypress-cucumber-preprocessor | 1,360 | 2026-10-31 | MIT | 509,211 | pass | test | Gherkin in Cypress (MWBv2 runbook) |

**What the scan shows:** every RDF-native JS client is either below DEC-5 (LDkit, LDO, LDflex, Alcaeus, shacl-form, shaperone, Soukai) or tied to Solid (@inrupt/solid-client). The DEC-5-passing RDF pieces are the **interop layer only**: jsonld.js, N3.js, RDF/JS types, Comunica, rdflib.js. Every mature data layer, form generator and codegen tool is **RDF-agnostic** and speaks REST/OpenAPI, JSON:API, GraphQL or Hydra-via-react-admin. Download numbers differ by four orders of magnitude: tens of millions per week for TanStack Query and openapi-typescript, against hundreds for LDO and Alcaeus.

---

## 2. Deep dives

### 2.1 jsonld.js (digitalbazaar)

- Repo `digitalbazaar/jsonld.js`, commit `7a93609`, licence BSD-style (custom text in `LICENSE`; SPDX not asserted on GitHub). `lib/` is 26 files, 8,798 LOC. Dependencies: `@digitalbazaar/http-client`, `canonicalize`, `lru-cache`, `rdf-canonize` (`package.json:31-35`). 30 contributors.
- Docs read: `README.md` (Conformance, frame, Safe Mode, test sections), in-repo `AGENTS.md`.

**Summary.** jsonld.js is the reference JSON-LD 1.1 processor for JavaScript and the only DEC-5-passing JSON-LD library in JS. It provides the full algorithm set: `compact`, `expand`, `flatten`, `frame`, `toRDF`/`fromRDF`, `canonize`/`normalize`, `merge`, `createNodeMap` (`lib/jsonld.js:131-770`). It is not a data layer or mapper. In a UI it is used to **reshape whatever JSON-LD the server sends into the exact tree the components want**, which is what framing is for.

**Architecture and implementation (evidence).**
- The API facade is `lib/jsonld.js`; each algorithm has its own module (`expand.js`, `compact.js`, `frame.js`, `fromRdf.js`, `toRdf.js`, `context.js`).
- **Context caching:** a module-level `LRU` of resolved contexts (`lib/jsonld.js:103`) is shared across calls through `ContextResolver` (`:156-157`). A UI does not refetch `@context` on every response.
- **Framing:** `lib/frame.js` implements `@embed` (`@once/@always/@never/@link`, `:112-170`), `@explicit` (`:222`), `@requireAll`, `@omitDefault` (`:284`) and named-graph framing (`:192`). These are the knobs that turn a flat graph (for example a CONSTRUCT result) into a nested view model.
- **Document loader:** pluggable. `lib/documentLoaders/xhr.js:19-30` accepts custom `headers` (for example `Authorization: Bearer …`), but `Accept` is reserved. A custom loader is the hook for authenticated contexts or for serving contexts from the bundle.
- **Safe mode:** the `safe: true` option fails on lossy constructs such as undefined terms that get dropped (`lib/jsonld.js:126`, README "Safe Mode"). This is the closest thing to "strict" processing for UI payload validation.
- **Conformance:** the test runner targets the W3C `json-ld-api` and `json-ld-framing` suites (`tests/test.js:1386-1387`). The README claim of conformance is backed by the harness; the suites were not run here.
- **TypeScript:** no first-party types. Consumers use `@types/jsonld` (api-platform/admin imports from `jsonld/jsonld-spec`; shacl-form has `@types/jsonld` in devDependencies).

**Patterns.** Pure functions over documents · Strategy (document loader, RDF parser registry `registerRDFParser`, `lib/jsonld.js:994`) · Shared LRU cache (`:103`) · Event handlers for warnings and safe mode (`:1014-1019`).

**Docs vs code.** "Conforms to JSON-LD 1.1 API/Framing": the test harness is present (`tests/test.js:1386`), not run. "Safe mode": confirmed (`lib/jsonld.js:122-126`, `:529-532`).

**Scores** (the C-criteria are reinterpreted for a JS interop library):

| # | Score | Justification | Evidence |
|---|---|---|---|
| C1 Feature coverage | 4 (as interop) | Full JSON-LD 1.1 + framing + RDF conversion + canonicalisation. No mapping, CRUD or cache by design | `lib/jsonld.js:131-770` |
| C2 Patterns | 4 | Clean algorithm modules, pluggable loader and parsers | `lib/documentLoaders/`, `:994` |
| C3 Dev friendliness | 3 | Good README. No own TS types; error messages follow the spec but are cryptic | `README.md`; `@types/jsonld` |
| C4 Adoption | 4 | 4 runtime deps, browser + Node | `package.json:31-35` |
| C5 Foundations | 5 | It *is* the foundation (W3C reference implementation) | `tests/test.js:1386` |
| C6 Data-centric fit | 4 | Framing gives model-driven view shapes; contexts can be generated from LinkML (`jsonldcontextgen`) | `lib/frame.js` |
| C7 SPARQL portability | n.a. | No SPARQL; consumes CONSTRUCT output as JSON-LD | — |
| C9 Composability | 5 | JSON-LD 1.1 standard; `toRDF` emits N-Quads that feed N3.js / RDF/JS | `lib/toRdf.js` |
| C10 Maintainability | 4 | Stable API through major versions (now 9.x), one org (Digital Bazaar) | `CHANGELOG.md` |
| C8 Health | 4 | CI (`.github/workflows/main.yaml`), W3C suites, 1.8k stars, 30 contributors; last push 2026-03 | GitHub |

**Reuse verdict: ADOPT** as the client-side JSON-LD processor in every variant where the server emits JSON-LD. Generate the frames and contexts from LinkML; do not hand-write them.

**Risks.** Framing is computationally heavy on large graphs, so keep payloads paginated. Remote `@context` fetches make the client depend on the network and are a security surface: bundle the generated context or use a custom document loader. There are no first-party TS types.

---

### 2.2 @api-platform/admin (+ api-doc-parser)

- Repo `api-platform/admin`, commit `ab9239c`, MIT, v4.0.9. `src/` is about 9.0k LOC TS/TSX (including stories and fixtures), 13 test files, CI in `.github/workflows/ci.yml`. 30 contributors.
- Dependencies: `react-admin ^5.8.3`, `@api-platform/api-doc-parser ^0.16.8`, `jsonld ^8.3.2` (`package.json`).
- Docs read: https://api-platform.com/docs/admin/ ("works with APIs in any language or framework as long as they expose a standard Hydra or OpenAPI documentation").

**Summary.** A zero-code admin UI. `<HydraAdmin entrypoint=…>` reads the API's Hydra documentation (or OpenAPI through `<OpenApiAdmin>`), then *guesses* list, show, edit and create screens, fields, inputs, filters and sort. It is the closest existing match to "generated data-management service + generated UI" over **JSON-LD**. It runs on react-admin, so it inherits react-admin's TanStack-Query cache, auth provider and i18n.

**Architecture (GitNexus clusters ≈ folders).**
- `src/hydra/` holds `HydraAdmin.tsx`, `dataProvider.ts` (818 LOC), `fetchHydra.ts` and `schemaAnalyzer.ts`.
- `src/openapi/` mirrors `src/hydra/` for OpenAPI.
- `src/core/` (`AdminGuesser`, `ResourceGuesser`), `src/{list,show,edit,create,field,input}/*Guesser.tsx` and `src/introspection/` (`useIntrospection`, `schemaAnalyzer`) hold the guessers and introspection.
- `src/mercure/` handles live updates.

**Implementation principles (evidence).**
- **The server contract is compacted JSON-LD + Hydra.** `fetchHydra.ts` rejects array bodies and bodies without `@id` (`src/hydra/fetchHydra.ts`, the "Hydra response needs to have an @id member" branch). Collections must carry `member`, `totalItems` and `view` (`dataProvider.ts:577-620`, through `normalizeHydraKey`, which accepts both `hydra:member` and `member`). **Successful responses are used as-is**, so the compact keys are the field names. Only **error** bodies are `jsonld.expand`-ed, to read `hydra:description` and the ConstraintViolation messages (`fetchHydra.ts` error branch; `schemaAnalyzer.ts:70-75`).
- **The query string uses API Platform conventions, not pure Hydra.** Sort is `order[field]`, paging is `page` / `itemsPerPage`, and filters are `field` or `field[]` (`dataProvider.ts:410-440`). Filters and order params are discovered from parameters whose variable contains `order[` (`introspection/schemaAnalyzer.ts:19-43`). A Python backend must emit `hydra:search` `IriTemplate` mappings in this dialect for filters to appear (inferred from `schema.parameters`; the api-doc-parser code was not read).
- **Field typing is vocabulary-coupled.** `getFieldType` hard-codes `schema.org/identifier`, `email` and `url`, then switches on the `xsd:` range (`hydra/schemaAnalyzer.ts:32-66`). The reference label comes from `schema.org/name` (`:18-28`). With an EU/SEMIC model (for example `dct:title` or `skos:prefLabel`) labels fall back to `id` unless they are overridden. The fix is to customise the guessers or to map onto schema.org.
- **Embedded-document cache:** embedded objects with `@id` are replaced by their IRIs and cached, to avoid refetching (`dataProvider.ts:75-105`). This is a client-side identity map.
- **Auth:** `fetchHydra` sets `Authorization: <user.token>` when `options.user.authenticated` (`fetchHydra.ts`). Login and refresh come from a react-admin `authProvider` (story `src/stories/auth/Admin.tsx:3-15` uses basic auth). OIDC needs an authProvider wrapping oidc-client-ts (there is no built-in one).
- **Live updates:** Mercure (SSE). `createSubscription.ts` opens an `EventSource` on the hub with a `mercureAuthorization` JWT cookie and pushes documents into the cache through `useUpdateCache` (`dataProvider/useUpdateCache.ts:7-54`, `queryClient.setQueryData`). This is an L6 → L5 bridge pattern.
- **Server-side validation surfaces in the form:** ConstraintViolation lists are mapped to per-field submission errors (`hydra/schemaAnalyzer.ts:70-95`).

**Patterns.** Schema-driven UI generation (guessers) · Adapter (`dataProvider` per protocol: Hydra, OpenAPI, REST) · Introspection context · Client cache with server push (Mercure → TanStack Query) · Error-document expansion.

**Docs vs code.** "Any language, as long as Hydra/OpenAPI": confirmed in principle, but the **query-parameter dialect and the schema.org label heuristics are API-Platform conventions** (`dataProvider.ts:410-440`, `schemaAnalyzer.ts:18-66`). A Python backend must imitate them. "Client-side validation of required fields": not traced (it lives in api-doc-parser `required` → react-admin validators; not read).

**Scores**

| # | Score | Justification | Evidence |
|---|---|---|---|
| C1 Feature coverage | 4 | Full CRUD UI, filters, sort, pagination, references, server validation errors, live updates. No offline support or bulk | `src/hydra/dataProvider.ts`, `src/mercure/` |
| C2 Patterns | 4 | Clean adapter/guesser split on react-admin's data-provider abstraction | `src/core/`, `src/hydra/` |
| C3 Dev friendliness | 4 | One component gives a working admin; guessers print the code to copy (`useDisplayOverrideCode.ts`) | `src/useDisplayOverrideCode.ts` |
| C4 Adoption | 3 | Brings React + MUI + react-admin; the server must speak the Hydra + API Platform dialect | `package.json` |
| C5 Foundations | 4 | react-admin, TanStack Query, jsonld.js | `package.json` |
| C6 Data-centric fit | 3 | Driven by the API's vocabulary documentation, but heuristics are tied to schema.org | `hydra/schemaAnalyzer.ts:18-66` |
| C7 SPARQL portability | n.a. | Hydra/REST client | — |
| C9 Composability | 4 | JSON-LD + Hydra + OpenAPI + JWT; dialect lock-in on query params | `dataProvider.ts:410-440` |
| C10 Maintainability | 3 | Tracks react-admin majors (v4 → v5); api-doc-parser is still 0.x | `package.json` |
| C8 Health | 4 | CI, 13 tests, Storybook, 515 stars, 30 contributors, push 2026-09 | `.github/workflows/` |

**Reuse verdict: INTEGRATE** (back-office / data-management UI) **if** the generated FastAPI service emits Hydra docs in the API Platform dialect. Otherwise **borrow ideas** (guessers, Mercure → cache bridge, violation → field error mapping). The cheaper equivalent is plain react-admin + `<OpenApiAdmin>`, which works from the FastAPI OpenAPI document with no Hydra needed.

**Risks.** Hidden dialect coupling (query params, schema.org); 0.x api-doc-parser; heavy MUI bundle; a react-admin major upgrade every couple of years.

---

### 2.3 shacl-form (ULB Darmstadt)

- Repo `ULB-Darmstadt/shacl-form`, commit `5f430f5` (2026-10-22), MIT, v3.7.5. `src/` is 6,380 LOC TS; 15 test files (web-test-runner + puppeteer); workflows for npm-publish and static demo only (**no test CI workflow found**). 8 contributors.
- Peer dependencies: `n3`, `jsonld ^9`, `shacl-engine`, `uuid`, `@ro-kit/ui-widgets`, leaflet (optional).
- Docs read: `README.md`, demo https://ulb-darmstadt.github.io/shacl-form/ (referenced in README; not fetched).

**Summary.** A framework-agnostic **web component** `<shacl-form>` (`src/form.ts:35`, `customElements.define` `:716`). It renders edit, view and **query** forms from SHACL shapes, validates them with `shacl-engine`, and serialises the result to Turtle, N-Triples or JSON-LD. It is the most capable maintained "UI from SHACL" component and works in React, Vue, Angular or plain HTML.

**Implementation principles (evidence).**
- **Inputs:** `data-shapes` or `data-shapes-url`, `data-values` or `data-values-url`, `data-values-subject`, `data-values-namespace` (IRI minting; empty yields blank nodes), `data-values-graph` (named graph), `data-language`, `data-mode=edit|view|query` (README:84-104).
- **Root shape resolution:** `dcterms:conformsTo`, then `rdf:type` / `sh:targetClass`, then the first node shape (README:86-89). It writes a `dcterms:conformsTo` triple to the root shape unless that is disabled (README:100).
- **Validation:** `validate()` builds the data graph and calls `config.validator.validate(...)` (shacl-engine) for the root node (`src/form.ts:458-502`). The `submit` event fires only when the data is valid (README:99).
- **Output:** `toRDF()` returns an N3 `Store`; `serialize(format)` (`form.ts:290-303`) uses the N3 Writer, except for `application/ld+json`, which a **hand-rolled `serializeJsonld`** handles (`src/serialize.ts:23-46`). That writer emits **one node object per triple**, with no `@context` and no grouping of the same subject. The named graph from `data-values-graph` is dropped. The output is valid JSON-LD but neither compacted nor framed, so a server should parse it as RDF, or the client should run it through `jsonld.fromRDF`/`compact`. **Finding:** if the server contract is compacted JSON-LD, add a `jsonld.compact(…, generatedContext)` step.
- **Extension points:** `setRdfUrlResolver` (how it fetches; the hook for an auth header or a backend API), `setClassInstanceProvider` (choices for `sh:class` pickers), `ResourceLinkProvider` (lazy listing of conforming resources) and `registerPlugin` (custom widgets) (`src/plugin.ts:65-75`, `form.ts:412-427`).
- **Query mode:** builds SPARQL SELECTs from the shape (`src/query/sparql.ts`: dataset scope default or named, projection, `orderBy`, `limit`/`offset`, facets). This gives shape-driven search UIs against a SPARQL endpoint.

**Patterns.** Web component (framework-neutral) · Shape-driven UI generation · Plugin registry · Provider callbacks for remote lookups · Shape → query builder.

**Docs vs code.** Edit, view and query modes, validation and serialisation are all confirmed in `form.ts` and `query/`. "JSON-LD output" is confirmed, but it is per-triple and uncompacted (`serialize.ts:23-46`).

**Scores**

| # | Score | Justification | Evidence |
|---|---|---|---|
| C1 Feature coverage | 4 | Edit, view, query, validation, lang-strings, `sh:class` pickers, rdf:List, maps, named graph | `form.ts`, `test/rdf-list.test.ts` |
| C2 Patterns | 4 | Web component with clean provider and plugin seams | `plugin.ts:65-75` |
| C3 Dev friendliness | 4 | Attribute-only happy path, demo site; TS types shipped | README:71-104 |
| C4 Adoption | 4 | Drop-in element; peer deps are RDF/JS standards | `package.json` peers |
| C5 Foundations | 5 | N3.js, jsonld.js, shacl-engine (RDF/JS) | `package.json` |
| C6 Data-centric fit | 5 | The UI *is* the SHACL shape, which LinkML `shaclgen` can generate (generator verified in the LinkML tree; output not tested with shacl-form) | README:84 |
| C7 SPARQL portability | 4 | Query mode emits plain SPARQL 1.1 SELECT | `query/sparql.ts` |
| C9 Composability | 5 | SHACL, RDF/JS, JSON-LD, Turtle; any framework | — |
| C10 Maintainability | 3 | Small, but frequent releases (3.x) and no test CI | `.github/workflows/` |
| C8 Health | 3 | 93 stars, 8 contributors, active (2026-10), tests present but not in CI | GitHub |

**Reuse verdict: BORROW IDEAS / vendor-in** (fails DEC-5 on stars). It is the strongest candidate for **U-features** (shape-driven forms). If the developer relaxes DEC-5 for leaf UI widgets, it can be adopted as a replaceable leaf component behind a thin wrapper, which is low risk because it is a web component with a standard SHACL input.

**Risks.** Below the DEC-5 threshold; a single institution; uncompacted JSON-LD output; SHACL constructs that LinkML `shaclgen` emits may not all be rendered (not tested).

---

### 2.4 LDO — Linked Data Objects (o-development)

- Repo `o-development/ldo`, commit `80fb5ce`, MIT. An 18-package monorepo with about 25k LOC TS in `packages/*/src`. Largest packages: `connected-solid` 6.3k, `jsonld-dataset-proxy` 2.6k, `type-traverser` 2.6k, `connected` 2.5k. Lint + test workflows. 8 contributors. npm `@ldo/ldo` **1.0.0-alpha.51**.
- Docs read: `packages/ldo/README.md`, https://ldo.js.org/latest/ ("Solid and RDF without the Complexity"; Solid, NextGraph and raw-RDF guides; **SPARQL endpoints not mentioned**).

**Summary.** LDO turns an RDF/JS dataset into **typed, JSON-LD-shaped, mutable JS objects** through ES Proxies (`packages/jsonld-dataset-proxy/src/ProxyContext.ts:54`). A CLI generates TS typings **and a JSON-LD context** from ShEx, and from SHACL through `@jeswr/shacl2shex` (`packages/cli/src/util/forAllShapes.ts:3-57`). Edits are recorded in a transactional dataset, and the diff becomes a SPARQL Update. "Connected" plugins sync with Solid pods and NextGraph. Bindings exist for React, Vue and Svelte.

**Implementation principles (evidence).**
- **Typing:** `schema-converter-shex/src/typing/shexjToTyping.ts` (ShEx → TS interfaces) and `src/context/shexjToContext.ts` (ShEx → JSON-LD context). One shape yields both a static type and a runtime mapping, the same idea as LDkit's schema-as-value but driven by codegen.
- **Object model:** proxies over the dataset. Property names come from the generated JSON-LD context, so `person.name = "x"` writes quads. Language preferences are supported (`jsonld-dataset-proxy/src/language/languageMapProxy.ts:40`). Collections are `Set`-like (`knows.add(...)`).
- **Unit of Work by diff:** `startTransaction` / `commitTransaction` / `transactionChanges` (`packages/ldo/src/methods.ts:233-308`). `toSparqlUpdate` turns the change set into `DELETE DATA {…} INSERT DATA {…}` (`methods.ts:358`, `rdf-utils/src/datasetChanges.ts:18-35`). Connected datasets push it with `commitToRemote()` (`connected/src/ConnectedLdoTransactionDataset.ts:177`). The Solid plugin sends `Content-Type: application/sparql-update` PATCH (`connected-solid/src/requester/requests/updateDataResource.ts:73`).
- **Remote model:** a `ConnectedPlugin` interface with `getResource`, `createResource`, … (`connected/src/types/ConnectedPlugin.ts:10-35`). Only the **Solid** and **NextGraph** plugins exist. **There is no SPARQL-endpoint, JSON-LD-REST or Hydra plugin.** Notifications use Solid WebSocketChannel2023 (`connected-solid/src/notifications/Websocket2023NotificationSubscription.ts`). Link traversal exists (`connected/src/linkTraversal`).
- **Auth:** a `fetch` is injected into the Solid plugin (`SolidConnectedPlugin.ts:11`), typically an authenticated fetch from `solid-client-authn`.
- **JSON-LD output:** `toJsonLd()` **throws "Not Implemented"** (`packages/ldo/src/methods.ts:413-415`). Despite the JSON-LD-shaped objects, LDO cannot serialise to JSON-LD; Turtle and N-Triples work.

**Patterns.** Proxy-based object view over a graph · Unit of Work by dataset diff · Codegen of types + context from shapes · Plugin per platform · Reactive bindings (`react/src/util/useTrackingProxy.ts:11`).

**Docs vs code.** "RDF without the complexity": confirmed for Solid. SPARQL endpoints are neither documented nor implemented. JSON-LD serialisation is **claimed by the API surface, not implemented** (`methods.ts:413`).

**Scores**

| # | Score | Justification | Evidence |
|---|---|---|---|
| C1 Feature coverage | 3 | Typed CRUD on objects, transactions, lang maps, notifications. Only Solid/NextGraph remotes; no query API; no JSON-LD out | `methods.ts:233-415`, `ConnectedPlugin.ts` |
| C2 Patterns | 5 | Proxy object view + Unit of Work by diff + plugin per backend: the clearest client-side UoW found | `methods.ts:233-358` |
| C3 Dev friendliness | 4 | Generated types, React/Vue/Svelte hooks, docs site | `packages/react`, ldo.js.org |
| C4 Adoption | 2 | Alpha versions, 18 packages, Solid-centric setup (`@ldo/cli init`) | npm 1.0.0-alpha.51 |
| C5 Foundations | 4 | RDF/JS, N3, ShEx (shexj), shacl2shex | package.json files |
| C6 Data-centric fit | 5 | Shape-first, plain-object view, persistence via plugins | `schema-converter-shex/` |
| C7 SPARQL portability | 2 | Generates SPARQL Update text but has no endpoint plugin | `datasetChanges.ts:18-35` |
| C9 Composability | 3 | Standards inside (ShEx, SHACL, SPARQL Update, RDF/JS), but remotes only Solid/NextGraph | `connected-*` |
| C10 Maintainability | 2 | Alpha, many packages, low downloads (223/wk) | npm |
| C8 Health | 3 | Tests + lint CI, active (2026-10-31), 73 stars, 8 contributors | GitHub |

**Reuse verdict: BORROW IDEAS** (fails DEC-5; alpha).
1. A client-side **Unit of Work by graph diff → `DELETE DATA`/`INSERT DATA`**, the same shape a Python UoW can produce.
2. **Types + JSON-LD context generated together from one shape.**
3. **A plugin port per backend.** A `ConnectedPlugin` for an rdf-persistence JSON-LD API would be the integration point if LDO is ever adopted.

**Risks.** Alpha churn; Solid coupling; `toJsonLd` missing; `DELETE DATA` / `INSERT DATA` patches carry no precondition, so lost updates are possible without ETags.

---

### 2.5 Comparison with LDkit (already analysed)

| Concern | LDkit | LDO | api-platform/admin | shacl-form | TanStack Query + OpenAPI codegen |
|---|---|---|---|---|---|
| Server contract | Raw SPARQL 1.1 Q+U | Solid / NextGraph | JSON-LD + Hydra (or OpenAPI) | Any RDF via URL resolver; SPARQL for query mode | REST / OpenAPI (JSON or JSON-LD bodies) |
| Types from | Schema literal (inferred) or SHACL/ShEx codegen | ShEx/SHACL codegen | Runtime introspection (no static types) | Runtime from SHACL (no static types) | OpenAPI (FastAPI) → TS + zod |
| Write model | Per-property DELETE/INSERT/WHERE | Diff → DELETE DATA/INSERT DATA | JSON-LD POST/PUT/PATCH | Graph → serialise → caller sends | Whatever the API defines |
| Cache / optimistic | none | in-memory dataset (cache) | TanStack (via react-admin), Mercure push | none | TanStack: cache, invalidation, optimistic |
| Auth | your `fetch` | injected `fetch` (Solid-OIDC) | `Authorization` header + authProvider | `setRdfUrlResolver` | your fetch / interceptor (oidc-client-ts) |
| Server-side ACL compatible | No (open endpoint) | Yes (Solid WAC/ACP) | Yes (API enforces) | Yes (API enforces) | Yes (API enforces) |
| DEC-5 | fail | fail | pass | fail | pass |

---

## 3. Patterns catalogue (L5)

| # | Pattern | Seen in | Note for MWBv2 |
|---|---|---|---|
| P-L5-1 | **Contract-first typed client from OpenAPI** (types + fetch client + query hooks + zod + mocks) | orval, hey-api, openapi-typescript | FastAPI already emits OpenAPI; Pydantic models are LinkML-generated, so the TS types trace back to LinkML with no new generator |
| P-L5-2 | **Server-state cache with invalidation and optimistic updates** | TanStack Query, react-admin (`useUpdateCache.ts`) | One cache library for every variant; the backend must give stable IDs (IRIs) as cache keys |
| P-L5-3 | **JSON-LD reshape on the client** (compact with a generated context, frame into view models) | jsonld.js (`frame.js`, `compact.js`) | Generate the context (`jsonldcontextgen`) and frames from LinkML; bundle the context (no remote fetch) |
| P-L5-4 | **Schema-introspected UI (guessers)** | api-platform/admin (Hydra/OpenAPI) | Fastest back office; dialect coupling |
| P-L5-5 | **Shape-driven form + client-side validation** | shacl-form, shaperone | The SHACL from LinkML drives the form; the server re-validates (pyshacl) |
| P-L5-6 | **JSON-Schema-driven forms** | RJSF, JSON Forms | LinkML `jsonschemagen` or Pydantic JSON Schema; DEC-5-passing alternative to shacl-form, but loses IRIs and lang-strings unless the schema encodes them |
| P-L5-7 | **Proxy object view + client-side Unit of Work by diff** | LDO (`methods.ts:233-358`) | Only needed for a "near-direct to the graph" UI (MWBv2 runbook) |
| P-L5-8 | **Schema-as-value with inferred types, SPARQL directly** | LDkit | Read-heavy UIs against a read-only SPARQL endpoint |
| P-L5-9 | **Server push → cache patch** (SSE/WebSocket events update the query cache) | api-platform/admin Mercure (`createSubscription.ts`, `useUpdateCache.ts`), LDO Solid notifications | Bridges L6 (delta-notifier-like events) to L5 |
| P-L5-10 | **Auth via injected fetch / interceptor** (Bearer from an OIDC client) | api-platform/admin `fetchHydra`, LDO `fetch` option, jsonld.js loader `headers` | One `authFetch` (oidc-client-ts / react-oidc-context, Zitadel) passed to every library |
| P-L5-11 | **Server-validation errors mapped to form fields** | api-platform/admin (ConstraintViolation → field errors) | Python service returns SHACL validation reports or RFC 9457 problem details with a JSON pointer / property path |
| P-L5-12 | **JSON:API resource store** (relationships, includes, sparse fieldsets) | ember-data/WarpDrive, Orbit, kitsu | Only if the semantic.works-style JSON:API contract (X6) is chosen |
| P-L5-13 | **Cypress + Gherkin over an MSW/fixture backend** | orval MSW mocks, cypress-cucumber-preprocessor | Generated mocks from the same OpenAPI keep the E2E fixtures in sync |

---

## 4. What each option expects from the server, and how it plugs into MWBv2 and an ACL-agnostic rdf-persistence

MWBv2 chain: UML → model2owl → LinkML → (Pydantic + rdf-persistence + authz) → FastAPI data-management service → TS UI.

| Server contract (L4) | Client stack (L5) | Generated from LinkML | ACL fit (DEC-8) | Cost / risk |
|---|---|---|---|---|
| **A. JSON-LD REST + OpenAPI** (FastAPI, compacted JSON-LD bodies with a generated `@context`, `application/ld+json`) | orval or hey-api → typed client + **TanStack Query** hooks + zod; jsonld.js only where expansion or framing is needed; RJSF/JSON Forms or shacl-form for forms; oidc-client-ts | Pydantic (`gen-pydantic`) → FastAPI OpenAPI → TS; `jsonldcontextgen` → context; `shaclgen` → forms | Clean. The API is the policy enforcement point; rdf-persistence stays ACL-agnostic behind it | Lowest maintenance; everything DEC-5-passing; JSON-LD semantics are "opaque" to the TS types (keys are compact terms) |
| **B. Hydra + JSON-LD** (A plus `hydra:apiDocumentation`, `hydra:Collection`, `IriTemplate` search in the API Platform dialect) | **@api-platform/admin** (back office) + the A stack for the product UI | A plus a Hydra-doc generator (new; LinkML has none; OldMan X8 idea) | Clean, as in A | Adds the Hydra generator and dialect coupling; buys a zero-code admin |
| **C. JSON:API** (semantic.works mu-cl-resources dialect, X6) | ember-data/WarpDrive or Orbit/kitsu + TanStack Query | A JSON:API generator (new), mirroring mu-cl-resources | Clean | Loses JSON-LD on the wire; reuses the semantic.works frontend ecosystem |
| **D. Read-only SPARQL 1.1 endpoint** (+ API for writes) | **LDkit** or Comunica for reads (and shacl-form query mode); A for writes | LDkit schema from `shaclgen` → `ldkit shacl-to-schema` | Needs an authorising SPARQL proxy (sparql-parser / mu-authorization style, or store-native graph ACLs); writes go through the API | Flexible reads with "GraphQL-like freedom" (the MWBv2 runbook wish); the read ACL must be graph-level in the proxy |
| **E. Solid / LDP** (pods) | LDO or @inrupt/solid-client + solid-client-authn | `shexgen` → `ldo build` | Solid WAC/ACP | Only if a Solid deployment is a requirement; otherwise avoid |
| **F. Fluree** (FlureeQL JSON-LD, JWT policies) | Custom fetch + TanStack Query (fluree-client is near-dead) | n.a. | Fluree policies | Vendor lock-in noted in the MWBv2 digest |

Notes:
- In **all** variants the frontend auth is the same: an OIDC client (oidc-client-ts / react-oidc-context, or `@zitadel/react`) gets an access token, and one `authFetch` adds `Authorization: Bearer` for TanStack Query fetchers, jsonld.js document loaders, LDkit engines and shacl-form's `setRdfUrlResolver`. Nothing in L5 should hold policy; the client only hides UI that the API reports as forbidden (U9 below).
- **Caching and optimistic updates** come from TanStack Query in all of A–D. rdf-persistence must supply stable IRIs as IDs and **ETags / version predicates** so that optimistic writes can fail cleanly (none of LDkit, LDO or shacl-form sends preconditions).
- **E2E (Cypress + Gherkin):** orval and hey-api can generate MSW handlers from the same OpenAPI, so component and E2E tests run on a fake backend. For variant D, the LDkit tests show the pattern of Comunica over an in-memory N3 store (`ldkit.md` D5).

## 5. Architecture variants enabled (recommendation per variant)

1. **V-A "Typed REST over JSON-LD" (recommended default).** FastAPI + Pydantic (LinkML) → OpenAPI → **orval/hey-api + TanStack Query + zod**, **jsonld.js** for context/frame where needed, **oidc-client-ts**, **RJSF or JSON Forms** (DEC-5) or **shacl-form** (ideas/vendor-in) for model-driven forms, **Cypress + badeball cucumber**. Every L5 dependency passes DEC-5 except shacl-form. This is the coherent, easiest-to-maintain stack.
2. **V-B "V-A + generated admin".** Add Hydra docs and **@api-platform/admin** for the data-management back office. Cheaper alternative: react-admin with `<OpenApiAdmin>` from the OpenAPI already produced in V-A.
3. **V-C "semantic.works-compatible".** A JSON:API entrypoint (X6) + **WarpDrive/ember-data** or **Orbit/kitsu**. Choose only to reuse the semantic.works frontend ecosystem.
4. **V-D "Graph-direct reads".** V-A for writes plus a **read-only, ACL-filtered SPARQL endpoint** consumed by **LDkit** (or Comunica) and shacl-form query mode. Closest to the MWBv2 runbook's "frontend talks near-directly to the DB through a proxy", but it needs a policy-aware SPARQL proxy (L3 angle).
5. **V-E "Solid".** LDO / @inrupt only if pods are a product requirement.

## 6. Feature inventory (taxonomy ids relevant to this angle, aggregated per deep-dived candidate)

| Id | jsonld.js | api-platform/admin | shacl-form | LDO | Evidence |
|---|---|---|---|---|---|
| X1 JSON-LD (de)serialisation | present | partial (consumes compacted; expands errors only) | partial (per-triple writer, no context) | partial (objects are context-shaped; `toJsonLd` throws) | `lib/jsonld.js`; `fetchHydra.ts`; `serialize.ts:23-46`; `methods.ts:413` |
| X2 other RDF formats | present (N-Quads) | absent | present (N3 Writer, RDF/XML parse) | present (Turtle, N-Triples) | `toRdf.js`; `serialize.ts:6-20`; `methods.ts:408-430` |
| X3 HTTP API exposure | n.a. | consumes Hydra/OpenAPI | n.a. | consumes Solid LDP | — |
| X4 schema/TS types for clients | absent (`@types/jsonld`) | absent (runtime introspection) | absent (runtime from SHACL) | present (ShEx/SHACL → TS) | `schema-converter-shex/src/typing` |
| X5 / X12 change notifications | absent | present (Mercure SSE) | absent | present (Solid WS 2023) | `mercure/createSubscription.ts`; `connected-solid/src/notifications` |
| X7 content negotiation | partial (loader `Accept` fixed) | partial (`fetchJsonLd`) | partial (format by URL resolver) | partial | `documentLoaders/xhr.js:19-30` |
| X8 Hydra contract | n.a. | present (consumer) | absent | absent | `src/hydra/` |
| X11 annotated representations (labels for IRIs) | absent | partial (schema.org/name heuristic) | present (`rdfs:label`/`sh:name` lang-aware) | absent | `hydra/schemaAnalyzer.ts:18-28`; README:93 |
| M5 runtime validation | partial (safe mode) | partial (server violations → fields) | present (shacl-engine) | absent | `form.ts:458-502` |
| M14 schema from SHACL/ShEx | n.a. | absent | present (form from SHACL) | present (types from ShEx/SHACL) | `cli/src/util/forAllShapes.ts:3-57` |
| P4 transactions / UoW | n.a. | absent | absent | present (client-side diff) | `methods.ts:233-358` |
| P6 named graphs | present (graph framing) | absent | partial (`data-values-graph`; dropped in JSON-LD) | partial (`graphOf`) | `frame.js:192`; README:91 |
| L2 lang-tagged literals | present | absent | present | present | `languageMapProxy.ts:40` |
| Q4 pagination / sort | n.a. | present (API Platform dialect) | present (query mode limit/offset/orderBy) | absent | `dataProvider.ts:410-414`; `query/sparql.ts` |
| D3 framework integration | n.a. | React | any (web component) | React/Vue/Svelte | `form.ts:716`; `packages/react` |
| D5 testing support | W3C suites | Storybook + fixtures | puppeteer tests | test-solid-server | `tests/test.js:1386`; `packages/test-solid-server` |
| A1 auth | partial (loader headers) | partial (Bearer from authProvider) | partial (URL resolver) | partial (injected fetch) | see §2 |

### Proposed new features (U* = UI/client area, X* = interop)

| Proposed id | Name | Description | Seen in |
|---|---|---|---|
| **U1** | Generated typed client SDK | The service contract (OpenAPI) is turned into TS types, a fetch client and runtime validators (zod) at build time, with no hand-written client code | orval, hey-api, openapi-typescript |
| **U2** | Server-state cache with invalidation and optimistic updates | Client cache keyed by IRI, invalidated or patched on mutation, with rollback on error | TanStack Query, react-admin `useUpdateCache.ts` |
| **U3** | Push-to-cache bridge | Server events (SSE/WebSocket deltas) patch the client cache directly | api-platform/admin Mercure, LDO Solid notifications |
| **U4** | Shape-driven forms | Edit, view and search forms generated at runtime from SHACL (or JSON Schema), with client-side validation before submit | shacl-form, shaperone, RJSF, JSON Forms |
| **U5** | Schema-introspected admin (guessers) | List/show/edit/create screens derived from the API description, with printable override code | api-platform/admin |
| **U6** | Server validation report → field errors | The API returns violations with a property path; the UI maps them onto form fields | api-platform/admin `hydra/schemaAnalyzer.ts:70-95` |
| **U7** | Client-side Unit of Work by graph diff | Edits to typed objects are tracked and committed as one minimal patch (`DELETE DATA`/`INSERT DATA`, or a JSON patch) | LDO `methods.ts:233-358` |
| **U8** | Generated mocks for UI tests | Fake backend handlers (MSW) generated from the same contract, for component and Cypress/Gherkin E2E tests | orval |
| **U9** | Capability hints for the UI | The API states which operations the current user may perform (for example `Allow` headers, Hydra `supportedOperation` filtered per user, or a `_permissions` field), so the UI hides actions without holding policy | api-platform/admin (Hydra operations; per-user filtering *not found* in code), proposed |
| **U10** | Shape-driven search UI | Search and facet forms generated from shapes, compiled to SPARQL | shacl-form query mode `query/sparql.ts` |
| **X17** | Bundled generated JSON-LD context | The `@context` the server emits is generated from the model and also shipped in the client bundle, so no remote context fetch is needed (performance and security) | jsonld.js document loader + LinkML `jsonldcontextgen` |
| **X18** | Model-generated JSON-LD frames | Frames (view shapes) are generated per aggregate from the model, so client and server agree on nesting and `@embed` | jsonld.js `frame.js`; proposed |
| **X19** | Optimistic-concurrency preconditions on writes | ETag / `If-Match` or a version predicate on every update, so client-side optimistic writes and diff patches cannot lose updates | absent in LDkit, LDO and shacl-form; proposed |
| **X20** | Hydra API documentation generation | `hydra:apiDocumentation` (classes, supportedProperty, IriTemplate search) generated from LinkML; refines X8 | consumer side api-platform/admin; LinkML has no generator (verified: no `hydragen` in `packages/linkml/src/linkml/generators/`) |

## 7. Open questions

1. **Is the wire format compacted JSON-LD with a generated context (variant A), or must the UI see expanded IRIs?** This decides whether jsonld.js is in the hot path or only at the edges.
2. **Will DEC-5 be relaxed for leaf UI components** (shacl-form, LDkit) that sit behind a replaceable seam? If not, V-A forms use RJSF/JSON Forms from LinkML JSON Schema, and IRIs, lang-strings and `sh:class` pickers need custom widgets.
3. **Is a read-only, ACL-filtered SPARQL endpoint for the UI wanted (variant D)?** If yes, the L3 angle must name the proxy (sparql-parser or a store-native policy).
4. **Is a generated back office (react-admin over OpenAPI, or api-platform/admin over Hydra) in the MWBv2 scope?** Hydra adds a generator (X20) and dialect coupling.
5. **React, or framework-neutral?** semantic.works uses Ember; most mature L5 options are React-first (react-admin, TanStack has Vue/Svelte/Solid adapters). shacl-form is framework-neutral.
6. **The LinkML TS / JSON Schema generator quality** (the MWBv2 digest records gaps). Is the OpenAPI from FastAPI/Pydantic the better source of TS types than `gen-typescript`? That is my recommendation, but it is not tested here.

---

## Round 4

Brief: `BRIEF-round4.md`. Read first: `docs/modules/ROOT/pages/architecture/soa/{index,building-blocks,variants,catalogue,feature-taxonomy}.adoc` and `angles/jsclient.adoc`. The clones and commits are the same as in round 3 (`jsonld.js` 7a93609, `api-platform-admin` ab9239c, `shacl-form` 5f430f5, `ldo` 80fb5ce). Nothing was executed. The api-platform-core and fluree-db indexes belong to other angles; no claim in this report depends on them.

### R4.0 How absences were confirmed

All four candidates are **browser / JS client libraries**. Features that only a server, store or policy engine can have were checked by grep over the source trees (`jsonld.js/lib`, `api-platform-admin/src`, `shacl-form/src`, `ldo/packages/*/src`, tests excluded) before they were marked:

| Keyword (regex, case-insensitive) | jsonld.js | api-platform-admin | shacl-form | ldo |
|---|---|---|---|---|
| `If-Match\|ETag` | 0 | 0 | 0 | 0 outside test dirs |
| `idempot` | 0 | 0 | 0 | 0 |
| `cursor` | 0 | 0 | 0 (CSS only) | 0 |
| `graphql` | 0 | 0 | 0 | 0 |
| `rollback\|revert\|undo` | 0 relevant | 0 | 0 | `subscribable-dataset/src/TransactionDataset.ts:271`, `connected-nextgraph/src/resources/NextGraphResource.ts:186` |
| `EventSource\|WebSocket\|subscribe` | 0 | `mercure/*` | 0 | `connected-solid/src/notifications/*` |

They are marked **n.a.** where the feature belongs to a server-side layer (L1–L4, L6 producer side): the PEP/PDP (AZ1–AZ9, AZ11–AZ18, AZ20, AZ23, AZ25–AZ29), Python generation (G1, G2, G10, G18–G22, G26), store transactions (T3, T8, T11) and store features (S15–S19). "Consumer" means the library reads an artefact the feature produces; such cells are marked *partial* when consuming exercises the feature.

### (a) v3 cross-check

J = jsonld.js · A = @api-platform/admin · S = shacl-form · L = LDO.

| Id | J | A | S | L | Evidence |
|---|---|---|---|---|---|
| AZ1 | n.a. | n.a. | n.a. | n.a. | Store-boundary PEP; client libraries (R4.0) |
| AZ2 | n.a. | n.a. | n.a. | n.a. | Server query injection |
| AZ3 | n.a. | n.a. | n.a. | n.a. | Server SPARQL AST PEP |
| AZ4 | n.a. | n.a. | n.a. | n.a. | PDP list filter |
| AZ5 | n.a. | n.a. | n.a. | n.a. | L builds the changeset (`methods.ts:308`) but authorization stays on the Solid server |
| AZ6 | n.a. | n.a. | n.a. | n.a. | Service pipeline |
| AZ7 | n.a. | n.a. | n.a. | n.a. | Service pipeline |
| AZ8 | n.a. | n.a. | n.a. | n.a. | Store policy |
| AZ9 | n.a. | n.a. | n.a. | n.a. | Store policy |
| AZ10 | absent | absent | absent | partial | L reads and writes Solid WAC ACL documents as RDF (`connected-solid/src/wac/setWacRule.ts`, `_ldo/wac.shapeTypes.ts`); evaluation is on the server |
| AZ11 | n.a. | n.a. | n.a. | n.a. | Store / PDP |
| AZ12–AZ18 | n.a. | n.a. | n.a. | n.a. | semantic.works / store / IdP mapping, all server side |
| AZ19 | partial | present | partial | present | J: static `headers` per document loader (`lib/documentLoaders/xhr.js:19-30`). A: `Authorization` set per request from `options.user.token` (`src/hydra/fetchHydra.ts`). S: only through `setRdfUrlResolver` (`src/form.ts:427`). L: injected `fetch` (`connected-solid/src/SolidConnectedPlugin.ts:11`) |
| AZ20 | n.a. | n.a. | n.a. | n.a. | Proxy hop caching |
| AZ21 | absent | absent | absent | absent | No principal parameter in any write API |
| AZ22 | absent | absent | n.a. | absent | J: module-wide context LRU (`lib/jsonld.js:103`); it holds contexts, not data, so the risk is low. A: react-admin query cache not partitioned by user (whether react-admin clears it on logout was not verified). S: no cache. L: one dataset cache per `createSolidLdoDataset` instance |
| AZ23 | n.a. | n.a. | n.a. | n.a. | Server gate |
| AZ24 | absent | partial | absent | partial | A: HTTP status carried in `HttpError` (`fetchHydra.ts`); 401/403 handling is react-admin's `authProvider.checkError`. L: typed `UnauthenticatedHttpError` (`connected-solid/src/requester/results/error/HttpErrorResult.ts:10,77`) |
| AZ25–AZ29 | n.a. | n.a. | n.a. | n.a. | Server or PDP side |
| G1 | n.a. | n.a. | n.a. | n.a. | Python domain classes |
| G2 | n.a. | n.a. | n.a. | n.a. | Python mapper |
| G3 | n.a. | n.a. | n.a. | absent | L: the CLI renders bundled EJS templates from a fixed path (`cli/src/build.ts:69`, `cli/src/templates/*.ejs`); no override option |
| G4 | n.a. | n.a. | n.a. | partial | L: one output set per shape file (`cli/src/util/forAllShapes.ts`); imports are not followed |
| G5 | n.a. | absent | n.a. | absent | L: `@id` is typed as plain `string` (`schema-converter-shex/src/typing/ShexJTypingTransformer.ts:108-113`). A: ids are plain strings |
| G6 | present | absent | present | partial | J: `@language` value objects throughout. S: langString inputs and `sh:languageIn` (`src/property-template.ts:89`, `constants.ts:21`). L: runtime `LanguageSet` (`jsonld-dataset-proxy/src/language/languageSet.ts:9`), but no lang-string *type* in the generated typings |
| G7 | partial | absent | absent | partial | J: applies contexts and frames (consumer, `lib/frame.js`) but generates nothing. L: generates the context (`schema-converter-shex/src/context/`) but no frames |
| G8 | n.a. | absent | absent | present | L: typings and JSON-LD context are generated together (`cli/src/templates/typings.ejs`, `context.ejs`), and the proxy uses the context as the object↔RDF mapping (`jsonld-dataset-proxy/src/ContextUtil.ts`) |
| G9 | n.a. | partial | n.a. | n.a. | A consumes OpenAPI (`src/openapi/`); consumer only |
| G10 | n.a. | n.a. | n.a. | n.a. | Server routes |
| G11 | n.a. | partial | n.a. | n.a. | A consumes Hydra `ApiDocumentation` (`src/hydra/`); consumer only |
| G12 | absent | absent | absent | absent | grep `graphql`: 0 |
| G13 | n.a. | partial | n.a. | n.a. | A consumes the API Platform filter/sort grammar (`introspection/schemaAnalyzer.ts:19-43`, `hydra/dataProvider.ts:410-440`) |
| G14 | n.a. | n.a. | partial | n.a. | S: query mode builds SELECTs from the shape (`src/query/sparql.ts`), client-side |
| G15 | n.a. | n.a. | n.a. | n.a. | Server profiles |
| G16 | n.a. | partial | partial | present | L: TS typings + context generated from shapes (`schema-converter-shex/`). A and S: model derived at runtime (introspection / SHACL); nothing generated |
| G17 | n.a. | n.a. | absent | present | L: SHACL → ShEx via `@jeswr/shacl2shex` over many files (`cli/src/util/forAllShapes.ts:3-57`) |
| G18–G22 | n.a. | n.a. | n.a. | n.a. | Build-time Python / OWL / SPARQL / RML generation |
| G23 | absent | absent | partial | absent | S: root shape picked from `dcterms:conformsTo`, then `rdf:type` / `sh:targetClass` (README:86-89); not a designator slot |
| G24 | absent | absent | partial | absent | S: `sh:in` lists (which may hold IRIs) become choices (`src/property-template.ts:86`, `util.ts:133`) |
| G25 | n.a. | absent | absent | partial | L: per-dataset subject proxies with object identity and a pluggable dataset (`jsonld-dataset-proxy/src/ProxyContext.ts:54`); the codec is fixed |
| G26 | n.a. | n.a. | n.a. | n.a. | Python mapper config |
| G27 | n.a. | n.a. | n.a. | partial | L: `ldo build` regenerates `_ldo/` (`cli/src/build.ts`); no version pinning or golden-file check |
| T1 | n.a. | absent | n.a. | present | L: one request with `DELETE DATA … INSERT DATA …` (`rdf-utils/src/datasetChanges.ts:18-35`; Solid PATCH `updateDataResource.ts:73`). A: one request per record; `updateMany` / `deleteMany` = N parallel calls (`hydra/dataProvider.ts:793-804`) |
| T2 | n.a. | absent | n.a. | absent | No version or precondition (R4.0) |
| T3 | n.a. | n.a. | n.a. | n.a. | Vendor transaction API |
| T4 | n.a. | absent | n.a. | partial | L: client-side revert of the local dataset when the NextGraph commit fails (`connected-nextgraph/src/resources/NextGraphResource.ts:186-190`); the remote is not compensated |
| T5 | n.a. | n.a. | n.a. | present | L: the transaction dataset overlays uncommitted changes on reads (`subscribable-dataset/src/TransactionDataset.ts`) |
| T6 | n.a. | absent | n.a. | absent | No retry |
| T7 | n.a. | n.a. | n.a. | absent | One update strategy per plugin |
| T8 | n.a. | n.a. | n.a. | n.a. | Store savepoints |
| T9 | absent | absent | absent | absent | grep `idempot`: 0 |
| T10 | n.a. | n.a. | n.a. | present | L: `rollback()` discards the overlay, and the proxies read from the dataset (`TransactionDataset.ts:271`) |
| T11 | n.a. | n.a. | n.a. | n.a. | Proxy batching |
| E1 | n.a. | n.a. | n.a. | n.a. | Producer side |
| E2 | absent | absent | absent | absent | No RDF Patch; L uses SPARQL Update |
| E3 | n.a. | absent | n.a. | present | L: a Solid "Update" notification triggers `read()` of the resource (`connected-solid/src/resources/SolidResource.ts:976-978`). A: Mercure carries the whole document (`mercure/createSubscription.ts`) |
| E4 | n.a. | n.a. | n.a. | n.a. | Hub / server side; A only sends the `mercureAuthorization` JWT cookie |
| E5 | absent | absent | absent | absent | No sequence handling in consumers |
| E6–E8 | n.a. | n.a. | n.a. | n.a. | Producer side |
| E9 | n.a. | present | absent | present | A: Mercure SSE (`mercure/createSubscription.ts`). L: Solid WebSocketChannel2023 (`connected-solid/src/notifications/Websocket2023NotificationSubscription.ts:100`) |
| U1 | n.a. | absent | absent | partial | L generates typings from shapes, not from the service contract |
| U2 | absent | present | absent | partial | A: react-admin TanStack cache, `mutationMode` (pessimistic by default, `useOnSubmit.ts:24`), `useUpdateCache.ts:35-54`. L: local dataset as cache, optimistic apply + revert on NextGraph (`NextGraphResource.ts:186`) |
| U3 | absent | present | absent | present | A: Mercure → `queryClient.setQueryData`. L: notification → re-read → dataset → reactive hooks |
| U4 | absent | partial | present | absent | S: `src/form.ts:458-502`. A: inputs guessed from Hydra fields, no shape constraints |
| U5 | absent | present | absent | absent | A: `src/core/*Guesser.tsx` |
| U6 | absent | present | partial | absent | A: violations → fields (`hydra/schemaAnalyzer.ts:70-95`). S: shows the *client-side* SHACL report on fields; there is no server-report input |
| U7 | absent | absent | absent | present | L: `methods.ts:233-358` |
| U8 | absent | absent | absent | absent | A has hand-written Storybook fixtures (`src/__fixtures__/`); nothing generated |
| U9 | absent | partial | absent | absent | A: `hasEdit` / `hasCreate` from the documented operations (`core/ResourceGuesser.tsx:32-43`); per user only if the server filters its docs per user. L: no `WAC-Allow` parsing (grep: 0) |
| U10 | absent | partial | present | absent | S: query mode (`src/query/`). A: filter inputs from `IriTemplate` parameters (REST, not SPARQL) |
| RAD3 | n.a. | partial | absent | partial | A: guessers print override code (`useDisplayOverrideCode.ts`). L: `@ldo/cli init/create` (`cli/src/init.ts`, `create.ts`) |
| RAD4 | n.a. | partial | n.a. | n.a. | A: no edit or create screens when the operations are absent (`ResourceGuesser.tsx:32-43`) |
| X17 | n.a. | partial | n.a. | n.a. | A consumes either Hydra or OpenAPI views of one API (`src/hydra`, `src/openapi`) |
| X18 | absent | absent | absent | absent | A: N parallel requests (`dataProvider.ts:793-804`); no client-local ids anywhere |
| X19 | absent | absent | absent | absent | grep `If-Match\|ETag`: 0 (R4.0) |
| X20 | n.a. | partial | absent | n.a. | A: follows `hydra:view` next/previous (`dataProvider.ts:617-626`) but requests by `page` number |
| X21 | n.a. | partial | absent | present | A: `PATCH` with `application/merge-patch+json` when documented (`dataProvider.ts:376, 498-501`). L: SPARQL Update PATCH (`updateDataResource.ts:73`). S: serialises the whole graph (`form.ts:290-303`) |
| X22 | partial | absent | n.a. | present | J: enabler (custom `documentLoader`, `expandContext`). A: fetches contexts remotely (`fetchHydra.ts` documentLoader → `fetchJsonLd`). L: the generated context ships in `_ldo/*.context.ts` (`templates/context.ejs`) |
| D11 | partial | present | absent | partial | A: Hydra error body expanded and its description shown (`fetchHydra.ts` error branch). J: `JsonLdError` with code and details (`lib/JsonLdError.js`). L: typed `HttpErrorResult` |
| D12 | absent | absent | absent | absent | No per-model exception types |
| D13 | absent | absent | absent | absent | — |
| S15–S19 | n.a. | n.a. | n.a. | n.a. | Store features |

Counts over the 102 v3 features (grouped rows count once per id they cover):

| | present | partial | absent | n.a. |
|---|---|---|---|---|
| jsonld.js | 1 | 4 | 23 | 74 |
| @api-platform/admin | 7 | 13 | 27 | 55 |
| shacl-form | 3 | 6 | 27 | 66 |
| LDO | 13 | 12 | 23 | 54 |

Reading the counts: the v3 additions are mostly server-side (AZ, T, S, most of G). Among the four clients, **LDO covers the most v3 features (client UoW T1/T5/T10, twin projections G8, E3/E9, U3/U7, X21/X22)**, and **@api-platform/admin covers the UI features** (U2/U3/U5/U6, E9, AZ19). **No client sends preconditions (X19), idempotency keys (T9) or atomic batches (X18)**, so in every variant the service must offer them and the generated client must wrap them.

### (b) Purpose and origin

#### Deep-dived candidates

| Tool | Built for | Who / context | Design angle | Fit in L0–L6 and V1–V5 |
|---|---|---|---|---|
| jsonld.js | Being the reference implementation of the W3C JSON-LD API, Framing and canonicalisation algorithms | Digital Bazaar (Manu Sporny, Dave Longley), editors of the JSON-LD specs; built for Verifiable Credentials / Linked Data Signatures (canonize + safe mode, `lib/jsonld.js:529-532`) | Spec-reference-first, correctness and security over ergonomics | L5 dependency in every variant that puts JSON-LD on the wire (V1, V3, V4, V5). In V2 (JSON:API) it is used only at the edges |
| @api-platform/admin | Giving API Platform (PHP/Symfony) users a free admin by reading the Hydra/OpenAPI docs that API Platform already emits | Les-Tilleuls.coop (Kévin Dunglas), API Platform core team, on top of Marmelab's react-admin | API-doc-first; it assumes API Platform conventions (query params, schema.org, Mercure) | L5 back office in V1 / V3 / V4 **if** the service imitates the API Platform dialect (Hydra + `order[]` / `page` / `itemsPerPage`, schema.org label hints). It does not fit V2 (JSON:API) or V5 (SPARQL) |
| shacl-form | Letting research data managers describe metadata with SHACL and get forms for entering and viewing it | ULB Darmstadt (university library), research data management (NFDI context) | Shape-first, framework-neutral web component, store-agnostic (data in and out as RDF) | L5 forms in every variant (it only needs shapes + RDF); query mode serves V5. Below DEC-5, so keep it behind a seam |
| LDO | Making Solid app development feel like plain JS objects | Jackson Morgan (`jaxoncreed`, 523 of ~600 commits), o-development; Solid community, later NextGraph | Shape-first codegen + proxy objects + plugin per decentralised platform | L0/L5 ideas. It plugs into none of V1–V5 without a new `ConnectedPlugin` for our API; fits only Solid products (outside V1–V5) |

#### Desk-scan candidates (purpose and origin as in `catalogue.adoc`, checked; variant fit below)

Corrections to the catalogue are in (d). Origins confirmed from repository ownership and contributor lists (`gh api repos/<r>/contributors`): N3.js (Ruben Verborgh, 798 commits; jeswr second), LDflex (Ruben Verborgh as originator; Jesse Wright `jeswr` is now the main human committer), Comunica (IDLab Ghent), rdf-object and jsonld-*-parser (Ruben Taelman), rdf-validate-shacl (Zazuko), Alcaeus and shaperone (hypermedia-app, Tomasz Pluskiewicz), Soukai (Noel De Martin), fdr (Kobrix, `bolerio` = Borislav Iordanov), TanStack Query (Tanner Linsley), SWR (Vercel), react-admin (Marmelab), refine (refinedev), WarpDrive (Ember community), Orbit (Cerebris, Dan Gebhardt), openapi-typescript (Drew Powers), json-schema-to-typescript (Boris Cherny), zod (Colin McDonnell), RJSF (Mozilla origin), JSON Forms (EclipseSource), oidc-client-ts (authts, fork of Brock Allen's oidc-client-js), `@zitadel/react` (ZITADEL; its only dependency is `oidc-client-ts ^3.3.0`, npm registry), Cypress (Cypress.io).

### (c) Variant fit

S = supports (works as-is), E = enables (makes the variant or approach materially easier), B = blocks (rules it out or forces a rework), — = not relevant. Approaches: A runtime mapper, B generated mapper + routes + TS client, C generic zero-code service.

| Candidate | V1 | V2 | V3 | V4 | V5 | A | B | C | Note |
|---|---|---|---|---|---|---|---|---|---|
| jsonld.js | E | S | E | E | S | S | E | S | Needed wherever JSON-LD is on the wire; in B it applies the generated context and frames |
| @api-platform/admin | S* | B | S* | S* | — | S | S | E | *Only with the API Platform Hydra dialect. Runtime introspection makes it the natural UI for C |
| shacl-form | S | S | S | S | E | S | S | E | Framework-neutral (works in V2's Ember); query mode enables V5; shapes at runtime suit C |
| LDO | B | B | B | B | B | — | S | — | Needs a new remote plugin for any of V1–V5; ShEx/SHACL codegen parallels B |
| LDkit | S | — | S | S | E | S | E | S | Graph-direct reads (V5); codegen from SHACL parallels B |
| N3.js / @rdfjs/types | S | S | S | S | E | S | S | S | Interop under jsonld.js, LDkit, shacl-form |
| Comunica | — | — | S | S | E | S | S | S | Client-side SPARQL / federation for V5 |
| rdflib.js | — | — | — | — | S | — | — | — | Solid-oriented |
| TanStack Query | E | S | E | E | E | S | E | S | One cache for every variant |
| SWR | S | S | S | S | S | S | S | S | Lighter alternative |
| react-admin | S | S | S | S | — | S | S | E | Data-provider port: Hydra, OpenAPI, JSON:API |
| refine | S | S | S | S | — | S | S | E | Alternative to react-admin |
| WarpDrive (ember-data) | — | E | — | — | — | — | S | S | The V2 frontend |
| Orbit.js / kitsu / jsona | — | E | — | — | — | — | S | S | JSON:API clients for V2 |
| Apollo Client | S† | — | S† | S† | — | — | S† | — | †Only with a GraphQL view (G12) |
| orval / hey-api / openapi-typescript | E | S | E | E | S | S | E | S | B generates the OpenAPI that feeds them; C gives generic, weaker types |
| json-schema-to-typescript | S | S | S | S | — | S | S | — | From LinkML JSON Schema |
| zod | S | S | S | S | S | S | E | S | Generated by orval / hey-api |
| RJSF / JSON Forms | S | S | S | S | — | S | E | S | JSON Schema from LinkML; IRIs and lang-strings need widgets |
| shaperone / Alcaeus / LDflex | — | — | — | — | S | — | — | — | Ideas only (DEC-5) |
| @inrupt/solid-client, Soukai | B | B | B | B | B | — | — | — | Solid only |
| fdr | — | — | — | — | S | — | — | — | Ideas only |
| fluree-client | — | — | S (B for portability) | — | — | — | — | — | FlureeQL lock-in; plain fetch + TanStack Query is enough |
| rdf-validate-shacl | S | S | S | S | S | S | S | S | Client-side SHACL (ideas only, DEC-5) |
| oidc-client-ts / @zitadel/react | E | S‡ | E | E | E | S | S | S | ‡V2 uses mu-identifier session cookies; OIDC only via a login service |
| Cypress + cucumber preprocessor | S | S | S | S | S | S | S | S | MWBv2 E2E |

**Headline:** V1, V3 and V4 share one L5 stack: TanStack Query + an OpenAPI-generated client + zod + jsonld.js + oidc-client-ts + RJSF / JSON Forms (or shacl-form). V2 swaps the data layer for WarpDrive / Orbit; V5 adds LDkit or Comunica for reads. Approach **B** gets the most from L5 (typed end to end through orval or hey-api). Approach **C** is best served by runtime-introspecting UIs (react-admin / api-platform/admin, shacl-form). No mature L5 tool blocks any of V1–V5. The Solid-family clients (LDO, @inrupt, Soukai) fit none of them.

### (d) Corrections to the integrated docs

1. **`building-blocks.adoc` L5 Facts:** "every RDF-native JavaScript client fails the threshold" is too strong. `@inrupt/solid-client` passes DEC-5 (244 stars, push 2026-11-02, round-3 table §1b); it is excluded because it is Solid-only. `angles/jsclient.adoc:13` says this correctly ("… or tied to Solid"). Suggested wording: "…fails the threshold or is tied to Solid (@inrupt/solid-client)".
2. **`angles/jsclient.adoc:202`** (open questions) says "Hydra adds a generator (X20)". In v3, X20 is *cursor pagination*; the Hydra generator is now **G11** (Id mapping: `angle-jsclient.md X20 → G11`). Any other mention of my round-3 X17–X20 in the angle page should be checked the same way (X17 → X22, X18 → G7, X19 → X19, X20 → G11).
3. **`catalogue.adoc` LDO row (l. 961-966):** "for Solid" should read "for Solid and NextGraph" (`packages/connected-nextgraph`). Origin "One author (o-development)" should be "Jackson Morgan (jaxoncreed) and o-development; 8 contributors".
4. **`catalogue.adoc` LDflex row (l. 968):** Origin "Ruben Verborgh" should add that Jesse Wright (`jeswr`, 239 commits against 190 for RubenVerborgh) is now the main maintainer.
5. **`catalogue.adoc` rdf-ext row (l. 933):** "Zazuko community" should be "Thomas Bergwinkl (`bergos`, 229 commits), close to Zazuko (Adrian Gschwend `ktk` contributes)". rdf-ext is its own GitHub org, not a Zazuko repo.
6. **`catalogue.adoc` cypress-cucumber-preprocessor row (l. 1255):** the origin is TheBrainFamily (Lukasz Gandecki `lgandecki`), and the project was transferred to Jonas Amundsen (`badeball`). "One maintainer" is accurate today.
7. **`catalogue.adoc` @api-platform/admin row (l. 1052):** "Generated back office if we emit Hydra (G11) or OpenAPI" should say that the Hydra path also needs the API Platform **query dialect** (`order[]`, `page`, `itemsPerPage`) and **schema.org** label and type hints (`hydra/dataProvider.ts:410-440`, `hydra/schemaAnalyzer.ts:18-66`). The OpenAPI path (`<OpenApiAdmin>`) has the same filter-dialect dependency (shared `introspection/schemaAnalyzer.ts`).
8. **`variants.adoc` V1:** "UI: typed REST client generated from OpenAPI, TanStack Query, jsonld.js" is fine. The service side is listed as "(JSON-LD + Hydra, JSON:API, OpenAPI)". For the generated admin to work, Hydra must be the *API Platform* flavour (see 7). No other contradictions were found in `index.adoc` or `variants.adoc`.
9. **`catalogue.adoc` fluree-client row (l. 1003):** "Near-dead" is a judgement, not a fact. The last push was 2026-03-26, which is inside 12 months; it fails DEC-5 on stars (6). Suggested: "Fluree PBC. Low activity (79 npm downloads per week)."

All other Origin cells for my candidates were checked and match the evidence (repo owner and top contributors): jsonld.js, N3.js, @rdfjs/types, jsonld-*-parser, Comunica, rdflib.js, rdf-validate-shacl, LDkit, rdf-object, @inrupt, Soukai, fdr, Alcaeus, shaperone, TanStack Query, SWR, react-admin, refine, WarpDrive, Orbit, kitsu/jsona, spraypaint, Apollo, AdminJS, zustand, openapi-typescript, orval, hey-api, json-schema-to-typescript, zod, linkml-runtime.js, shacl-form, RDForms, RJSF, JSON Forms, oidc-client-ts, @zitadel/react, Cypress.

### (e) Proposed new features (round 4)

| Proposed id | Area | Feature | Seen in |
|---|---|---|---|
| **X23** | Interop | Strict JSON-LD processing: the client (and server) fail when a context drops or cannot map a term, instead of losing data silently | jsonld.js safe mode (`lib/jsonld.js:122-126`, `:529-532`) |
| **U11** | UI and client | Framework-neutral UI components (Web Components) so one generated or reused widget serves React, Vue and Ember (V2) front ends | shacl-form (`src/form.ts:35`, `:716`) |
| **G28** | Generation | Conformance link: generated or entered data carries `dcterms:conformsTo` to its shape, which then selects the form, validation and type for that instance | shacl-form (README:86-89, `data-generate-node-shape-reference` README:100) |
| **U12** | UI and client | Bulk operations sent as one batch, not N parallel single requests, with per-item results; refines X18 from the client side | gap in @api-platform/admin (`dataProvider.ts:793-804`) |

---

## Round 5

Brief: `BRIEF-round5.md`. Same clones and commits as rounds 3 and 4; nothing was executed. Pages reviewed: `angles/jsclient.adoc`, the L5 section of `building-blocks.adoc`, `variants.adoc`, and the L5 mentions in `index.adoc` and `design-implications.adoc`.

### R5.0 New code reading this round (it changes two earlier claims)

1. **jsonld.js caches remote contexts across calls only when the document loader tags them `static`.** `ContextResolver._get` reads the shared LRU only for the `static` tag (`lib/ContextResolver.js:84-100`). Remote contexts are cached under `remoteDoc.tag` (`:127`), and the bundled loaders never set a tag (grep `tag` in `lib/documentLoaders/*.js`: 0 hits). With the default loaders, each `jsonld.*` call therefore refetches a remote `@context`; only the per-operation cache (`:27`) and the browser HTTP cache apply. The round-3 claim "a UI does not refetch `@context`" (§2.1) is wrong: it holds only with a custom loader that returns `tag: 'static'` or serves the bundled context. This strengthens X22.
2. **LDO's `commitToRemote` is atomic per resource only.** Changes are grouped by named graph (= resource), one `resource.update()` is sent per graph in parallel (`Promise.all`), and failures come back as an `AggregateError` with no rollback of the graphs that succeeded (`connected/src/ConnectedLdoTransactionDataset.ts:205-233`). The round-4 "T1 present" for LDO holds per resource; across resources the result is partial commits.
3. **@api-platform/admin passes the token verbatim:** `requestHeaders.set('Authorization', options.user.token)` (`src/hydra/fetchHydra.ts`). The app must store `"Bearer …"`, not the bare token.

### (a) v4 cross-check

J = jsonld.js · A = @api-platform/admin · S = shacl-form · L = LDO. Absences were confirmed by grep over the four source trees (tests excluded) for `aggregate` (shacl-form hits are `aggregatedMinCount/MaxCount` cardinality helpers, `property-template.ts`; LDO hits are `AggregateError`, so not aggregates in the DDD sense), `mcp|modelcontext`, `opentelemetry|traceparent`, `expectType|tsd|assert_type`, `testcontainers|toxiproxy`, `did you mean`, `rate limit|startAt|endAt`, `If-Match|ETag`: 0 relevant hits in all four. The n.a. rule is the one from R4.0: features that only a server, store, migration tool or Python generator can have.

| Id | J | A | S | L | Evidence |
|---|---|---|---|---|---|
| B1 | n.a. | absent | absent | absent | No aggregate notion (grep, above). A only knows `embedded` fields from the API docs; S nests `sh:node` shapes, which are not ownership boundaries |
| B2 | n.a. | n.a. | n.a. | n.a. | Generation-time check |
| B3 | n.a. | partial | partial | partial | A: one GET per resource with embedded documents cached by IRI (`hydra/dataProvider.ts:75-105`). S: one fetch of `data-values-url`. L: one read per Solid resource (document = unit) |
| B4 | n.a. | partial | partial | partial | A: `PUT` of the whole document by default (`dataProvider.ts:376`). S: whole graph serialised (`form.ts:290-303`). L: minimal diff (`methods.ts:308`), but not bounded by an owned subtree |
| B5 | n.a. | partial | partial | absent | A: reference fields hold IRIs and resolve separately (ReferenceInput guessers). S: `sh:class` pickers hold IRIs with lazy `ResourceLinkProvider` (`plugin.ts:68-75`). L: nested proxies navigate freely across subjects |
| B6 | n.a. | n.a. | n.a. | absent | L: one transaction may span any number of subjects and resources |
| B7 | n.a. | n.a. | n.a. | absent | L: `DELETE DATA` / `INSERT DATA` carry no guards (`rdf-utils/src/datasetChanges.ts:18-35`) |
| B8 | n.a. | absent | absent | present | L: `transactionChanges()` returns a `DatasetChanges` value (`methods.ts:308`), rendered as SPARQL Update by `changesToSparqlUpdate` and sent by both the Solid and NextGraph plugins (`updateDataResource.ts:73`, `NextGraphResource.ts:180-183`) |
| B9 | n.a. | n.a. | n.a. | n.a. | Server outbox |
| B10 | n.a. | n.a. | partial | partial | S: `data-values-graph` writes the data into one named graph (README:91). L: changes are grouped by named graph = resource document (`ConnectedLdoTransactionDataset.ts:205-220`) |
| B11 | absent | absent | absent | absent | No version or ETag handling (grep) |
| B12 | n.a. | partial | absent | absent | A: react-admin `mutationOptions.onSuccess` passed through (`useOnSubmit.ts:68`); runs after the HTTP success, not after a store commit |
| B13 | n.a. | n.a. | n.a. | n.a. | Server delete semantics |
| B14 | n.a. | n.a. | n.a. | n.a. | Server packaging |
| B15 | n.a. | n.a. | n.a. | n.a. | Server session; L's overlay gives read-your-writes (T5, round 4) |
| B16 | n.a. | n.a. | n.a. | n.a. | Server sagas |
| PG1 | n.a. | n.a. | absent | n.a. | S: `SparqlQueryBuilder` concatenates strings (`query/sparql.ts:52-80`); no AST |
| PG2 | n.a. | n.a. | n.a. | n.a. | LPG projection |
| PG3 | n.a. | n.a. | n.a. | n.a. | LPG edges |
| PG4 | n.a. | n.a. | partial | n.a. | S: `SparqlDatasetScope` default or named graph for queries (`query/sparql.ts:6-8`); query only, not authorization |
| EV1–EV9 | n.a. | n.a. | n.a. | n.a. | Migrations are server or ops side |
| AZ30–AZ36 | n.a. | n.a. | n.a. | n.a. | Store, PEP or gateway side. AZ33 is answered by the server; clients only see a 404 |
| G28 | n.a. | n.a. | n.a. | n.a. | Contract publishing |
| G29 | n.a. | n.a. | n.a. | absent | L: SHACL → ShEx through `@jeswr/shacl2shex` with no lossiness report (`cli/src/util/forAllShapes.ts:3-57`) |
| G30–G33 | n.a. | n.a. | n.a. | n.a. | Python and OWL build gates |
| G34 | absent | absent | present | absent | S: root shape from `dcterms:conformsTo`, and a reference to it written on output (README:86-89, :100) |
| G35 | n.a. | absent | n.a. | absent | L: typings are plain interfaces, with no field metamodel or operators (`schema-converter-shex/src/typing/`) |
| G36 | n.a. | absent | n.a. | absent | L: no filter or input types; there is no query API |
| T12 | n.a. | n.a. | n.a. | n.a. | Store commit model |
| T13 | n.a. | n.a. | n.a. | n.a. | Protocol-boundary guard (S `data-mode=view` is a UI mode, not a protocol guard) |
| T14 | n.a. | n.a. | n.a. | present | L: one dataset over several plugins (Solid + NextGraph, `connected/src/ConnectedLdoDataset.ts:31, 60-62`), flushed per resource with no cross-resource atomicity (`ConnectedLdoTransactionDataset.ts:205-233`) |
| S20–S23 | n.a. | n.a. | n.a. | n.a. | Store features |
| X23 | present | absent | absent | absent | J: `safe: true` (`lib/jsonld.js:122-126`, `:529-532`). A expands error bodies without `safe`. S and L use no JSON-LD processing on input |
| X24 | absent | absent | absent | absent | grep `mcp`: 0 |
| E10 | n.a. | absent | n.a. | absent | A: a Mercure subscription takes only a topic and a JWT (`mercure/createSubscription.ts`). L: WebSocketChannel2023 subscribe with no options (grep `rate\|startAt\|endAt`: 0) |
| I7 | n.a. | n.a. | n.a. | n.a. | Server IRI policy |
| I8 | n.a. | absent | absent | absent | S mints final IRIs at creation (`node.ts:38-40`). L: the remote mints with `createResource` (`ConnectedPlugin.ts:34`); no temporary-to-permanent swap |
| P20 | n.a. | absent | n.a. | absent | L: per-graph updates run in parallel and unordered (`Promise.all`, `ConnectedLdoTransactionDataset.ts:205`) |
| U11 | n.a. | absent | present | partial | S: custom element (`form.ts:35, 716`). L: separate React, Vue and Svelte bindings (`packages/react`, `vue`, `svelte`). A: React only |
| U12 | absent | absent | absent | absent | No ontology-driven desktop editor; S generates web forms from SHACL, not from the ontology |
| U13 | n.a. | absent | n.a. | partial | A: N parallel requests (`dataProvider.ts:793-804`). L: one request per resource, so many subjects in one document go together; several documents mean several requests |
| D14 | n.a. | n.a. | n.a. | n.a. | Python write API |
| D15 | absent | absent | absent | absent | No query logging to redact |
| D16 | n.a. | n.a. | n.a. | n.a. | Server contract test |
| D17 | n.a. | absent | present | present | S: `SparqlQueryBuilder.buildSelect()` returns the query text (`query/sparql.ts:64-67`). L: `toSparqlUpdate()` (`methods.ts:358`) |
| D18 | n.a. | absent | absent | partial | L: resource-level unfetched state (`readIfUnfetched`, GitNexus process `ReadIfUnfetched → OverwriteQuads`); property level: absent and unloaded both read as `undefined` |
| D19 | absent | absent | absent | partial | L: `packages/test-solid-server` (an in-process Community Solid Server for tests) |
| D20 | n.a. | n.a. | n.a. | partial | L: same test server package; one store kind only |
| D21 | absent | absent | absent | absent | Docs examples are not executed in CI (A has Storybook stories, not docs tests) |
| D22 | partial | absent | absent | absent | J: compaction produces CURIEs and terms from the context (`lib/compact.js`); not for id arguments |
| D23 | absent | absent | absent | absent | grep: 0 |
| D24 | present | absent | absent | partial | J: W3C-defined error codes on `JsonLdError` (for example `invalid @embed value`, `lib/frame.js:130-133`), documented in the JSON-LD API spec. L: typed result `type` strings (`HttpErrorResult.ts:10`) |
| D25 | partial | absent | absent | absent | J: deterministic output only through `canonize` (`lib/jsonld.js:564`). L: multi-valued properties are `Set`s in dataset order |
| D26 | absent | absent | absent | absent | grep `expectType\|tsd`: 0 |
| D27 | absent | absent | absent | absent | grep: 0 |
| D28 | n.a. | n.a. | n.a. | n.a. | Server contract fuzzing |
| D29 | absent | absent | absent | absent | grep `opentelemetry\|traceparent`: 0 |

Counts over the 77 v4 ids (grouped rows count once per id):

| | present | partial | absent | n.a. |
|---|---|---|---|---|
| jsonld.js | 2 | 2 | 11 | 62 |
| @api-platform/admin | 0 | 4 | 26 | 47 |
| shacl-form | 3 | 5 | 20 | 49 |
| LDO | 3 | 9 | 24 | 41 |

Reading: v4 is again dominated by server, store and migration concerns. The useful client facts are three. LDO has an **inspectable change-set value (B8)** and a **cross-store session (T14), but no cross-resource atomicity**. shacl-form has the **conformance link (G34)** and is the only **framework-neutral component (U11)**. **No client handles versions or ETags (B11)**, so B11, X19 and T2 must be added in the service and wrapped in the generated client.

### (b) Page review — corrections

`angles/jsclient.adoc`:

1. **Overstatement (jsonld.js):** "Resolved contexts sit in a shared LRU cache (`:103`), so a UI does not refetch `@context`." → Fix: "Resolved contexts are reused across calls only when the document loader marks them `static` (`lib/ContextResolver.js:84-100`); the bundled loaders do not (no `tag` set), so serve the generated context from the bundle with a custom loader (X22)." The same correction applies to the raw report §2.1.
2. **Stale paragraph:** "Round-4 proposals, not yet in the taxonomy: …" → They are now v4 ids. Replace with "Round-4 proposals merged in v4: X23 strict JSON-LD processing, U11 framework-neutral components, G34 conformance link, U13 bulk operations as one batch."
3. **Missing caveat (LDO):** after "`startTransaction` / `commitTransaction` record a diff; …" add: "`commitToRemote` sends one update per resource in parallel; a failure leaves the other resources committed (`AggregateError`, `connected/src/ConnectedLdoTransactionDataset.ts:205-233`)." In the feature-coverage table, mark LDO T1 as "per resource".
4. **Missing caveat (@api-platform/admin, Auth bullet):** "`Authorization` header from a react-admin `authProvider`" → add: "the token is set verbatim (`fetchHydra.ts`), so store it with the `Bearer ` prefix; no built-in OIDC."
5. **Fit column inconsistent with `catalogue.adoc`:** the landscape table says *dependency* for SWR, react-admin, refine, RJSF and JSON Forms, and *ideas* for rdflib.js and jsonld-streaming-parser / jsonld-context-parser / rdf-ext. The catalogue says *integrate*, *integrate*, *integrate*, *integrate*, *integrate*, *none* and *none*; @rdfjs/types is *dependency* on the page and *compatible* in the catalogue; LDkit is *ideas* on the page and *integrate* in the catalogue. Fix: use the catalogue values. They match my verdicts: SWR and refine are alternatives, react-admin is an optional back office, and LDkit integrates only behind a seam for V5.

`building-blocks.adoc` L5:

6. **Overstatement:** "*Gap:* none to build if the service emits good OpenAPI and JSON-LD." → Fix: "Gap: thin client glue only: a jsonld.js document loader serving the bundled generated context (X22); one `authFetch` from the OIDC client; RJSF / JSON Forms widgets for IRIs and language strings; wrappers for preconditions, idempotency keys and batches (X19, T9, U13), which no client library sends."

`variants.adoc`, `index.adoc` and `design-implications.adoc`: no L5 statement is contradicted by my evidence. The building-blocks L5 Facts line was corrected after round 4 and is now accurate.

### (c) Final verdicts and what to remember

| Candidate | Final verdict |
|---|---|
| jsonld.js | **adopt** (dependency): the client JSON-LD processor in every JSON-LD variant |
| @api-platform/admin | **integrate** (optional back office), only if the service speaks the API Platform Hydra dialect; otherwise react-admin `<OpenApiAdmin>` |
| shacl-form | **ideas** (vendor-in or keep behind a seam if DEC-5 is relaxed for leaf UI) |
| LDO | **ideas** (client unit of work by diff, types + context from one shape, plugin per backend) |

Three things a system architect must remember about this angle:

1. **The L5 stack is mainstream and RDF-agnostic; the RDF knowledge lives in the contract.** Generate OpenAPI, the JSON-LD context and frames, and SHACL from LinkML. Use TanStack Query + orval or hey-api + zod + jsonld.js + oidc-client-ts. Every RDF-native JS client fails DEC-5 or is Solid-only.
2. **Concurrency and atomicity are server duties.** No client library sends ETags, idempotency keys or atomic batches, and LDO commits are atomic per resource only. B11, X19, T9 and U13 must be designed into the service and wrapped once in the generated client.
3. **Bundle the generated `@context` and process strictly.** jsonld.js refetches remote contexts unless the loader marks them static, and it drops unmapped terms silently unless `safe: true` is used. A custom loader plus safe mode (X22, X23) prevents both network coupling and silent data loss.

### (d) Purpose and origin, variant fit

Already written in Round 4 (b) and (c) for all candidates; unchanged.

### (e) New features

None. The two round-5 findings (static-tag context caching, per-resource atomicity) are covered by X22, T1, T14 and X18 / U13.
