# Angle: L3 identity & authorization over RDF/graph data (`angle-authz`)

- Change: `soa-python-rdf-orm` · round 3 · analyst: angle-authz · date: 2026-11-03
- Brief: `BRIEF-round3.md` (DEC-4/5, DEC-8, DEC-10); rubric: `RUBRIC.md`; compared against `semantic-works.md` (sparql-parser, not re-analysed).
- Deep dives (clone + `gitnexus analyze` + docs), all shallow clones as siblings of this repo:

| Clone | Commit | Licence | GitNexus index |
|---|---|---|---|
| `/home/lps/work/repos/fluree-db` (fluree/db) | 807902b (2026-11-02) | **BUSL-1.1** → Apache-2.0 after 4 years per version (`LICENSE:1-51`) | started; see "Not checked" — 1.33 M Rust LOC, evidence from source reading |
| `/home/lps/work/repos/CommunitySolidServer` | 628cc42 (2026-11-02) | MIT | 6,151 nodes / 22,363 edges / 498 clusters / 289 flows |
| `/home/lps/work/repos/jena` (sparse: `jena-fuseki-access` + `DatasetGraphFilteredView`) | c9b6b49 (2026-11-02) | Apache-2.0 | 435 nodes / 952 edges / 27 clusters / 36 flows |
| `/home/lps/work/repos/openfga` | 2dfa5d3 (2026-11-02) | Apache-2.0 | 8,811 nodes / 52,049 edges / 324 clusters / 300 flows |

Layer tags used below: **L2** stores · **L3** identity & authorization · **L4** data service/API.

## 1. Summary

1. **No standard exists for triple-level RDF authorization.** Every store-native mechanism is vendor-specific: GraphDB FGAC, Stardog, AllegroGraph, Virtuoso, Fuseki and Fluree. Only Solid WAC/ACP is a W3C-community spec, and it works at document level (one document = one named graph in CSS's SPARQL backend). **Graph-level is the only portable granularity.** It can be enforced the same way everywhere by restricting the dataset (FROM / FROM NAMED, or a filtered dataset view).
2. **Fluree has changed a lot since the 2024 evaluation.** fluree/db is now a Rust v4 engine that serves SPARQL 1.1 Query/Update and the Graph Store Protocol. It ships an embedded `pip install fluree` package (4.2.5, 2026-11-01), verifies OIDC/JWKS tokens, and runs flake-level (triple-level) **policies stored as RDF data**. Policy conditions can be written in **SPARQL ASK with `$this`/`$identity`/`$value`/`$op`** (SHACL-SPARQL convention). This is the strongest match to DEC-8's preference for a "SPARQL-like data-centric policy language". The catch is the licence: **BUSL-1.1**, which is not OSI open source.
3. **No generic PDP knows RDF.** OpenFGA, SpiceDB, Keto and Permify (Zanzibar/ReBAC) map well to *graph-level* and *resource-level* access when the object is a named graph or a subject IRI. They cannot express triple patterns without one tuple per triple. Cerbos, OPA and Oso can return *list-filter* ASTs, but every one of their adapters targets SQL/ORMs. **A SPARQL adapter for those ASTs exists nowhere.** It would be the one piece Meaningfy builds, and it is a translator, not an authz engine (DEC-8 holds).
4. **IdPs supply identity and coarse roles only.** Zitadel puts project roles in `urn:zitadel:iam:org:project:{projectId}:roles`. Keycloak, Authentik and Ory work the same way, and none of them knows graphs. The claims must feed a PDP, or map to graph tokens (as in semantic.works `MU-AUTH-ALLOWED-GROUPS`), or map to Fluree `f:policyClass`.
5. **For rdf-persistence:** stay ACL-agnostic and expose **one port, `AccessScope`/`PolicyEnforcementPoint`**. It does two jobs: (a) it narrows the dataset (graph set) per request, and (b) it optionally rewrites or filters the query and checks a write. Adapters for the port: *pass-through + header propagation* (sparql-parser, Fluree, GraphDB with OAuth), *FROM-graph injection from a PDP list call* (OpenFGA ListObjects / SpiceDB LookupResources), *post-filter / BatchCheck*.

## 2. Landscape (desk scan, 2026-11-03)

Stars and last push come from `gh api repos/...`. PyPI downloads cover the last month (pypistats). DEC-5 = >200 stars AND a commit in the last 12 months (an org or monorepo passes its packages on). "n.a." = not open source.

### 2.1 Store-native RDF security

| Candidate | Repo / stars / last push / licence / lang | DEC-5 | Granularity | Policy form | Identity source | Layers |
|---|---|---|---|---|---|---|
| **Fluree DB v4** (policies) | fluree/db · 477 · 2026-11-02 · BUSL-1.1 · Rust; PyPI `fluree` 4.2.5 | pass (licence caveat) | **flake (triple)**: `f:onProperty`/`f:onClass`/`f:onSubject` + `f:query`; ledger-level by token scope; *no* per-named-graph targeting | **policy-as-data** (JSON-LD `f:AccessPolicy` stored in the ledger), conditions in JSON-LD / **SPARQL ASK** / Cypher | did:key JWS, Ed25519 JWT, **OIDC/JWKS bearer** (`fluree.identity` / `sub`) → `f:policyClass` | L2 L3 L4 |
| **GraphDB FGAC** | closed source (Ontotext); graphdb.js 40★ | n.a. (commercial, Enterprise) | **quad** (`subject/predicate/object/context`, `*`, `default`, `named`), clear-graph, plugin, system scopes | ordered ACL list, first match wins, default allow; role or `!role`; read/write; allow/deny | local, LDAP, **OpenID + OAuth roles claim (JSONPath `roles_claim`)** | L2 L3 |
| **Stardog** | closed; pystardog 42★ | n.a. | **named graph** read/write (`named-graph:db\graph`); sensitive-property masking (read only) | RBAC grants (admin CLI) | users/roles, Kerberos, OAuth (separate page, not read) | L2 L3 |
| **AllegroGraph** | closed; agraph-python 49★ (MIT client) | n.a. | **triple** filters on s/p/o/g per user or role; allow/disallow; writes to filtered triples error | admin-defined filters (WebView/API) | users/roles; LDAP/OAuth "perhaps" (docs) | L2 L3 |
| **Virtuoso** | openlink/virtuoso-opensource · 977 · 2026-10-26 · GPL-2 (NOASSERTION) · C | pass | **named graph** bitmask (1 read, 2 SPARUL write, 4 sponge, 8 list group) per user + defaults | SQL procedures `DB.DBA.RDF_GRAPH_USER_PERMS_SET` | SQL users + SPARQL_SELECT/UPDATE roles; WebID / OAuth on `/sparql-auth` (not verified) | L2 L3 |
| **Apache Jena Fuseki** (`jena-fuseki-access`) | apache/jena · 1494 · 2026-11-02 · Apache-2.0 · Java | pass | **named graph, read-only datasets** (updates denied on access-controlled datasets) | assembler RDF config (`access:entry (user graphs…)`) | HTTP basic/digest via Jetty; user function pluggable in code | L2 L3 |
| **RDF4J** | eclipse-rdf4j/rdf4j · 423 · 2026-11-03 · BSD-3 · Java | pass | none built in (server security = servlet container) | — | container | L2 |
| **Oxigraph** | oxigraph/oxigraph · 2021 · 2026-11-02 · Apache/MIT · Rust | pass | none | — | — | L2 |
| **QLever** | ad-freiburg/qlever · 935 · 2026-11-02 · Apache-2.0 · C++ | pass | none (access token guards updates only; docs claim, not verified) | — | — | L2 |

### 2.2 Proxy / middleware / web-standard policies

| Candidate | Repo / stars / last push / licence | DEC-5 | Granularity | Policy form | Layers |
|---|---|---|---|---|---|
| semantic.works **sparql-parser** (compare only; see `semantic-works.md`) | mu-semtech/sparql-parser · 5 · 2026-10-23 · MIT (asd) | **fail** (stars) — idea source | graph-per-token; quad → graph dispatch by type/predicate | Lisp config (`supply-allowed-group` SPARQL query + `grant … :to-graph`) | L3 (proxy) L6 |
| **Community Solid Server** (WAC + ACP) | CommunitySolidServer · 610 · 2026-11-02 · MIT · TS | pass | **document/container** (= one named graph in `SparqlDataAccessor`) | **policy-as-data**: `.acl` (WAC) or `.acr` (ACP) RDF documents | L2 L3 L4 |
| Solid WAC spec / ACP lib | solid/web-access-control-spec 131; `@solid/access-control-policy` (solid-contrib, 0★) | spec; lib fails | document | RDF vocab `acl:` / `acp:` | L3 |
| ODRL evaluators | odrl-force/ODRL-Evaluator · 24 · 2026-10-12 · MIT · TS | fail → ideas | usage-control policies over RDF requests | ODRL (RDF) | L3 |
| SolidLab UMA server | SolidLabResearch/user-managed-access · 9 | fail → ideas | UMA + ODRL | ODRL | L3 |
| Other SPARQL authz proxies (GitHub search "sparql authorization / acl / access control proxy") | sparql-guard 1★, lblod/sparql-authorization-wrapper-service 0★, kadaster-labs/secured-sparql-endpoint-subgraph 0★, mu-authorization (Elixir) 3★, mu-query-rewriter 1★, National-Node-Net/rdf-abac 1★ | **all fail** | graph or subgraph rewriting | various | L3 |
| SHACL-based access | **no maintained implementation found**; Fluree borrows the SHACL-SPARQL `$this` convention for policy conditions | — | — | — | — |

### 2.3 Generic authorization engines (PDPs) callable from Python

| Candidate | Repo / stars / last push / licence | DEC-5 | Model | Data in | **List filtering** (the key capability) | Python SDK (PyPI, downloads/month) | Layers |
|---|---|---|---|---|---|---|---|
| **OpenFGA** (CNCF) | openfga/openfga · 6082 · 2026-11-02 · Apache-2.0 · Go | pass | Zanzibar ReBAC + **conditions (CEL, `cel-go v0.31.0`, `go.mod:19`)** | relation tuples (+ contextual tuples) | **ListObjects** (default max 1000, deadline 3 s), StreamedListObjects, ListUsers, BatchCheck | `openfga-sdk` 0.10.5 · 1.48 M | L3 |
| **SpiceDB** (AuthZed) | authzed/spicedb · 7187 · 2026-11-01 · Apache-2.0 · Go | pass | Zanzibar + caveats | relationships | **LookupResources** (cursored; ≥10 k → post-filter with CheckBulk, or Materialize — commercial) | `authzed` 1.25.0 · 1.01 M | L3 |
| **Ory Keto** | ory/keto · 5418 · 2026-09-04 · Apache-2.0 · Go | pass | Zanzibar (OPL) | tuples | list relationships + expand; no ListObjects-equivalent reverse lookup (as of docs read; not verified in code) | `ory-keto-client` · 5 k | L3 |
| **Permify** | Permify/permify · 5968 · 2026-11-02 · **AGPL-3.0** · Go | pass | Zanzibar + ABAC rules | tuples + attributes | LookupEntity / LookupSubject | `permify` 1.7.5 · 17 k | L3 |
| **Cerbos** | cerbos/cerbos · 4643 · 2026-11-02 · Apache-2.0 · Go | pass | RBAC/ABAC policies (YAML + CEL), stateless | **attributes per request** (principal + resource attrs) | **PlanResources** → `ALWAYS_ALLOWED` / `ALWAYS_DENIED` / `CONDITIONAL` + **expression AST**; adapters: SQLAlchemy, Prisma, Drizzle, Mongoose, Convex, ChromaDB | `cerbos` 0.16.1 · 203 k | L3 |
| **OPA / Rego** (CNCF graduated) | open-policy-agent/opa · 12423 · 2026-11-02 · Apache-2.0 · Go | pass | general policy-as-code | input + bundled data | **partial evaluation / Compile API** → SQL, UCAST, Lucene filters | community `opa-python-client` · 31 k (no official SDK) | L3 |
| **Topaz** (Aserto) | aserto-dev/topaz · 1368 · 2026-10-30 · Apache-2.0 · Go | pass | OPA + built-in Zanzibar directory | tuples + Rego | via OPA + directory relation queries | `aserto` · 0.2 k (weak) | L3 |
| **Casbin / pycasbin** | apache/casbin 20477; apache/casbin-pycasbin · 1778 · 2026-10-31 · Apache-2.0 | pass | PERM model (ACL/RBAC/ABAC) in-process; `keyMatch`/`regexMatch` on IRIs | policy rows (adapters: SQL, files) | no query plan; you enumerate permissions (`get_implicit_permissions_for_user`) | `casbin` 2.45 M, `pycasbin` 1.7 M | L3 |
| **Oso** | osohq/oso · 3484 · **archived** ("Legacy Oso open source library") | **fail** (archived) | Polar | — | old data filtering (SQLAlchemy) | `oso` legacy; **`oso-cloud` 2.6.0 · 748 k** = SaaS (local authorization → SQL filter for Postgres/MySQL; beta datastore-agnostic form) | L3 |

### 2.4 Identity providers (OIDC / OAuth2 / JWT)

| Candidate | Repo / stars / last push / licence | DEC-5 | Roles / tenancy model | Python integration | Authz features |
|---|---|---|---|---|---|
| **Zitadel** (requested) | zitadel/zitadel · 15499 · 2026-11-02 · **AGPL-3.0** (server) · Go | pass | instance → **organizations** → **projects** → project roles; **project grants** delegate a project's roles to other orgs; **role assignments** (ex user grants). Token claim `urn:zitadel:iam:org:project:{projectId}:roles` → `{role: {orgId: orgDomain}}`; audience scope `urn:zitadel:iam:org:project:id:{projectId}:aud`; Actions add custom claims | `zitadel-client` 4.1.9 (Apache-2.0, management API) · 23 k/month; token validation = standard OIDC (Authlib / PyJWT + JWKS, or introspection) | RBAC only; no fine-grained PDP (docs) |
| **Keycloak** | keycloak/keycloak · 37663 · 2026-11-03 · Apache-2.0 · Java | pass | realms, clients, realm/client roles, groups, **Organizations** | `python-keycloak` (885★, MIT; last push 2026-02-15) · 4.1 M | **Authorization Services** (resources, scopes, policies, UMA 2.0) — a PDP in its own right, but resource-registry style, no list filtering over external data |
| **Ory Kratos + Hydra** (+ Keto, Oathkeeper) | ory/kratos 13950, ory/hydra 17647 · 2026-07-29 · Apache-2.0 | pass | identities (Kratos) + OAuth2/OIDC server (Hydra); roles live in Keto | REST clients | full Zanzibar via Keto |
| **Authentik** | goauthentik/authentik · 26211 · 2026-11-03 · MIT core + enterprise (NOASSERTION) · Python | pass | users, groups, property mappings → claims | OIDC; Python-native internals | policies for app access only |

Python-side token libraries (glue, all pass DEC-5): `authlib/authlib` 5448★ BSD-3; PyJWT; `fastapi` security utilities.

## 3. Deep dives

### 3.1 Fluree DB v4 — policy engine (L2 L3 L4)

- Repo `/home/lps/work/repos/fluree-db`, commit 807902b, BUSL-1.1 (`LICENSE:1-51`: "may not use the Licensed Work for a Database Service"; Change License Apache-2.0 at the 4th anniversary of each version). About 1.33 M Rust LOC across ~70 crates (`fluree-db-policy` is 4,150 LOC). 15+ contributors; CI in `.github/workflows/ci.yml`.
- Docs read (in repo, these are the published mdBook sources): `docs/security/policy-model.md`, `policy-authorization.md`, `authentication.md`, `policy-in-queries.md` (excerpts), `docs/api/overview.md`, `docs/api/headers.md`, `fluree-db-python/README.md`.

**Summary.** Policies are ordinary JSON-LD nodes (`@type f:AccessPolicy`) stored in the ledger and selected per request by identity → `f:policyClass`. Each policy targets flakes by property, class (with RDFS subclass/subproperty entailment) or subject. It then allows them statically (`f:allow`) or when an existence query (`f:query`) succeeds. That query can be JSON-LD, SPARQL ASK/SELECT or read-only Cypher, with pre-bound `$this`, `$identity`, `$value` and `$op`. Enforcement runs inside the scan operators, so the results are already filtered (no query rewriting). Writes are checked per flake, with create/update/delete verbs and pre/post-state.

**Architecture and implementation (evidence).**
- `fluree-db-policy/src/lib.rs:1-40` states the evaluation semantics: schema bypass on view → candidate collection (property → subject → default) → class filtering → *required subset* → deny-overrides → required = AND gates, otherwise allow-overrides → `default_allow` fallback.
- The combining code is in `fluree-db-policy/src/evaluate.rs:309-398` (sync), `459-522` (async) and `679-770` (detailed, shared tail). Line 361 has the comment "default_allow applies only when no policies apply". The code matches the doc's combining algorithm (`policy-model.md` §Combining algorithm).
- Query-side enforcement: `fluree-db-query/src/policy/enforcer.rs` `QueryPolicyEnforcer` "filters flakes by policy … used by scan operators for per-leaf filtering". It has a `PredicateCoverage` fast path that skips the filter for predicates no policy covers. **The doc comment notes that caching of `f:query` results is a TODO**, so the cost is per flake × condition (also stated in `policy-model.md` §Performance).
- Identity: `fluree-db-credential/src/oidc_jwt.rs:1-33` verifies RS256 JWTs with pre-fetched JWKS (the server fetches the keys). There are also did:key / Ed25519 JWS paths (`jws.rs`, `did.rs`). Claims: `fluree.identity` (overrides `sub`), `fluree.policy.class`, ledger scopes `fluree.ledger.read/write.*` (`authentication.md:76-140`).
- Transport: the headers `fluree-identity`, `fluree-policy-class`, `fluree-policy`, `fluree-policy-values` and `fluree-default-allow` are parsed in `fluree-db-server/src/extract/headers.rs:199-291`. They apply to SPARQL, Cypher and GraphQL as well (`policy-authorization.md`). A **trusted-application credential** (`"fluree.policy": "request"`) lets a backend pick the identity and policy class for each request. This is exactly the shape of an rdf-persistence PEP adapter.
- Python: `fluree-db-python/python/fluree/_fluree.pyi:34-118` shows a `policy=` parameter on `begin/query_sparql/query_jsonld/...`. README §Policy: `ledger.with_policy(identity=…, policy_class=…, policy=…, values=…, default_allow=…)` returns a governed handle. If a query tries to name its own policy, it raises `InvalidRequestError` ("a query passed in from elsewhere can never widen what a governed handle sees").
- SPARQL surface: SPARQL Query + **SPARQL UPDATE** + **W3C Graph Store Protocol** (`docs/api/overview.md:68-96`; `fluree-db-sparql/` parser; `testsuite-sparql/`). The endpoint paths are Fluree's own (`/v1/fluree/query/<ledger>`), not `/sparql`.
- **Named graphs and policy:** "Policies apply per-flake, regardless of which named graph the flake came from … there's no per-graph policy override" (`docs/security/policy-in-queries.md:220`). A policy condition *can* read an ACL graph (`["graph", "ex:acl", …]`, `policy-model.md`). Graph-level isolation therefore comes from **ledger scopes** (one ledger per tenant) or from a condition that reads a graph-membership ACL. It is **not** a native `f:onGraph` (grep for `onGraph`/`on_graph` in `fluree-db-policy/src` and `docs/security` finds nothing).

**Patterns.** Policy-as-data (RDF policies, versioned, time-travel-auditable); PEP = query/scan operator (store-native); PIP = the ledger itself (conditions query the data); PDP = `PolicyContext`; combining algorithm = XACML-like (required = deny-unless-permit gate, others = permit-overrides); trusted subsystem / delegated selection (app credential).

**Docs vs code.** The combining semantics are confirmed in `evaluate.rs`. The OIDC/JWKS path is confirmed in `oidc_jwt.rs`. Python `policy=` is confirmed in `.pyi`. The SPARQL `f:query` language is documented; the policy wire types are in `fluree-db-policy/src/wire.rs` (601 LOC), but the SPARQL-condition lowering was **not traced in code**. "f:query result caching" is documented as a cost concern and marked TODO in code. The Fluree 2024 evaluation's "v3 closed-mode / policy docs missing" no longer holds: v4 has a full `docs/security/` (≈4,000 lines).

**Scores (authz reading of the rubric).**

| # | Score | Justification | Evidence |
|---|---|---|---|
| C1 coverage | 5 | Triple-level read + write, verbs, value/op gates, pre/post state, RDFS-aware targeting, required gates, default-deny, cross-ledger policy source | `policy-model.md`; `evaluate.rs:309-770` |
| C2 patterns | 5 | Clean PDP/PEP split, policy-as-data, documented combining algorithm, fail-closed on unparseable or ambiguous policy | `lib.rs:1-40`; `policy-model.md` "fails closed" |
| C3 dev friendliness | 4 | Typed Python stubs, governed-handle API, a cookbook; Rust-heavy internals | `_fluree.pyi`; README §Policy |
| C4 adoption | 3 | Embedded Python wheel or server; but you adopt a whole database | `fluree-db-python/README.md` |
| C5 mature foundations | 3 | Its own engine (Rust), its own SPARQL parser; uses jsonwebtoken | `fluree-db-sparql/`, `oidc_jwt.rs` |
| C6 data-centric fit | 5 | Policies are RDF in the same graph; conditions in SPARQL ASK; identity is an RDF node | `policy-model.md` §Stored policies |
| C7 SPARQL portability | 2 | Policy semantics are Fluree-only; SPARQL/GSP are present but on Fluree paths, and policy selection goes through proprietary headers | `api/headers.md`, `extract/headers.rs:289-291` |
| C9 composability | 3 | OIDC/JWKS, JSON-LD, SPARQL, GSP: yes. Policy vocabulary `f:` is proprietary and BUSL | `authentication.md:57-74`; `LICENSE` |
| C10 operability | 3 | Single binary or embedded; per-flake `f:query` cost; fast-moving v4 (Python wheel "Development Status :: 3 - Alpha") | `pyproject.toml`; `enforcer.rs` TODO |
| C8 health | 4 | Very active (push 2026-11-02), CI, test suites; 15 contributors; one company | gh api; `.github/workflows` |

**Reuse verdict: integrate (as one store option) + borrow ideas.** If Meaningfy accepts BUSL (fine for internal/project use; not fine for offering Fluree "as a Database Service"), Fluree is the only *off-the-shelf* triple-level, data-centric, SPARQL-conditioned policy engine with an OIDC path and a Python binding. **Borrow** in all cases: the policy vocabulary shape (`onProperty/onClass/onSubject` + SPARQL ASK condition with `$this/$identity/$value/$op`), the combining algorithm, governed handles that cannot be widened, and default-deny.

### 3.2 Community Solid Server — WAC / ACP (L2 L3 L4)

- Repo `/home/lps/work/repos/CommunitySolidServer`, 628cc42, MIT, 49+ contributors. GitNexus: 6,151 nodes / 289 flows.
- Docs: Solid WAC spec (solidproject.org/TR/wac), ACP spec (solidproject.org/TR/acp), code docstrings.

**Summary.** Authorization is a chain of `PermissionReader`s. GitNexus reports `PermissionReader` as an interface with **8 implementations** (WebAcl, Acp, Owner, ParentContainer, PathBased, AllStatic, AuthAuxiliary, Union). They feed a `PermissionBasedAuthorizer` called from `AuthorizingHttpHandler` (`src/server/AuthorizingHttpHandler.ts:50`). Policies are RDF documents: `.acl` (WAC) and `.acr` (ACP).

**Implementation evidence.**
- `src/authorization/WebAclReader.ts`: the mode map `acl:Read→read`, `acl:Write→append+write`, `acl:Append`, `acl:Control`. `getAclRecursive` follows the WAC "effective ACL resource" algorithm (walks up containers). `determinePermissions` iterates `acl:Authorization` subjects and delegates to `AccessChecker`s (`access/AgentAccessChecker.ts`, `AgentClassAccessChecker.ts`, `AgentGroupAccessChecker.ts`).
- `src/authorization/AcpReader.ts:39-160`: collects effective policies from ACRs and calls `allowAccessModes(policies, context)` from `@solid/access-control-policy` (`package.json:80`).
- Write-mode derivation per operation: `permissions/SparqlUpdateModesExtractor.ts`, `N3PatchModesExtractor.ts`, `CreateModesExtractor.ts`, `DeleteParentExtractor.ts`. **SPARQL UPDATE is accepted only as a PATCH on one document.** There is no dataset-wide SPARQL query endpoint.
- Graph mapping: `src/storage/accessors/SparqlDataAccessor.ts:47-225`. Each resource is stored as **one named graph** (`GRAPH <resource>`, metadata in `meta:<resource>`). So in a SPARQL backend, WAC/ACP = **graph-level ACL with policies as RDF**.
- Identity: Solid-OIDC (DPoP-bound tokens; `@solid/access-token-verifier`, `package.json:81`). The agent is a WebID.

**Scores.** C1 3 (document-level only, read/append/write/control; no triple-level, no query-wide filtering). C2 5 (composable reader chain, DI via Components.js). C3 3 (heavy Components.js config). C4 2 (a whole LDP server). C5 4 (N3.js, sparqljs, standard libs). C6 4 (policies as RDF data). C7 2 (LDP/Solid protocol, not SPARQL protocol; SPARQL backend optional). C9 4 (W3C/Solid standards, OIDC). C10 3. C8 4 (13 authz unit-test files in `test/unit/authorization`, CI, active).

**Reuse verdict: borrow ideas.** Use the WAC/ACP vocabularies as a candidate **standard RDF policy-as-data format for graph-level grants** (agent / agentClass / agentGroup → mode on a graph IRI, inherited through containers). Use the reader-chain composition (union of permission readers) as the shape of an rdf-persistence PEP. Do not adopt CSS itself: it is a resource server, not a SPARQL dataset ACL.

### 3.3 Apache Jena Fuseki — `jena-fuseki-access` (L2 L3)

- Sparse clone `/home/lps/work/repos/jena`, c9b6b49, Apache-2.0. Module ~1,775 LOC.
- Docs: https://jena.apache.org/documentation/fuseki2/fuseki-data-access-control.html

**Implementation evidence.**
- `SecurityContextView.java`: a context is a set of visible graph names + a default-graph flag. `createQueryExec` puts a quad-level `GraphFilter` into the query context on TDB1/TDB2 (`GraphFilterTDB2.java:38-62`, a filter on NodeIds at index level). Otherwise it wraps the dataset in `DataAccessCtl.filteredDataset` → `DatasetGraphFilteredView` (jena-arq). GitNexus query "filter quads by visible graphs" returns `DatasetGraphFilteredView.filter`, `SecurityContext.visibleGraphs`, `AssemblerSecurityRegistry`.
- `AccessCtl_DenyUpdate.java`: updates on access-controlled datasets are rejected. The docs say: "Graph level access control only applies to read-only datasets."
- **User resolution is pluggable in code**: `DataAccessCtl.java:60-66` `Function<HttpAction,String> requestUserServlet` / `paramUserServlet`. **The docs do not mention this**; they cover only Jetty/password-file auth. A JWT-verifying servlet filter + a custom function would connect it to OIDC. That would be custom Java, though: nothing off-the-shelf does it.
- Policy config is RDF (assembler): `VocabSecurity.java:39-44` (`access:dataset`, `access:registry`, `access:entry`, `access:user`, `access:graphs`).

**Scores.** C1 2 (read-only, graph-level, static per-user list). C2 4 (filtered dataset view = clean decorator; index-level filter). C3 2. C4 3 (config only). C5 5. C6 3 (policy in RDF assembler, but static). C7 4 (standard SPARQL protocol). C9 3 (no OIDC out of the box). C10 4. C8 5.

**Reuse verdict: integrate (as a read-side graph-level option) + borrow the dataset-view idea.** It is the clearest open-source example of "authorization = restrict the dataset to the visible graphs", applied below the query engine, so `GRAPH ?g` cannot leak. rdf-persistence's in-process (rdflib/pyoxigraph) adapter can copy this with a filtered `Dataset` view.

### 3.4 OpenFGA — Zanzibar PDP with ListObjects (L3)

- Repo `/home/lps/work/repos/openfga`, 2dfa5d3, Apache-2.0, CNCF, 100+ contributors. GitNexus: 8,811 nodes / 300 flows.
- Docs: https://openfga.dev/docs/interacting/relationship-queries

**Implementation evidence.**
- `pkg/server/commands/list_objects.go:63-246`: `listObjectsDeadline` / `listObjectsMaxResults` defaults from `serverconfig`. Reverse expansion runs in `pkg/server/commands/reverseexpand/reverse_expand_weighted.go` (`buildUserFilter` l.457-503, `ReverseExpandQuery.buildFilteredIterator`; GitNexus query "ListObjects reverse expand"). The internal channel buffer is sized from `min(maxResults,1000)` (`list_objects.go:355`).
- Conditions (ABAC on top of ReBAC): `internal/condition/` + `cel-go` (`go.mod:19`).
- Storage: `pkg/storage/{memory,postgres,mysql,sqlite}`, a tuple store separate from the RDF store. **Tuples must be kept in sync with the graph** (a dual-write / CDC concern that links to L6 deltas).

**Mapping to RDF.** The type model fits graph-level and resource-level directly:
```
type user
type group
  relations define member: [user, group#member]
type graph                                   # one named graph
  relations
    define owner:  [user, group#member]
    define reader: [user, group#member] or owner
    define writer: [user, group#member] or owner
type resource                                # a subject IRI (aggregate root)
  relations
    define graph:  [graph]
    define reader: [user] or reader from graph
```
`ListObjects(user:alice, reader, graph)` → the graph IRIs to inject as `FROM`/`FROM NAMED` (or `VALUES ?g`). Triple-level (predicate) rules are **not** a good fit. They need a tuple per (subject, predicate) or CEL conditions over attributes that are passed in per check.

**Scores.** C1 4 (check/batch/list/listUsers/conditions; no triple patterns). C2 5. C3 4 (DSL, playground, Python SDK). C4 3 (another service + DB). C5 n.a. C6 2 (tuples ≠ RDF; must be projected from the graph). C7 n.a. (store-agnostic: works with any SPARQL store). C9 4 (OIDC claims → `user:` ids; AuthZEN interop in the ecosystem, not verified). C10 4. C8 5.

**Reuse verdict: integrate** as the graph/resource-level PDP for store-agnostic variants. Pair it with a "graph-scope" PEP adapter in rdf-persistence. Keep tuples in sync from rdf-persistence domain events (L6).

### 3.5 Desk-only notes (no clone)

- **GraphDB FGAC** (10.6+/11.x docs, Enterprise): an ordered rule list with scope `statement` (s/p/o/context with `*`, `default`, `named`), `clear_graph`, `plugin`, `system`; role / `!role`; read/write; allow/deny; first match wins, **default allow**; admins and repository managers bypass; no bnodes; implicit `CLEAR ALL` deny. Roles come from **OpenID + OAuth `roles_claim` (JSONPath)**, which plugs straight into Zitadel/Keycloak roles (`CUSTOM_` prefix unless `bare_custom_roles`). rdflib's `rdflib.contrib.graphdb` client lists FGAC rule management (per the rdflib API docs; not verified in code). It is the strongest *commercial* store-native triple-level option behind standard SPARQL.
- **Stardog:** named-graph read/write grants. Unreadable graphs are silently dropped from the dataset; writes to unauthorized graphs fail all-or-nothing; the filter is fixed per connection/transaction. Sensitive-property masking applies to reads only.
- **AllegroGraph:** per-user/role s/p/o/g allow/disallow filters, HTTP clients only, applied to new sessions. Filtered triples "appear as if they weren't in the store"; writes to them error.
- **Virtuoso:** per-user graph bitmask + default perms + graph groups. It needs SQL roles SPARQL_SELECT/UPDATE. The identity is a Virtuoso SQL user, so an IdP must be mapped to DB users (no claim mapping found in docs).
- **Cerbos PlanResources:** the most useful output for us. It returns `ALWAYS_ALLOWED` / `ALWAYS_DENIED` / `CONDITIONAL` + an operator/operand AST over `request.resource.attr.*`. A **SPARQL adapter** (AST → `FILTER`/triple patterns over the resource's properties) does not exist; the official adapters are SQL/ORM/Mongo/vector-DB only.
- **OPA data filtering:** partial evaluation with `compile: unknowns` → SQL / UCAST / Lucene. UCAST is a generic condition AST and would be the input to a SPARQL translator. There is no official Python SDK.
- **Oso:** the open-source library is archived. Oso Cloud (SaaS) has "local authorization" → SQL for Postgres/MySQL. **Avoid** (SaaS dependency, no SPARQL).
- **Casbin/pycasbin:** in-process, extremely popular. A `keyMatch2`/`regexMatch` over graph IRIs gives cheap graph-level RBAC (`p, role:editor, https://data/graph/tenant-a/*, write`). There is no query plan, but enumerating the user's allowed graph patterns is trivial. **Good minimal option** when no separate PDP service is wanted.
- **Keycloak Authorization Services:** a PDP with resource/scope/policy and UMA. Usable for coarse resource-level checks; it duplicates what a Zanzibar engine does and has no list-filter over external data.

## 4. Patterns catalogue (L3 over RDF)

| # | Pattern | Where it lives (evidence) | Granularity | Leak-safety | Cost / notes |
|---|---|---|---|---|---|
| P-A | **Store-native PEP** (store filters by authenticated user) | Fluree `enforcer.rs`; GraphDB FGAC; AllegroGraph filters; Stardog NG security; Jena `SecurityContextView`; Virtuoso perms | graph → triple | highest (below the query engine: `GRAPH ?g`, property paths and aggregates cannot leak) | vendor lock-in of the *policy*; identity must reach the store (OIDC passthrough, or a trusted app credential + per-request identity header) |
| P-B | **SPARQL-rewriting proxy** (parse → replace dataset / inject FROM / dispatch quads) | semantic.works sparql-parser `acl.lisp:249-263, 301`; sparql-guard (1★) | graph | high for reads if every GRAPH clause is stripped/re-scoped; writes need quad dispatch | one more hop; a full SPARQL parser is required (sparql-parser re-implements it in Lisp); deltas are a by-product |
| P-C | **Repository-level scope injection (in-process PEP)** | the proposal for rdf-persistence; same idea as Jena `DatasetGraphFilteredView` | graph (resource with a PDP check) | good **only if** every generated query goes through the repository and the scope is applied as dataset / `VALUES ?g` (not string concatenation) | cheapest; ACL-agnostic library + pluggable PEP adapter |
| P-D | **Pre-filter via PDP list call** (ListObjects / LookupResources / Casbin enumeration) → `FROM` / `VALUES` | OpenFGA `list_objects.go`; SpiceDB LookupResources | graph / resource | good | ListObjects caps (default 1000 / 3 s); fine for graphs-per-tenant (few), poor for millions of resources |
| P-E | **Query-plan / partial-evaluation translation** (Cerbos plan AST, OPA UCAST → SPARQL FILTER) | Cerbos PlanResources; OPA Compile API | attribute-level (resource properties) | good if the translator is exact | **SPARQL translator does not exist** → the one thing to build (small, testable) |
| P-F | **Post-filter / BatchCheck** | OpenFGA BatchCheck; SpiceDB CheckBulk | resource | safe, but leaks counts / breaks pagination | use after a broad query, for ≥10 k candidates (SpiceDB guidance) |
| P-G | **Graph-per-tenant (or per-ACL-domain)** | Fluree ledger scopes; sparql-parser `define-graph` per org; CSS doc = graph | graph | simple, portable | all stores support it; inference/union graphs need care (Stardog: schema graphs bypass) |
| P-H | **Triple-level policies** (property/class/subject targeting + condition) | Fluree `f:onProperty/onClass/onSubject` + `f:query`; GraphDB statement scope; AllegroGraph filters | triple | store-native only | no portable equivalent; emulate with **predicate allow-lists per role in the mapper** (projection) for reads only |
| P-I | **Policy-as-data (RDF)** | Fluree `f:AccessPolicy`; Solid WAC/ACP; Jena assembler; ODRL | any | — | versionable, queryable, auditable; fits model-driven generation (LinkML could emit policy nodes) |
| P-J | **Policy-as-code** | Cerbos YAML, Rego, OpenFGA DSL, Casbin conf | any | — | mature tooling, tests, CI; foreign to the RDF model |
| P-K | **Header-propagated security context** | semantic.works `MU-AUTH-ALLOWED-GROUPS`/`USED-GROUPS`; Fluree `fluree-identity`/`fluree-policy-class`; Fluree trusted app credential | — | — | rdf-persistence must forward these opaquely (taxonomy X13) |
| P-L | **Governed handle (non-widenable scope)** | Fluree Python `ledger.with_policy(...)` + `InvalidRequestError` when a query names its own policy | — | prevents privilege widening by injected query text | copy into the rdf-persistence session/UoW API |
| P-M | **Identity → policy selector mapping** | Zitadel roles claim → GraphDB `roles_claim` / Fluree `f:policyClass` / OpenFGA `group#member` tuples | — | — | always a small mapping function at the API edge (FastAPI dependency) |

**Query rewriting vs post-filtering.** Rewriting (P-B/C/D/E) is required for correct pagination and counts. Post-filtering (P-F) is a fallback only. The store-native approach (P-A) avoids both and is the safest for arbitrary user SPARQL. **Rule: if end users or the UI can send free SPARQL (MWBv2 "near-direct DB" idea), the PEP MUST be P-A or P-B.** P-C/D/E are safe only for queries that rdf-persistence generates itself.

## 5. How it plugs into MWBv2 and an ACL-agnostic rdf-persistence

MWBv2 chain: UML/model2owl → LinkML → generated Python backend (FastAPI, cosmic-python) → data service → JS UI (JSON-LD).

- **Identity (all variants):** IdP (Zitadel) issues OIDC tokens. A FastAPI dependency validates the JWT (Authlib/PyJWT + JWKS) and builds a `Principal(sub, org, roles, raw_claims)`.
- **rdf-persistence port (proposal, ACL-agnostic):**
  - `AccessScope` (value object): `readable_graphs | None`, `writable_graphs | None`, `forward_headers: Mapping[str,str]`, `principal_ref`. `None` means "let the store/proxy decide" (taxonomy A2).
  - `PolicyEnforcementPoint` (port), with two methods:
    - `scope_for(principal, action, aggregate_type) -> AccessScope` (pre-query);
    - `authorize_write(principal, changeset) -> None | raise` (pre-commit, at the UoW).
  - Adapters:
    - `PassThroughPEP` (headers only: sparql-parser, Fluree app credential, GraphDB OAuth);
    - `GraphListPEP(pdp)` (OpenFGA ListObjects / SpiceDB LookupResources / Casbin enumeration → FROM graphs);
    - later `PlanPEP(cerbos|opa)` (AST → SPARQL FILTER).
  - The SPARQL adapter applies `AccessScope` structurally (dataset clause / `VALUES ?g`), never by string splicing. The UoW calls `authorize_write` with the computed delta (it can be reused by the L6 delta format X12).
- **The LinkML model can carry authz annotations** (e.g. `annotations: {acl_graph_template: ..., sensitive: true}`) that the generator turns into (a) graph placement (taxonomy P12), (b) OpenFGA/Cerbos/Fluree policy artefacts, and (c) the predicate projections per role. This is generation of *configuration* for an existing engine, not a new engine (DEC-8 holds).

## 6. Recommended coherent stacks (for the architecture variants, DEC-10)

| Stack | IdP | PDP | PEP placement | Store | Granularity | When |
|---|---|---|---|---|---|---|
| **S1 — Fluree-native, data-centric** | Zitadel (OIDC/JWKS) | Fluree policy engine (policies as RDF, SPARQL ASK conditions) | store-native (P-A); backend holds a Fluree **trusted application credential** and sends `fluree-identity` + `fluree-policy-class` from Zitadel roles per request; or embedded `fluree` Python with `with_policy(...)` | Fluree v4 | **triple** | Strongest fit to DEC-8 "SPARQL-like data-centric policies" and to MWBv2's original Fluree choice; safe for free SPARQL from the UI. **Risks:** BUSL-1.1, single vendor, policy vocabulary lock-in, per-flake condition cost |
| **S2 — Open-standard store + Zanzibar PDP** | Zitadel | OpenFGA (or SpiceDB) | in-process PEP in rdf-persistence (P-C + P-D): ListObjects → graph scope; BatchCheck for item-level; tuples synced from domain events | any SPARQL 1.1 store (Fuseki/TDB2, Oxigraph, Virtuoso, GraphDB Free) | graph + resource | Vendor-neutral, all Apache-2.0, CNCF; fits graph-per-tenant / graph-per-dataset. Not safe for free UI SPARQL unless combined with S3's proxy; no triple-level |
| **S3 — semantic.works-style proxy** | Zitadel → claims mapped to allowed groups | sparql-parser (graph groups via SPARQL `supply-allowed-group`) | SPARQL-rewriting proxy (P-B); rdf-persistence = header-transparent client (`PassThroughPEP`) | Virtuoso (or any SPARQL 1.1 store) | graph (+ predicate exclusion) | Reuses a production-proven reference architecture with deltas (L6); safe for free SPARQL. **Risks:** sparql-parser fails DEC-5 (5★, single author, Lisp), so it is an idea or a pinned black box, not a dependency |
| (S2′ — commercial triple-level) | Zitadel → GraphDB `roles_claim` | GraphDB FGAC | store-native | GraphDB Enterprise | triple (quad) | When a client already licenses GraphDB; standard SPARQL protocol kept, policies in GraphDB's ACL |

Minimal option inside S2: **pycasbin** instead of OpenFGA (no extra service; IRI pattern matching for graph-level RBAC).

## 7. Feature inventory (existing taxonomy ids, for this angle)

| Id | Status in the landscape | Evidence |
|---|---|---|
| A1 Authorization / ACL hooks | covered by every engine above; **for rdf-persistence: a port + adapters, not hooks** | §5 |
| A2 Auth-proxy compatibility | required by S1 (Fluree headers), S3 (sparql-parser), S2′ | `policy-authorization.md`; `semantic-works.md` |
| A3 Field-level access modes | store-native in Fluree (`f:onProperty`, `$value` gates), GraphDB (statement scope with predicate), Stardog (masking); emulable by role projections | §3.1, §3.5 |
| X13 Request-context propagation | Fluree `fluree-*` headers; sparql-parser `MU-*` headers | `extract/headers.rs:289-291` |
| P12 Policy-driven graph placement | sparql-parser only; Fluree has no graph-level placement policy | `semantic-works.md`; `policy-in-queries.md:220` |

### Proposed new features (area prefix **AZ**)

| Id | Area | Feature | Seen in |
|---|---|---|---|
| AZ1 | Authz | **Access-scope port**: per-request dataset narrowing (readable/writable graph sets) applied structurally to every generated query/update | Jena `SecurityContextView`; Stardog NG filter; proposal §5 |
| AZ2 | Authz | **Write authorization on the changeset** (UoW computes delta → PEP authorizes before commit; verbs create/update/delete; pre/post state) | Fluree `allow_modify_flake_*`, `f:queryState`; CSS `*ModesExtractor` |
| AZ3 | Authz | **Triple-level policy targeting** (by property / class with RDFS entailment / subject) | Fluree `f:onProperty/onClass/onSubject`; GraphDB statement scope; AllegroGraph |
| AZ4 | Authz | **SPARQL-condition policies** with pre-bound `$this/$identity/$value/$op` | Fluree `f:query` (`f:sparql` datatype) |
| AZ5 | Authz | **Policy-as-data**: policies stored, versioned and queried as RDF in the graph | Fluree, Solid WAC/ACP, Jena assembler |
| AZ6 | Authz | **List-filter integration**: PDP list/plan call → SPARQL dataset/FILTER (ListObjects, LookupResources, Cerbos plan AST, OPA UCAST) | OpenFGA, SpiceDB, Cerbos, OPA |
| AZ7 | Authz | **Combining algorithm & default-deny** (required gates, deny-overrides, allow-overrides, default-allow switch) | Fluree `evaluate.rs`; GraphDB first-match default-allow |
| AZ8 | Authz | **Non-widenable governed session** (scope bound to the handle; query text cannot change it) | Fluree Python `with_policy` + `InvalidRequestError` |
| AZ9 | Authz | **IdP claim → policy selector mapping** (roles/orgs → graph groups / policy classes / tuples) | Zitadel roles claim; GraphDB `roles_claim`; Fluree `f:policyClass` |
| AZ10 | Authz | **Authz-tuple sync from domain events** (keep ReBAC tuples consistent with RDF writes) | OpenFGA/SpiceDB + L6 deltas |
| AZ11 | Authz | **Read masking / redaction** of sensitive properties (vs hiding) | Stardog sensitive properties |
| AZ12 | Authz | **Policy-aware explain/statistics hiding** (no cardinality leak to scoped callers) | Fluree `policy-authorization.md` §explain |
| AZ13 | Authz | **Authz decision audit trail** (call id, used groups / policies on response) | Cerbos `cerbosCallId`; sparql-parser `MU-AUTH-USED-GROUPS` |

## 8. Reuse shortlist

- **Adopt:** Zitadel as the IdP (AGPL server, run as a service; Apache-2.0 Python client) with standard OIDC validation in FastAPI (Authlib / PyJWT). Keycloak is the fallback when the AGPL is unwanted.
- **Integrate (per variant):** Fluree v4 policy engine (S1); OpenFGA, with SpiceDB as the alternative (S2); pycasbin as the minimal in-process PDP (S2-lite); GraphDB FGAC (S2′); Jena `jena-fuseki-access` for read-only graph-level publishing.
- **Borrow ideas:** sparql-parser (proxy, graph groups, used-groups header); Solid WAC/ACP vocabularies (graph-level policy-as-data); Fluree's policy vocabulary, combining algorithm and governed handle; Cerbos/OPA plan-AST → SPARQL translation (the only new code: a translator, not an engine).
- **Avoid:** Oso (archived OSS / SaaS), any sub-200★ SPARQL authz proxy as a dependency, rolling our own policy language.

## 9. Open questions

1. Is **BUSL-1.1** acceptable for Meaningfy deliveries (internal and client-hosted is fine; "Database Service" offerings are not)? This decides S1.
2. Will the UI send **free SPARQL** (MWBv2 "near-direct DB through a proxy")? If yes, only store-native (S1/S2′) or proxy (S3) PEPs are safe; S2 needs a proxy in front.
3. Is the required granularity **graph-per-tenant/dataset** (portable everywhere) or truly **triple-level** (store-specific only)?
4. Should policies be **generated from the LinkML model** (annotations → Fluree policies / OpenFGA model / Cerbos policies)? That would be an L0↔L3 feature.
5. Is Zitadel's AGPL acceptable as a deployed service, or should Keycloak be the default IdP?
6. Is a Cerbos-plan or OPA-UCAST → SPARQL translator worth building, or is P-D (graph lists) enough?

## Not checked

- The Fluree GitNexus index did not finish within this session (1.33 M LOC). Fluree evidence comes from source reading and the in-repo docs. The SPARQL `f:query` lowering and the `f:query` result caching were not traced in code.
- Closed stores (GraphDB, Stardog, AllegroGraph) are covered from docs only. Virtuoso OAuth/WebID SPARQL auth was not verified. The Keto reverse-lookup capability, Permify details and the Topaz SDK were not verified in code.
- No candidate code was installed or run (per brief). Fluree JWT authz (the open action from the 2024 evaluation) remains untested.

## Round 4

Brief: `BRIEF-round4.md`. Taxonomy: `feature-taxonomy.adoc` **v3**. The Fluree GitNexus index finished and is registered as repo **`db`** (2,620 files, 84,750 symbols, 248,780 edges; `gitnexus list`). It was used for the Fluree confirmations below.

### R4.0 Fluree code claims re-checked with GitNexus (index `db`)

| Round-3 claim | Verdict | Evidence |
|---|---|---|
| Read enforcement inside scan operators | **confirmed** | `QueryPolicyEnforcer::filter_flakes_for_graph` (`fluree-db-query/src/policy/enforcer.rs:104`) is called from the binary index scan, `fluree-db-query/src/binary_scan.rs:1082`. The predicate fast path is `classify_view_predicate`, called from `fast_path_common.rs:3982`. Cypher over the graph `CALLS` edges also finds it in `fluree-db-api/src/format/hydration.rs` (`filter_flakes_by_policy`), `block_fetch.rs` (`apply_policy_filter`) and `graph_commit_builder.rs`. History, commit contents and JSON-LD hydration are filtered too. |
| Write enforcement per flake at staging | **confirmed** (new location) | `fluree-db-transact/src/stage.rs:2861` `enforce_modify_policy_per_flake` → `allow_modify_flake_write_async_detailed` (GitNexus `CALLS`). `hidden_restatements` (same file) uses `allow_flake_for_graph`. |
| Combining algorithm (required = AND gate, allow-overrides, default-allow only when no policy applies) | **confirmed** | `evaluate.rs:309-770`. GitNexus finds the order-independence and fail-closed tests: `targeted_query_policies_are_order_independent`, `failing_targeted_query_blocks_default_fallthrough`, `test_policy_context_deny_overrides_allow`, `schema_flakes_bypass_view_policy_only` |
| SPARQL `f:query` conditions | **confirmed** (round 3: "not traced") | `PolicyQueryLanguage::{Sparql,Cypher}` in `fluree-db-policy/src/types.rs:17-44`; dispatch at `fluree-db-query/src/policy/executor.rs:224-225`; `evaluate_sparql` at l.459-465 (SPARQL support is registered by a higher layer: `lang_support::register_sparql_support`); `$this` ↔ `?$this` name mapping at l.115-121 |
| `f:query` result caching is a TODO | **confirmed** | `enforcer.rs:37-44` ("TODO: Add PolicyQueryCache"). Subject-class lookups *are* cached (`get_cached_subject_classes`, l.130-133). |
| No per-named-graph policy targeting | **confirmed, with a nuance** | Enforcement is graph-aware: `filter_flakes_for_graph(…, g_id, …)` resolves classes in the flake's graph. Targeting has no graph predicate: no `onGraph` in `fluree-db-policy/src`; the docs say "no per-graph policy override" (`policy-in-queries.md:220`). |
| OpenFGA ListObjects defaults 1000 / 3 s | **confirmed** | `openfga/pkg/server/config/config.go:27-28` |

### R4.1 v3 cross-check (deep-dived candidates)

Columns: **Fluree** = Fluree DB v4 (engine + policy + Python package) · **CSS** = Community Solid Server · **FGA** = OpenFGA (a PDP only) · **JFA** = Jena `jena-fuseki-access`. "n.a." = outside the tool's role: a store or PDP does not generate code, render UI or provide an ORM session. Absences were checked by grep over the clone (terms given) or GitNexus.

**Authorization (AZ1–AZ29)**

| Id | Fluree | CSS | FGA | JFA |
|---|---|---|---|---|
| AZ1 access-scope port at store boundary | present (store-internal): `PolicyContext` per request/handle; ledger scopes from token (`authentication.md:97-112`) | partial: per-resource permission map, not a dataset narrowing (`WebAclReader.ts` `findPermissions`) | n.a. (decision only; ListObjects feeds a PEP) | **present**: `SecurityContextView.createQueryExec` → `DataAccessCtl.filteredDataset` / TDB `GraphFilter` |
| AZ2 uniform injection before pagination/counts | **present**: filtering at scan (`binary_scan.rs:1082`), so counts/aggregates see filtered flakes | n.a. (no query endpoint; per-document access) | n.a. | **present**: the dataset view is below the engine, so all query forms are filtered |
| AZ3 rewriting PEP on SPARQL AST | absent (filters flakes, does not rewrite) — grep `rewrite` in `fluree-db-query/src/policy`: none | absent | n.a. | absent (dataset view, no rewrite) |
| AZ4 list-filter integration | n.a. (native) | n.a. | **present** as the PDP side: `ListObjects`/`StreamedListObjects` (`pkg/server/list_objects.go:213`), `ListUsers` (`list_users.go:36`); SPARQL translation absent | n.a. |
| AZ5 write authorization on the changeset | **present**: `stage.rs:2861`; verbs + `f:queryState` pre/post (`policy-model.md`) | **present**: modes from the patch (`SparqlUpdateModesExtractor.ts`, `N3PatchModesExtractor.ts`, `CreateModesExtractor.ts`) | partial: `Check` per changed object, called by the PEP | absent: updates refused outright (`AccessCtl_DenyUpdate.java`) |
| AZ6 staged PEP hooks in service pipeline | absent (store-level) | partial: `AuthorizingHttpHandler` before the operation (`src/server/AuthorizingHttpHandler.ts:50`); no post-read stage | n.a. | partial: Fuseki action wrappers `AccessCtl_*` per operation |
| AZ7 separated PEP/PIP/PDP | **present**: PDP `fluree-db-policy`, PEP `QueryPolicyEnforcer` + `stage.rs`, PIP = ledger (class cache, `class_lookup.rs`) | **present**: credentials extractor → `ModesExtractor` → `PermissionReader` chain (8 impls, GitNexus) → `PermissionBasedAuthorizer` | partial: PDP + tuple store as PIP | partial: registry (PIP/PDP) + filter (PEP), no separate decision API |
| AZ8 triple-level targeting (property / class+RDFS / subject) | **present**: `f:onProperty/onClass/onSubject`, RDFS entailment (`policy-model.md` §RDFS entailment) | absent (document granularity) | absent (needs a tuple per triple) | absent (graph granularity) |
| AZ9 SPARQL-condition policies `$this/$identity/$value/$op` | **present**: `executor.rs:224-225, 459-465` | absent (ACP matchers are agent/client/issuer/vc, not SPARQL) | absent (CEL conditions, not SPARQL: `go.mod:19` `cel-go`) | absent |
| AZ10 policy-as-data (RDF, declarative, fail-closed) | **present**: `f:AccessPolicy` nodes; fail-closed on bad conditions (`policy-model.md`) | **present**: `.acl`/`.acr` RDF read by `WebAclReader`/`AcpReader` | absent (tuples + DSL, not RDF) | partial: RDF assembler config (`VocabSecurity.java:39-44`), static lists, no conditions |
| AZ11 combining algorithm + default-deny | **present**: `evaluate.rs:309-770`, `default_allow` switch | partial: union of allows (`UnionPermissionReader.ts`), no deny rules in WAC | partial: union / intersection / `but not` in the model (`Userset_Intersection`, typesystem) | absent (allow list only) |
| AZ12 SPARQL-defined group membership | partial: an `f:query` can compute membership on each check; there are no tokens | partial: `acl:agentGroup` → `vcard:hasMember` lookup (`AgentGroupAccessChecker.ts`) | partial: usersets `group#member` from tuples | absent |
| AZ13 parameterised graph templates | absent (grep `template` in `fluree-db-policy/src`: none) | partial: container inheritance (`acl:default`) by path | absent | absent |
| AZ14 type/predicate write policy → graph placement | absent (no placement policy; grep `onGraph`: none) | absent | n.a. | absent |
| AZ15 caller (service) scopes | **present**: trusted application credential `"fluree.policy": "request"`; `policy_authorities` (`policy-authorization.md`) | partial: client-id matching in ACP (`acp:client`), not tested in code | absent (single API credential per store; caller identity is not modelled) | absent |
| AZ16 privileged bypass with opt-in | **present**: `PolicyWrapper::root()` (`lib.rs`), root `fluree.storage.*` claims; root only when no rules are selected (`policy-authorization.md`) | partial: `AllStaticReader` (configurable allow-all) | n.a. | partial: `SecurityContextAllowAll` |
| AZ17 non-widenable governed session | **present**: Python `with_policy` + `InvalidRequestError`; HTTP 403 on conflicting selections (`policy-authorization.md`) | n.a. | n.a. | absent |
| AZ18 IdP claim → policy selector | **present**: `fluree.identity`/`sub`, `fluree.policy.class`, `data_auth_default_policy_class` | partial: WebID from Solid-OIDC token; no role mapping | partial: contextual tuples carry claims per check (`commands/check_command.go`) | absent (servlet user name only) |
| AZ19 per-request end-user identity propagation | **present**: `fluree-identity` etc. headers (`extract/headers.rs:289-291`) | present: DPoP-bound token per request | present: `user` per call | partial: `Function<HttpAction,String>` (`DataAccessCtl.java:60-66`) |
| AZ20 token propagation/caching across hops | partial: a fixed signed delegation token can travel to downstream clients (`policy-authorization.md` §Fixed signed delegation) | absent | n.a. | absent |
| AZ21 principal threaded into field-level write checks | **present**: `$identity` + `$value` + `f:onProperty` on `f:modify` | absent | n.a. | n.a. |
| AZ22 client caches partitioned by principal | n.a. (server); explain stats hidden per scope (see AZ26) | n.a. | n.a. (server-side check cache only, `pkg/storage/cache.go`) | n.a. |
| AZ23 trusted-proxy gate | partial: `policy_authorities` — only listed issuers may select policy | absent | n.a. (pre-shared key auth to the API) | absent |
| AZ24 authz error contract 401/403 | **present**: 403 on conflicts, `f:exMessage`, `PermissionDeniedError` (Python) | **present**: `UnauthorizedHttpError` / `ForbiddenHttpError` (`util/errors/*.ts`) | partial: gRPC/HTTP error codes, but decisions return `allowed=false` | partial: denied operations answer **400 "Not supported"** (`AccessCtl_Deny.java:43`, `AccessCtl_AllowGET.java:71-73`), not 403 |
| AZ25 read masking | absent (hides, does not mask; `mask` hits only in delta filters) | absent | n.a. | absent |
| AZ26 policy-aware explain/statistics | **present** (`policy-authorization.md` §Policy-scoped explain) | n.a. | n.a. | absent |
| AZ27 decision audit trail | partial: credential-scope debug events (`RUST_LOG=…authorization=debug`); policies used are not returned on the response | partial: `WAC-Allow` header shows granted modes (`server/WacAllowHttpHandler.ts:28-55`) | partial: `ReadChanges` = tuple changelog (`pkg/server/read_changes.go:19`); no decision log | absent |
| AZ28 authz-tuple sync from domain events | n.a. (policies read live data) | n.a. | partial: the target of the sync (Write with duplicate handling `pkg/server/commands/write.go`; `ReadChanges`); no RDF/CDC connector — grep `rdf\|sparql` in `pkg/`: none | n.a. |
| AZ29 ACL config generated from model | absent | absent | absent | absent |

**Transactions, events, stores, interop (T, E, S, X, RAD4)** — only for the candidates where these apply (Fluree, CSS). FGA and JFA are n.a. except where noted.

| Id | Fluree | CSS | FGA / JFA |
|---|---|---|---|
| T1 single-request atomic flush | present: one request = one commit (`docs/transactions/overview.md`) | partial: one SPARQL update per resource write (`SparqlDataAccessor.ts` `sparqlInsert`) | FGA: Write is atomic per request (≤100 tuples by default — config, not verified) · JFA n.a. |
| T2 guarded update / CAS | present: `docs/transactions/conditional-updates.md` | partial: `If-Match` preconditions (`storage/conditions/BasicConditions.ts:35`) | n.a. |
| T3 vendor multi-request tx | present (embedded): Python `begin()` / `Transaction.commit/rollback` (`_fluree.pyi:37, 182-193`) | absent | n.a. |
| T4 compensating undo | absent (grep `compensat`: none) | absent | n.a. |
| T5 read-your-writes in a tx | present (embedded `Transaction`; `fluree-db-python/src/transaction.rs`) | absent | n.a. |
| T6 automatic retry on conflict | partial: retry helpers in the CLI/indexer only (grep `retry`); Python retry is per the catalogue, not verified | absent | n.a. |
| T7 store capability descriptor | absent | absent | n.a. |
| T8 savepoints | present: `fluree-db-python/src/transaction.rs` (savepoint), `fluree-db-api/tests/it_transaction.rs` | absent | n.a. |
| T9 idempotent writes | partial: upsert / sync are idempotent by design (`docs/transactions/upsert.md`, `sync.md`) | absent | FGA partial: duplicate-tolerant writes (`pkg/server/write.go`) |
| T10 rollback resets cached object state | n.a. | n.a. | n.a. |
| T11 write-batch limits | absent | absent | FGA: max tuples per write (server config) |
| E1 outbox | absent (grep `outbox`: none) | absent | n.a. |
| E2 RDF Patch | absent | absent | JFA: n.a. for the access module (RDF Patch is in Jena/RDF Delta, outside this clone) |
| E3 head-moved + pull | present (`fluree-db-api/src/transaction.rs`, SSE crate `fluree-sse`) | absent | n.a. |
| E4 policy-filtered change feeds | partial: commit contents and history are policy-filtered (`hydration.rs` `filter_flakes_by_policy`) | **present**: notification subscriptions are authorized (`NotificationSubscriber.ts`, `StreamingHttpRequestHandler.ts:48-74`) | n.a. |
| E5 ordered, resumable sequence | present: `t` + commit id/digest | absent | FGA partial: `ReadChanges` continuation token |
| E6 delta-only virtual graphs | absent | absent | n.a. |
| E7 call-id trail | absent | absent | n.a. |
| E8 coalesced notifications | absent | absent | n.a. |
| E9 standard notification channels | absent (own SSE) | **present**: WebSocket/Webhook/StreamingHTTP Channel2023 (`index.ts:396-397`) | n.a. |
| S15 time travel | present (`docs/concepts/time-travel.md`) | absent | n.a. |
| S16 branching | present (`README.md`, `fluree-db-api/src/merge.rs`) | absent | n.a. |
| S17 diff-load / sync | present (`docs/transactions/sync.md`) | partial: PUT replaces a document | n.a. |
| S18 bulk loader | present (bulk `import`, `turtle.md:460`) | absent | n.a. |
| S19 commit metadata | present (`commit-receipts.md`, Python `message=`) | absent | n.a. |
| X17 multi-profile rendering | partial: JSON-LD, SPARQL results, GraphQL, Cypher over one ledger | partial: content negotiation over RDF formats | n.a. |
| X18 atomic multi-op with local ids | absent | absent | n.a. |
| X19 conditional requests | absent on the data API (grep `If-Match` hits only in a JSON-LD/delta adapter) | **present** (`http/input/conditions/BasicConditionsParser.ts:14`) | n.a. |
| X20 cursor pagination | absent | absent | FGA: continuation tokens on Read/ReadChanges |
| X21 RDF patch bodies | present: SPARQL UPDATE | **present**: N3 Patch + SPARQL Update (`N3PatchBodyParser`, `SparqlUpdatePatcher.ts:21`) | n.a. |
| X22 bundled JSON-LD context | n.a. | n.a. | n.a. |
| RAD4 tiered exposure | present: curated GraphQL schema, mutations opt-in (`docs/query/graphql.md:25,119`) | n.a. | n.a. |

**Generation, UI and DevEx (G1–G27, U1–U10, RAD3, D11–D13)**

| Ids | Fluree | CSS | FGA | JFA |
|---|---|---|---|---|
| G1–G11, G13–G27 | n.a. (database; no code generation) | n.a. | n.a. (FGA DSL is hand-written) | n.a. |
| G12 GraphQL from SHACL/LinkML | partial: GraphQL schema from the ledger, curated by a `graphql:Schema` instance (`docs/query/graphql.md:25`) | n.a. | n.a. | n.a. |
| U1–U8, U10 | n.a. | n.a. | n.a. | n.a. |
| U9 capability hints | absent | **present**: `WAC-Allow` header (`WacAllowHttpHandler.ts`) | partial: ListObjects/BatchCheck can feed hints | absent |
| RAD3 | n.a. | n.a. | n.a. | n.a. |
| D11 store error bodies surfaced | present (`docs/api/errors.md`) | present (error serialisation) | present | partial (400 text body) |
| D12, D13 | n.a. | n.a. | n.a. | n.a. |

**Counts (AZ1–AZ29, present / partial / absent / n.a.):** Fluree **16 / 4 / 6 / 3** · CSS **5 / 9 / 9 / 6** · OpenFGA **2 / 8 / 6 / 13** · Jena access **2 / 6 / 17 / 4**. Outside AZ, Fluree covers most T/S/E store features (T1–T3, T5, T8, E3, E5, S15–S19 present); CSS covers the interop features X19, X21, E4, E9 and U9; OpenFGA and Jena access are n.a. there.

Mapping to my round-3 proposals: see the "Id mapping" appendix (`angle-authz.md` AZ1→AZ1, AZ2→AZ5, AZ3→AZ8, AZ4→AZ9, AZ5→AZ10, AZ6→AZ4, AZ7→AZ11, AZ8→AZ17, AZ9→AZ18, AZ10→AZ28, AZ11→AZ25, AZ12→AZ26, AZ13→AZ27). Nothing was lost in the merge.

### R4.2 Purpose and origin

**Deep-dived**

- **Fluree DB v4.** Built by Fluree PBC (Winston-Salem, NC). It started as a Clojure "blockchain-style ledger graph database" (v1–v3) and became a Rust rewrite: v4.0.0 was released 2026-04-22 (gh releases), and the Python wheel `fluree` first appeared on 2026-10-08 (PyPI). The design angle is *data-centric security and provenance*: policies, identities and history live in the same ledger as the data, and are enforced on every flake. **Fits:** L2 + L3 (+ L4 through its HTTP API, L6 head events) in **V3**. Possibly an optional backend behind V1's store port, but then its policies stay unused unless identity headers are forwarded. It is not a library we build on; it is a database we would run.
- **Community Solid Server.** Built by IDLab (imec – Ghent University), originally commissioned by Inrupt as the modular reference server for the Solid specifications. The design angle is *personal data pods*: one document = one resource with its own ACL, WebID identity, Solid-OIDC, and a dependency-injected component architecture (Components.js). **Fits:** idea source for L3 (PEP/PIP/PDP pipeline, WAC/ACP vocabularies as graph-level policy-as-data, `WAC-Allow` hints) and L4/L6 (conditional requests, N3 Patch, Solid Notifications). It does not fit V1–V5 as a component: it is a resource server, not a SPARQL dataset ACL, and it serves pod products only (as `variants.adoc` says).
- **OpenFGA.** Built at Auth0 (Okta) as an open-source implementation of Google's Zanzibar paper; donated to the CNCF (README carries the CNCF Slack/community links). The design angle is *relationship-based authorization as a service*: a tuple store + model DSL + Check/ListObjects APIs, data-store-agnostic. **Fits:** L3 PDP in **V1** and **V5** (graph/resource-level lists → our PEP port), and in V4 for coarse checks next to GraphDB FGAC. It knows nothing of RDF; the tuples must be synced (AZ28).
- **Jena `jena-fuseki-access`.** Written by Andy Seaborne in Apache Jena (ASF; Jena itself began at HP Labs). The design angle is *publishing*: expose a dataset where each user sees a fixed set of named graphs, read-only. **Fits:** L2/L3 for the **V5** read path (a read-only graph-filtered endpoint, `variants.adoc` V5) and as the reference design for AZ1 in our in-process adapter. It cannot be the write path (updates are refused).

**Desk-scan candidates (purpose and origin only)**

| Candidate | Built for / origin / angle | Where it fits |
|---|---|---|
| GraphDB FGAC | Ontotext (Sofia), enterprise feature since 10.4 (quad-based) / 10.6 (FGAC) for regulated knowledge graphs; ACL-list-first | V4 store-native triple-level PEP |
| Stardog security | Stardog Union (US), enterprise KG platform; named-graph RBAC + masking | ideas only (AZ25); store if a client mandates it |
| AllegroGraph filters | Franz Inc. (Lisp heritage); per-user triple filters | ideas only |
| Virtuoso graph perms | OpenLink Software; multi-model SQL/RDF server for Linked Data hubs (DBpedia); SQL-user-first | V2 store (behind sparql-parser, which bypasses its perms with one DB user) |
| RDF4J / Oxigraph / QLever | stores without built-in ACL | V1 stores; PEP must sit in front (our port or a proxy) |
| sparql-parser | redpencil.io for Flemish government apps (semantic.works) | V2 PEP |
| Solid WAC / ACP | WAC: Tim Berners-Lee's group at MIT/W3C (2009+), now Solid CG; ACP: authored at Inrupt, adopted by the Solid CG | vocabulary candidate for graph-level policy-as-data in V1 |
| ODRL-Evaluator | `odrl-force` org (created 2024-12; top contributors woutslabbinck, jvherweg — IDLab Ghent/SolidLab researchers, affiliation not stated in the repo); usage-control compliance reports | ideas only (fails DEC-5) |
| SpiceDB | AuthZed (founded by ex-CoreOS/Red Hat engineers); Zanzibar with caveats | V1/V5 alternative to OpenFGA |
| Ory Keto / Kratos / Hydra | Ory GmbH (Munich); headless, API-first identity + Zanzibar stack | alternative IdP stack for V1 |
| Permify | Permify (Istanbul/US startup); Zanzibar + ABAC; AGPL | ideas (licence) |
| Cerbos | Cerbos Ltd (London); stateless policy-as-code PDP with query plans | V1/V5 attribute-level PDP if an AST→SPARQL translator is built (AZ4) |
| OPA | Styra founders (2016), CNCF graduated (2021, README); general policy-as-code | ideas (UCAST → SPARQL) |
| Topaz | Aserto; OPA + Zanzibar directory | none (weak Python SDK) |
| Casbin / pycasbin | created by Yang Luo (2017); **now Apache Casbin (ASF)** — repos are `apache/casbin`, `apache/casbin-pycasbin`, README has ASF licence headers | V1 minimal in-process PDP |
| Oso | Oso Security; open-source library archived, product moved to Oso Cloud SaaS | none |
| Zitadel | ZITADEL (CAOS AG, St. Gallen, CH); multi-tenant IdP with organisations/projects/grants | IdP for V1–V5 |
| Keycloak | Red Hat (JBoss), now a CNCF project (README: CNCF code of conduct, CLOMonitor badge) | fallback IdP for V1–V5 |
| Authentik | Authentik Security (company around Jens Langhammer's project); self-hosted IdP | alternative IdP |

### R4.3 Variant fit

S = supports (works as-is), E = enables (makes the variant possible / is its key part), B = blocks or conflicts, – = irrelevant. Approaches A (runtime mapper), B (generated mapper + routes), C (generic service).

| Candidate | V1 Portable | V2 semantic.works | V3 Fluree | V4 GraphDB | V5 Graph-direct reads | A | B | C | Note |
|---|---|---|---|---|---|---|---|---|---|
| Fluree policies / DB v4 | S (as a store behind the port; policies unused unless headers forwarded) | – | **E** | – | S (store-native PEP makes free SPARQL safe) | S | S | S | BUSL; policies need identity per request (AZ19) |
| Community Solid Server | – (ideas) | – | – | – | – | – | – | – | pods only; vocabularies + pipeline ideas |
| OpenFGA | **E** (graph/resource PDP) | B-ish (duplicates sparql-parser's groups) | – (redundant with policies) | S (coarse checks) | S (ListObjects → graph list for the read proxy) | S | **E** (B can generate the FGA model from LinkML annotations, AZ29) | S | needs tuple sync (AZ28) |
| Jena `jena-fuseki-access` | S (read-only replicas) | – | – | – | **E** (read-only graph-filtered endpoint) | S | S | S | no writes; user from servlet auth only |
| GraphDB FGAC | – | – | – | **E** | S | S | S | S | default allow; admins bypass |
| sparql-parser | B (V1 is proxy-free) | **E** | – | – | S (a policy-aware SPARQL proxy) | S | S | **E** with mu-cl-resources | fails DEC-5 |
| pycasbin | **E** (lite) | – | – | – | partial | S | S | S | no list plan |
| Cerbos / OPA | S (needs AZ4 translator) | – | – | – | S (same) | S | S | S | translator to build |
| Zitadel / Keycloak | **E** | S (claims → allowed groups) | **E** (OIDC/JWKS → `fluree.identity`) | **E** (`roles_claim`) | **E** | – | – | – | identity is common to all |

Headline: **graph-level authorization is portable across V1, V2, V4 and V5; triple-level authorization only exists in V3 (Fluree) and V4 (GraphDB).** Approach B is the only one that can *generate* authz configuration (FGA model, Fluree policy nodes, sparql-parser graph specs) from the LinkML model (AZ29).

### R4.4 Corrections to the integrated docs

1. `catalogue.adoc` **Casbin / pycasbin**, Origin "Casbin community. Library-first." → **"Created by Yang Luo (2017); now Apache Casbin under the ASF (`github.com/apache/casbin`, `apache/casbin-pycasbin`). Library-first."**
2. `catalogue.adoc` **ODRL-Evaluator**, Origin "Origin not recorded." → **"`odrl-force` organisation (repo created 2024-12; main contributors woutslabbinck and jvherweg, IDLab Ghent/SolidLab researchers — affiliation inferred, not stated). Usage-control-first."**
3. `catalogue.adoc` **Jena `jena-fuseki-access`**: correct, but add that denied operations return **HTTP 400 "Not supported"**, not 403 (`AccessCtl_Deny.java:43`). This matters for AZ24 and for clients that expect 403.
4. `catalogue.adoc` **Community Solid Server**, Origin "Solid project (imec – Ghent University)": add "commissioned by Inrupt" (not verified in the repo; from project history). Optional.
5. `variants.adoc` V3 "no cascade delete": still true for entity deletes. v4 adds only an **edge-annotation cascade** (`fluree-db/docs/transactions/retractions.md:198-208`). Keep it, but cite v4.
6. `angles/authz.adoc` "Not checked: the Fluree GitNexus index did not finish" → **now finished (index `db`)**. Read enforcement is confirmed at `binary_scan.rs:1082`, write enforcement at `fluree-db-transact/src/stage.rs:2861`, and SPARQL conditions at `executor.rs:224-225, 459-465` (R4.0). The SPARQL-condition claim moves from "documented" to "confirmed in code".
7. `angles/authz.adoc` / `catalogue.adoc` "a policy cannot target a named graph": correct as stated. Optionally add "enforcement is graph-aware (classes resolved per graph) but targeting is not".
8. Origin cells checked and **correct**: Fluree DB v4 ("Rust rewrite (2026)": v4.0.0 on 2026-04-22), `fluree` PyPI ("first release 2026-10": 2026-10-08), OpenFGA (Auth0/Okta, CNCF), Keycloak (Red Hat, CNCF), OPA (Styra, CNCF graduated 2021), Zitadel (Swiss), Oso (archived), sparql-parser (redpencil.io), GraphDB/Stardog/AllegroGraph/Virtuoso vendor cells.

### R4.5 Proposed new features (round 4, existing area AZ)

| Id | Feature | Seen in |
|---|---|---|
| AZ30 | **Graph-aware enforcement with class resolution per graph** (policy targeting by class uses the type triples of the flake's own graph, not a union) | Fluree `filter_flakes_for_graph` (`enforcer.rs:104`) |
| AZ31 | **Effective-ACL inheritance along a container/graph hierarchy** (`acl:default`; nearest ancestor's policy applies) | CSS `WebAclReader.getAclRecursive` (WAC "effective ACL resource") |
| AZ32 | **Predicate-coverage fast path**: skip per-triple policy evaluation for predicates that no policy covers | Fluree `classify_view_predicate` (`enforcer.rs:71`, `fast_path_common.rs:3982`) |
| AZ33 | **Deny response that does not reveal existence** (out-of-scope graphs/ledgers answer 404, not 403) | Fluree `docs/api/overview.md:288` |

## Round 5

Brief: `BRIEF-round5.md`. Taxonomy: `feature-taxonomy.adoc` **v4** (77 new ids). Candidates: **Fluree** (DB v4), **CSS** (Community Solid Server), **FGA** (OpenFGA), **JFA** (Jena `jena-fuseki-access`). Absences were checked by grep over the clones (terms given) or with GitNexus (Fluree index `db`).

### R5.1 v4 cross-check

**Ids relevant to this angle**

| Id | Fluree | CSS | FGA | JFA |
|---|---|---|---|---|
| AZ30 class resolution per graph | **present**: `filter_flakes_for_graph(…, g_id, …)` (`fluree-db-query/src/policy/enforcer.rs:104`); per-graph class cache test (`evaluate.rs:1405-1417`) | n.a. (no class targeting) | absent (no classes; types are FGA types) | n.a. |
| AZ31 effective-ACL inheritance down a hierarchy | absent: no hierarchy in targeting (grep `inherit` in `fluree-db-policy/src` only hits the class cache and verb lifecycle) | **present**: `WebAclReader.getAclRecursive` (WAC effective ACL resource) | partial: `TupleToUserset` (`reader from parent`, `pkg/typesystem/typesystem.go:109`) models inheritance in tuples | absent |
| AZ32 predicate-coverage fast path | **present**: `classify_view_predicate` (`enforcer.rs:71`, `fast_path_common.rs:3982`) | n.a. | n.a. | n.a. |
| AZ33 existence-hiding denial | partial: out-of-scope ledgers → 404 (`docs/api/overview.md:288`); policy-scoped explain hides statistics; ETag/Last-Modified n.a. | **present**: 404 only if the agent may read, else denied (`authorization/PermissionBasedAuthorizer.ts:57-69`, `exposeExistence`) | n.a. | absent: 400 "Not supported" (`AccessCtl_Deny.java:43`) |
| AZ34 lagging policy configuration | **present**: config uses "lagging semantics" — changes take effect on the next transaction (`docs/ledger-config/README.md:187`) | absent: an `.acl` write applies immediately | n.a. | n.a. (static assembler config) |
| AZ35 policy-filter equivalence test | partial: COUNT over a join respects the restricted view (`fluree-db-api/tests/it_policy_indexed.rs:375`); no per-query-family equivalence suite | absent | n.a. | absent (tests in `jena-fuseki-access/src/test` check visibility, not totals) |
| AZ36 edge sanitisation of internal security headers | partial: policy headers are honoured only under a policy-authority credential; conflicts → 403 (`policy-authorization.md`, `policy_authorities`) | n.a. (DPoP-bound tokens; no internal headers) | n.a. | n.a. |
| S20 per-named-graph store configuration | **present**: `f:graphOverrides` → `f:GraphConfig` per graph, including `f:policySource` (`docs/ledger-config/README.md:51`, `writing-config.md:260`) | n.a. | n.a. | partial: graph list per user in the assembler |
| S22 store-side shape enforcement in the write transaction | present: `f:shaclDefaults` (`docs/ledger-config/README.md:39`) | absent: SHACL only validates notification channel descriptions (`server/notifications/BaseChannelType.ts`) | n.a. | n.a. |
| S23 ops admin port | present per angle-stores (`.flpack`); not re-checked | absent | n.a. | n.a. (Fuseki admin is outside this module) |
| T12 read-tracked optimistic commit | present per angle-stores; not re-checked | n.a. | n.a. | n.a. |
| T13 read-only mode guard | absent as a switch (policy can deny `f:modify`) | **present**: `storage/ReadOnlyStore.ts` | n.a. | **present**: `AccessCtl_DenyUpdate.java` |
| PG4 scope abstraction for partitions | partial: ledger = partition for token scopes; named graph = scope for queries | partial: document/container = graph | partial: FGA type `graph` as the partition object (R3 §3.4 model) | **present**: visible-graph set = scope (`SecurityContextView.java`) |
| B10 aggregate storage strategy (graph per aggregate) | partial: named graphs via TriG / GSP (`docs/api/graph-store.md`) | **present**: one graph per resource (`SparqlDataAccessor.ts:47-225`) | n.a. | n.a. |
| E10 subscription channel options | absent: own SSE (`fluree-sse`), no channel options found | **present**: `state`, `startAt`, `endAt`, `rate`, `accept` (`server/notifications/NotificationChannel.ts:22-41`) | n.a. | n.a. |
| EV9 migration rehearsal on a branch | present: branches + merge (`fluree-db-api/src/merge.rs`) | absent | n.a. | n.a. |
| D15 parameter redaction in logs | partial: tokens, inline policies and policy values are omitted from authorization logs (`policy-authorization.md`) | absent | absent | absent |
| D17 inspectable compiled query | partial: `explain` (`docs/query/explain.md`) | n.a. | n.a. | n.a. |
| D29 OpenTelemetry spans | **present**: `fluree-db-server/src/telemetry.rs` | absent (grep `opentelemetry`: none) | **present**: `go.opentelemetry.io/otel v1.47.0` (`go.mod:46`), `otelgrpc`/`otelhttp` | absent |
| X24 MCP projection under the same security | partial: an MCP server exists (`fluree-db-mcp/`), but it **rejects policy claims** because it "cannot enforce the complete selection contract" (`policy-authorization.md` §Transport) | absent | absent (grep `mcp`: none) | absent |

**Remaining v4 ids** — B1–B9, B11–B16, PG1–PG3, EV1–EV8, G28–G36, T14, U11–U13, D14, D16, D18–D28, X23, I7, I8, P20: **n.a. for all four**. They are features of a persistence library, generator, client or test kit; a store, pod server or PDP does not offer them. One note: Fluree's SPARQL/JSON-LD surface would be the *target* of B7 (guarded single update) and B8 (change-set rendering), not a provider of them.

**Counts over the 20 relevant ids (present / partial / absent / n.a.):** Fluree **9 / 8 / 3 / 0** · CSS **5 / 1 / 8 / 6** · FGA **1 / 2 / 3 / 14** · JFA **2 / 1 / 6 / 11**. The other 57 v4 ids are n.a. for all four.

### R5.2 Page review (last chance to correct)

`angles/authz.adoc` (line numbers from `cat -n`):

1. **l.115 overstatement:** "BUSL-1.1 is fine for internal and client-hosted use". The Additional Use Grant forbids any *commercial offering* that lets third parties "define their own schemas, ontologies, or data models and use the Licensed Work to store, query, and manage data under them" (`fluree-db/LICENSE:12-30`). A Meaningfy product where customers model their own data (MWBv2-style) may fall under this. **Fix:** "Internal use, and a deployment a client runs for its own applications, appear permitted. A commercial offering where third parties create databases or define their own schemas on Fluree is a 'Database Service' (`LICENSE:12-30`), so a legal reading is required per product."
2. **l.86 missing evidence:** "Counts and aggregates therefore see filtered data." This is backed by a test. **Fix:** add "(tested: `fluree-db-api/tests/it_policy_indexed.rs:375`, COUNT over a join under a restricted view)".
3. **l.194 factual error:** "Gaps shared by all four: AZ3, AZ13, …". CSS has AZ13 *partial* (container inheritance), and OpenFGA is n.a. for AZ3, AZ14 and AZ25. **Fix:** "Gaps shared by all four: AZ29 (ACL config generated from the model); AZ3, AZ14 and AZ25 are absent in the three enforcement points and n.a. for OpenFGA."
4. **l.206 overstatement:** OpenFGA V2 = "B". It does not block V2; it is redundant with sparql-parser's groups. **Fix:** "–" with "redundant with sparql-parser's groups in V2".
5. **l.258 factual error:** S2 "Vendor-neutral, Apache-2.0". The stack's IdP, Zitadel, is AGPL-3.0 (server). **Fix:** "Vendor-neutral; OpenFGA/SpiceDB/pycasbin Apache-2.0 (Zitadel server AGPL-3.0, Keycloak Apache-2.0)".
6. **l.272-278 stale:** "Round-4 proposals (no taxonomy id yet)". They are now **AZ30–AZ33 and AZ35** in v4. **Fix:** replace the list with those ids, and change "taxonomy v3" on l.270 to v4.
7. **l.37, l.54, l.257-266, l.282-283 labels:** "variant S1 / S2 / S2′ / S3". See R5.4: rename to V3 / V1 / V4 / V2.
8. **l.140 caveat:** "OIDC would need a custom Java servlet filter". Add "(not checked against Fuseki 5 modules / Jetty 12 OIDC support)".
9. **l.61 vs catalogue inconsistency:** pycasbin is "dependency" here and "integrate" in `catalogue.adoc`. As an in-process library, **dependency** is right; fix the catalogue cell.

`index.adoc`:

10. **l.36 overstatement:** "no authorization engine speaks SPARQL". Fluree's policy engine evaluates SPARQL ASK conditions. **Fix:** "no general-purpose authorization engine (PDP) has a SPARQL adapter".

`variants.adoc`:

11. **V1 l.17:** "in-process policy check (OpenFGA, or pycasbin)". OpenFGA is a separate server; only the *enforcement point* is in-process. **Fix:** "an in-process enforcement point calling OpenFGA (a service) or pycasbin (a library)".
12. **V5 l.55 missing option:** "Needs a policy-aware SPARQL proxy (`sparql-parser` exists, graph-level)". Add "or Jena Fuseki `jena-fuseki-access` as the read-only graph-filtered endpoint (passes DEC-5; read-only by design; answers 400 instead of 403)".
13. **V3 l.41 precision:** "named-graph policies only as per-graph defaults (`f:graphOverrides`)". Correct, but add "policy *targeting* stays per triple; a graph override changes defaults and the policy source, not what a rule matches".

`building-blocks.adoc` (L3) and `design-implications.adoc` (policy-enforcement port): no errors found against my evidence. The L3 "Facts" line is precise ("No general authorization engine has a SPARQL adapter").

**Total: 13 corrections** (5 factual/overstatement, 4 missing caveats or evidence, 2 stale, 2 consistency).

### R5.3 Final verdicts and what an architect must remember

| Candidate | Final verdict | One line |
|---|---|---|
| Fluree DB v4 policies | **integrate** (V3 only) + ideas everywhere | The only off-the-shelf triple-level, RDF-native, SPARQL-conditioned policy engine; BUSL-1.1 |
| Community Solid Server | **ideas** | Reader pipeline, WAC/ACP vocabularies, existence-hiding 404, `WAC-Allow` hints |
| OpenFGA | **integrate** (V1, V5) | Graph/resource-level PDP behind our enforcement port; tuples must be synced |
| Jena `jena-fuseki-access` | **integrate** (V5 read path) | Read-only, graph-filtered SPARQL endpoint; reference design for the dataset-scope adapter |

Three things a system architect must remember:

1. **Pick the granularity first, then the variant.** Graph-level access is portable (any store + OpenFGA/pycasbin + our scope port, or Jena access for reads). Triple-level access exists only store-native (Fluree, GraphDB) and locks the policy into that vendor.
2. **Free SPARQL from the UI changes everything.** Our in-process enforcement port only protects the queries rdf-persistence generates. If any client can send its own SPARQL, enforcement must be in the store (Fluree, GraphDB, Jena access) or in a rewriting proxy (sparql-parser).
3. **Identity must reach the enforcement point unforgeably.** For Fluree, use a policy-authority credential plus per-request identity. For a proxy, strip client-sent internal headers at the edge (AZ36). For OpenFGA, keep the tuples synced from domain events (AZ28). Otherwise the policies silently stop applying.

### R5.4 Stack labels S1/S2/S3 → variant ids

**Retire the S labels.** They predate `variants.adoc`, and every one maps to a variant: **S1 → V3**, **S2 → V1** (S2-lite with pycasbin → V1 lite), **S2′ → V4**, **S3 → V2**. V5 had no stack; its enforcement point is Jena access, sparql-parser or Fluree on the read path. Keep the *pattern* ids P-A…P-M: they name enforcement placements, which cut across variants. In `angles/authz.adoc`, rename the "Recommended options" table to "Authorization per variant" with rows V1–V5. Update the S references on l.37, 54, 257-266 and 282-283.

### R5.5 New features

None proposed. The taxonomy covers this angle (AZ1–AZ36 plus S20, PG4 and T13).
