<!-- SECONDARY INPUT: preserved, never groomed. What to keep as it is, with reasons, from analysis.md. -->

# Keep: what stays as it is, and why

These are drawn from the developer's notes ([`seed.md`](seed.md)) and the findings in
[`analysis.md`](analysis.md) (§ numbers below). Each item was checked against the mature
libraries that could replace it. It stays because the library is already underneath it, because
no library does the job, or because a library would lose something the toolkit needs. Where the
choice is not on record yet, [`improvements.md`](improvements.md) group G records it.

## Libraries already reused (nothing to adopt)

| What | Library underneath | § |
|---|---|---|
| RDF model, parsing, serialisation, result parsing, isomorphism, SPARQL parse trees | **rdflib** 7.6 | 4.3 |
| JSON-LD expand, to_rdf, from_rdf and framing; rdflib cannot frame | **PyLD** 3.3 | 4.3 |
| SHACL validation | **pySHACL** | 4.3 |
| Schema introspection and predicate IRIs | **linkml-runtime** SchemaView | 2.3, 4.3 |
| JWT header, JWK set, signature, `iss`/`aud`/required claims | **PyJWT** | 1.2 |
| HTTP | **httpx** | 1.3 |
| Service framework, SSE, telemetry hooks | **FastAPI** | 3.2 |
| Event bus on Redis Streams | **FastStream** | 4.2 |

## Hand-written code that stays

| Keep | Why | § |
|---|---|---|
| **`domain/sparql.py`: `term()`, `fill()`, `SparqlTerm`** | rdflib's `n3()` has two injection holes (an unchecked datatype IRI and blank-node label) and corrupts `\u` text; tested on 7.6.0. `initBindings` renders through the same `n3()` for remote stores and cannot bind graph names, `LIMIT` or `VALUES`. SPARQLWrapper has no binding at all. `SparqlTerm` is what makes "SPARQL is never built by concatenating input" checkable (spec `rp-aggregate-store`, PD-3). No library has it | 2.4 |
| **`checked_group`** | Already reuses rdflib's parser; it is the only safe gate for untrusted migration patterns | 2.4 |
| **An HTTP store adapter (`FusekiStore`)** | Every adapter to a shared server is HTTP, rdflib's included. `SPARQLUpdateStore` and SPARQLWrapper are synchronous, have no test transport, cover 4 of the 8 port methods, and cannot express the guarded single-request commit. The adapter already uses rdflib for every parse and serialise. It gets split, not replaced (improvements E-5) | 2.1 |
| **The `Store` port** | The `ToolkitStore` wrapper turns a refused toolkit-built query into an internal error; no library offers that | 2.1 |
| **`FakeStore` as the in-memory store** | It *is* the rdflib store the developer asked about, used where it fits: tests and development. Only its engine (rdflib or pyoxigraph) is open (improvements B-7) | 2.1 |
| **`_http.py`** | A 74-line base over httpx, not a client: timeouts, the test transport and error mapping in one place for three adapters (PD-28a). Without it, the same code appears three times | 1.3 |
| **`jwks.py` cache and discovery layer** | About 60 lines: an async single-flight cache, an outage-safe cooldown keyed on the last attempt, OIDC discovery with issuer match, an https guard, clock and transport injection for the testkit IdP. `PyJWKClient` is synchronous urllib (it blocks the event loop) and has neither discovery nor injection. joserfc and authlib have no async JWKS client either | 1.2 |
| **`domain/iris.py` templates and matching** | It is policy, not URI plumbing. The templates already live in LinkML (`IriPolicy`), are filled by `str.format`, and are matched back by compiled regexes. RFC 6570 libraries only expand, never match, and would change the stored policy syntax. A template language is a recorded no-go (`iri-policy` EPIC). rdflib `Namespace` does a different job (CURIEs) | 2.3 |
| **The runtime generic router** | The spec requires "no generated routes; a new class + restart serves it" (`rp-service-api`). Connexion, openapi-core and the code generators all assume a static spec or one-shot code | 3.2 |
| **FastAPI, not connexion** | Connexion lacks full OpenAPI 3.1, would double the routing, has scheme-level security only (our check is per tenant and aggregate), and validates JSON Schema while ours is SHACL. openapi-core pins below our FastAPI and Starlette. We would still have to produce the spec from LinkML, which is what `openapi.py` does | 3.2 |
| **Generated OpenAPI components and the install hook**, with `_inline_property_refs` and `_without_item_schemas` | The components come from LinkML. linkml-openapi was spiked and rejected. The two workarounds target `openapi-typescript` and FastAPI's 3.2 `itemSchema`; no library does either | 3.2 |
| **`problems.py` (RFC 9457)** | Small and data-driven. No mature FastAPI problem+json library covers the error matrix plus the detail-redaction policy (PD-15) | 3.2 |
| **`request_media_type`, `etag_of`, `limited_body`** | Trivial or bespoke (a streamed size limit); a library would not shrink them | 3.1 |
| **`services/mapper.py`** | linkml-runtime's loader needs `class_class_uri` (our classes strip `linkml_meta`). Its dumper writes blank nodes where we need skolem or part IRIs, writes no language tags, and knows no owned, bookkeeping or internal slots. The research marked the mapper "build". Only its docstring's reason needs correcting (improvements G-4) | 4.3 |
| **ODRL subset evaluation (`services/access.py`)** | Python has no mature ODRL evaluator; ODRL-Evaluator is JavaScript and fails DEC-5. Decided by D-4. OpenFGA reopens in `fine-grained-access` | 4.3 |
| **The outbox, relay and event hub; `session._skolemised`** | Build items the research planned (BL-7, BL-13). The skolemiser must mint a fresh UUID per write, unlike `Graph.skolemize` | 4.3 |
| **Live event delivery over SSE** | Push with bounded catch-up is what live clients need. An LDES pull view would be an *addition*, not a replacement (improvements H) | 4.3 |
| **stdlib `logging` with module loggers and no handler configuration** | Already the correct library posture under OpenTelemetry; only the style and attribute names change (improvements D-3) | 3.3 |

## Constants that stay where they are

| Keep | Why | § |
|---|---|---|
| **The Zitadel path slugs, the org header and the claim and scope URNs** (`zitadel.py:35-42`) | Fixed by the Zitadel API, as the developer suspected. Deployment values (issuer, token, organisation, project) are already constructor arguments | 1.4 |
| **About 500 protocol and vocabulary constants**: vocabulary IRIs (`vocabulary.py`), SPARQL text (`session.py`), header names (`negotiation.py`), problem slugs (`problems.py`), OIDC names (`jwks.py:31-37`), S3 error codes and facts (`s3.py:29-32`), Fuseki endpoint names | Part of the contract, not variables. Next to their use they read best | 5.1 |
| **Diagnostic truncations and algorithm guards** (`SHOWN`, `MOST_PROBLEMS`, `MAX_MESSAGES`, `MAX_ERROR`, `_MAX_RESERVED_REDRAWS`, `MAX_TENANT_CLASH_DRAWS` per PD-5) | Not deployment knobs | 5.1 |
| **Header names and SPARQL protocol media types as Python constants** | No stdlib or Starlette module defines them. `aiohttp.hdrs` is not worth a dependency. They are protocol keywords, not model data | 2.2, 3.1 |
| **`listing.py:50` `PAGE`** | Already derived from the generated model | 5.1 |

## Dicts that stay

| Keep | Why | § |
|---|---|---|
| Dicts at a library boundary: boto3, PyJWT and PyLD options, httpx kwargs, OpenAPI, JSON Schema and JSON-LD documents, SPARQL result rows, regex `groupdict`, raw TOML or YAML validated at once | That is the shape the library demands; wrapping it in a model only moves the dict | 5.2 |
| The lazy-import name→module maps (`__init__.py:169`, `testkit/__init__.py:43`) | An index, not a concept | 5.2 |
| `mapper.py:226` and other schema-keyed generic maps | Generic over any LinkML schema by design | 5.2 |

## Structure and generation that stay

| Keep | Why | § |
|---|---|---|
| **`rdf_persistence/model/rp_*.yaml` flat at that path** | MWBv2's schemas import these paths, and `metamodel_importmap()` globs them, so they are public contract. They are already one theme each; the *generated* code mirrors the themes | 5.3 |
| **The 141-name public re-export** in `rdf_persistence/__init__.py` | The stability lever for consumer code, both hand-written and generated, through any move | 5.3 |
| **Committed generated code with `check-generated` and `check-freshness`** | Makes the bootstrap safe (the library's models are generated by its own generator) whether the generator moves or not | 5.4 |
| **linkml out of the runtime** (PD-2) and the `works-without-the-generate-extra` contract | The runtime needs only linkml-runtime | 5.4 |
| **The fine-grained import contracts** (`collaboration-layers`, `migrations-below-the-runner`, `tenancy-without-the-runner`) | They map cleanly inside the new tenancy, collaboration and messaging themes | 5.3 |
| **HMAC (HS*) refused, no liboqs** | HS* would hand the provider's signing secret to every verifier. pyca `cryptography` already has ML-DSA for when the IdP supports it | 1.1 |
