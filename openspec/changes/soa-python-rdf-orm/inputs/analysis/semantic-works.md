# semantic.works (formerly mu.semte.ch) — reference architecture

Change: `soa-python-rdf-orm` · Analyst scope: the developer's reference architecture · Scored as ONE platform.

- **Repos / commits analysed** (all clones are shallow, 1 commit each, so history and maintainer counts are not visible locally):

  | Repo | Commit (date) | Language | Licence | Files / source LOC |
  |---|---|---|---|---|
  | mu-cl-resources | d083c3e (2025-09-17, v1.27.2) | Common Lisp | MIT (`mu-cl-resources.asd`) | 33 / ~5.4k Lisp |
  | sparql-parser | 4059dcd (2026-05-29, v0.0.15) | Common Lisp | MIT (`sparql-parser.asd`) | 61 / ~10.1k Lisp |
  | delta-notifier | 2fac0f5 (2026-06-03, v0.4.1) | JavaScript | MIT (`package.json`) | 13 / ~470 JS |
  | mu-python-template | 1fc512b (2025-05-09, v2.0.0-beta.3) | Python (Flask) | MIT (`LICENSE`) | 14 / ~380 Py |
  | mu-javascript-template | e7a2705 (2025-09-30, v1.9.1) | JavaScript (Express) | (no LICENSE file in clone) | 28 / ~490 JS |
  | mu-project | 684f626 (2026-06-05) | config (compose, Elixir, Lisp, JS) | MIT (`LICENSE`) | 14 |

  The git submodules of mu-cl-resources (`cl-fuseki`, `mu-cl-support`, `jsown`, `luckless`) are empty in the clone. The SPARQL client (`cl-fuseki`) and the `s-url`/`s-prefix` helpers (`mu-cl-support`) were therefore not read.

- **GitNexus index stats** (the repos were not indexed at the start. They were listed when checked again after the docs had been read, and I did not run `analyze`):

  | Repo | Files | Symbols | Edges | Clusters | Processes |
  |---|---|---|---|---|---|
  | mu-cl-resources | 28 | 94 | 84 | – | – |
  | sparql-parser | 54 | 99 | 83 | – | – |
  | delta-notifier | 9 | 58 | 117 | 3 | 6 |
  | mu-python-template | 9 | 91 | 124 | 4 | 4 |
  | mu-javascript-template | 24 | 106 | 131 | 5 | 4 |
  | mu-project | 10 | 21 | 17 | – | – |

  **GitNexus does not parse Common Lisp.** `MATCH (n:Function)` returns 0 rows for mu-cl-resources, and `query` returns only `File` nodes with no processes for both Lisp repos. All Lisp evidence below therefore comes from reading the source with grep/Read. **GitNexus worked for the JS repos.** In delta-notifier it found the processes `informWatchers → sendBundledRequest → sendRequest → handleResponse`, `informWatchers → formatChangesetBody` and `informWatchers → foldChangeSets`. In mu-javascript-template it found `update → newSparqlClient` and `query → newSparqlClient` (module "Mu", `helpers/mu/sparql.js`).

- **Docs read**
  - In-repo: all six READMEs, `mu-cl-resources/docs/cache-keys.org`, `mu-javascript-template/README.md`, and `mu-project/config/**`.
  - Published:
    - https://semantic.works/ and https://semantic.works/docs. Both return only the title "semantic.works": the site is a client-rendered SPA and WebFetch saw no content.
    - https://mu.semte.ch/, https://mu.semte.ch/about/, https://mu.semte.ch/getting-started/
    - https://mu.semte.ch/2019/01/02/on-sharing-authorization/, https://mu.semte.ch/2018/03/22/get-to-know-mu-cl-resources/
    - https://github.com/mu-semtech/mu-identifier, https://github.com/mu-semtech/mu-dispatcher, https://github.com/mu-semtech/project

## Summary

semantic.works is a **stack of Docker microservices that share one triplestore**, not a library. The semantic model in the store is the integration contract: services never call each other, they read and write the same triples (mu.semte.ch/about: "Instead of letting microservices depend on each other, we lean on the semantic web for data integration").

- Rapid application development comes from **mu-cl-resources**. It turns a declarative domain file (`domain.lisp` / `domain.json`) into a full **JSON:API** for ember-data with no code: CRUD, relationships, filters, sort, include, sparse fieldsets and pagination.
- Cross-cutting concerns sit in **proxies around the store**:
  - **sparql-parser** (the next-generation mu-authorization) parses every SPARQL request, rewrites it to the graphs the user may read or write, and emits **deltas**;
  - **delta-notifier** fans those deltas out to subscribing services, which use them for cache invalidation and reactive services.
- The language templates (Python/Flask, JS/Express) give a service author only a raw SPARQL client that forwards the auth headers, plus escape helpers. **There is no ORM layer in the templates.** That gap is where rdf-persistence fits.

## Architecture (end-to-end) — with evidence

```
browser (Ember app, ember-data JSON:API adapter)
   │  cookie
   ▼
identifier (Elixir) ── session cookie → MU-SESSION-ID header; caches MU-AUTH-ALLOWED-GROUPS   [mu-identifier README]
   ▼
dispatcher (Elixir) ── dispatcher.ex: match "/people/*path", accept json → forward to http://resource/people/   [mu-project/config/dispatcher/dispatcher.ex; mu-dispatcher README]
   ▼                                   (adds x-rewrite-url, Vary: accept, cookie)
resource = mu-cl-resources (Lisp) ── domain.json → JSON:API ↔ SPARQL SELECT/INSERT/DELETE
   │   SPARQL over HTTP + MU-SESSION-ID, MU-CALL-ID, MU-AUTH-ALLOWED-GROUPS (+ mu-auth-sudo / mu-auth-scope from templates)
   ▼
database = sparql-parser (Lisp) ── parse → ACL rewrite (FROM <graphs for tokens>) / quad dispatch to graphs → backend   [sparql-parser/connection/server.lisp:92-129, acl/acl.lisp:249-263, 301]
   ├──▶ triplestore (Virtuoso, :8890/sparql)                [mu-project/docker-compose.yml:54-72, config/authorization/config.lisp *backend*]
   └──▶ delta-notifier (JS) ── rules.js match → POST callback (e.g. http://resource/.mu/delta)   [delta/messenger.lisp:36-61; delta-notifier/app.js]
              └──▶ mu-cl-resources /.mu/delta → clear internal caches + POST clear-keys to mu-cache   [call-implementation.lisp:1180-1300]
```

The blueprint is `mu-project/docker-compose.yml`. It wires the services as identifier → dispatcher → resource, plus migrations, delta-notifier, `database` (sparql-parser 0.0.15) and `triplestore` (Virtuoso). Applications talk to the service named `database`, so the authorization proxy is transparent to them.

### 1. Request path

- **identifier.** Gives each browser agent a session and passes it to the backend as `MU-SESSION-ID`. It also caches `Mu-Auth-Allowed-Groups` returned by the backend; a backend can send `CLEAR` to force a recalculation (mu-identifier README). The identifier "is not connected to the database".
- **dispatcher.** An Elixir DSL with `match`/`get`/… rules, accept-type aliases, ordered `define_layers`, host matching and `forward` (mu-dispatcher README). The mu-project default has only a 404 fallback and a commented `/themes/*path` example (`dispatcher.ex`).
- **resources.** Routes are declared with `defcall` in `framework/call-specification.lisp`:

  | Line | Route |
  |---|---|
  | 14 | GET list |
  | 51 | GET item |
  | 87 | POST create |
  | 158 | PATCH item |
  | 231 | DELETE item |
  | 304/307 | GET related / relationship links |
  | 310 | PATCH relationship |
  | 377 | POST relationship |
  | 444 | DELETE relationship |
  | 504 | POST `/.mu/delta` |

- **sparql-parser.** `execute-query-for-context` (`connection/server.lisp:92`) parses the string into an AST.
  - **Query:** `manipulate-query` → `acl:apply-access-rights`. This step removes dataset clauses and `GRAPH` patterns, then adds `FROM` graphs computed from the access tokens. If no graph is accessible it adds `…/empty-graph` (`acl/acl.lisp:249-263`). `mu-auth-sudo` bypasses all of this.
  - **Update:** `handle-sparql-update-unit` (`updates/handle-update-unit.lisp:687`) expands the update into concrete quads and runs `dispatch-quads-to-graph-specifications` (`acl/acl.lisp:301`). That step places each quad in the graph(s) whose type/predicate specification it matches. It then computes the *effective* changes against the store (`detect-effective-changes`, l.290), writes in batches (≤100 quads / ≈8000 chars per query, l.3-7, 704-718), updates the type cache, and calls `delta-messenger:delta-notify` (l.725-730).
- **delta-notifier.** `POST /` receives `{changeSets:[{insert, delete, effectiveInsert, effectiveDelete, origin, allowedGroups, scope, sequenceId}]}`. It normalises the quads, then for each rule it filters out changes from its own origin (by DNS-resolved IP), matches `{subject,predicate,object}` patterns, and sends the change either directly or bundled per grace period (`app.js:19-86`, `bundle-requests.js`). The payload is reformatted to the rule's `resourceFormat` (`send-request.js:6-43`).

### 2. Domain model → JSON:API resources

The domain is declared in `define-resource` (Lisp macro, `resource-model.lisp:605`) or in `domain.json` v0.1. `domain-parsing.lisp:54-147` maps the JSON form onto the same `define-resource*`.

**Resource keys**
- `name`, `path` (the JSON:API `type` and URL segment), `class` (rdf:type), `new-resource-base`, `features` (e.g. `include-uri`, `no-pagination-defaults`), `super`.
- **Attributes:** `{type, predicate}`. Types: string, number, integer, float, boolean, date, datetime, time, url, uri-set, string-set, language-string(-set), g-year, geometry (README "Defining resources in JSON").
- **Relationships:** `{predicate, target, cardinality: one|many, inverse?}`.
- The cardinality is turned into `has-one-link` / `has-many-link` classes (`resource-model.lisp:12-33`).

**CURIEs and splitting**
- A value containing `://` is read as a URL, otherwise as a prefix (`domain-parsing.lisp:112-118`).
- `read-domain-file` lets a project split the domain over several files and mix Lisp and JSON (`domain-parsing.lisp:5`).
- Global settings are Lisp-only: "Most settings can only be configured in Lisp format" (README).

**Inheritance**
- On create, all superclass types are written (`flattened-ld-class-tree`, `call-implementation.lisp:117-118`).
- Listing a type matches `VALUES ?class { <all subclasses> }` (l.318-320). The response uses the most specific type.

**Validation**
- `:required` on a property makes create/patch check for the field (`call-specification.lisp:96,168`, condition `required-field-missing`).
- The only model validation is "no slash in on-path" (`resource-validations.lisp`).

**Hooks**
- Lisp-only `before`/`after`/`around` hooks per resource and operation (`callbacks.lisp:79-97`), wrapped around every call by `with-surrounding-hook`.

### 3. Relationships, pagination, filters and includes → SPARQL

**List** (`call-implementation.lisp:304-323`, `response-generation.lisp:59-108`):

```sparql
SELECT DISTINCT ?uuid [order vars] WHERE {
  GRAPH <application-graph> {
    ?s mu:uuid ?uuid; a ?class. VALUES ?class { <subclasses> }
    <filter patterns>
    OPTIONAL { ?s <sort path> ?sortVar } } }
GROUP BY ?uuid ORDER BY ASC(?sortVar) LIMIT size OFFSET size*number
```

- **Pagination**
  - `page[size]` defaults to 20 (`MU_DEFAULT_PAGE_SIZE`); `page[number]` is 0-based (l.28-38).
  - The total count comes from a separate `COUNT(DISTINCT …)` query (l.15-27), which can be cached.
  - `first`/`last`/`prev`/`next` links are built in l.110-132.
  - Included resources are never paginated.
- **Filters** (`sparql-pattern-filter-string`, l.196-328). JSON:API `filter[...]` paths walk attribute and relationship chains as SPARQL property paths (`property-path-for-filter-components`, `resource-model.lisp:454`).

  | Filter | SPARQL |
  |---|---|
  | plain | `FILTER CONTAINS(LCASE(str(?v)), LCASE("…"))` |
  | `:exact:` | triple pattern with typed literal |
  | `:gt:/:lt:/:gte:/:lte:` | `FILTER (?v > x)` |
  | `:id:` | `?t mu:uuid ?x VALUES ?x {…}` |
  | `:uri:` | `VALUES ?t {<uri>}` |
  | `:has:/:has-no:` | `FILTER (NOT) EXISTS {…}` |
  | `:not:` | `FILTER NOT EXISTS` |

  `:or:` is documented in the README but was not located in `sparql-pattern-filter-string`. It may live in `extract-filters-from-request` / `filter-body-for-search` (l.330-381), which I did not read in full.
- **Sort.** `sort=-age,owner.name`, plus the `:no-case:` modifier (`LCASE(STR())`), compiles to OPTIONAL property-path patterns (l.40-57).
- **Include.** `include=owner.publications` is parsed into a tree, max depth 15 (`included-items.lisp:8`). A single UNION query is built: a `VALUES ?source {…}` block per source plus relationship constraints for each subtree (`construct-logical-union-query-for-included-items`, l.371-395). That avoids N+1 queries.
- **Relationship read.** `<s> <p> ?resource . ?resource mu:uuid ?uuid; a ?class` (l.985-1026). Inverse relationships use `^p` / `s-inv`.
- **Sparse fieldsets.** `fields[type]=a,b` (README; `sparse-fields-for-resource`, `call-implementation.lisp:353`).

### 4. Writes — INSERT/DELETE patterns, UUIDs, graphs

**Identity**
- Every resource has a `mu:uuid` string literal. The JSON:API `id` is that UUID, never the IRI.
- The IRI for a new resource is `new-resource-base` + UUID (`create-call`, l.95-98).
- Lookups go uuid ↔ uri through SPARQL with caches (`caching.lisp:10-90`).
- Clients cannot choose the id on POST: it is always minted (l.95).

**Create** (l.114-123): one `INSERT DATA { GRAPH <app> { <s> mu:uuid "…"; a <C>, <SuperC>; <p> <o> … } }`, then one relationship update per relationship in the body.

**Update attributes** (l.157-176), inside `with-update-group`:
1. `DELETE { <s> <p> ?v } WHERE { {<s> <p> ?v} UNION … }`;
2. then `INSERT DATA` for the new values.

So the strategy is replace-per-property: it touches only the keys present in the PATCH.

**Update relationships** (l.194-272):
- `DELETE { <s> <p> ?s2 } WHERE { … ?s2 a ?type VALUES ?type {subclasses} }`, then `INSERT DATA`.
- For a has-one inverse, the stale inverse links on the target are cleared first (`clear-inverse-has-one-relationships`).
- The relationship-link endpoints (PATCH/POST/DELETE `…/links/rel`) add or remove individual links (l.1028-1153).

**Delete** (l.847-929): one `DELETE … WHERE { VALUES ?s {<s>} ?s mu:uuid "…" OPTIONAL{…} }`. It removes the uuid, all types, all declared properties and links, and incoming links declared by other resources (`cache-delete-call-additional-inverse-links-to-clear`). Undeclared triples are left in place.

**Grouping and atomicity**
- `with-update-group` concatenates the updates with `;` into **one HTTP update request** (`query-execution.lisp:18-30`). Atomicity is whatever the store gives a multi-operation request.
- sparql-parser then **splits** that request into ≤100-quad batches (`handle-update-unit.lisp:704-718`). Atomicity across batches is therefore not guaranteed. A `parallel-event-sequencer` orders updates that touch overlapping quads (`support/parallel-event-sequencer.lisp`, `make-sequencer-keys-for-quads`).
- There is no optimistic concurrency or versioning anywhere.

**Graphs**
- mu-cl-resources always writes into a single `*application-graph*` (`MU_APPLICATION_GRAPH`, default `http://mu.semte.ch/application`; `settings.lisp:13-16`, `query-execution.lisp:64-128`).
- sparql-parser **strips that graph** and re-dispatches each quad to the graph(s) whose `define-graph` type/predicate specifications it matches, multiplied by the user's tokens (e.g. `…/organizations/<uuid>`). See `acl.lisp:301-439` and the README "Define access rights for a set of similar graphs".
- In effect, **graph placement is a policy of the proxy, not of the application.**
- Literal handling:
  - Booleans default to a custom datatype `http://mu.semte.ch/vocabularies/typed-literals/boolean` (README "Data types"; `query-parsing.lisp:144`). The mu-project config sets `*use-custom-boolean-type-p*` to nil.
  - Strings over 4096 chars are moved to files by sparql-parser (`support:*string-max-size*`, README).

### 5. Authorization groups and graphs (only to understand the middleware seam)

Configured in Lisp (`config/authorization/config.lisp`; sparql-parser README "Reference"):
- `define-graph name ("graph-uri-prefix" :delta t :sparql t) ("Type" -> "pred" x> "pred" <- "pred" <x "pred") …` describes which triples belong to a graph, by subject/object type and predicate.
- `supply-allowed-group "name" :query "SELECT ?x WHERE { <SESSION_ID> … }" :parameters ("x")` says who belongs to a group. The parameters are appended to the graph URI.
- `grant (read write) :to-graph g :for-allowed-group "name" :scopes '(…)` ties groups to graphs. Scopes cover service-originated queries (`mu-auth-scope` header).

**Header protocol**
- `MU-SESSION-ID` goes in.
- `MU-AUTH-ALLOWED-GROUPS` is computed once and cached by the identifier.
- `MU-AUTH-USED-GROUPS` comes back on responses and is used for access-rights-aware caching ("On sharing authorization", mu.semte.ch 2019).
- `mu-auth-sudo` bypasses the ACL. The JS template only allows it when `ALLOW_MU_AUTH_SUDO` is set (`sparql.js:17-23`).

**The seam:** authorization is a *SPARQL-protocol-level proxy*, invisible to services except through these headers. A future rdf-persistence JSON-LD middleware could either sit **behind** such a proxy, forwarding the headers, or offer a similar hook. In either case the ORM itself must stay ACL-agnostic but **header-transparent**.

### 6. Delta production and consumption

**Production.** sparql-parser emits a `changeSets` message (`delta/messenger.lisp:36-116`):
- `insert`, `delete`, `effectiveInsert`, `effectiveDelete`: quads in **SPARQL-JSON term encoding** (`{subject,predicate,object,graph}`, each `{type,value,datatype?,xml:lang?}`);
- `sequenceId`, `origin` (source IP), `allowedGroups` (or "sudo"), `scope`;
- headers `mu-call-id`, `mu-session-id`, `mu-call-id-trail`.

It is sent asynchronously through a message bus with exponential-backoff retry (l.63-90). A `define-graph … :delta nil` turns deltas off per graph.

**Fan-out.** delta-notifier rules have the shape `{match:{subject|predicate|object:{type,value}}, callback:{url,method}, options:{resourceFormat, gracePeriod, ignoreFromSelf, foldEffectiveChanges, retry, retryTimeout}}`. The output formats are:
- `v0.0.1`: `[{inserts:[quad], deletes:[quad]}]`, built from the raw `insert`/`delete` (`send-request.js:7-15`);
- `v0.0.0-genesis`: `{delta:{inserts:[{s,p,o}], deletes}}`;
- falsy: no body, used as a trigger.

`foldEffectiveChanges` cancels insert/delete pairs using the effective sets (`folding.js:8-53`). The mu-project default subscribes resources at `http://resource/.mu/delta`, with `v0.0.1` and `ignoreFromSelf` (`config/delta/rules.js`).

**Consumption in mu-cl-resources** (`delta-call`, `call-implementation.lisp:1180-1300`):
1. Compute effective inserts and deletes.
2. Map each subject/object URI to resources via its rdf:type.
3. Clear the object, class and relation caches.
4. POST `clear-keys` to mu-cache (`CACHE_CLEAR_PATH`).

The cache-key vocabulary is `{uri}`, `{ld-resource}`, `{uri, ld-relation}` and `{ld-resource, ld-relation}` (`docs/cache-keys.org`).

**Services.** A JS service handles deltas with `app.post('/delta', bodyParser.json({limit:'50mb'}))` (JS template README "Handle delta's").

### 7. What the templates give a service developer

- **Python** (`mu-python-template`): Flask app injected as builtin `app` (`web.py:12-30`), Python 3.8 per the README.
  - SPARQLWrapper `query()`/`update()` against `MU_SPARQL_ENDPOINT`/`MU_SPARQL_UPDATEPOINT`. They forward `MU-SESSION-ID`, `MU-CALL-ID`, `MU-AUTH-ALLOWED-GROUPS` and `MU-AUTH-USED-GROUPS` (`helpers.py:115-164`).
  - `generate_uuid()` = `uuid1` (l.55-57), a JSON:API `error()` helper, content-type and type validators, and `sparql_escape_*`.
  - Dependencies are `flask`, `SPARQLWrapper`, `rdflib` (`requirements.txt`).
  - **Gaps:**
    - It does **not** support `mu-auth-sudo`/`mu-auth-scope`, so sparql-parser scopes cannot be used from Python.
    - It does not propagate `mu-auth-allowed-groups` back on the response.
    - Its SPARQLWrapper clients are module-global and mutated per request (thread-unsafe pattern).
    - It has no ORM, no JSON:API serialisation and no delta helper.
- **JavaScript** (`mu-javascript-template` 1.9.1): Express `app`; `query`/`update(q, {sudo, scope})` via sparql-client-2 (`helpers/mu/sparql.js:13-120`).
  - Forwards the session, call-id and allowed-groups headers, and **writes `mu-auth-allowed-groups`/`mu-auth-used-groups` back** on the response.
  - Also provides `uuid()`, `sparqlEscape*`, a JSON:API `errorHandler`, `beforeExit`, live reload, the Chrome debugger and second-class TypeScript.
  - It has no ORM either.

## Implementation principles (summary)

| Concern | How it works in code |
|---|---|
| Mapping | Declarative resource → class / predicate table. Generic functions dispatch on the slot type (`interpret-json-value`, `from-sparql`), with typed-literal importers keyed by xsd datatype (`query-parsing.lisp:50-154`) |
| Identity | `mu:uuid` literal + IRI = base + UUID. In-process uuid↔uri caches |
| Sessions / transactions | None. Per-request `with-update-group` batching; the auth proxy re-batches |
| Querying | Strings assembled with `format`. There is no query AST in mu-cl-resources; sparql-parser has a full EBNF parser/AST (`sparql-ast/`) |
| Serialisation | JSON:API only (jsown). No JSON-LD and no RDF serialisations exposed |
| Caching | Internal model/count caches + the external mu-cache, cleared from delta messages |

## Patterns catalogue

| Pattern | Where |
|---|---|
| Metadata mapping / declarative schema → generic CRUD (Data Mapper without domain objects) | `define-resource`, `domain.json` → `call-implementation.lisp` |
| Shared database as integration point (integration DB, CQRS-ish via deltas) | mu.semte.ch/about; whole stack |
| API gateway / reverse proxy | identifier + dispatcher |
| Query rewriting proxy for authorization (row-level security on graphs) | `acl:apply-access-rights` (`acl.lisp:249`) |
| Change data capture → publish/subscribe | sparql-parser delta messenger → delta-notifier rules |
| Cache-aside with event-driven invalidation and cache keys | `caching.lisp`, `delta-call`, `docs/cache-keys.org` |
| Hooks / interceptors (before/after/around) | `callbacks.lisp` |
| Batch / unit of work (weak: groups update strings only) | `with-update-group` (`query-execution.lisp:25`) |
| Single-table-like inheritance (all supertypes asserted) | `flattened-ld-class-tree` on create |
| Header-propagated context (session, call-id trail, groups) | templates `helpers.py:123`, `sparql.js:31-41`; delta headers |

## Docs vs code

| Claim (source) | Status |
|---|---|
| Full JSON:API support "errors being a notable exception" (mu-cl-resources README) | Confirmed: `error-codes.lisp` has its own conditions; not verified against the spec |
| `POST /people/<uuid>` listed as a call (README "Resulting API") | **Doc error**: code is `defcall :post (base-path)` (`call-specification.lisp:87`), i.e. POST to the collection |
| `filter[:or:]` | Claimed, not found in `sparql-pattern-filter-string`. Rest of the filter pipeline not fully read |
| Internal cache flag `*cache-model-properties*` (README §Caching) vs `*cache-model-properties-p*` (README §Config, mu-project domain.lisp) | Doc inconsistency; code uses `-p` (`caching.lisp:117`) |
| Inheritance: write all types, read most specific | Confirmed (`call-implementation.lisp:117`, `318`) |
| Pagination default 20, `MU_DEFAULT_PAGE_SIZE`, count in meta | Confirmed (`settings.lisp`, `response-generation.lisp:15-38`) |
| delta-notifier: "receives raw delta messages from mu-authorization", configure `config/authorization/delta.ex` | **Outdated**: in the current stack sparql-parser sends them via `add-delta-messenger` (`delta/messenger.lisp:128`, mu-project `config.lisp`) |
| delta-notifier v0.0.1 "may be extended with authorization rights" | The input already carries `allowedGroups`/`scope`/`origin`, but `formatChangesetBody` drops them (`send-request.js:7-15`) |
| sparql-parser scopes need JS template ≥1.9.0 | Confirmed: JS sends `mu-auth-scope` (`sparql.js:25-29`); Python template does **not** |
| "Different SPARQL stores" possible via plugins (README) | Claimed; defaults are Virtuoso-specific (`expand-bindings :virtuoso-p t`, `server.lisp:120`; custom boolean type workaround) |
| semantic.works docs site | Not checkable: SPA content not retrievable with WebFetch |
| "Ecosystem of user-facing microservices supported by semantic models"; Ember SPA frontend (mu.semte.ch/about, getting-started) | Confirmed by the stack layout; Ember usage itself is out of the clones |

## Scores C1–C8 (semantic.works as one platform)

| # | Score | Justification | Evidence |
|---|---|---|---|
| C1 Feature coverage | 3 | Full CRUD over HTTP, has-one/has-many/inverse, rich filters, sort, include, pagination, lang strings and typed literals, deltas. No transactions/UoW/identity map, no JSON-LD, no SHACL, only one application graph from the app's view | `call-specification.lisp:14-504`; `response-generation.lisp:196-328`; `query-execution.lisp:64-128` |
| C2 Approach & patterns | 3 | Clean metadata-mapping and proxy patterns at stack level, but no domain objects at all (generic resource service). Persistence is string-built SPARQL; hooks are the only extension point | `resource-model.lisp:580-615`; `callbacks.lisp`; `acl.lisp:249` |
| C3 Developer friendliness | 3 | Very short happy path (domain.json + dispatcher rule → API). But settings and hooks are Lisp-only, errors are terse, there are no static types, and the docs site is not machine-readable. READMEs are rich (Diátaxis-style in sparql-parser) | mu-cl-resources README; sparql-parser README |
| C4 Ease of adoption | 2 | Everything is Docker images, so adoption means running the stack (identifier, dispatcher, resources, sparql-parser, delta-notifier, Virtuoso). There is no in-memory store and no library mode | `mu-project/docker-compose.yml` |
| C5 Reuse of mature foundations | 2 | Lisp core re-implements the SPARQL parser (`sparql-ast/`, ~2.8k LOC), JSON (jsown) and the client (cl-fuseki). Templates do use SPARQLWrapper + rdflib (Py) and sparql-client-2 (JS) | `sparql-parser/sparql-ast/*`; `.gitmodules`; `mu-python-template/requirements.txt` |
| C6 Data-centric & DDD fit | 2 | Model-first in the sense of a declarative domain file, but it is an API mapping, not a domain model. No aggregates or repositories; services share the whole store; no LinkML/OWL source | `domain-parsing.lisp`; mu.semte.ch/about |
| C7 SPARQL 1.1 portability | 3 | Speaks plain SPARQL 1.1 Query/Update over HTTP (proxy pattern is store-agnostic), but defaults and workarounds are Virtuoso-oriented. No Graph Store Protocol | `server.lisp:120`; README "Using different sparql stores"; `docker-compose.yml:63-72` |
| C8 Health | 3 | MIT; active (latest commits 2025-09 to 2026-06); production use by Flemish government apps (sparql-parser README "Existing configurations"). But no automated tests in mu-cl-resources/delta-notifier, only 2 scenario files in sparql-parser, CI = Docker build only, and a single dominant author (asd `:author` Aad Versteden) | `.woodpecker/*.yml`; `sparql-parser/test/`; `delta-notifier/package.json` "test": no test |

## JS-friendliness (not scored)

**Excellent: this is the platform's core strength.**
- Generated **JSON:API** (`application/vnd.api+json`) works out of the box with **ember-data** and any JSON:API client (README "Resulting API"; getting-started uses `store.findAll`/`createRecord`/`destroyRecord`).
- Relationship links, `included`, sparse fieldsets and pagination links all follow the JSON:API conventions.
- An external generator produces **OpenAPI** from the domain (`mu-semtech/cl-resources-openapi-generator`, README "Generators"; not analysed).
- The JS service template is first-class.
- No TS types are generated and there is no JSON-LD.

## Feature inventory

| Id | Status | Evidence |
|---|---|---|
| M1 Host-language classes | absent | Domain is DSL/JSON, not Python/TS classes |
| M2 Schema language | present | `domain.json` v0.1 / `domain.lisp` DSL (`domain-parsing.lisp:54-147`) |
| M3 Code generation | partial | No code generated in the core. The API is generated at runtime. External OpenAPI and app generators (README "Generators", not analysed) |
| M4 Inheritance → rdf:type | present | `super`, all supertypes written, subclasses queried (`call-implementation.lisp:117,318`) |
| M5 Validation | partial | `:required` only (`call-specification.lisp:96,168`); no SHACL or type checks beyond parsing |
| I1 IRI minting | present | base + UUID, `mu:uuid` literal (`call-implementation.lisp:95-98`); UUIDv1 in Python template (`helpers.py:55`) |
| I2 Blank nodes / embedded | absent | Every resource needs `mu:uuid` + IRI |
| I3 Identity map | absent | Only uuid↔uri and model-property caches across requests (`caching.lisp`) |
| R1 Single / multi values | partial | `*-set` types = unordered sets; no rdf:List |
| R2 References, inverse | present | has-one/has-many, `inverse` (`resource-model.lisp:12-33`; `domain-parsing.lisp:120-137`) |
| R3 Lazy / eager, depth | present | `include=a.b` (depth ≤15) vs relationship links (`included-items.lisp:8,371`) |
| R4 Cascade | partial | Delete removes the resource's own and incoming declared links, not linked resources (`call-implementation.lisp:847-929`) |
| L1 Typed literals | present | xsd importers (`query-parsing.lisp:50-154`); custom boolean type default |
| L2 Language-tagged strings | present | `language-string(-set)` (`request-parsing.lisp:53-56`, `query-parsing.lisp:32`) |
| P1 CRUD | present | `call-specification.lisp` defcalls |
| P2 Update strategy | present | Per-property DELETE-WHERE + INSERT DATA (`call-implementation.lisp:157-176`) |
| P3 Unit of work | partial | `with-update-group` string batching only (`query-execution.lisp:25`) |
| P4 Transactions | absent | No rollback; proxy splits into ≤100-quad batches (`handle-update-unit.lisp:3-7,704`) |
| P5 Optimistic concurrency | absent | — |
| P6 Named graphs | partial | App sees one graph (`settings.lisp:13`); proxy dispatches quads to many graphs by policy (`acl.lisp:301`) |
| P7 Bulk load / export | absent | In resources. mu-migrations-service exists (`docker-compose.yml:34-44`, not analysed) |
| Q1 Fetch by id | present | By UUID (`show-call`), or `filter[:uri:]` by IRI |
| Q2 Filter → SPARQL | present | JSON:API filter DSL (`response-generation.lisp:196-328`) |
| Q3 Raw SPARQL mapped back | absent | Templates return raw SPARQL-JSON only |
| Q4 Pagination / order / aggregate | partial | Page + sort + count; no general aggregation (`response-generation.lisp:15-132`) |
| Q5 Multi-hop | present | Dotted filter/sort paths compiled to property paths (`resource-model.lisp:454-579`) |
| S1 In-memory store | absent | — |
| S2 Remote SPARQL endpoint | present | `MU_SPARQL_ENDPOINT`; `client:*backend*` |
| S3 Graph Store Protocol | absent | — |
| S4 Pluggable store | partial | Any SPARQL endpoint behind the proxy; README mentions store plugins |
| X1 JSON-LD | absent | — |
| X2 Other RDF formats | absent | In resources; raw SPARQL only |
| X3 HTTP API exposure | present | Generated JSON:API |
| X4 Schema export for clients | partial | External OpenAPI generator (claimed, not analysed) |
| X5 Change notifications | present | Delta messages + delta-notifier rules (`messenger.lisp`, `app.js`) |
| D1 Static typing | absent | Lisp/JS/Py untyped; JS template has JSDoc `QueryOptions` only |
| D2 Async API | partial | JS template is Promise-based; Python is sync |
| D3 Framework integration | present | Flask / Express templates; Ember via JSON:API |
| D4 Docs | partial | Good READMEs (tutorial + reference); docs site not retrievable; some outdated or inconsistent statements |
| D5 Testing support | absent | No fakes or fixtures; tests are scenario scripts against a live store |
| O1 OWL semantics | absent | sparql-parser `reasoner/` is experimental (take-1/take-2); not wired to resources |
| O2 Reasoner integration | partial (experimental) | `sparql-parser/reasoner/` |
| A1 Authorization hooks | present (noted only) | Graph/group ACL in proxy (`acl/`); per-resource hooks in resources (`callbacks.lisp`) |

### Proposed new features

| Proposed id | Area | Feature | Seen in |
|---|---|---|---|
| X6 | Interop | **Generated JSON:API contract** (filters, sort, include, sparse fieldsets, pagination links) from the model | mu-cl-resources |
| X7 | Interop | **Delta / change-set format** with SPARQL-JSON term encoding (insert/delete/effective*), subscription rules, fold, grace-period batching | sparql-parser + delta-notifier |
| X8 | Interop | **Cache-key emission and invalidation protocol** (cache keys on reads, clear keys on writes or deltas) | mu-cl-resources + mu-cache |
| X9 | Interop | **Header context propagation** (session-id, call-id trail, allowed/used groups, sudo, scope) through the persistence client | templates, sparql-parser |
| X10 | Interop | **External model file compatibility** (consume an existing `domain.json` as a model source) | mu-cl-resources |
| P8 | Persistence | **Effective-change detection** (diff writes against the store; emit only real changes) | `handle-update-unit.lisp:290` |
| P9 | Persistence | **Policy-driven graph placement** (quad → graph by type/predicate spec, not by caller) | `acl.lisp:301` |
| Q6 | Query | **Count / total in paginated responses** with optional count caching | `response-generation.lisp:15` |
| Q7 | Query | **Batched include (N+1 avoidance)** via a single VALUES+UNION query for related resources | `included-items.lisp:371` |
| D6 | DevEx | **Lifecycle hooks** (before/after/around per resource and operation) | `callbacks.lisp` |
| D7 | DevEx | **Service template / scaffold** (container, live reload, env-configured endpoint) | mu-*-template |
| RAD1 | RAD | **Zero-code CRUD service from the model** (deployable resource service) | mu-cl-resources |
| RAD2 | RAD | **Declarative routing / gateway config** (dispatcher) | mu-dispatcher (out of library scope) |
| A2 | Access | **Auth-proxy compatibility** (the ORM's queries pass through a rewriting proxy unchanged: no reliance on GRAPH clauses being honoured) | sparql-parser strips GRAPH patterns |

## Reuse verdict for rdf-persistence

**Borrow ideas + aim for compatibility. Do not adopt the code** (Common Lisp, a stack rather than a library). The reuse value lies in the *contracts*.

**Reuse and be compatible with:**
1. **JSON:API contract of mu-cl-resources**: URL shapes, `filter[...]` grammar incl. `:exact:/:gt:/:id:/:uri:/:has:`, `sort`, `include`, `fields`, 0-based `page[number]`, `meta.count`. An rdf-persistence JSON:API entrypoint that speaks this dialect would let existing Ember/JS front-ends and generators work unchanged. That is the strongest RAD lever for the JS ecosystem.
2. **`domain.json` v0.1 as an import format.** Small and well-specified (`domain-parsing.lisp:54-147`). It maps cleanly onto LinkML: resource → class with `class_uri`; attributes → slots with `slot_uri` + range; relationships → object slots with `multivalued` and `inverse`; `super` → `is_a`; `new-resource-base` → id prefix. A `domain.json ↔ LinkML` converter is cheap and gives migration paths in both directions.
3. **`mu:uuid` + base-IRI identity convention** as an *optional* IRI-minting strategy, so data written by rdf-persistence is visible to mu-cl-resources and vice versa.
4. **Delta format v0.0.1 / changeSets** as the event schema for rdf-persistence's change notifications (X5). Also provide a **delta consumer** (Python handler for `/.mu/delta`-style POSTs) to invalidate identity-map or cache entries.
5. **Header propagation** (`mu-session-id`, `mu-call-id`, `mu-auth-allowed-groups`, `mu-auth-used-groups`, `mu-auth-sudo`, `mu-auth-scope`) as a pluggable "request context" on the SPARQL adapter. This makes rdf-persistence usable as the Python persistence layer **inside a semantic.works stack, behind sparql-parser**. It also fixes the Python template's gaps (no sudo/scope, global mutable clients).

**Do differently:**
- **Python core on rdflib / pyoxigraph / SPARQLWrapper** (DEC-4) with in-memory stores for tests. semantic.works has no library mode and no in-memory testing.
- **LinkML as the model source.** Generate pydantic domain objects *and* the JSON:API/`domain.json` mapping from it, instead of a hand-written API mapping with no domain objects.
- **Real domain objects + repository/UoW** (cosmic-python): explicit aggregates, an identity map per session, diff-based flush. mu-cl-resources' per-property delete/insert is a good *default flush strategy* to copy.
- **JSON-LD (with @context generated from LinkML) as the primary middleware representation**, and JSON:API as a second profile. semantic.works offers JSON:API only.
- **Query builder with an AST**, not `format` strings (injection safety). Use rdflib's algebra or a small builder.
- **Do not depend on GRAPH clauses being honoured**: behind sparql-parser, graph placement is policy-driven. Graph handling should be a strategy: explicit named graph, or "let the proxy decide".
- **The ACL seam:** keep authorization outside the ORM, as semantic.works does (proxy). Expose hooks plus header propagation so a sparql-parser-like proxy or a future RBAC middleware can plug in.

## Risks / anti-patterns observed

- **No transactions:** multi-statement writes are split into batches by the proxy, so a partial write is possible (`handle-update-unit.lisp:704-718`). The PATCH delete-then-insert sequence has no concurrency control.
- **String-assembled SPARQL** throughout mu-cl-resources (`format` templates). Safety relies on the escape helpers.
- **The shared whole-store integration model** couples services through the vocabulary, which conflicts with aggregate boundaries. The inheritance strategy (write all supertypes) duplicates `rdf:type` triples.
- **Virtuoso bias:** custom boolean datatype, `virtuoso-p` binding expansion, the long-string-to-file workaround.
- **Configuration split** between JSON and Lisp; hooks and settings require Lisp, a high barrier for Python/JS teams.
- **Weak automated testing:** no unit tests in mu-cl-resources or delta-notifier; CI only builds images. There is a bus-factor concern (single author on the core Lisp components).
- **Caching correctness** depends on deltas arriving from every writer. Writes that bypass sparql-parser silently stale the caches (README "Cache clearing with delta-notifier").
- **Docs drift:** delta-notifier still points to the Elixir mu-authorization; the README lists POST on an item URL; cache flag names are inconsistent.

## Round 2 cross-check (taxonomy v1)

Source of truth for the ids: `docs/modules/ROOT/pages/architecture/soa/feature-taxonomy.adoc`, section "v1 features".

**Method**
- **Lisp repos:** GitNexus has no Common Lisp symbols (0 Function nodes), so evidence for mu-cl-resources and sparql-parser comes from source reading.
- **JS repos:** evidence is GitNexus-backed where noted.
- **"Absent" rows** were confirmed by grep over all six clones (`*.lisp, *.js, *.py, *.json, *.ex, *.md`). The terms searched were: `json-ld|@context|hydra|shacl|swrl|owl:imports|upsert|facet|skolem`. None of them matched in the code.

Paths are relative to `/home/lps/work/repos/`.

| Id | Status | Evidence |
|---|---|---|
| M6 Runtime model materialisation | partial | Resources are built at boot from `domain.json`/`domain.lisp` with no codegen step (`mu-cl-resources/framework/domain-parsing.lisp:5-66`, `configuration/domain.lisp` → `read-domain-file`). The source is an API mapping, not an ontology or observed rdf:type. |
| M7 Convention-based predicate derivation | absent | `predicate` is mandatory per attribute and relationship (`domain-parsing.lisp:139-147`, `jsown:val … "predicate"`). There is no namespace + name default. |
| M8 JSON-LD context as mapping | absent | grep `json-?ld\|@context`: no hits in code |
| M9 Attribute ≠ property (per language) | absent | One attribute per predicate. `language-string-set` returns all languages in a single attribute (`request-parsing.lisp:53-56`, `query-parsing.lisp:32-37`). |
| M10 Behaviour bound to classes | absent | No methods per class. Behaviour is only possible through hooks (D6, `callbacks.lisp`). |
| M11 Strict / warn-on-unmapped import | partial | Unknown JSON keys raise `no-such-property` (`resource-model.lisp:340-349`). sparql-parser logs and errors on quads that match no graph spec (`*unwritten-data-actions* '(:log :error)`, `updates/handle-update-unit.lisp:740-766`). This applies to API input and writes, not to data import. |
| M12 Alternative type discriminator | partial | sparql-parser can assign types from the URI prefix (`add-type-for-prefix`, `sparql-parser/cache/types.lisp:188`; README "Handle resources without an explicit type"). Resources itself always uses rdf:type. |
| M13 Constraint emission (SHACL / indexes) | absent | grep `shacl`: no hits in code. Nothing is generated from the domain. |
| M14 Reverse engineering from data | absent | No such tool in the clones |
| M15 External model-file compatibility (domain.json) | present | It is the native format: `domain-parsing.lisp:54-147`; README "Defining resources in JSON" |
| I4 Skolemisation policy | absent | No skolem code. Blank nodes in update quads are `:not-supported` (`sparql-parser/updates/detect-quads.lisp:160`). Resources always mint IRIs. |
| R5 Cardinality constraints | partial | Only `one`/`many` (`domain-parsing.lisp:120-137`). Has-one PATCH deletes before inserting, which enforces at most one (`call-implementation.lisp:230-250`). There is no min-cardinality or check on connect. |
| R6 Mutually exclusive relations | absent | — |
| R7 Relations with own properties | absent | Links are plain triples (`call-implementation.lisp:206-210`) |
| R8 Inverse navigation without declaring | absent | An inverse must be declared as a relationship with `inverse: true` (`domain-parsing.lisp:136`) |
| L3 Pluggable literal-type registry | present | `define-typed-literal-importer` registry keyed by datatype IRI (`query-parsing.lisp:50-154`), plus `interpret-json-value` generic per slot type (`request-parsing.lisp:53-82`). Lisp-only. |
| P8 Owned-predicate semantics | present | PATCH deletes and inserts only the mapped predicates that are sent (`call-implementation.lisp:157-176`). DELETE removes only declared properties and links (l.866-928). Foreign triples are preserved. |
| P9 Change detection / effective diff | partial | sparql-parser computes effective inserts and deletes against the store and writes only those (`detect-effective-changes`, `handle-update-unit.lisp:290`, 704-718). There is no client-side dirty tracking: PATCH sends the keys it receives. |
| P10 Collection patch operators | partial | Add and remove on has-many through `POST`/`DELETE …/links/rel` (`call-implementation.lisp:1099-1153`). No operators for `*-set` attributes, which are replaced whole. |
| P11 Orphan cleanup | absent | Delete does not cascade to linked resources (`call-implementation.lisp:847-929`) |
| P12 Policy-driven graph placement | present | `dispatch-quads-to-graph-specifications` (`sparql-parser/acl/acl.lisp:301-439`), `define-graph` type/predicate specs |
| P13 Transaction options | partial | Timeouts only: `dex:*default-read-timeout*` 120 s (`mu-cl-resources/configuration/settings.lisp`), `MU_SPARQL_TIMEOUT` (`mu-python-template/helpers.py:118-121`), sparql-parser `*max-query-time-for-retries*` (README). No transaction concept. |
| P14 Bulk upsert / get-or-create | absent | grep `upsert\|get.or.create`: no hits |
| P15 Concurrency mode | partial | sparql-parser caps connections per backend with a semaphore (`*max-concurrent-connections*` 8, `connection/client.lisp:13,32`). A `parallel-event-sequencer` orders writes on overlapping quads (`handle-update-unit.lisp:573-590`). |
| Q6 Injection-safe parameter binding | partial | Escape helpers only: `mu-python-template/escape_helpers.py` `sparql_escape_*`; JS `sparqlEscape*` (`helpers/mu/index.js`, GitNexus `Const mu`); `s-str`/`s-url` in resources. No prepared statements. |
| Q7 Typed SPARQL AST builder | partial | sparql-parser has a full EBNF parser, AST manipulation and generator (`sparql-ast/parser.lisp`, `manipulation.lisp`, `generator.lisp`), but uses it only to rewrite queries. mu-cl-resources builds queries with `format` strings (`response-generation.lisp:59-108`). |
| Q8 Derived query methods | absent | n.a. for a declarative HTTP API. Grep finds no such API in the templates. |
| Q9 Eager loading / N+1 avoidance | present | `construct-logical-union-query-for-included-items` VALUES+UNION (`included-items.lisp:371-395`) |
| Q10 Grouped result mapping | present | Pagination runs over `DISTINCT ?uuid` groups (`response-generation.lisp:59-108`); rows are then grouped into items (`group-solutions-to-complete` / `complete-solutions`, `call-implementation.lisp:493-610`). |
| Q11 Query safety / integrity on user SPARQL | partial | Every query is parsed by sparql-parser (unparseable queries are rejected). `assert-no-variables-in-quads` (`handle-update-unit.lisp:785`) and the unwritten-data error (l.755) also apply. No result-integrity checks. |
| Q12 Full-text search | partial | Only a case-insensitive substring `FILTER CONTAINS(LCASE(str(?v)), …)` (`response-generation.lisp:320-328`). README:781 states that fuzzy text search is not supported. |
| Q13 User-defined SPARQL functions | absent | — |
| Q14 Standard external filter language → SPARQL | present | JSON:API `filter[...]` dialect (`response-generation.lisp:196-381`) |
| Q15 Totals, facets, capped counts | partial | Total `COUNT(DISTINCT)` in `meta.count` with optional count caching (`response-generation.lisp:15-27`, `*include-count-in-paginated-responses*`, `*cache-count-queries-p*`). No facets or capped counts. |
| Q16 Configurable open-world negation | absent | `:has-no:` is hard-wired to `FILTER NOT EXISTS` (`response-generation.lisp:280-293`) |
| Q17 Polymorphic query over subclasses | present | `VALUES ?class { <ld-subclasses> }` (`call-implementation.lisp:318-320`, `1000-1006`) |
| Q18 CBD extraction | absent | — |
| S5 Read / write endpoint split | present | Python has separate `MU_SPARQL_ENDPOINT`/`MU_SPARQL_UPDATEPOINT` (`helpers.py:115-117`). sparql-parser `*backends*` sends reads to one random backend and writes to all (`connection/client.lisp:145-153`). |
| S6 Client-side cache with invalidation | present | uuid↔uri, model and count caches (`caching.lisp:10-200`). Cache keys and clear keys go to mu-cache (`docs/cache-keys.org`), invalidated by deltas (`call-implementation.lisp:1180-1300`). |
| S7 HTTP resilience | present | Exponential backoff in sparql-parser (`connection/client.lisp:164`, `delta/messenger.lisp:64-65`). Chunked updates of ≤100 quads (`handle-update-unit.lisp:3-7`). delta-notifier `retry`/`retryTimeout` (`send-request.js:44-82`, GitNexus process `informWatchers → handleResponse`). |
| S8 Community-standard store port | absent | Custom clients: cl-fuseki (`.gitmodules`), sparql-client-2 (`helpers/mu/sparql.js:2`), raw SPARQLWrapper (`helpers.py:115`). No RDF/JS or rdflib Store port. |
| X6 Generated JSON:API contract | present | `call-specification.lisp:14-504`; README "Querying the API" |
| X7 Content negotiation | partial | The dispatcher routes on accept types (`mu-project/config/dispatcher/dispatcher.ex` `define_accept_types`). Resources checks `application/vnd.api+json` (`settings.lisp:8-11`, `request-parsing.lisp:177`). Only one media type; no profiles. |
| X8 Hydra hypermedia contract | absent | grep `hydra`: no hits. JSON:API `links` only. |
| X9 API vocab ↔ storage vocab mapping | present | JSON key/type ↔ predicate/class is the core of the domain file (`resource-model.lisp:123-185`). Optional `*camelcase-json-variables*` (`resource-model.lisp:127`). |
| X10 Read models / projections | partial | Several resource definitions can project the same class or predicate differently. The README "polymorphic API" discussion says API types may diverge from store types. There is no separate read-model mechanism. |
| X11 Annotated representations | absent | — |
| X12 Delta / change-set format with subscription rules | present | `sparql-parser/delta/messenger.lisp:36-116`; `delta-notifier/app.js:19-107`, `send-request.js:6-43`, `folding.js` (GitNexus: `informWatchers → formatChangesetBody / foldChangeSets`) |
| X13 Request-context propagation | present | `helpers.py:123-164`; `helpers/mu/sparql.js:13-120` (GitNexus `update/query → newSparqlClient`); delta headers (`messenger.lisp:52-60`); `mu-call-id-trail` in `delta-notifier/app.js:27-30` |
| X14 Graph / model diff as API | absent | Effective diffs exist only as delta events (X12), not as a callable API |
| D6 Lifecycle hooks | present | `before`/`after`/`around` (`callbacks.lisp:79-97`), wrapped around every call by `with-surrounding-hook`. sparql-parser also has `*user-quad-transform-functions*` (`updates/quad-transformations.lisp:3`). |
| D7 Single-source sync and async APIs | absent | JS is Promise-only (`sparql.js:65-90`); Python is sync-only (`helpers.py:130-164`) |
| D8 Multi-store integration test matrix | absent | Tests are only `sparql-parser/test/scenario*.lisp` against one live store. CI runs docker build only (`.woodpecker/*.yml`). |
| D9 Service template / scaffold | present | `mu-python-template` (`web.py`, `Dockerfile`), `mu-javascript-template` (`boot.sh`, `run-development.sh`) |
| RAD1 Zero-code CRUD service from the model | present | mu-cl-resources as a whole |
| RAD2 Declarative routing / gateway | present (out of library scope) | `mu-project/config/dispatcher/dispatcher.ex`; mu-dispatcher README |
| O3 OWL class-expression API | absent | — |
| O4 Inferred vs asserted views | absent | `sparql-parser/reasoner/` (take-1, take-2) is an experimental type reasoner for ACL dispatch; no inference graph |
| O5 Local closed-world closure | absent | — |
| O6 Rule support (SWRL) | absent | grep `swrl`: no hits |
| O7 Ontology import resolution | absent | grep `owl:imports`: no hits |
| A2 Auth-proxy compatibility | present | This is the platform's design: resources writes to an application graph (`query-execution.lisp:64-128`), and sparql-parser removes GRAPH patterns and re-dispatches (`acl/acl.lisp:249-263`, 301) |
| A3 Field-level access modes | partial | Per-graph read/write grants, with predicate exclusion `x>`/`<x` in `define-graph` (sparql-parser README "Reference"). Not per field per user; no type-change guard. |

**Re-marked v0 features (meaning changed in v1)**

| Id | Status | Evidence |
|---|---|---|
| O2 Reasoner integration (modes) | partial (experimental) | An in-process, in-proxy reasoner for types only (`sparql-parser/reasoner/take-1/reasoner.lisp`, `take-2/tree.lisp`). Neither batch nor incremental is selectable, and there is no write-back graph. |
| X4 Schema export (incl. Pydantic / JSON Schema) | partial | Only the external OpenAPI generator (`mu-semtech/cl-resources-openapi-generator`, README "Generators"; not in the clones). No Pydantic or JSON Schema output. |
| X5 Change notifications | present | Refined by X12 (present) |
| D2 Async API | partial | JS async (Promises), Python sync. D7 is absent. |

**Counts (63 v1 features):** 20 present, 16 partial, 27 absent, 0 n.a. Q8 is marked absent although it is effectively n.a. for this platform.

### Proposed new features (round 2)

| Proposed id | Area | Feature | Evidence |
|---|---|---|---|
| S9 | Stores | **Multi-backend replication**: writes fanned out to all endpoints, reads load-balanced to one (distinct from S5 read/write split) | `sparql-parser/connection/client.lisp:145-153` |
| P16 | Persistence | **Large-literal offloading**: strings above a size threshold stored as file references, transparently restored on read | `sparql-parser` README `support:*string-max-size*`; `handle-update-unit.lisp:496-570` |
| P17 | Persistence | **Write-path quad transformation hooks** (rewrite or expand quads before storage, below the object level) | `sparql-parser/updates/quad-transformations.lisp:3-10` |

## Round 3

Inputs: `BRIEF-round3.md`, `RUBRIC.md` (C9, C10), the taxonomy v2 section. Paths are relative to `/home/lps/work/repos/`.

GitHub data (`gh api repos/mu-semtech/<repo>`, 2026-11-03):

| Repo | Stars | Last push | Licence (GitHub) |
|---|---|---|---|
| sparql-parser | 5 | 2026-10-23 | none detected (asd says MIT) |
| mu-cl-resources | 18 | 2026-09-24 | none detected (asd says MIT) |
| delta-notifier | 0 | 2026-06-03 | none detected (package.json says MIT) |
| mu-authorization (Elixir predecessor) | 3 | 2024-07-18 | MIT |
| mu-javascript-template | 5 | 2026-09-29 | none detected |
| mu-python-template | 5 | 2026-10-27 | MIT |
| mu-project | 16 | 2026-06-05 | MIT |
| mu-dispatcher | 5 | 2026-06-19 | MIT |
| mu-identifier | 5 | 2026-09-01 | MIT |

The org has 55 public repos. **Every repo fails the DEC-5 star threshold (>200)**, so as library dependencies they are ideas-only. Whether running them as external Docker *services* falls under DEC-5 is an open question (see below).

### (a) v2 cross-check

"Absent" was confirmed by grep over all six clones. The terms searched were `soft.?delete|tombstone|regex|vector|similar|rename|diagram|stream|conformance`, and none matched any feature code.

| Id | Status | Evidence |
|---|---|---|
| M16 Multi-typed instances, deterministic resolution | partial | Every supertype is written. On read the "most specific type" wins (README "Inheritance"; `call-implementation.lisp:117-118`; `resource-distance`, `resource-model.lisp:266`). There is no general method resolution order for unrelated multiple types. |
| M17 Mapping validation at definition time | partial | `run-validations` only checks there is no `/` in `on-path` (`resource-validations.lisp:3-28`). Cardinality and URI shape are checked when the domain is parsed (`domain-parsing.lisp:105-110,126-131`). No check for unique predicates or consistent inverse pairs. |
| I5 IRI / namespace renaming | absent | Not found |
| I6 Equality by persistent identity | partial | `item-spec` identity is uuid/node-url, resolved through the uuid↔uri caches (`caching.lisp:16-110`). There are no domain objects to compare. |
| P16 Undoable / soft deletes | absent | DELETE is a hard `DELETE … WHERE` (`call-implementation.lisp:890-928`); grep finds no soft delete or tombstone |
| P17 Large-literal offloading | present | sparql-parser `support:*string-max-size*` 4096 → string files (README "support"; `handle-update-unit.lisp:496-570`; `administration/string-files.lisp`) |
| P18 Write-path quad-transformation hooks | present | `define-quad-transformation` with `update`/`keep` (`updates/quad-transformations.lisp:3-107`); real use in `test/scenario.lisp:58-74` (normalises a typed `mu:uuid` literal) |
| P19 Change-aware reload of a source | absent | Domain changes need a restart (`mu-project/config/resources/repository.lisp` NOTE: "docker-compose stop; docker-compose rm; docker-compose up"). mu-migrations (not cloned) runs migrations once. |
| Q19 Regex / substring filters | partial | Substring only (`FILTER CONTAINS(LCASE(...))`, `response-generation.lisp:320-328`). No regex filter. |
| Q20 Vector / similarity search | absent | Not found |
| S9 Multi-backend replication | present | `connection/client.lisp:145-153` |
| S10 Linked Data dereferencing store | absent | Not found |
| S11 Embedded-store administration | partial | sparql-parser administration batch-moves long strings to files (`administration:update-database-long-strings-to-string-files`, README "administration"). Store admin itself is left to Virtuoso. |
| S12 Batched queries in one client call | partial | Updates only: `with-update-group` joins them with `;` into one request (`query-execution.lisp:18-30`). Selects are separate calls. |
| S13 Streaming large result sets | absent | Results are parsed whole (`jsown:parse`, `server.lisp:113-117`). delta-notifier accepts 500 MB bodies whole (`app.js:19`). |
| S14 Query observability | partial | Query and response logging toggles (`sparql:*query-log-types*`, `*log-sparql-query-roundtrip*`, `LOG_SPARQL_*` in the templates) and `mu-call-id` / `mu-call-id-trail` correlation. No timing or fingerprint. |
| X15 Document-centric grouping | absent | Not found. Each resource is its own IRI with `mu:uuid`. |
| X16 Conformance to a standard API profile | partial | Follows JSON:API (README: "We intend to support the full spec … errors being a notable exception"). No conformance endpoint or declared profile. |
| D10 Model diagram generation | absent | Only a README pointer to WebVOWL; no generator in the clones |

Counts: 3 present, 8 partial, 8 absent.

### (b) Developer experience (DX) deep-dive

**Shortest path from empty to a CRUD API and an Ember app.** The steps are taken from `mu-project/README.md`, the mu-cl-resources README "Add mu-cl-resources to a stack", and https://mu.semte.ch/getting-started/.

1. `mu project new awesome-project-name`, or clone mu-project. The mu-project README says: "Setting up your environment is done in three easy steps: 1. … `docker-compose.yml` 2. … `config/dispatcher.ex` 3. … start the docker-compose."
2. Edit `config/resources/domain.json`. The template file is empty (`{"version":"0.1","prefixes":{},"resources":{}}`). One resource with 2 attributes is about 15 lines (README "Introduction to a configuration through domain.json"). A relationship adds 5 lines per side.
3. Edit `config/dispatcher/dispatcher.ex`: 3 lines per resource path, e.g. `match "/people/*path", @json do Proxy.forward conn, path, "http://resource/people/" end`.
4. Authorization: the default `config/authorization/config.lisp` already grants `(read write)` on `http://mu.semte.ch/graphs/public` with `(_ -> _)` to the group `"public"`. So for a prototype nothing needs editing. The flip side is that **the default is world-writable**.
5. `docker-compose up`. Then `GET /people` works through the identifier on port 80.
6. Frontend (getting-started; not in the clones): `ember new`, one ember-data model file per resource mirroring the attributes and relationships, `ember serve --proxy http://localhost`, then `store.findAll('person')` / `createRecord(...).save()` / `destroyRecord()`.

**Footprint for one resource:** 2 backend files touched (`domain.json`, `dispatcher.ex`) at about 18 lines, plus about 3 frontend files (model, route, template) per resource. No backend code at all. This zero-code CRUD (RAD1) is what developers love.

**Concepts and languages to learn**
- **The 7 services in the default compose** (`mu-project/docker-compose.yml`):

  | Service | Role |
  |---|---|
  | identifier | sessions |
  | dispatcher | Elixir routing DSL |
  | resource | domain.json/Lisp |
  | migrations | SPARQL / Turtle migrations |
  | delta-notifier | JS rules |
  | database | sparql-parser, ACL in Lisp |
  | triplestore | Virtuoso ini |

- Configuration languages: **YAML, Elixir, JSON, Common Lisp (twice), JavaScript, SPARQL and Virtuoso ini**.
- Conventions: `mu:uuid` on every resource, the application graph vs the ACL graphs, the header protocol (`mu-session-id`, `mu-auth-allowed-groups`, `mu-auth-sudo`, `mu-auth-scope`, `mu-call-id`), delta formats and `ignoreFromSelf`.

**Real error messages** (from the code):
- Dispatcher 404: `"Route not found.  See config/dispatcher.ex"` (`mu-project/config/dispatcher/dispatcher.ex`).
- Resources:
  - `"Access for ~A operation on ~A with id ~A was denied."` (`call-specification.lisp:9`);
  - `"Could not find property (~A) on resource (~A)."` (l.29);
  - `"Request invalid"` for an unknown link (l.26);
  - `"Could not execute SPARQL query."` (l.38);
  - `"Server configuration issue: …"` (l.43).
  - At boot: `"FOUND VALIDATION ISSUES WHEN VALIDATING RESOURCES.  SEE ABOVE."` (`resource-validations.lisp:12`).
- sparql-parser: HTTP 500 with `"Failed to process query."` (`connection/server.lisp:179-182`). Errors from the backend store are opaque to the client; the detail is only in the container log (`"Could not process query, yielding 500."`, l.195).
- Python template: requests with a missing content type get a JSON:API error (`helpers.py:101-105`). The docstring says it "Returns a 404 otherwise", but the code returns `error(...)` with the default status **400**, so docstring and code disagree.

**Ops footprint:** 7 containers by default. Add the frontend, plus mu-cache when the external cache is enabled, for 8–9. Count the Ember dev server too.
- RAM: sparql-parser reserves `LISP_DYNAMIC_SPACE_SIZE` = 4096 MB by default (README).
- Logs: via the Docker json-file driver (`x-logging` in the compose file).
- Upgrades: image-tag bumps per service; sparql-parser is still at 0.0.x.

**What developers love (evidence-based)**
- Zero-code JSON:API with a rich filter dialect, include and sparse fields.
- Ember-data works out of the box.
- One `docker-compose up`.
- Live reload in the templates (`MODE=development`, `NODE_ENV=development`).
- Deltas make reactive services trivial.
- One shared triplestore, so there is no service-to-service API to maintain.

**What developers hate / footguns**
1. Lisp-only settings and hooks: "Most settings can only be configured in Lisp format" (README).
2. A domain change needs a full container restart (`repository.lisp` NOTE).
3. **The headers are trusted.** sparql-parser takes `mu-auth-allowed-groups` from the request as the token set without recomputing it (`acl.lisp:175-184,196-212`), and `mu-auth-sudo` bypasses the ACL (`acl.lisp:253`, `server.lisp:144-155`). Any container on the Docker network can therefore escalate. Security relies on network isolation and on the identifier not forwarding these headers from the browser; I did not verify that last point in identifier code.
4. Caches go stale silently if a writer bypasses sparql-parser (README "Cache clearing with delta-notifier").
5. Quads that match no `define-graph` are not written, and **logged as an error** (`*unwritten-data-actions* '(:log :error)`, `handle-update-unit.lisp:740-766`). This surprises people who write a new type before adding an ACL spec.
6. `ignoreFromSelf` uses the IP from a DNS lookup (`app.js:110-133`), which breaks with scaled replicas or IP reuse.
7. `page[number]` is 0-based; booleans use a custom datatype unless reconfigured; POST cannot choose the id.
8. The Python template forwards headers through module-global SPARQLWrapper instances mutated per request (`helpers.py:115-164`), which is unsafe under concurrency. It also lacks sudo and scope.
9. The documentation is spread over READMEs; the semantic.works docs site is not machine-readable.

**DX score: 3/5.** Prototyping is excellent (2 files, no code) and the front end is first-class. That is offset by a polyglot configuration surface (Lisp/Elixir), 7+ containers, opaque 500s, trusted-header security and restarts to change the model.

### (c) Authorization deep-dive (sparql-parser)

**A real configuration**, from the integration scenario `sparql-parser/test/scenario.lisp:118-171`, abridged:

```lisp
(acl:supply-allowed-group "public")
(acl:supply-allowed-group "user"
  :parameters ("id")
  :query "PREFIX session: <http://mu.semte.ch/vocabularies/session/>
          PREFIX mu: <http://mu.semte.ch/vocabularies/core/>
          SELECT ?id WHERE { <SESSION_ID> session:account/mu:uuid ?id. }")
(acl:supply-allowed-group "admin" :parameters ()
  :query "… SELECT ?account WHERE { <SESSION_ID> session:account ?account.
                                     ?account ext:hasRole ext:Administrator. }")
(acl:define-graph acl::public-data ("http://mu.semte.ch/graphs/public")
  ("foaf:Person" acl::-> acl::_) ("schema:Book" acl::-> acl::_) ("geo:Geometry" acl::-> acl::_))
(acl:define-graph acl::user-data ("http://mu.semte.ch/graphs/personal/")
  (acl::_ acl::-> "ext:hasBook" acl::-> "ext:hasSuperFavorite" acl::-> "ext:longContent")
  ("foaf:Person" acl::<- "ext:hasFavoriteAuthor")
  ("ext:NoNameOrLabel" acl::x> "ext:name" acl::x> "ext:label"))
(acl:define-graph acl::push-updates ("http://mu.semte.ch/graphs/push" :delta t :sparql nil)
  ("push:Update" acl::-> acl::_))
(acl:grant (acl::read acl::write) :to acl::public-data :for "admin")
(acl:grant (acl::read)            :to acl::public-data :for "public")
(acl:grant (acl::read acl::write) :to acl::user-data   :for "user")
```

**Model.** Group membership is a **SPARQL SELECT** over session data (`<SESSION_ID>` is substituted into the parsed AST and checked by `sparql-generator:is-valid`; `acl.lisp:66-95`). Each result row becomes an **access token** `{name, variables}`. Its `:parameters` are appended to the graph base IRI, which gives per-user or per-organisation graphs (`token-graph-specification-graph`, `acl.lisp:243-247`). Grants link groups to graph specifications for `read`/`write`, optionally per **scope**, i.e. the calling service (`accessible-graphs`, l.223-234).

**Granularity**
- **Reads are graph-level.** `apply-access-rights` strips the query's dataset and GRAPH clauses and adds `FROM <g>` for every readable graph (`acl.lisp:249-263`). Any triple in a readable graph is visible, whatever its type or predicate: the type/predicate specification does *not* filter reads.
- **Writes are triple-level by pattern.** Each inserted or deleted quad is placed in the graphs whose type specification matches the quad: subject type `->`, object type `<-`, predicate exclusions `x>`/`<x`. The type is resolved through a type cache plus SPARQL lookups (`dispatch-quads-to-graph-specifications`, `acl.lisp:301-439`; `cache/types.lisp`).
- The upshot: triple-level *write* policy and graph-level *read* policy. Real triple-level read confidentiality has to be modelled by putting data into separate graphs at write time. The `:sparql nil :delta t` option makes **delta-only virtual graphs** (push channels that are never stored).
- `mu-auth-used-groups` (needed for access-aware caching in the 2019 blog post) is **not emitted** by sparql-parser: no occurrence in `connection/server.lisp`. Only `mu-auth-allowed-groups` is returned (l.169-187). Claimed for mu-authorization; not found in sparql-parser.

**How a Python service built on rdf-persistence plugs in**
- Point the SPARQL adapter at `http://database:8890/sparql`, i.e. sparql-parser, not the triplestore.
- Per request, forward the incoming `mu-session-id`, `mu-call-id` and `mu-auth-allowed-groups`. Copy `mu-auth-allowed-groups` from SPARQL responses back to the HTTP response, so the identifier caches it (as JS `sparql.js:93-106` does).
- Support `mu-auth-sudo: true`, gated by configuration as JS does with `ALLOW_MU_AUTH_SUDO`, and `mu-auth-scope`, defaulting from `DEFAULT_MU_AUTH_SCOPE`.
- Never rely on `GRAPH`/`FROM` in its own queries, because they are stripped. Treat the "target graph" as a hint only.
- Expect HTTP 500 for denied writes (unwritten-data error) rather than 403.
- Make write batching idempotent: the proxy re-batches, so a write is not atomic.
- These are the X13 (context propagation) and A2 (auth-proxy compatibility) requirements, and they keep rdf-persistence ACL-agnostic as DEC-8 requires.

**Could the config be generated from LinkML or SHACL?** Partly.
- `define-prefixes` comes from LinkML `prefixes`.
- Type specifications come from class `class_uri` + slot `slot_uri`: `(Class -> slot…)` for owned slots, `<-` for slots whose range is the class.
- A LinkML annotation such as `acl_graph: user-data` per class or slot would yield the `define-graph` partitions. `x>` exclusions come from slots tagged confidential.
- SHACL `sh:targetClass` + `sh:path` carries the same information.
- **Not derivable from the model:** group membership queries and grants. They are policy, not structure, and would have to be authored, e.g. as a small YAML/LinkML-annotation policy file that is compiled to `config.lisp`.
- Because the graph specification mirrors the class/predicate structure, a generator is cheap and stays in sync with the model. This is a real MWBv2 opportunity (proposed AZ2 below).

**Reuse verdict (rdf-persistence-based stacks)**
- **Integrate** sparql-parser as an *optional, external* policy enforcement point (PEP) behind the generic SPARQL port when deploying into semantic.works-compatible stacks. Do not embed or reimplement it (DEC-8).
- **Borrow** its ideas for the policy language: SPARQL-defined groups, parameterised graph templates, type/predicate write dispatch, scopes, delta-only graphs. Benchmark the broader authorization-engine survey against them.
- **Avoid** it as the *default* PEP for MWBv2 because:
  - it fails DEC-5 (5 stars);
  - Common Lisp means a high maintenance cost for Meaningfy;
  - it has a trusted-header security model with no OIDC/JWT;
  - reads are graph-level only;
  - `used-groups` is not emitted.

### (d) Layer coverage and standalone reuse

| Layer | Coverage | semantic.works component(s) | Evidence |
|---|---|---|---|
| L0 modelling & codegen | partial | `domain.json`/`domain.lisp` (API mapping, no codegen); external OpenAPI generator | `domain-parsing.lisp` |
| L1 domain & persistence | partial | mu-cl-resources is a generic resource store with no domain objects; templates give raw SPARQL | `call-implementation.lisp`; `helpers.py`, `sparql.js` |
| L2 stores & transactions | partial | Virtuoso; sparql-parser multi-backend, batching, effective diff; no transactions | `client.lisp:145`, `handle-update-unit.lisp` |
| L3 identity & authorization | present (sessions + graph ACL; no IdP/OIDC in the clones) | mu-identifier, sparql-parser; login via mu-login (not cloned) | `acl/`; mu-identifier README |
| L4 data-management service / API | present | mu-cl-resources JSON:API; dispatcher | `call-specification.lisp` |
| L5 JS client & UI | partial (external) | Ember + ember-data via JSON:API; JS service template | getting-started |
| L6 change events | present | sparql-parser deltas + delta-notifier | `messenger.lisp`, `app.js` |

**Standalone reuse outside semantic.works**

| Component | Depends on | Reusable as | Caveats |
|---|---|---|---|
| **sparql-parser** | Any SPARQL 1.1 endpoint (`*backends*`). Sessions as triples (`<SESSION_ID>` queries), the `mu-session-id` header, the mu header protocol | A transparent **SPARQL PEP proxy + CDC (delta) emitter** in front of any store | Lisp, 4 GB heap default, Virtuoso-flavoured result handling (`expand-bindings :virtuoso-p t`), trusted headers. Clients must send `mu-session-id`, and some IdP bridge must write session→account triples. |
| **delta-notifier** | Only the `changeSets` JSON POST | A **generic webhook fan-out** for RDF change events: pattern rules, batching, folding, retries | Small (~470 LOC), no tests, IP-based self-filtering. Could be fed by any CDC source that emits the same JSON. |
| **mu-cl-resources** | `mu:uuid` on every resource; one SPARQL endpoint | A **JSON:API-over-SPARQL** service for any store, given the uuid convention | Lisp; `mu:uuid` triples must be backfilled for existing data |
| mu-dispatcher / mu-identifier | HTTP only | Generic reverse proxy / session cookie proxy | Standard proxies (Traefik, nginx) + an OIDC proxy do this. Low value outside the stack. |
| Templates | The mu header protocol | Patterns only | rdf-persistence should provide the Python equivalent (D9). |

### (e) C9 and C10 scores

| # | Score | Justification | Evidence |
|---|---|---|---|
| C9 Composability / ecosystem fit | 3 | Composes over **plain HTTP and SPARQL 1.1 Query/Update**, so every service is swappable behind its port (the stack itself proves it: sparql-parser replaced the Elixir mu-authorization transparently). It emits JSON:API and SPARQL-JSON term encoding in deltas. **Missing:** JSON-LD, SHACL, LinkML, Graph Store Protocol, RDF/JS, and OIDC/JWT (identity is a proprietary session-cookie + `mu-*` header protocol). The `mu:uuid` convention and the custom boolean datatype leak into the data. | `docker-compose.yml`; `server.lisp:137-197`; `messenger.lisp:92-116`; `settings.lisp:13`; README "Data types" |
| C10 Maintainability & operability | 2 | Each component is small, deployed as versioned Docker images, and configured by files, with simple tag-bump upgrades. **But:** 5+ configuration languages (Lisp, Elixir, JSON, JS, YAML), 7+ containers, core components in Common Lisp (a scarce skill), sparql-parser at 0.0.x, no unit tests or CI tests (Woodpecker only builds images), effectively one author per core component, and observability limited to log flags and `mu-call-id` with no metrics, tracing or timing. | `.woodpecker/*.yml`; `sparql-parser.asd` v0.0.15; README "Enable additional logging"; `delta-notifier/package.json` "no test specified" |

### (f) Proposed new features (round 3)

| Proposed id | Area | Feature | Evidence |
|---|---|---|---|
| AZ1 | Authorization | **SPARQL-defined group membership** (a group = a SELECT over session data; rows become parameterised tokens) | `acl.lisp:66-95`; sparql-parser README `supply-allowed-group` |
| AZ2 | Authorization | **Parameterised graph templates**: graph IRI = base + token parameters (per-user / per-org graphs) | `acl.lisp:243-247` |
| AZ3 | Authorization | **Type/predicate-pattern write policy** (`->`, `<-`, `x>`, `<x`) deciding which graphs a quad may land in | `acl.lisp:301-439`; README `define-graph` |
| AZ4 | Authorization | **Caller scopes**: grants restricted to a calling service identity (`mu-auth-scope`) | README "Define access rights for specific services"; `acl.lisp:223-234` |
| AZ5 | Authorization | **Privileged bypass (sudo) with explicit opt-in** per service | `sparql.js:17-23`; `acl.lisp:253` |
| AZ6 | Authorization | **Access-token propagation and caching across hops** (allowed-groups computed once, carried in headers, cached at the edge) | `acl.lisp:196-212`; mu-identifier README |
| AZ7 | Authorization | **ACL configuration generated from the model** (LinkML/SHACL classes and slots → graph specifications; policy authored separately) | Gap identified in (c); not present in semantic.works |
| E1 | Events | **Delta-only virtual graphs**: writes routed to subscribers but never stored (`:sparql nil :delta t`) | `test/scenario.lisp:159-160`; README `define-graph` keywords |
| E2 | Events | **Call-id trail / loop prevention** for event-triggered writes (`mu-call-id-trail`, `ignoreFromSelf`) | `delta-notifier/app.js:27-30,110-133`; `messenger.lisp:55-57` |
| E3 | Events | **Ordered sequencing of overlapping writes with sequence ids** in emitted events | `handle-update-unit.lisp:573-590`; `messenger.lisp:108` (`sequenceId`) |
| G1 | Generation | **Front-end model scaffolding from the API model** (ember-data models / TS types generated from `domain.json`) | Gap: done by hand in getting-started; the mu-application-generator README mention is not in the clones |
| T1 | Transactions | **Write-batch size heuristics** (max quads / chars per update) with an ordering guarantee but no atomicity across batches | `handle-update-unit.lisp:3-7,704-718` |

**Open questions (round 3)**
- Does DEC-5 apply to Docker *services* (sparql-parser, delta-notifier) consumed over HTTP, or only to library dependencies? It decides whether "integrate as optional PEP" is allowed.
- Does mu-identifier strip browser-supplied `mu-auth-*` headers? Not verified in code; this is critical for the trusted-header model.
- Should MWBv2 target compatibility with the semantic.works header protocol (X13/A2) as a first-class deployment, or only through an adapter?

## Round 4

Inputs: `BRIEF-round4.md`; the integrated pages `index.adoc`, `building-blocks.adoc` and `variants.adoc`; feature taxonomy **v3** with its Id-mapping appendix.

**New clones for the security question** (shallow, read-only): `mu-identifier` 4d8978b (2025-04-29) and `mu-dispatcher` f85e83b (2026-05-18). I indexed both with `gitnexus analyze`:

| Repo | Nodes | Edges | Clusters | Flows |
|---|---|---|---|---|
| mu-identifier | 39 | 33 | 0 | 0 |
| mu-dispatcher | 50 | 45 | 0 | 0 |

**GitNexus does not parse Elixir symbols** (`MATCH (n:Function)` → 0 rows), but its file ranking for "strip mu-auth-allowed-groups mu-auth-sudo request headers" put `clear_mu_internal_keys.ex` and `add_custom_request_headers.ex` first. The evidence below is from reading those files.

### Security question settled: browser-sent `mu-*` headers

**Answer: yes. mu-identifier strips the security headers a browser sends and reissues the ones it owns.** mu-dispatcher strips nothing security-related.

1. **Request pipeline.** The request manipulators run in order `ClearMuInternalKeys → EnsureUserSession → AddCustomRequestHeaders` (`mu-identifier/lib/proxy.ex:23-27`).
2. **`ClearMuInternalKeys`** deletes from the incoming request `mu-auth-allowed-groups`, `mu-auth-used-groups`, `mu-auth-scope`, `mu-auth-sudo`, `cache-keys`, `clear-keys` and `x-cache` (`lib/manipulators/clear_mu_internal_keys.ex:5-15`). The same module runs on the response (`proxy.ex:28-34`), so none of these headers leak to the browser either.
3. **`AddCustomRequestHeaders`**:
   - deletes `mu-session-id`, `mu-call-id`, `mu-call-id-trail` and `mu-auth-allowed-groups` (`add_custom_request_headers.ex:7-12`);
   - reissues `mu-session-id` from the **signed + encrypted session cookie** (`:proxy_user_id`, created as `http://mu.semte.ch/sessions/<uuid1>` in `ensure_user_session.ex:16-26`; cookie options in `proxy.ex:13-19`), and a fresh random `mu-call-id` (l.14-18);
   - re-adds `mu-auth-allowed-groups` only from the encrypted session value written by `PutAllowedGroupsInSession` from backend responses, or from `DEFAULT_MU_AUTH_ALLOWED_GROUPS_HEADER`. The value `"CLEAR"` drops it (l.20-47).
4. **mu-dispatcher** only adds `x-rewrite-url` and (tries to) remove `accept-encoding` on requests, and adds `Vary: accept, cookie` on responses (`mu-dispatcher/lib/proxy.ex:2-3`, `lib/manipulators/*.ex`). It forwards every other header unchanged, so it depends on the identifier being the only entry point.
5. **Residual risks**, which correct the "any container can escalate" wording only in scope:
   - **(a) Internal callers.** Any container on the Docker network, and any service whose port is published (bypassing the identifier), can still send `mu-auth-sudo` or a forged `mu-auth-allowed-groups` straight to sparql-parser, which trusts them (`sparql-parser/acl/acl.lisp:175-212,253`; `connection/server.lisp:144-155`). The JS template's `ALLOW_MU_AUTH_SUDO` gate is a client-side courtesy, not enforcement (`helpers/mu/sparql.js:17-23`).
   - **(b) Duplicate headers.** `List.keydelete` removes only the **first** matching tuple. It is safe if the HTTP adapter merges duplicate header names. Cowboy 2 (`mix.exs:34`) presents request headers as a map, so duplicates arrive merged; I did not verify this in the dependency source, which is not vendored.
   - **(c) Pass-through.** Any other `mu-*` header, e.g. a future one, passes through. The strip list is a deny-list, not an allow-list.
   - **(d) Accept-encoding bug.** mu-dispatcher's `RemoveAcceptEncodingHeader` matches `"accept_encoding"` with an underscore (`remove_accept_encoding_header.ex:8`), so it never strips `accept-encoding`. Its README claims it does (mu-dispatcher `README.md:416`): **claimed, not working in code**.

### (a) v3 cross-check

Method: absences were confirmed by grep over the eight clones (the six originals + mu-identifier + mu-dispatcher; `*.lisp, *.js, *.py, *.ex`; `.claude/` and `node_modules/` excluded). Terms: `etag|if-match`, `cursor`, `atomic`, `outbox`, `savepoint`, `idempoten`, `rdf.?patch`, `time.?travel|as-of`, `websocket|server-sent|eventsource|mercure`, `graphql`, `openapi|swagger`, `redact|mask`, `explain`, `@context|json-?ld`, `rollback`, `optimistic`. All returned no feature code (the `atomic` hit is a comment in `client.lisp`; `cursor` and `optimistic` hits are unrelated).

Mapping from my round-3 ids: AZ1→AZ12, AZ2→AZ13, AZ3→AZ14, AZ4→AZ15, AZ5→AZ16, AZ6→AZ20, AZ7→AZ29, E1→E6, E2→E7, E3→E5, G1→G16, T1→T11.

| Id | Status | Evidence |
|---|---|---|
| AZ1 PEP at the store boundary | present (proxy form, not a library port) | Every service talks to `database` = sparql-parser, which narrows the dataset per request (`acl.lisp:249-263`; `mu-project/docker-compose.yml:54-61`) |
| AZ2 Uniform policy injection before pagination | present | All queries (item, list, count, include) pass `apply-access-rights` (`server.lisp:82-92`). The legacy in-resource token check is also injected into the list body before LIMIT (`call-implementation.lisp:318-320`, `34-47`). |
| AZ3 Rewriting PEP on a typed SPARQL AST | present | `remove-graph-graph-patterns`, `add-from-graphs` on the EBNF AST (`acl.lisp:256-263`; `sparql-ast/manipulation.lisp`) |
| AZ4 List-filter integration with an external PDP | absent | No external PDP. Groups come from SPARQL over session data. |
| AZ5 Write authorization on the changeset | present | Quads are computed, dispatched to writable graphs and the untreated ones are rejected before writing (`handle-update-unit.lisp:687-735,740-766`; `acl.lisp:301-439`). Pre-state is used for effective changes (l.290). |
| AZ6 Staged PEP hooks in the service pipeline | partial | Resources `before/after/around` hooks (`callbacks.lisp:79-97`) and the legacy `check-access-rights-for-item-spec` on show, update and delete (`call-implementation.lisp:49-71`) |
| AZ7 Separated PEP / PIP / PDP | partial | Logically separate (PIP = group queries `acl.lisp:66-95`; PDP = grants `accessible-graphs` l.223; PEP = rewrite l.249) but in one process and one configuration file |
| AZ8 Triple-level targeting | partial | Writes only, by subject/object type and predicate (`->`, `<-`, `x>`, `<x`). Reads are graph-level. No RDFS entailment: explicit types plus prefix rules (`cache/types.lisp:72,188`). |
| AZ9 SPARQL-condition policies with pre-bound variables | partial | Only `<SESSION_ID>` is substituted into the group query (`acl.lisp:76-80`) |
| AZ10 Policy-as-data | partial | Membership facts are RDF (sessions, accounts, roles), but the policy itself is Lisp code in `config/authorization/config.lisp`. Fail-closed: no graphs → `…/empty-graph` (`acl.lisp:262`). |
| AZ11 Combining algorithm, default deny | partial | Default deny on read (empty graph) and write (unwritten-data error); grants are unioned (allow-overrides); no deny rules |
| AZ12 SPARQL-defined group membership | present | `acl.lisp:66-95`; `test/scenario.lisp:118-145` |
| AZ13 Parameterised graph templates | present | `acl.lisp:243-247` |
| AZ14 Type/predicate write policy | present | `acl.lisp:301-439` |
| AZ15 Caller scopes | present | `accessible-graphs` scope check (`acl.lisp:231`); `mu-auth-scope` header (`server.lisp:155`) |
| AZ16 Sudo with per-service opt-in | partial | sparql-parser honours `mu-auth-sudo` from any caller (`acl.lisp:253`). The opt-in is only in the JS template (`sparql.js:17-23`). The identifier strips it from browsers (`clear_mu_internal_keys.ex:14`). |
| AZ17 Non-widenable governed session | partial | Query text cannot widen the dataset because GRAPH and FROM are stripped (`acl.lisp:256-258`), but headers can (sudo, forged groups from internal callers) |
| AZ18 IdP claim → policy selector | absent | No IdP or OIDC. Groups are derived from session triples written by a login service (not cloned). |
| AZ19 Per-request identity propagation | present | Identifier reissues `mu-session-id` per request (`add_custom_request_headers.ex:14-18`); JS per request via `httpContext` (`sparql.js:31-41`); Python per request but on shared global clients (`helpers.py:130-164`) |
| AZ20 Token propagation and caching across hops | present | `add_custom_request_headers.ex:20-47`, `put_allowed_groups_in_session.ex:8-27`; `acl.lisp:196-212` |
| AZ21 Principal threaded into field-level checks | absent | — |
| AZ22 Caches partitioned by principal | present | mu-cl-resources user-aware hash tables keyed by allowed groups (`caching.lisp:10-13`, `support.lisp:407-475`); dispatcher `Vary: accept, cookie` (`add_vary_header.ex`) |
| AZ23 Trusted-proxy gate with a shared secret | absent | Network trust only. The identifier sanitises the edge, but nothing guards internal callers. |
| AZ24 Authorization errors → 401/403 | partial | The legacy resources check returns 403 (`request-parsing.lisp:164-172`, `call-specification.lisp:5-12`). A write denied by sparql-parser surfaces as 500 (`server.lisp:179-182`); a denied read is silently empty. |
| AZ25 Read masking / redaction | absent | `x>` excludes predicates from a graph; it does not mask values |
| AZ26 Policy-aware explain / statistics | absent | — |
| AZ27 Authorization audit trail | partial | `mu-call-id`, `mu-auth-allowed-groups` on the response (`server.lisp:176,187`), `*log-incoming-requests-p*`; `allowedGroups` and `scope` in deltas (`messenger.lisp:110-115`). `used-groups` is not emitted. |
| AZ28 Authorization-tuple sync from events | n.a. | Groups are evaluated live by SPARQL over the store; there is no separate tuple store to keep in sync |
| AZ29 ACL config generated from the model | absent | Gap noted in round 3 |
| G1 Persistence-free generated domain classes | absent | No codegen |
| G2 Separate generated mapper | absent | — |
| G3 Overridable generator templates | absent | — |
| G4 Per-module generation | absent | `read-domain-file` splits the domain (`domain-parsing.lisp:5`), but nothing is generated |
| G5 IRI-typed fields | partial | `url` and `uri-set` attribute types (README "Defining resources in JSON") |
| G6 Language-tagged string type with round-trip | present | `language-string(-set)` in the domain and JSON (`request-parsing.lisp:53-56`, `query-parsing.lisp:32-37`); fallback `*default-language-import-fallback*` "en" (`settings.lisp:39`) |
| G7 JSON-LD context / frames from the schema | absent | grep `@context\|json-?ld`: no hits |
| G8 Twin projections (classes + context) | absent | — |
| G9 OpenAPI from the schema | partial (external) | `cl-resources-openapi-generator` (mu-cl-resources README "Generators"); not in the clones |
| G10 Route / handler generation per aggregate | partial | Routes are derived at runtime from the domain, not generated as code (`call-specification.lisp:14-504` generic over `base-path`) |
| G11 Hydra ApiDocumentation | absent | — |
| G12 GraphQL schema | absent | grep `graphql`: no hits |
| G13 Per-class filter/sort/include grammar | partial | Derived automatically from attributes and relationships (`response-generation.lisp:40-57,196-328`); no per-slot annotations to enable or restrict |
| G14 Read-model query generation | partial | SELECT and include UNION queries built at runtime from the domain (`response-generation.lisp:59-108`, `included-items.lisp:371`) |
| G15 Response profiles / endpoint hierarchies | absent | Flat `/type`, `/type/id`, `/type/id/rel`, `/type/id/links/rel` |
| G16 Client-side model generation | absent | ember-data models are hand-written (getting-started); `mu-application-generator` is mentioned in the README only |
| G17 Shapes / ontology → schema import | absent | — |
| G18 UML → OWL / SHACL | absent | — |
| G19 Reasoner-based model quality gate | absent | — |
| G20 Inference materialisation artefact | absent | — |
| G21 Generated data-quality SPARQL checks | absent | — |
| G22 Generated RML / YARRRML | absent | — |
| G23 Polymorphic typing via a type designator | partial | The most specific `rdf:type` → JSON:API `type` (README "Inheritance"; `resource-distance`, `resource-model.lisp:266`); no designator slot |
| G24 Enum values as IRIs | absent | No enum type in the attribute types |
| G25 Standalone bindings with pluggable codec | absent | — |
| G26 Inheritance-safe mapping config | present | Subtypes inherit attributes and relationships (README "Inheritance"; `ld-properties` / `all-links` merge supers, `resource-model.lisp:226-265,320-338`) |
| G27 Build-time regeneration discipline | n.a. | No codegen |
| T1 Single-request atomic flush | partial | mu-cl-resources sends one `;`-joined request (`query-execution.lisp:18-30`), but sparql-parser re-splits it (`handle-update-unit.lisp:704-718`) |
| T2 Guarded update / CAS | absent | grep `optimistic`: no feature code |
| T3 Vendor multi-request transactions | absent | — |
| T4 Compensating rollback | absent | grep `rollback`: no hits |
| T5 Read-your-writes in a transaction | absent | — |
| T6 Retry on conflict | absent | Exponential backoff covers network or store errors (`client.lisp:164`), not conflicts |
| T7 Store capability descriptor | absent | — |
| T8 Savepoints | absent | — |
| T9 Idempotent writes / key | absent | grep `idempoten`: no hits |
| T10 Rollback resets cached state | absent | Caches are cleared after writes (`call-implementation.lisp:188-191`); there is no rollback |
| T11 Write-batch size limits | present | `handle-update-unit.lisp:3-7,704-718` |
| E1 Outbox / publish-after-commit | partial | Deltas are emitted after the store write (`handle-update-unit.lisp:704-730`) via an in-memory message bus with retries (`delta/message-bus.lisp`, `messenger.lisp:63-90`). Not transactional: lost on crash. |
| E2 RDF Patch format | absent | grep `rdf.?patch`: no hits |
| E3 Head-moved notification + pull | partial | A falsy `resourceFormat` sends a body-less trigger, after which the consumer re-reads the store (delta-notifier README "false or undefined"; `send-request.js`) |
| E4 Policy-filtered change feeds | partial | Raw deltas carry `allowedGroups`/`scope` (`messenger.lisp:110-115`), but delta-notifier does not filter by them and drops them from v0.0.1 (`send-request.js:7-15`) |
| E5 Ordered, gap-detectable sequence | partial | `sequenceId` per change set (`messenger.lisp:108`) and a sequencer on overlapping quads (`handle-update-unit.lisp:573-590`). No `prev` link; retries may reorder (delta-notifier README "retry" warning). |
| E6 Delta-only virtual graphs | present | `:sparql nil :delta t` (`test/scenario.lisp:159-160`; README `define-graph`) |
| E7 Call-id trail / loop prevention | present | `delta-notifier/app.js:27-30,110-133`; `messenger.lisp:55-57` |
| E8 Coalesced change notifications | partial | `gracePeriod` bundling per session and groups (`bundle-requests.js`) and `foldEffectiveChanges` (`folding.js:8-53`); per time window, not per entity/property |
| E9 Standard notification channels | absent | Custom webhook POST only; grep `websocket\|server-sent\|mercure`: no hits |
| U1 Generated typed client SDK | absent | — |
| U2 Server-state cache keyed by IRI | n.a. | Front end is outside the clones (the ember-data store keys by type + uuid, not IRI) |
| U3 Push-to-cache bridge | absent | Not in the clones |
| U4 Shape-driven forms | absent | — |
| U5 Schema-introspected admin | partial (external, claimed) | `mu-application-generator` "scaffolds a resource editing application" (mu-cl-resources README "Generators"); not in the clones |
| U6 Server validation mapped to fields | absent | `required-field-missing` returns a title only (`call-specification.lisp:107-110`), no JSON:API `source.pointer` |
| U7 Client-side unit of work by graph diff | absent | — |
| U8 Generated mocks | absent | — |
| U9 Capability hints | absent | — |
| U10 Shape-driven search / facet UI | absent | — |
| RAD3 Front-end scaffold from the API description | partial (external, claimed) | `mu-application-generator` (README "Generators") |
| RAD4 Tiered exposure (read-only by default) | absent | Every resource gets full CRUD routes; restriction only through ACL write grants |
| X17 Multi-profile rendering | absent | JSON:API only |
| X18 Atomic multi-operation write with local ids | absent | grep `atomic`: only a code comment |
| X19 Conditional requests (ETag / If-Match) | absent | grep `etag\|if-match`: no hits |
| X20 Cursor pagination | absent | Only `page[number]`/`page[size]` (`response-generation.lisp:28-38`) |
| X21 RDF patch bodies | absent | — |
| X22 Bundled JSON-LD context | absent | — |
| D11 Store error bodies surfaced | absent | Masked as "Could not execute SPARQL query." (`call-specification.lisp:38`) and "Failed to process query." (`server.lisp:179-182`) |
| D12 Per-model exception types | absent | Generic conditions with a resource slot (`error-codes.lisp:7-35`) |
| D13 Model-aware error messages | present | "Could not find property (~A) on resource (~A).", "Access for ~A operation on ~A with id ~A was denied.", "Resource for path (~A) not found" (`call-specification.lisp:9,29,100-103`) |
| S15 Time travel / history | absent | grep `time.?travel\|as-of`: no hits |
| S16 Branching / merging | absent | — |
| S17 Diff-load / sync | absent | Effective-change detection exists (P9), but there is no "make the graph equal to this document" call |
| S18 Bulk-loader path | partial (external) | mu-migrations-service in the default compose (`docker-compose.yml:34-44`); not cloned |
| S19 Commit metadata on every write | partial | Each change set carries `sequenceId`, `origin`, `allowedGroups`, `scope` and the call-id headers (`messenger.lisp:52-60,100-116`), but in the event only, not stored |

**v3 counts (102):** 17 present, 26 partial, 56 absent, 3 n.a. (AZ28, G27, U2).

### (b) Purpose and origin

| Component | Built for / by / context | Design angle | Fits (L0–L6) | Does not fit |
|---|---|---|---|---|
| **mu.semte.ch / semantic.works as a whole** | Building user-facing linked-data web apps fast. By Aad Versteden (madnificent; author in every `.asd` and `package.json`) and colleagues, first at TenForce and later at redpencil.io (sparql-parser's `*file-abbreviation-uri-prefix*` is `services.redpencil.io`, README). Published as "An Ecosystem of User-facing Microservices supported by Semantic Models" (USEWOD 2015, cited on mu.semte.ch/getting-started). Production use in Flemish government apps (lblod "lokaal mandatenbeheer", Kanselarij Kaleidos, rollvolet; sparql-parser README "Existing configurations"). | Microservices that never call each other and integrate through one shared triplestore; Ember single-page front ends; declarative configuration; cross-cutting concerns in proxies around the store | Reference for L3, L4, L6 and the overall topology | As a *library* for an rdf-persistence-based Python stack: it is a runtime platform, not code to import |
| **mu-cl-resources** | Removing "repetitive and boring" CRUD back-end work: "a declarative configuration can get rid of all of this" (README "Why this component?") | Metadata mapping → generic JSON:API for ember-data | L4 (and the L0 format `domain.json`) | L1: no domain objects, no hook for domain rules beyond Lisp hooks |
| **sparql-parser** | A Common Lisp rewrite of mu-authorization (Elixir) (README l.6). It moves authorization out of the microservices "into a layer on top of the SPARQL endpoint" (mu-cl-resources README "Authorization"; blog "On sharing authorization") and adds delta generation. | Transparent SPARQL-protocol PEP + change-data capture; graph-per-token reads, quad dispatch on writes | L3 (PEP), L6 (CDC), L2 (multi-backend replication) | L2 transactions (it breaks request atomicity); OIDC-based identity |
| **delta-notifier** | Fan-out of raw deltas "to interested entities" (README) | Rule-matched webhooks with batching and folding | L6 | Ordered, durable or authorised feeds (no persistence, no policy filter) |
| **mu-identifier** | Session identification at the edge; caching of access groups | Cookie-session proxy that sanitises internal headers | L3 (edge) | OIDC/JWT; in V1/V3/V4 an OIDC-aware gateway (Zitadel + oauth2-proxy/Traefik) does this job |
| **mu-dispatcher** | Routing requests to services | Elixir DSL on Plug | L4 gateway (RAD2) | Any standard reverse proxy covers it; low reuse value |
| **Templates (Python, JS)** | Quick-starting a service inside the stack | Thin: framework + SPARQL client + header forwarding | L1 seam (header protocol) | No persistence layer: the gap rdf-persistence fills |

### (c) Variant fit

V1 Portable Python core · V2 semantic.works-compatible · V3 Fluree · V4 GraphDB · V5 graph-direct reads (CQRS). A = runtime mapper · B = generated mapper and routes · C = generic zero-code service.

| Candidate | V1 | V2 | V3 | V4 | V5 | A | B | C |
|---|---|---|---|---|---|---|---|---|
| JSON:API dialect (mu-cl-resources contract) | supports (one profile of the service) | **enables** (required) | supports | supports | n.a. (writes only) | supports | supports (generated routes) | **enables** (mu-cl-resources is the archetype) |
| `domain.json` format | supports (import) | **enables** | supports | supports | — | supports (LinkML ↔ domain.json converter) | supports | **enables** |
| mu-cl-resources (service) | blocks (Lisp, no domain rules) | supports (side by side with Python services) | blocks (assumes `mu:uuid`, its own graph) | blocks | — | — | — | **enables** (as is) |
| sparql-parser (PEP + CDC) | optional (graph-level PEP in front of any SPARQL store) | **enables** (required) | blocks (duplicates Fluree's native policies; Fluree policies cannot target named graphs) | blocks (splits GraphDB transactions; duplicates GraphDB FGAC) | **enables**: an existing policy-aware SPARQL proxy for the read path (graph-level only) | neutral (ACL-agnostic via X13) | neutral | neutral |
| delta-notifier / `changeSets` format | supports (format for the outbox relay) | **enables** | supports (adapter from Fluree commits) | supports | supports (feeds a read replica) | — | — | — |
| mu-identifier + mu-dispatcher | blocks (no OIDC; use Zitadel + gateway) | **enables** | blocks | blocks | blocks | — | — | — |
| Header protocol (`mu-*`, X13) | supports (one request-context adapter) | **enables** | n.a. (Fluree has its own headers) | n.a. | supports | supports | supports | supports |
| Templates | — | supports (rdf-persistence replaces the Python one) | — | — | — | — | — | — |

**Headline:** the semantic.works *contracts* support every variant and approach C directly. Its *runtime components* are needed only for V2. sparql-parser additionally **enables V5** as a ready, graph-level read proxy, and it **blocks V3/V4** because it would duplicate or degrade their native policies and transactions.

### (d) Corrections to the integrated docs

1. **Trusted headers** (`index.adoc:148-149`, `variants.adoc:32`, `libraries/semantic-works.adoc:79`). The scope must be narrowed: browsers *cannot* inject `mu-auth-*`, `mu-session-id` or `mu-call-id`, because mu-identifier strips and reissues them (`clear_mu_internal_keys.ex:5-15`, `add_custom_request_headers.ex:7-47`). The real risk is **internal callers**: any container, or any service port published past the identifier, can send `mu-auth-sudo` or forged groups to sparql-parser. The open question in `libraries/semantic-works.adoc:79` ("Whether…") is now answered.
2. **`index.adoc:37-38`** "JSON:API (semantic.works dialect, with Atomic Operations)". semantic.works does **not** implement JSON:API Atomic Operations (no code; grep `atomic`). The doc should say Atomic Operations is *our* extension on top of the mu dialect.
3. **`variants.adoc:26-28`** V2 "in front of Virtuoso". sparql-parser talks to any SPARQL 1.1 endpoint or endpoints (`client:*backend*`/`*backends*`, `connection/client.lisp:9-53`). Virtuoso is the default and its result handling is Virtuoso-flavoured (`expand-bindings :virtuoso-p t`), but other stores are not excluded.
4. **`variants.adoc:55`** V5 "Needs a policy-aware SPARQL proxy". sparql-parser *is* one (graph-level, AZ1–AZ3). Worth naming as the existing option, with its DEC-5 failure.
5. **`building-blocks.adoc:61-62`** "chunks of at most 100 quads". These are *heuristics* (`*max-quads-per-query-heuristic*` 100, `*max-query-size-heuristic*` 8000 chars; README: "current implementation will try to query even if over this size"). Better wording: "roughly 100 quads / 8000 characters per request".
6. **mu-dispatcher README** (not in the integrated docs, but cited by them via my round-1 text). `RemoveAcceptEncodingHeader` never fires because it matches the key `"accept_encoding"` (`remove_accept_encoding_header.ex:8`). Claimed, not working.

### (e) Proposed new features (round 4)

| Proposed id | Area | Feature | Evidence |
|---|---|---|---|
| AZ30 | Authorization | **Edge sanitisation of internal security headers**: the gateway deletes client-supplied internal headers (groups, sudo, scope, session, call id) from requests and responses, and reissues the ones it owns from a signed + encrypted session (an allow-list is preferable to the deny-list seen) | `mu-identifier/lib/manipulators/clear_mu_internal_keys.ex:5-15`, `add_custom_request_headers.ex:7-47`, `proxy.ex:23-34` |

## Round 5

Inputs: `BRIEF-round5.md`; taxonomy **v4**; the pages `libraries/semantic-works.adoc` and `variants.adoc` (V2 row).

Absences were confirmed by grep over the eight clones (`*.lisp, *.js, *.py, *.ex`; `.claude/` and `node_modules/` excluded). Terms: `opentelemetry|traceparent`, `saga`, `migration`, `testcontainers`, `redact`, `read-?only`, `did you mean`, `on_commit|after-commit`, `conformsTo`, `mcp`. None matched any feature code; the `read-?only` and `version` hits are unrelated (a sequencer comment, the domain.json `version` key). GitNexus cannot help here: it has no Lisp or Elixir symbols (rounds 1 and 4).

### (a) v4 cross-check

**v4 counts (77):** 1 present, 20 partial, 50 absent, 6 n.a.

| Id | Status | Evidence |
|---|---|---|
| B1 Aggregate declaration in the model | absent | `domain.json` has no root or owned notion (`domain-parsing.lisp:66-96`) |
| B2 Boundary validation at generation | absent | — |
| B3 Whole-aggregate load in one query | absent | `include` is per request and client-chosen (`included-items.lisp:371`), not a boundary |
| B4 Whole-aggregate save with snapshot diff | absent | Per-property replace of the keys sent (`call-implementation.lisp:157-176`) |
| B5 Typed cross-aggregate references | partial | Relationships are `{type, id}` references resolved explicitly through `include` or relationship links (`call-implementation.lisp:931-1026`); there are no aggregates to bound them |
| B6 Aggregates-per-commit policy | absent | — |
| B7 Single conjunctive guarded operation | absent | No guards. The proxy re-splits updates (`handle-update-unit.lisp:704-718`). |
| B8 Inspectable backend-neutral change-set | partial | sparql-parser computes dispatched, effective quad sets as values and renders them both as SPARQL and as a delta (`handle-update-unit.lisp:687-730`). Internal to the proxy; no dry-run API. |
| B9 Domain events via outbox | absent | Deltas are store-level and emitted by the proxy, not domain events |
| B10 Aggregate storage strategy (graph per aggregate) | partial | Graph per *token* (user or organisation) through parameterised graph templates (`acl.lisp:243-247`), decided by policy, not per aggregate |
| B11 Aggregate version kept by the mapper | absent | — |
| B12 After-commit hooks | partial | Resources `after` hooks (`callbacks.lisp:85-90`) run after the call. They are not commit-aware, since there is no transaction. |
| B13 Boundary-aware delete | partial | Delete also removes inbound links declared on other resources (`call-implementation.lisp:876-928`); there is no cascade or refusal |
| B14 Bounded-context partitioning | absent | By design every service shares the whole store (mu.semte.ch/about) |
| B15 No-autoflush contract | n.a. | No session or unit of work |
| B16 Process manager / saga | absent | grep `saga`: no hits |
| PG1 Query AST with pluggable renderers | absent | sparql-parser's AST renders SPARQL only (`sparql-ast/generator.lisp`) |
| PG2 LPG projection config | n.a. | RDF-only platform |
| PG3 Edge-property mapping | absent | Links are plain triples (`call-implementation.lisp:206-210`) |
| PG4 Partition scope used by persistence and authorization | partial | Named graphs serve both storage placement and access in sparql-parser (`acl.lisp:249-263,301`). Graphs only; no other partition kinds. |
| EV1 Migration runner (ordered files, RDF log) | partial (external, not cloned) | `semtech/mu-migrations-service:0.9.0` with `./config/migrations` mounted in the default stack (`mu-project/docker-compose.yml:34-44`). Its behaviour was analysed by angle-evolution, not by me. |
| EV2 Migration integrity | absent (per angle-evolution) | Not verified by me |
| EV3 Schema diff → SPARQL skeletons | absent | — |
| EV4 Down migrations | absent | grep `migration` in the clones: no hits |
| EV5 Object-level data transformation | absent | — |
| EV6 Post-migration validation gate | absent | — |
| EV7 Schema version stamped and checked | absent | `domain.json` `version: "0.1"` is the file-format version, not a data-schema version (`domain-parsing.lisp:56-64`) |
| EV8 Staged bulk load | partial (external, per angle-evolution) | mu-migrations-service; not cloned |
| EV9 Migration rehearsal | absent | — |
| AZ30 Graph-aware enforcement (class resolved in the fact's graph) | partial | The type cache tracks uri–type–graph combinations (`cache/types.lisp:72-90`), and user type providers take `(uri graph)` (`types.lisp:148-149,177-178`). I did not verify whether dispatch always resolves in the quad's own graph rather than a union. |
| AZ31 Effective-ACL inheritance down a hierarchy | absent | Flat graph specifications; no container hierarchy |
| AZ32 Predicate-coverage fast path | absent | — |
| AZ33 Existence-hiding denial (404, withheld counts) | partial | An unreadable resource is outside the `FROM` graphs, so `show` answers 404 (`call-implementation.lisp:339-343`) and counts only cover readable graphs. The legacy resources check answers 403 (`request-parsing.lisp:164-172`). |
| AZ34 Lagging policy configuration | partial | Policy rules are a boot-time Lisp file, so a write cannot change them. Group *membership* is data, though: a caller allowed to write session/role triples can widen its own groups once the identifier cache is cleared (`acl.lisp:66-95`; `add_custom_request_headers.ex:36-37`). |
| AZ35 Policy-filter equivalence test | absent | Only scenario tests (`sparql-parser/test/scenario*.lisp`) |
| AZ36 Edge sanitisation of internal security headers | present | `mu-identifier/lib/manipulators/clear_mu_internal_keys.ex:5-15`, `add_custom_request_headers.ex:7-47`, `proxy.ex:23-34` (deny-list) |
| G28 Contract hygiene | n.a. | No generated contracts in the clones |
| G29 Importer lossiness report | absent | — |
| G30 Cross-path equivalence gate | absent | — |
| G31 Toolchain prerequisites check | absent | — |
| G32 Reasoner profile choice | absent | — |
| G33 Generated-metadata completeness check | partial | `domain.json` parsing fails on a bad cardinality or URI reference (`domain-parsing.lisp:105-110,126-131`), and `predicate`/`class` are required keys. No generation. |
| G34 Conformance link (`dcterms:conformsTo`) | absent | grep `conformsTo`: no hits |
| G35 Generated typed field metamodel | absent | — |
| G36 Generated typed filter / input types | absent | — |
| T12 Read-tracked optimistic commit | absent | — |
| T13 Read-only mode guard | absent | grep `read-?only`: no guard. A `define-graph … :sparql nil` makes a graph delta-only, which is not a service read-only switch. |
| T14 Cross-store unit of work without atomicity | partial | sparql-parser writes every update to all `*backends*` with no cross-store atomicity (`connection/client.lisp:145-170`). This is replication, not a unit of work. |
| S20 Per-named-graph store configuration | partial | Per-graph-specification options `:sparql` and `:delta` (sparql-parser README `define-graph`; `acl/configuration-interface.lisp:51-60`). No SHACL or reasoning per graph. |
| S21 Graphs mirrored to version control | absent | — |
| S22 Store-side shape / uniqueness enforcement | absent | — |
| S23 Ops admin port per store adapter | partial | sparql-parser administration moves long strings to files (`administration/string-files.lisp`). No backup, restore or statistics. |
| X23 Strict JSON-LD processing | n.a. | No JSON-LD |
| X24 MCP projection | absent | grep `mcp`: no hits |
| E10 Subscription channel options | partial | Rule options `resourceFormat`, `gracePeriod`, `ignoreFromSelf`, `foldEffectiveChanges`, `retry`, `retryTimeout` (delta-notifier README; `send-request.js:84-145`). No rate limit, state-on-connect or validity window. |
| I7 Reversible IRI minting | partial | IRI = base + UUID, so the id is the suffix, but mu-cl-resources recovers it by a `mu:uuid` lookup, not by parsing (`caching.lisp:47-110`) |
| I8 Deferred IRI minting | absent | Minted immediately on POST (`call-implementation.lisp:95-98`) |
| P20 Reference-aware flush ordering | absent | No unit of work |
| U11 Framework-neutral UI components | absent | Ember only |
| U12 Ontology instance editor | absent | — |
| U13 Bulk operations in one batch | absent | No JSON:API Atomic or bulk endpoints |
| D14 Stale-write warning | absent | — |
| D15 Parameter redaction in query logs | absent | Full queries are logged (`*query-log-types*`, `LOG_SPARQL_*`); grep `redact`: no hits |
| D16 Formal HTTP/access contract checked in CI | absent | — |
| D17 Inspectable compiled query | partial | Query logging toggles only (`query-execution.lisp:13-16`; `helpers.py:139-140`); no API to inspect a compiled query |
| D18 Explicit-loading sentinel | n.a. | No objects. Over JSON:API, unloaded relationships appear as links, not data. |
| D19 Test kit | absent | — |
| D20 Real-store test fixtures | absent | grep `testcontainers`: no hits |
| D21 Tested documentation | absent | — |
| D22 CURIEs everywhere | partial | CURIEs in `domain.json` (`domain-parsing.lisp:112-118`) and in ACL `define-prefixes` (`acl/prefix.lisp`). Not in the API: ids are UUIDs, `:uri:` filters take full IRIs. |
| D23 "Did you mean" suggestions | absent | `"Could not find property (~A) on resource (~A)."` has no suggestion (`call-specification.lisp:29`) |
| D24 Stable error codes with docs pages | absent | Only generic `status`/`code` such as "403" (`request-parsing.lisp:111-120`) |
| D25 Deterministic order of multi-valued properties | absent | Set-valued attributes are returned in store order |
| D26 Typing regression tests | n.a. | Untyped languages |
| D27 Fault-injection tests | absent | — |
| D28 API contract fuzzing | absent | — |
| D29 Store-port observability (OpenTelemetry) | partial | `mu-call-id` and `mu-call-id-trail` correlation across hops (`add_custom_request_headers.ex:14-18`; `delta-notifier/app.js:27-30`). No spans or timing; grep `opentelemetry\|traceparent`: no hits. |

### (b) Page review: `libraries/semantic-works.adoc` and the V2 row in `variants.adoc`

| # | Page line (quoted) | Problem | Fix |
|---|---|---|---|
| 1 | l.64 "Quads matching no spec are not written and logged as an error." | **Understated.** The default `*unwritten-data-actions* '(:log :error)` *raises*: `maybe-error-on-unwritten-data` runs before the write, so that update operation fails (HTTP 500) (`handle-update-unit.lisp:697-700,740-766`). Earlier operations of the same multi-operation request (l.731-737) may already be written. | "Quads matching no spec make the operation fail with an error (default `:log :error`) before it is written; earlier operations in the same request may already be stored." |
| 2 | l.9 / l.84 "Core components by one dominant author" / "one dominant author" | **Overstated as a measurement.** The clones are shallow (1 commit each), so it rests on the `.asd`/`package.json` `:author` fields. The JS template's last commit is by another contributor (Erika Pauwels). | "Single named author in the package metadata (commit history not analysed; shallow clones)." |
| 3 | l.142 V3 "blocks" / l.143 V4 "blocks" | **Mixed verdict in one cell.** Only sparql-parser (and identifier/dispatcher) block; the contracts support V3 and V4, as the "Why" text itself says. | Fit "partly: contracts support; sparql-parser blocks". |
| 4 | "What to avoid": no line on delta loss | **Missing caveat.** Deltas can be lost. sparql-parser queues them in an in-memory bus (lost on restart; `delta/message-bus.lisp`, `messenger.lisp:63-90`). delta-notifier answers 204 before delivering (`app.js:39-40`), and its `retry` defaults to 0 (`send-request.js:95`). Caches and reactive services then go stale. | Add: "*Lossy deltas:* in-memory queue in sparql-parser, fire-and-forget in delta-notifier (retry 0 by default); no replay. Not suitable as an outbox." |
| 5 | l.179 Sources | mu-identifier and mu-dispatcher are listed under "Documentation" but were cloned and read in round 4 | Move them to "Repositories" with their commits (`4d8978b`, `f85e83b`) |
| 6 | variants.adoc V2 "Ember/WarpDrive frontends work unchanged." | **Missing caveat.** This holds only if the generated service reproduces the dialect exactly, including **UUID JSON:API ids backed by `mu:uuid`** (not IRIs), 0-based `page[number]` and the filter modifiers. | Append: "…provided the service reproduces the mu-cl-resources dialect exactly (UUID ids via `mu:uuid`, 0-based pages, filter modifiers)." |
| 7 | variants.adoc V2 shape (identity) | **Missing caveat.** V2's identity is the identifier's session cookie plus session triples written by a login service. Using Zitadel/OIDC needs a bridge that writes `session:account` triples, or groups injected by a trusted service (`acl.lisp:66-95,175-184`). | Add to costs: "no OIDC: Zitadel needs a login bridge writing session triples". |

I found no other factual errors. The page already carries the round-4 corrections (trusted headers scoped to internal callers, Atomic Operations as our extension, any SPARQL 1.1 backend, 100 quads as a heuristic, the dispatcher accept-encoding bug).

### (c) Final verdict and three things to remember

**Final verdict: compatible.** Honour the contracts (JSON:API dialect, `domain.json`, `changeSets`, `mu-*` headers). Run the runtime only for V2 (sparql-parser optionally as a graph-level PEP). Adopt no code.

**Three things a system architect must remember**
1. **Security sits at two perimeters.** The identifier sanitises the browser edge, but sparql-parser trusts any internal caller's `mu-auth-sudo` and group headers. In a semantic.works deployment, network isolation *is* the authorization boundary.
2. **There is no atomicity and no durable change log.** Updates are re-split into batches by the proxy, and deltas are best-effort (in-memory, retry 0). Anything needing all-or-nothing writes or reliable events needs our own unit of work and outbox, or another variant.
3. **The value is the contract, not the code.** A zero-code JSON:API from a model, policy-driven graph placement and proxy-emitted deltas are the patterns to reproduce in Python/LinkML. Reproducing the mu dialect exactly (UUID ids, `mu:uuid`) is the price of Ember compatibility.

### (d) Not applicable

This report is a library report, not an angle report. Purpose and origin plus variant fit were written in round 4.

### (e) New features

None proposed. The v4 taxonomy covers everything found in this pass; the delta-loss caveat is a property of the existing E1/E5 features, not a new feature.
