<!-- SECONDARY INPUT: preserved, never groomed. Findings on the developer's notes in seed.md. -->

# Analysis: the manual revision notes

Read-only analysis of `develop` at b3626cb, 2026-11-16, of the developer's notes in
[`seed.md`](seed.md). Five analysts worked in parallel, one per group of notes, and the lead
merged their findings. Every claim cites a file and line, so it can be checked. The changes
proposed are in [`improvements.md`](improvements.md); what stays, and why, is in
[`keep.md`](keep.md).

**Overall finding.** The package reuses more than it looks like it does. rdflib, PyJWT, httpx,
pyld, pyshacl and linkml-runtime are already the engines underneath. The hand-written layers on
top have a recorded reason in most cases: async, injection safety, IRI policy, test transports.
In some cases the reason is missing from the record. In one case the record says the opposite of
what was built (DEC-4, §2.1). The real debts are elsewhere. Tunables are scattered as module
constants. Dicts carry concepts that should be models. The package is a flat layered list rather
than thematic modules. The generators live inside the runtime library. Logging and tracing are
not aligned with OpenTelemetry.

## 1. Cryptography, JWKS and `_http.py`

### 1.1 Does the algorithm matter, and can we use a post-quantum one?

- The library only **verifies** tokens; the identity provider (Zitadel) **signs** them. The
  allow-list is `RS256` and `ES256` (`adapters/jwks.py:30-32`). It is enforced on the header
  (`jwks.py:101`) and again in `jwt.decode(algorithms=...)` (`jwks.py:110-112`). The testkit
  signs with RSA-2048 and RS256 (`testkit/tokens.py:130-132`).
- **The provider chooses the algorithm, not us.** A Zitadel admin picks the active web key:
  RS256/384/512, ES256/384/512 or EdDSA (Ed25519), with RS256 as the default. Zitadel does not
  offer post-quantum keys. A resource server can only accept a subset of what the provider signs
  with.
- **Latent bug.** If an admin switches the web key to ES384, RS512 or EdDSA, every token is
  refused with 401. The allow-list should be a parameter, not a constant.
- **HS512 is the wrong family.** It is HMAC with a shared secret. With a key of 256 bits or more
  it holds up against a quantum attacker, since Grover only halves the strength. But every
  service that verifies would then hold the secret that signs, so any of them could mint tokens.
  The code rules HS* out on purpose (`jwks.py:30`), and Zitadel does not issue HS-signed access
  tokens.
- **Standards today:**
  - ML-DSA (FIPS 204, final) has a JOSE registration: key type `AKP`, algorithms
    `ML-DSA-44/65/87`, from draft-ietf-cose-dilithium, now RFC 9964. Secondary sources say so;
    the datatracker status was not confirmed.
  - FN-DSA (FIPS 206) is still a draft, with final publication expected late 2026 or early 2027.
  - SLH-DSA and composite (hybrid) signatures are IETF drafts.
- **Libraries:**
  - pyca `cryptography` 50 (already locked) ships ML-DSA keys with sign and verify; it has no
    FN-DSA.
  - PyJWT 2.15 has no ML-DSA or `AKP`. A custom `Algorithm` over `cryptography` is feasible.
  - joserfc, authlib and jwcrypto: no ML-DSA found. python-jose is unmaintained.
  - liboqs-python is not needed now that `cryptography` has ML-DSA.
- **Urgency is low for signatures.** Access tokens live minutes, so "harvest now, decrypt later"
  does not apply. The post-quantum work that matters now is **TLS** (hybrid ML-KEM key exchange)
  on the Zitadel, Fuseki and S3 links. That is infrastructure, not this library.
- **Verdict.** It matters only through the allow-list. Make the allow-list a parameter with an
  asymmetric-only default, and add ML-DSA the day Zitadel and PyJWT support it.

### 1.2 Why is `jwks.py` so low-level?

- It does **not** reimplement cryptography. PyJWT already does header parsing, `PyJWKSet`, the
  signature, `iss`, `aud` and the required claims (`jwks.py:97, 110-122, 183`). What is
  hand-written is about 60 lines of key cache and fetch (`jwks.py:148-204`) plus local checks.
- The behaviour is recorded in PD-28a (`archive/2026-11-06-toolkit-v1-foundation/design.md:450-455`).
  **Why PyJWT's own `PyJWKClient` was not used is not recorded.** The earlier review only said
  "PyJWT + JWKS" (`archive/2026-11-05-soa-python-rdf-orm/inputs/analysis/angle-authz.md:72,77`).
- Comparison with PyJWT 2.15 `PyJWKClient`:

  | Concern | `jwks.py` | `PyJWKClient` | Verdict |
  |---|---|---|---|
  | Cache with TTL | 600 s | 300 s `lifespan` | equivalent |
  | Unknown-`kid` cooldown | keyed on the last *attempt* (`jwks.py:173-180`), so an outage is not hammered | keyed on the last *success*, so a failing provider is re-hit every call | ours is stricter |
  | Async, single-flight | `asyncio.Lock`, double-checked (`:156-168`) | sync `urllib` and `RLock`; blocks the event loop | ours fits FastAPI |
  | OIDC discovery and issuer match | yes (`:190-198`) | no | ours |
  | Test transport, injected clock | yes; drives the testkit IdP | no | ours |
  | Clock-skew leeway | **none** (`exp <= now`, `:133-136`) | `leeway=` | **gap in ours** |

- joserfc and authlib have no async JWKS client with caching or discovery either. Switching would
  replace PyJWT and still leave the cache to us.

### 1.3 Why do we have `_http.py`?

- It is not an HTTP client. It is a 74-line base over **httpx**, the mature client, already
  pinned (`pyproject.toml`). It gives one `AsyncClient` with explicit timeouts (connect 5 s,
  read 30 s, `_http.py:17-18`), a `transport=` seam for test doubles, the mapping of
  `httpx.HTTPError` to each adapter's "unavailable" error (`:54-59`), and `json_body`.
- Callers: `jwks.py:19`, `zitadel.py:15`, `fuseki.py:13`, `testkit/zitadel.py:19`. Without it,
  the same `try/except httpx.HTTPError` and client set-up would appear three times. It is the
  de-duplication, recorded in PD-28a (`design.md:456-458`). Its timeouts should be parameters.

### 1.4 Constants in the Zitadel adapter

| Constant (`adapters/zitadel.py`) | Line | Class |
|---|---|---|
| `ORG_HEADER`, `USERS`, `MANAGEMENT`, `USER_GRANT_SEARCH` | 35-38 | Zitadel API protocol: stay |
| `PROJECTS`, `MACHINE_USERS`, `OWN_ORGANISATION`, `TOKEN_PATH` | 39-42 | protocol, but **used only by the testkit** (`testkit/zitadel.py:36-42`). The token endpoint can come from discovery |
| `PAGE_SIZE = 100` | 43 | default with an optional override |
| `ACTIVE_STATE`, `INACTIVE_STATE` | 44 | protocol enum values; belong in LinkML (`ZitadelUser.state` is a bare `str`, `adapters/generated/rp_wire.py:195`) |

**You were right.** No constant in `zitadel.py` is a deployment variable: issuer, service token,
organisation and project are already constructor arguments (`zitadel.py:112-127`). The values
that are deployment variables sit elsewhere:

- the HTTP timeouts (`_http.py:17-18`)
- `JWKS_TTL_SECONDS` and `UNKNOWN_KID_COOLDOWN_SECONDS` (`jwks.py:26,29`)
- `ALLOWED_ALGORITHMS` (`jwks.py:32`)

## 2. Store, SPARQL, IRIs and media types

### 2.1 Do we need `FusekiStore`, and why HTTP and not rdflib?

- **Any adapter to a shared server is HTTP, rdflib's included.** rdflib's
  `SPARQLStore`/`SPARQLUpdateStore` call `urllib.request.urlopen`
  (`rdflib/plugins/stores/sparqlconnector.py:105-177`). The store is a server shared by every
  worker, with one TDB2 dataset per tenant (`docs/.../architecture/index.adoc:128-133`), and
  `second-store` DEC-6 and DEC-9 reject embedded stores. So "rdflib or HTTP" is a false choice.
  The real choice is whose HTTP client.
- **`fuseki.py` already uses rdflib where it helps:** `Result.parse` (`:64`), `Graph().parse`
  (`:66`) and `graph.serialize` (`:123`). The hand-written part is about 30 lines of POST/PUT and
  a status-to-error map.
- **`SPARQLUpdateStore` would cost more than it saves:**
  - It is synchronous, and the port is async (`services/store.py:249`).
  - It has no test transport, which PD-28a requires.
  - It has no Graph Store PUT, no dataset admin and no N-Quads export or import: four of the
    eight port methods.
  - Its errors are bare.
  - Its buffered add-a-triple API cannot express the guarded single-request commit
    (`services/session.py:402-430`; spec `rp-aggregate-store`).
  - Its `initBindings` rewrites query text with a regex, which its own docstring warns about
    (`sparqlstore.py:809-870`).
- **SPARQLWrapper** would replace about 20 lines (`fuseki.py:98-116`). It is synchronous, its
  last release was in 2022, and it has no Graph Store, admin or binding support. Not worth it.
- **pyoxigraph** (already installed through linkml-runtime) is a fast, standards-strict embedded
  store. It is right for tests and development, and conflicts with DEC-9 as a production adapter.
- **An rdflib store already exists:** `testkit/fakes.py:124` `FakeStore`, an rdflib `Dataset`
  per name. It passes the same conformance suite, and carries its own update splitter because
  rdflib's parser fails between 50 and 100 operations (rdflib#3710, `fakes.py:91-113`).
- **The adapter is half generic, half Fuseki:**
  - **Generic SPARQL 1.1 Protocol:** query and update POST, Graph Store PUT, result parsing.
  - **Fuseki-only:** the `/{ds}/query|update|data` layout, the `/$/datasets` admin with
    `dbType=tdb2`, and dataset-level N-Quads (`fuseki.py:29-32, 127-160`).
- **rdflib 7.6 ships RDF4J and GraphDB clients** (`rdflib/contrib/rdf4j`, `contrib/graphdb`).
  They cover repository admin, Graph Store, `transaction()` with commit and rollback, and GraphDB
  ACLs. They are synchronous. This matters for `second-store`.
- **Process gap.** The research epic's DEC-4 said "build on rdflib, pyoxigraph and the existing
  SPARQL clients; reject our own SPARQL client"
  (`archive/2026-11-05-soa-python-rdf-orm/proposal.md:37-43`). The foundation epic then built its
  own httpx client. The reasons were good (the list above), but they were never recorded as a
  decision superseding DEC-4.

### 2.2 Media types

- **Scattered:**
  - `domain/media.py:3-13`: 5 types, `REPRESENTATIONS` and 3 header names.
  - `fuseki.py:25-27, 35`: SPARQL protocol types and the rdflib names `"json"`, `"turtle"`.
  - `entrypoints/negotiation.py:19-27`: `text/event-stream` and header names.
  - `services/documents.py:54`: a literal `"application/n-quads"` that duplicates `N_QUADS`.
  - `services/documents.py:302, 462`: the literals `"nt"` and `"turtle"`.
  - `services/loading.py:14-19`: a format-name map.
- **Libraries already know most of them.** rdflib accepts media types directly as format names:
  `text/turtle`, `application/n-quads`, `application/ld+json`, `application/n-triples`,
  `application/rdf+xml` and `application/trig` all work for parse and serialise, and
  `rdflib.util.FORMAT_MIMETYPE_MAP` maps them. pyoxigraph has `RdfFormat.media_type`. No library
  has the SPARQL request types (`application/sparql-query`, `application/sparql-update`). No
  stdlib or Starlette module has header-name constants (`http.HTTPStatus` and `HTTPMethod` are
  already used). Stdlib `mimetypes` does not know `.ttl` or `.jsonld`.
- **A LinkML enum already exists:** `RdfFormat` (`model/rp_files.yaml:95-114`), with `meaning:
  formats:*`. The media type is only in the free-text description. Putting it on each value as
  an annotation, read through SchemaView like `services/vocabulary.py`, makes the contract formats
  (load, answer, OpenAPI) model data. Header names and SPARQL protocol types are protocol
  constants and stay in Python.
- **"Could be more."** Responses offer JSON, JSON-LD and Turtle; loading accepts four formats.
  Adding N-Triples, TriG or RDF/XML output is cheap with rdflib. That is a product decision.

### 2.3 IRIs (`domain/iris.py`, 793 lines)

- **Already reused:** `URIRef` everywhere, and `urllib.parse.quote` (`:696-702`). There is no
  hand-rolled `urljoin`, `compute_qname` or `Namespace` logic. Predicate IRIs come from the
  metamodel (`services/vocabulary.py`), so `rdflib.Namespace` has nothing to replace.
- **The policy templates already exist, in LinkML:** `IriPolicy`
  (`model/service/rp_service.yaml:97-116`, patterns at `:592-628`), filled with `str.format`
  (`iris.py:605-608`). `_compile` (`:325-340`) turns a template back into a regex with named
  groups, which powers `is_aggregate`, `tenant_of_access` and similar (`:710-781`).
- **RFC 6570 libraries do not fit.** `uri-template` and `uritemplate` only expand templates; they
  cannot match an IRI back to its variables. Simple expansion would also percent-encode the `/`
  inside `{root}`, which changes the stored policy syntax that `iri_policy_guard.py` protects. The
  `iri-policy` epic recorded "a template language" as a no-go
  (`archive/2026-11-08-iri-policy/proposal.md:88-89`).
- **Room to trim:** the module-level wrappers (`iris.py:57-205`) only delegate to
  `DEFAULT_IRIS`. They predate the policy and can be retired in favour of `Iris` instances.

### 2.4 SPARQL (`domain/sparql.py`) and `SparqlTerm`

- **What it is:**
  - `term()` escapes one IRI, literal or blank node (`:59-76`).
  - `fill()` and `fragment()` substitute `$name` placeholders and accept only `SparqlTerm`
    values (`:79-98`).
  - A few builders: `join`, `union`, `values`, `order_by`.
  - `checked_group` validates untrusted migration patterns on **rdflib's own parse tree**
    (`:192-272`).
- **Why not rdflib's `n3()`?** Tested on rdflib 7.6.0:
  - **Injection:** a literal's datatype IRI is not checked.
    `Literal("x", datatype=URIRef("http://e/d>x")).n3()` gives `"x"^^<http://e/d>x>`.
  - **Injection:** blank-node labels are not checked. `BNode("a b").n3()` gives `_:a b`.
  - **Corruption:** SPARQL expands `\u` escapes before parsing, so a value containing
    backslash-u comes back changed. The conformance case
    `a_literal_with_codepoint_escape_text_is_stored_as_sent` (`store_conformance.py:83`) pins this.
  - **Raw control characters** pass through unescaped.
- **Why not `initBindings` or SPARQLWrapper?** Bindings are algebra-level and in-process only.
  For a remote store rdflib turns them back into text with the same `n3()`. Bindings also cannot
  fill a `GRAPH` name in `INSERT DATA`, a `LIMIT` or a `VALUES` list. SPARQLWrapper has no
  binding at all.
- **`SparqlTerm` is needed.** It is a marker `str` subclass that lets `fill()` refuse raw strings
  at run time. It makes the spec requirement "SPARQL is never built by concatenating input"
  checkable (`rp-aggregate-store/spec.md:28-35`; PD-3). About 140 uses, 138 of them in
  `session.py`. No library has it.

## 3. HTTP surface: negotiation, OpenAPI and logging

### 3.1 `negotiation.py`: are the keywords defined elsewhere, and is there a library?

- **What it is.** About 60 lines of hand-written `Accept` parsing: q-values, specificity, ties to
  the first offered type (`entrypoints/negotiation.py:42-91`). Wrappers raise `NotAcceptable`
  (`:93-114`). ETag and If-Match helpers sit at `:126-140`. The rest is header-name constants
  (`:18-31`).
- **The keywords are mostly not defined elsewhere:**
  - Stdlib `http` has only `HTTPStatus` and `HTTPMethod`, and both are already used.
  - Starlette and FastAPI have no header-name constants and no Accept negotiation.
  - FastAPI does have `EventSourceResponse.media_type` (`fastapi/sse.py:33`), which can replace
    our `EVENT_STREAM`.
  - Only `aiohttp.hdrs` has a full header set, which is not worth a dependency.
  - rdflib registers media types as format names (§2.2).
- **There is a mature library for the parsing: `python-mimeparse` 2.0** (falconry, 2024, pure
  Python, no dependencies). Its `best_match(supported, header)` does q-values, wildcards and
  parameter fitness, and would replace about 50 lines. Points to pin with the existing
  `tests/unit/entrypoints/test_negotiation.py`:
  - no match returns `''`;
  - a malformed range raises;
  - check the tie-break order;
  - map an empty header to `*/*`.
- **Other options are worse fits:**
  - werkzeug's `MIMEAccept` is mature but brings in all of werkzeug.
  - No maintained FastAPI negotiation package was found.
  - rdflib-endpoint and Prez hand-roll their own (Prez `connegp_service.py`,
    `archive/.../analysis/prez.md:30`).
- **Correctness gaps in our code:**
  - `expected_version` (`:140`) strips `W/`, but RFC 9110 §13.1.1 says If-Match uses *strong*
    comparison.
  - It ignores `If-Match: *` and ETag lists.
  - Media-type parameters such as a JSON-LD `profile=` are ignored in matching.

### 3.2 OpenAPI: can a spec-first library (connexion) run it?

- **How the API is built now.** It is neither spec-first nor route-derived:
  - The router builds routes **at install time from the LinkML schema**
    (`entrypoints/router.py:337-420`), and the spec requires it: "no generated routes … a new
    class + restart serves it" (`openspec/specs/rp-service-api/spec.md:5-17`).
  - Component schemas are generated from LinkML (`generation/components.py`).
  - `openapi.py` (546 lines) writes each operation as typed `fastapi.openapi.models` objects: the
    error matrix to problem responses (`:225-256`), the ETag, If-Match and Location headers
    (`:159-182`), one filter per listable slot (`:391-407`), and the tenant routes (`:272-388`).
  - It also carries two workarounds, for `openapi-typescript` (`:493`) and FastAPI's OpenAPI 3.2
    `itemSchema` (`:509`).
  - Already decided: "our own hook" (`docs/.../architecture/open-decisions.adoc:41-43`).
    linkml-openapi was spiked and rejected (`architecture/api.adoc:423-441`). Connexion was never
    evaluated.
- **Connexion 3 (3.3.0) does not fit:**
  1. It lacks full OpenAPI 3.1 support (issue #1396; listed as unfunded), and our document is 3.1.
  2. Wrapping FastAPI with `ConnexionMiddleware` gives two routing tables. Dropping FastAPI loses
     `Depends` (the whole access gate, `auth.py`), `fastapi.sse` and native telemetry.
  3. Its security is scheme- and scope-level. Our check is per tenant and aggregate from path
     parameters (`auth.py:269-287`), so it stays our code.
  4. Its request validation is JSON Schema, while ours is SHACL on JSON-LD. It would duplicate
     validation, or be wrong for JSON-LD.
  5. It wants a spec at start-up. We would still have to *produce* that spec from LinkML, which is
     exactly what `openapi.py` does, so nothing is saved.
  6. It adds werkzeug, requests, jinja2 and more, and is maintained mostly by one person.
- **Alternatives:**
  - **openapi-core 0.23** pins `fastapi<0.140` and `starlette<1.1`, which cannot be installed with
    our pins, and it duplicates validation.
  - **fastapi-code-generator, datamodel-code-generator and openapi-python-generator** generate
    one-shot code from a static spec, which conflicts with "no generated routes". This was
    rejected before (`archive/.../analysis/angle-codegen.md:369`).
  - **apispec** adds nothing to FastAPI's builder.
- **Verdict.** Keep FastAPI with the spec generated from the schema. Make `openapi.py` more
  spec-driven: turn the error matrix and the operation templates into model data. Add
  **schemathesis**, already a reuse candidate (`docs/.../background/soa/building-blocks.adoc:115`),
  as a contract fuzzer against `/openapi.json`. That gives the guarantee spec-first promises, that
  the implementation obeys the spec, without a runtime framework.

### 3.3 Logging and OpenTelemetry

- **Inventory:**
  - Module loggers in 15 modules, named `log`, except `logger` in `adapters/redis_events.py:25`.
  - No handler configuration, which is correct for a library.
  - `print` only in the CLI.
  - **No OpenTelemetry spans anywhere**, although a "store port OTel decorator" was planned as
    BL-5 (`archive/2026-11-05-soa-python-rdf-orm/architecture/realisation-matrix.md:203,373`).
- **Two styles are mixed:**
  - **Structured:** a constant message plus `extra={...}`, in `tenancy.py:940`, `sweep.py`,
    `migration_runner.py`, `file_removal.py`, `tenant_dump.py:120` and `iri_policy_guard.py`.
  - **Interpolated:** identifiers in the message, no attributes, in `kit.py:229-279`,
    `relay.py:152-202`, `messagebus.py:141-198`, `session.py:1509,1553`, `fuseki.py:56`,
    `zitadel.py:147`, `s3.py:57` and `redis_events.py`. These bodies cannot be queried.
- **Defects:**
  - **Pre-formatted messages:** an f-string in `iri_policy_guard.py:62`, and
    `log.error(str(error))` in `migration_runner.py:67,98`.
  - **Logged and raised twice:** `messagebus.py:150` logs and raises, then `kit.py:279` logs the
    same error again.
  - **Ad hoc attribute keys** (`step`, `tenant`, `resource`, `database`, `schema`, `migration`) that
    follow no semantic convention. Tests assert on them, e.g.
    `tests/unit/services/test_migration_runner.py:351-392`.
- **Available without new dependencies.** `opentelemetry-api` 1.45 is already installed through
  FastAPI 0.162. FastAPI 0.162 has native telemetry (`FastAPI(telemetry=...)`): HTTP server spans,
  metrics, and logs of validation failures, using the global providers the application configures.
- **OpenTelemetry-aligned practice for a library:**
  - Stdlib `logging` with module loggers, never configuring handlers.
  - A constant, low-cardinality message with attributes in `extra=`, and `exc_info=` on failures,
    so the application's logging bridge maps them and adds `trace_id` and `span_id`.
  - Attribute names from the semantic conventions where they exist: `db.system.name`,
    `db.namespace`, `db.operation.name`, `server.address`, `error.type`, `messaging.*`.
    Otherwise an `rp.*` namespace: `rp.tenant.id`, `rp.step`, `rp.migration`.
  - Log or raise, not both.
  - Spans only through `opentelemetry-api`, never the SDK. They are no-ops until the application
    installs a provider.

## 4. Re-reading the research epic

**Sources read in full:**

- `archive/2026-11-05-soa-python-rdf-orm/` (proposal, landscape scan, candidate ADRs, realisation
  matrix)
- `docs/.../background/soa/catalogue.adoc`, the register of every tool studied
- `build-vs-reuse.adoc`
- `architecture/open-decisions.adoc`

### 4.1 Verdict on "did we reinvent wheels?"

**No, at the RDF, JSON-LD, SHACL and LinkML level.** The direct dependencies are rdflib 7.6, PyLD
3.3, pySHACL, linkml-runtime 1.12 (SchemaView), pydantic, FastAPI, PyJWT, httpx and FastStream,
and the code uses them. Where the code is hand-made, it is mostly in places the research itself
marked **build**:

- the mapper
- the session and commit compiler (BL-4)
- the outbox and relay (BL-7, BL-13)
- migrations
- the ODRL subset (D-4)

The research found no Python ORM over RDF that passed its reuse bar (DEC-5: more than 200 stars and
a commit in the last 12 months). Its conclusion was "no ORM layer meets the bar → we write it"
(landscape scan §E).

### 4.2 Libraries the research considered, and where they stand

| Library | Verdict then | Now |
|---|---|---|
| rdflib | adopt (DEC-4) | direct dependency, used throughout |
| pyoxigraph / oxrdflib | adopt for dev and test | pyoxigraph only transitive; the fake uses rdflib |
| SPARQLWrapper, rdflib `SPARQLUpdateStore` | client of choice (DEC-4) | **not used**: own httpx client, no decision recorded (§2.1) |
| rdflib `contrib.rdf4j`, `contrib.graphdb` | adopt | not used yet; relevant to `second-store` |
| LinkML, linkml-runtime | adopt; loader and dumper as "ideas for the mapper" | direct; the mapper is ours (§4.3) |
| PyLD | dependency, "framing on the server" | direct; used for expand, to_rdf, from_rdf and frame |
| pySHACL | dependency | direct |
| ~14 Python RDF ORMs (sparqlmodel, SuRF, RDFAlchemy, pydantic-rdf…) | ideas only, all below DEC-5 | none |
| pyLDAPI | none, "superseded by Prez" (cat:848-853) | none; Flask era, stale |
| Prez | ideas: typed SPARQL AST, negotiation by profile | none |
| rdflib-endpoint | ideas; fails DEC-5 | none |
| rdflib-web | not catalogued; dead (2017, Python 2) | none |
| **LDES / TREE** | **never considered**; appears nowhere in `openspec/` or `docs/` | none |
| OpenFGA, pycasbin | integrate (DEC-8, DEC-26) | replaced by our own ODRL subset (D-4); OpenFGA reopens in `fine-grained-access` |
| schemathesis, OpenTelemetry instrumentations | adopt / dependency | **never adopted**; BL-5 (store-port tracing) not built |
| FastStream | not in the research | chosen after a spike in `aggregate-events` |

### 4.3 Overlaps found, per library

1. **JSON-LD is parsed two ways.**
   - `services/documents.py` uses PyLD (`expand`, `to_rdf`, `from_rdf`, `frame`) with a loader
     that refuses remote contexts (`:63-68`).
   - `services/loading.py:26-62` parses JSON-LD with rdflib's `json-ld` plugin, plus its own
     recursive remote-context guard `_refers_outside`.

   One behaviour, through PyLD and the same refusing loader, would drop about 30 lines and one
   inconsistency. PyLD stays because rdflib cannot frame.
2. **Defect, confirmed by reading.** `documents.dataset_of` (`services/documents.py:78-84`)
   re-encodes rdflib triples for PyLD, to work around a PyLD 3.3.0 N-Quads backslash bug. Its
   literal branch emits `value` and `datatype` but never `language`, so a language-tagged literal
   leaves as `xsd:string` and loses its tag. LangString support (DEC-35) is not built yet, which
   is probably why no test caught it. It will surface when that support lands.
3. **The mapper and linkml-runtime's `rdflib_loader`/`rdflib_dumper`.** Keep the mapper, but its
   docstring gives the wrong reason (`services/mapper.py:7-10`). It says they take only LinkML
   dataclasses, but they accept `BaseModel`. The true reasons:
   - the loader needs `class_class_uri`, and our generated classes strip `linkml_meta`;
   - the dumper writes blank nodes where we need skolem or part IRIs;
   - neither writes language tags;
   - neither knows owned, bookkeeping or internal slots.

   Re-check this against the pinned 1.12.1 before rewriting the docstring.
4. **CURIEs.** The mapper says "CURIEs are not expanded" (`mapper.py:19-20`). If they ever are,
   use `SchemaView.expand_curie` or `curies` (already installed), not new code.
5. **LDES.** The event feed is push with bounded catch-up: outbox, relay to Redis Streams, SSE
   with `Last-Event-ID` inside a 7-day window, then `event: reset`. There is no LDES-shaped pull
   feed. Python has no mature LDES library; the ecosystem is Java (VSDS LDI) and TypeScript. So
   LDES would be *honoured as a specification*, not taken as a dependency. An LDES view over the
   provenance graph is a sound optional read route for harvesters and replication, and fits EU and
   SEMIC consumers. It is a gap in the research, not a wheel we rebuilt.
6. **Small and justified:**
   - `session._skolemised` (`session.py:344-354`) against `Graph.skolemize`: ours must mint a
     fresh UUID per write, and a test requires it.

### 4.4 Decisions: in force, and drifted

- **In force; respect them:**
  - DEC-4: no own RDF model, parser or store.
  - DEC-5: the reuse bar.
  - DEC-16: classic W3C stores.
  - DEC-17: the UI never reaches the store.
  - DEC-19 and D-13: LinkML is the single source.
  - DEC-20 and DEC-29: one graph per aggregate.
  - DEC-21: strict commit.
  - DEC-23: in-process bus with outbox and relay.
  - DEC-34, DEC-35 and DEC-37: no hand-written domain classes.
  - DEC-38: async only.
- **Drifted:**
  - **DEC-4's client clause:** replaced in practice by the httpx adapter, with no record.
  - **DEC-8 and DEC-26:** replaced by D-4.
  - **DEC-27:** promised N-Triples by negotiation; D-1 narrowed it to JSON, JSON-LD and Turtle.
  - **BL-5 (OpenTelemetry) and schemathesis:** planned, never adopted.
  - **pyoxigraph as test store:** deferred.

## 5. Constants, dicts, structure and generators

### 5.1 Constants and parameter management

- **Size.** There are about 536 module-level UPPER_CASE assignments outside generated code. Most
  sit in `services/vocabulary.py` (63), `session.py` (44), `domain/iris.py` (30) and
  `entrypoints/problems.py` (23).
- **Classification.** You were right that not all of them should move:

  | Class | Count | Examples | Where it belongs |
  |---|---|---|---|
  | Protocol and vocabulary, fixed by design | ~500 | RDF and vocabulary IRIs, SPARQL text, header names, problem slugs, Zitadel and OIDC paths, S3 error codes | next to its use |
  | Diagnostic truncation and algorithm guards | ~7 | `yaml_files.py:14-15`, `documents.py:57`, `iris.py:253`, `tenancy.py:87` (PD-5), `s3.py:32` (the S3 maximum of 1000) | next to its use |
  | **Deployment and tuning parameters** | **~27 values at 15 sites** | listed below | **one central settings model** |
  | Test-only | 6 | `testkit/bootstrap.py:14-15`, `testkit/tokens.py:24` | testkit |

- **The deployment and tuning parameters, all of them:**

  | Parameter | Site | Value | Supplied today |
  |---|---|---|---|
  | HTTP connect and read timeouts | `adapters/_http.py:17-18` | 5 s, 30 s | hard-coded |
  | S3 timeouts and attempts | `adapters/s3.py:33` | 5 s, 30 s, 3 | hard-coded, **a second copy** of the HTTP timeouts |
  | JWKS TTL, unknown-`kid` cooldown, algorithm allow-list | `adapters/jwks.py:26,29,32` | 600 s, 10 s, RS256/ES256 | hard-coded |
  | Zitadel page size | `adapters/zitadel.py:43` | 100 | hard-coded |
  | Redis polling interval | `adapters/redis_events.py:27` | 100 ms | hard-coded |
  | Redis stream, retention, claim idle | `adapters/redis_events.py:37-39` | `rp-events`, 7 d, 30 s | constructor defaults |
  | SSE lifetime, access TTL, keep-alive, resume window | `entrypoints/sse.py:36-39` | 5 min, 1 s, 15 s, 7 d | module constants as keyword defaults |
  | Relay interval, publish timeout | `services/relay.py:90-91` | 5 s, 10 s | constructor defaults |
  | Event hub queue | `services/event_hub.py:28` | 1000 | constructor default |
  | Message-bus limit | `services/messagebus.py:109,266` | 100 | parameter default |
  | Roots per commit | `services/mapper.py:291` | 500 | `Mapper(max_roots=)` default |
  | Nodes per document | `services/documents.py:59` | 10 000 | hard-coded |
  | Dump manifest size | `services/tenant_dump.py:51` | 64 KiB | hard-coded |
  | Body and restore size | `model/service/rp_service.yaml:44-47` | 1 MiB, 1 GiB | **already** in the generated `ServiceSettings` |

- **Latent bug, confirmed.** `reference_collections.py:266` checks against the module constant
  `DEFAULT_MAX_ROOTS`, not the mapper's configured `max_roots`. A consumer who sets `max_roots`
  gets a different limit on reference collections.
- **How settings reach the library today.**
  - There are **no environment reads** in the library; `os.environ` appears only in the testkit.
  - There is no dotenv and no settings class.
  - Three routes exist:
    1. the LinkML-generated `ServiceSettings` passed into `ServiceKit(settings=…)`
       (`entrypoints/kit.py:104,154`);
    2. constructor defaults;
    3. hard-coded module constants.
  - The consumer's composition root already builds every adapter, so the wiring point exists.
- **ted-sws:**
  - `ted_sws/__init__.py:20` calls `dotenv.load_dotenv` **at import** and writes `os.environ` at
    `:25-28`.
  - Per-area mixins (`MongoDBConfig :39`, `FusekiConfig :170`, …) declare one `@env_property()`
    method per variable, aggregated into `TedConfigResolver` and a singleton `config`.
  - The resolvers in `core/adapters/config_resolver.py` are `Env`, `Airflow`, `AirflowAndEnv`,
    `Vault` and `VaultAndEnv`. `env_property` (`:122-137`) resolves the value **on every access**.
- **mapping-suite-sdk:**
  - The same `env_property` mechanism (`core/adapters/config_resolver.py`), with
    `EnvConfigResolver` and `DefaultValueConfigResolver` (`:32-38`, which ignores the
    environment).
  - Areas are grouped per package (`core/config.py:14-61`, `mapping_package_v3/__init__.py:7-26`)
    and aggregated in `mapping_suite_sdk/config.py:15-29` as `mssdk_config`.
  - It does **not** load dotenv at import. In practice it is one central defaults registry that
    can be switched to the environment per property.
- **Fit for a library.** The MSSDK shape fits: one central registry of defaults, grouped by area.
  The ted-sws shape does not: a library must not load `.env` or write `os.environ` when imported,
  because that reaches into the host application. `env_property` also re-reads on every access
  and does not validate. This repository already has a better primitive: settings as a
  LinkML-generated model (`ServiceSettings`), validated once. `pydantic-settings` is installed
  transitively (`uv.lock:2134`) and could give an opt-in `from_env()` bridge if declared.

### 5.2 Dicts with bare keys

- **Line 126.** `_held_around` (`services/unique_keys.py:120-132`) returns
  `{"values", "registry", "p_kind", "aggregate", "p_owned_by", "excluded", **extra}`. These are
  the `$placeholder` names of the SPARQL template `KEY_HELD` (`:39-45`), spread into `fill()`.
  - The template's contract is restated as bare strings in a second place.
  - `fill` checks for missing or unused names, but only at run time (`domain/sparql.py:89-92`).
  - The same registry bundle (registry, kind, owned-by, aggregate) is rebuilt by hand in
    `session.py:434-439` and `listing.py:281-293`. The latter needs `**{"class": …}` because
    `class` is a keyword.

  It is a concept with no name.
- **Sweep.**
  - About 150 dict-literal lines with string keys. 47 of them are the lazy-import name→module
    maps in `__init__.py:169` and `testkit/__init__.py:43`, which are an index, not a concept.
  - About 50 `dict[...]` annotations, mostly typed lookup indexes, which are fine.
  - About 45 string subscripts or `.get("…")` calls.
- **Classification:**

  | Class | Sites | Examples |
  |---|---|---|
  | **Concept-carrying, should be a model** | **~30 in ~14 files** | see the next list |
  | Legitimate boundary: the shape a library demands | ~70 | boto3 (`s3.py:82-154`), PyJWT options (`jwks.py:117-121`), PyLD options, httpx kwargs, OpenAPI, JSON Schema and JSON-LD documents, SPARQL result rows, regex `groupdict`, raw TOML or YAML validated at once |
  | Generic by design | ~8 | `mapper.py:226` (slot-keyed data over any schema), typed caches |

- **Concept-carrying sites:**
  1. **SPARQL term bundles:** `unique_keys.py:120-132`, `session.py:434-439`,
     `listing.py:281-293`, `migrations.py:242-247`. One shared `RegistryTerms`, and one term
     model per template.
  2. **`model_copy(update={…})` with bare field names, 8 sites:**
     - `provenance.py:169-175`
     - `transitions.py:195-200, 239-240`
     - `visible_part.py:31`
     - `discussion.py:289`
     - `iris.py:74, 263, 279-288`

     `model_copy` **skips validation**, so a mistyped key is silently ignored or produces an
     invalid model. Build the model with keyword arguments instead.
  3. **IRI template variables:** `{"base", "deployment", "tenant_segment"}` is built twice
     (`iris.py:274-278` and `:417-421`), and its regex groups are read back by string
     (`iris.py:454-461, 636-747`, e.g. `found["tenant_id"]`). They should be an
     `IriTemplateVariables` model and a parsed `IriParts` model.
  4. **`migration_runner.py:156-162`:** `_failure()` returns `dict[str, str]`.
  5. **The log-attribute set:** about 18 `extra={"step", "tenant", "resource", …}` sites share
     one de facto schema (§3.3). `extra=` is the logging API, but the repeated key set is a
     concept.
  6. **testkit:**
     - JWT claims built by bare keys (`testkit/tokens.py:86-92`) while a claims model exists;
     - `model_shape.py:67`;
     - `conformance.py:53-54`.
  7. **`generation/config.py:20` `FIELD_OF_TOML_KEY`:** aliases belong on the generated model.
- **Generated or hand-written?** The IRI variables, claims and generation config are model data,
  so they belong in LinkML. The SPARQL term bundles and the log context are rendering parameters,
  not domain data. A small frozen model next to the template fits them better than a LinkML class.
  The repository principle says "generated models", so this is a decision for you (§6, open
  questions).

### 5.3 Thematic structure

**Where the models are today, and why.** There are four LinkML targets, each with its own folder
(`pyproject.toml:94-118`):

| Schema | Output package | Content |
|---|---|---|
| `model/rp.yaml`, which imports rp_core, rp_annotations, rp_provenance, rp_access, rp_tenancy, rp_files, rp_collections, rp_discussion, rp_workflow | `domain/generated` | one `.py` per module, shapes, context, 9 frames |
| `model/service/rp_service.yaml` (35 KB) | `domain/generated/service` | ServiceSettings, VerifiedCaller, Page, Problem, ListPlan, IriPolicy, Migration…; OpenAPI components |
| `model/adapters/rp_wire.yaml` (22 KB) | `adapters/generated` | Zitadel* ×28, JwtClaims, Fuseki*, DiscoveryDocument |
| `generation/model/rp_generation.yaml` (37 KB) | `generation/generated` | the generator's own records |

This was decided in the foundation epic (PD-18, `archive/2026-11-06-toolkit-v1-foundation/design.md:276-285, 468`).
Generated code goes to **the lowest layer that imports it**, and each schema needs its own folder,
because the generator clears its folder and writes a manifest per run (PD-26). So the models
were placed **by importing layer, not by theme**. The result is what you saw: `rp_service.yaml`
is a catch-all imported by 8 of the 12 themes below, and `rp_wire.yaml` mixes identity and store
wire formats.

**The sibling projects use your two-level pattern.**

- ted-sws has 18 level-1 themes (`core`, `notice_metadata_processor`, `mapping_suite_processor`,
  `notice_validator`, `event_manager`, `data_manager`, …). Each theme has its own `adapters`,
  `model`, `services` and, where it needs them, `entrypoints`. Tests mirror the themes.
- mapping-suite-sdk has `core` (adapters, `config.py`, models), `mapping_package_v1/v2/v3` and
  `mapping_suite` (adapters, models, services), and `tools` (entrypoints, services only: the
  consumption side). Its `.importlinter` has per-theme contracts.
- Both have a kernel, domain-heavy themes that others reuse, and thin consumption themes.

**A thematic map of rdf_persistence.** All 61 non-generated modules were placed by their import
graph. **The graph between themes is acyclic**, so nothing has to be redesigned, only moved.

| Order | Theme | Modules today | LinkML | Kind |
|---|---|---|---|---|
| 0 | kernel | `domain.base`, `exceptions`, `media`, `sparql`; `services.artifacts`, `yaml_files`; `adapters._http` | rp, rp_core, rp_annotations | shared kernel |
| 1 | iris | `domain.iris` | IdSpec, IriPolicy (from rp_service) | domain, reused |
| 1 | schema | `services.schema`, `schema_structure`, `vocabulary` | metamodel introspection | reused, also by the generator |
| 1 | provenance | `services.provenance`, `visible_part` | rp_provenance | domain, reused |
| 2 | persistence | `services.store` (port), `session`, `unique_keys`, `listing`, `loading`, `mapper`, `decoding`; `adapters.fuseki` | rp_core; ListPlan, Filter (rp_service); Fuseki* (rp_wire) | domain and adapters, reused |
| 3 | files | `domain.blob_keys`, `services.files` (port), `adapters.s3` | rp_files | adapters, reused |
| 3 | migrations | `services.migrations` | `model/migrations/`, Migration* | reused |
| 3 | access | `services.access`, `identity`, `tokens`; `adapters.jwks`, `zitadel` | rp_access; Zitadel*, JwtClaims (rp_wire) | domain and adapters, reused |
| 4 | tenancy | `services.tenancy`, `sweep`, `tenant_sweep`, `tenant_dump`, `migration_runner`, `iri_policy_guard`; `domain.tenant_move` | rp_tenancy | mixed |
| 5 | events | `services.events` (port), `event_hub`, `event_stream`, `relay`; `adapters.redis_events` | EventEnvelope | mixed |
| 5 | collaboration | `discussion`, `reference_collections`, `workflows`, `transitions`, `write_guards`, `collaboration` | rp_discussion, rp_collections, rp_workflow | consumption-leaning |
| 6 | messaging | `services.messagebus` | none | consumption |
| 7 | api (the service kit) | `services.aggregates`, `documents`, `file_removal`, `components`; all of `entrypoints/` | Page, Problem, OpenAPI components | consumption |

**Placements the import graph forced:**

- `aggregates` and `documents` go to api, since they are "the use cases of the generic API" and
  import tenancy.
- `migration_runner` and `tenant_dump` sit in tenancy. This matches the existing contracts
  `migrations-below-the-runner` and `tenancy-without-the-runner`.

**Layout.** `rdf_persistence/<theme>/{domain,services,adapters,entrypoints,generated}`, with
sub-layers only where a theme needs them. Import-linter would use one layers contract per theme,
plus one contract ordering the themes. The hand-maintained list of 39 modules in
`nothing-in-services-imports-the-bus` collapses to "nothing below messaging imports messaging".

**Constraints:**

- **Keep `rdf_persistence/model/rp_*.yaml` flat at that path.** MWBv2's schemas import these paths,
  and `metamodel_importmap()` globs `model/*.yaml` (`services/schema.py:18-24`), so the path is a
  public contract. The files are already one theme each, so the *generated* code can mirror themes
  without moving the schemas. `rp_service.yaml` and `rp_wire.yaml` are the ones to split.
- **The public surface stays stable.** `rdf_persistence/__init__.py` re-exports 141 names, and
  generated consumer code imports metamodel classes from the top package
  (`generation/extensions/pydantic_split.py:54`).
- **MWBv2 imports from only 5 modules:** `rdf_persistence` (33 times), `.testkit` (8),
  `.domain.base` (5), `.adapters.fuseki` (2) and `.testkit.fakes` (1). Shims for the two deep
  paths, or 7 changed imports in MWBv2, cover the move.
- **The generator needs work first.** Per-theme output needs pydantic_split to take a package per
  module rather than the hard-coded `TOOLKIT_PACKAGE` (`pydantic_split.py:55`), and the
  folder-clearing rule (PD-26) must allow it.

### 5.4 Generators as a sibling repository

- **Size.** `rdf_persistence/generation/` is about 3 950 lines:
  - cli, pipeline, steps, config, manifest;
  - lock and lock_step (migrations);
  - `checks/` (hard, rules, boundary, application);
  - `extensions/` (pydantic_split, pydantic_validators, shacl, shacl_constraints, jsonld_context,
    typescript, mermaid);
  - 10 templates and its own LinkML model.
- **Its tests:** 38 unit files (408 of the repository's 3 583 tests) and **no feature, integration
  or e2e tests**. Acceptance is "regenerate and diff" (`check-generated`, PD-19), plus mypy and
  `tsc` on the output, with golden fixtures in `tests/fixtures/library/`. That is the gap you
  sensed.
- **Packaging today:** `linkml` is a `generate` extra (PD-2), and the runtime needs only
  linkml-runtime. The contract `works-without-the-generate-extra` already separates the
  linkml-free part. MWBv2 uses `rdf-persistence[generate,testkit]` in its dev group.
- **Coupling. This is the deciding fact:**
  - **Generator → library is strong.**
    - It imports `services.schema_structure` (18 times), `services.schema` (11),
      `services.artifacts`, `services.migrations`, the metamodel's generated `rp_core` (RpAnnotation,
      ModuleKind), and `domain.base`, `iris`, `sparql`, `exceptions`.
    - Its templates emit `from rdf_persistence.domain.base import RpModel`.
    - It is a **metamodel-aware** generator, not a generic LinkML one.
  - **Library → generator:** the runtime layers have none. But the **testkit** has 8 files
    (freshness, conformance, model_shape, shape_snapshot, guards, markers, zitadel) that import
    `generation.config` or `generation.generated`, and MWBv2 imports the testkit.
- **Options:**

  | | Sibling repo | Second distribution in a uv workspace, same repo | Status quo |
  |---|---|---|---|
  | Metamodel and generator change together | 2 PRs and ordered releases | 1 PR, atomic | 1 PR |
  | Versions | independent; needs a compatibility matrix | two, released together or apart | one |
  | Test separation | full | full (`packages/<gen>/tests/{unit,feature,integration,e2e}`, own CI path filter) | mixed |
  | linkml out of the library's dependencies | yes | yes | extra only |
  | Cost | highest | medium | none |

- **Assessment.** Your goal is reliable generators that apps outside this repository can use, with
  their own full test pyramid. That is right, and a separate **distribution** delivers it. A
  separate **repository** adds one thing more, independent release cadence. It costs atomic
  changes: most generator changes are metamodel changes, as the coupling above shows. A
  workspace now, with the dependency made one-way (generator → library), makes a later move to a
  sibling repository a mechanical `git filter-repo`. This is your call; it is listed as open
  question Q-3.

## 6. Open questions for the developer

- **Q-1 Settings source.** Generate the new settings models in LinkML next to `ServiceSettings`
  (consistent with PD-24..28), or write them by hand? The recommendation is LinkML.
- **Q-2 Term bundles and log context.** These are rendering parameters, not domain data. Allow
  small hand-written frozen models next to the templates, or generate them too?
- **Q-3 Generators.** Sibling repository now, or a second distribution in this repository first,
  then a sibling once the dependency is one-way?
- **Q-4 LDES.** Add an LDES view over the provenance graph as an optional read route, as a
  separate EPIC?
- **Q-5 More representations.** Serve N-Triples, TriG or RDF/XML, as DEC-27 once promised?
- **Q-6 Post-quantum signatures.** Accept "follow the identity provider; add ML-DSA when Zitadel
  and PyJWT ship it", with TLS hybrid key exchange raised with infrastructure?
