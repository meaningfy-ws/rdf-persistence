<!-- SECONDARY INPUT: preserved, never groomed. Proposed changes from analysis.md; the EPIC will shape them. -->

# Improvements: what to change, and why

These are drawn from the developer's notes ([`seed.md`](seed.md)) and the findings in
[`analysis.md`](analysis.md) (§ numbers below). The rule throughout: **reuse what is mature and
used; build well only what does not exist.** The items are grouped by size. Each says what
changes, why, and what it depends on. They are candidates for the EPIC to shape, not a PLAN.

## A. Defects found (fix first, small)

| # | Change | Why | § |
|---|---|---|---|
| A-1 | `documents.dataset_of` emits `language` (and `rdf:langString`) for language-tagged literals | It drops the tag today, so a language-tagged literal becomes `xsd:string`. It will bite when LangString (DEC-35) lands | 4.3 |
| A-2 | `reference_collections.py:266` uses the mapper's configured `max_roots`, not `DEFAULT_MAX_ROOTS` | A consumer's `max_roots` is ignored for reference collections | 5.1 |
| A-3 | The JWT algorithm allow-list becomes a parameter. Default: RS/PS/ES 256-512 and EdDSA. Always refuse `none` and HS* | Switching Zitadel's web key to anything but RS256 or ES256 refuses every token (401 outage) | 1.1 |
| A-4 | Add `leeway_seconds` (default about 30 s) to the `exp`/`nbf` check in `jwks.py:133-136` | There is zero clock-skew tolerance today; host and IdP drift causes spurious 401s | 1.2 |
| A-5 | `If-Match` uses strong comparison, accepts `*` and accepts ETag lists (RFC 9110 §13.1.1) | `expected_version` strips `W/` and ignores `*` and lists (`negotiation.py:140`) | 3.1 |
| A-6 | Build models with keyword arguments instead of `model_copy(update={...})` with bare field names (8 sites) | `model_copy` skips validation, so a misspelt key is silently ignored or leaves an invalid model | 5.2 |
| A-7 | Remove the duplicate ERROR log of `MessageLimitExceeded` (`messagebus.py:150` and `kit.py:279`) | Logged twice for one failure | 3.3 |

## B. Reuse: replace hand-written code with a mature library

| # | Change | Library | Why | § |
|---|---|---|---|---|
| B-1 | Replace the Accept parsing in `negotiation.py` (about 50 lines) with `mimeparse.best_match`; keep the thin wrappers that raise `NotAcceptable` | **python-mimeparse** 2.0 (falconry; pure Python, no dependencies) | Mature and small, and it handles media-type parameters (e.g. a JSON-LD `profile=`) that ours ignores. The existing negotiation tests guard the swap | 3.1 |
| B-2 | Route loaded JSON-LD through PyLD `to_rdf` with the same refusing document loader; delete `loading._refers_outside` | **PyLD** (already a dependency) | One JSON-LD behaviour across the toolkit instead of two parsers with two remote-context guards; about 30 lines fewer | 4.3 |
| B-3 | Pass media types straight to rdflib `parse`/`serialize(format=...)`. Delete `RDFLIB_JSON`/`RDFLIB_TURTLE` (`fuseki.py:35`), `_RDFLIB_FORMATS` (`loading.py:14-19`) and the `"nt"`/`"turtle"` literals (`documents.py:302,462`). Use `EventSourceResponse.media_type` for SSE | **rdflib**, **FastAPI** (already dependencies) | rdflib registers media types as format names; `tenant_dump.py:321` already does this. It removes a second, parallel keyword set | 2.2, 3.1 |
| B-4 | Add `opentelemetry-api` spans around the Store port, `Session.commit`, migrations, sweep, relay rounds and bus handlers. Declare the dependency explicitly. Document the application-side set-up: the SDK, FastAPI native telemetry, `opentelemetry-instrumentation-httpx`, FastStream's OTel middleware and the logging bridge | **opentelemetry-api** (already installed through FastAPI) | BL-5 was planned and never built. Spans are no-ops until the application installs a provider, which is the correct library posture | 3.3 |
| B-5 | Add **schemathesis** contract tests against `/openapi.json` | **schemathesis** (a reuse candidate already, `building-blocks.adoc:115`) | Gives the guarantee "spec-first" promises, that the implementation obeys the spec, without a runtime framework that cannot run our dynamic routes | 3.2 |
| B-6 | For `second-store` (GraphDB), evaluate rdflib's `contrib.graphdb` / `contrib.rdf4j` clients before writing a raw-HTTP adapter | **rdflib** contrib (already installed) | They cover repository admin, Graph Store, `transaction()` and ACLs. They are synchronous, so they would run in a worker thread like boto3 | 2.1 |
| B-7 | Consider pyoxigraph as the engine of the testkit `FakeStore` (test and dev only) | **pyoxigraph** (installed through linkml-runtime; declare it if adopted) | Standards-strict, atomic multi-operation updates, faster; removes the rdflib#3710 update splitter. Results still have to be returned as rdflib types | 2.1 |
| B-8 | An optional `from_env()` bridge for settings, opt-in, never at import | **pydantic-settings** (transitive; declare it if adopted) | ted-sws/MSSDK-style environment resolution, validated once, without import-time side effects | 5.1 |

## C. Constants and parameters

| # | Change | Why | § |
|---|---|---|---|
| C-1 | One central settings home, grouped by area (`HttpSettings`, `JwksSettings`, `EventSettings`, `SseSettings`, `LimitSettings`), **generated from LinkML next to `ServiceSettings`** in `rp_service.yaml`, with the current values as defaults. Thread it through constructors from the consumer's composition root | It covers the ~27 deployment and tuning values at 15 sites (table in §5.1). It follows the MSSDK idea (one registry of defaults by area) and PD-24..28 (models generated). Unlike ted-sws, it does no `.env` load or `os.environ` write at import, which a library must never do | 5.1 |
| C-2 | Merge the duplicated timeouts (`_http.py:17-18`, `s3.py:33`) into `HttpSettings` | Two copies of one value | 5.1 |
| C-3 | **Leave the ~500 protocol and vocabulary constants where they are**: Zitadel slugs, IRIs, SPARQL text, header names, problem slugs. Exception: the Zitadel slugs used only by the testkit move to `testkit/zitadel.py` | The developer's own second thought: a slug is fixed by the protocol, not a variable. Keeping it next to its use is clearer | 1.4, 5.1 |
| C-4 | Put Zitadel's user states (`ACTIVE_STATE`/`INACTIVE_STATE`) in a LinkML enum in `rp_wire.yaml`; `ZitadelUser.state` is a bare `str` today | LinkML is the single source (principle 2) | 1.4 |
| C-5 | Add the media type to each value of the LinkML `RdfFormat` enum (as an annotation or `meaning`), read through SchemaView. Decide whether `REPRESENTATIONS` derives from it. Header names and SPARQL protocol types stay Python constants | The contract formats become model data, as the developer suggested. Protocol keywords are not model data | 2.2 |

## D. Models instead of bare dicts

| # | Change | Why | § |
|---|---|---|---|
| D-1 | A shared `RegistryTerms` model and one term model per SPARQL template, replacing `_held_around` (`unique_keys.py:126`), `session._owner_terms` (`:434-439`), the listing terms (`listing.py:281-293`) and the migration guard (`migrations.py:242-247`) | The developer's anti-pattern. One concept is rebuilt by bare keys in four places, and checked only at run time | 5.2 |
| D-2 | `IriTemplateVariables` and `IriParts` models in `iris.py` (generated with `IriPolicy`) | The variables dict is built twice (`:274`, `:417`), and regex groups are read back by string (`found["tenant_id"]`) | 5.2 |
| D-3 | One `LogContext` model whose attribute names follow OTel semantic conventions (`db.system.name`, `db.namespace`, `error.type`, `messaging.*`) plus an `rp.*` namespace. Every log call takes a constant message, attributes and `exc_info=` | It unifies two logging styles, makes about 18 `extra=` sites one concept, and gives queryable, low-cardinality records. The caplog tests that read `record.step` etc. change with it | 3.3, 5.2 |
| D-4 | testkit: use the claims model in `tokens.py`, and add a shape model in `model_shape.py` and a case model in `conformance.py`. Use model aliases instead of `FIELD_OF_TOML_KEY` (`generation/config.py:20`) | Same anti-pattern | 5.2 |
| D-5 | Add a rule to `docs/rules/` (through the rulebook): "a dict with string keys that names a concept is a model" | It keeps the anti-pattern from returning, as the developer asked: "must not happen anywhere" | 5.2 |

## E. Structure: thematic modules (large, staged)

| # | Change | Why | § |
|---|---|---|---|
| E-1 | Split `rp_service.yaml` and `rp_wire.yaml` by theme. Teach `pydantic_split` a target package per module instead of the hard-coded `TOOLKIT_PACKAGE`, and allow per-theme `generated/` folders (PD-26) | The models are placed by importing layer today, not by theme. `rp_service.yaml` is a catch-all used by 8 themes. This is the generated half of the developer's request, and it must come first | 5.3 |
| E-2 | Move the hand-written modules into `rdf_persistence/<theme>/{domain,services,adapters,entrypoints,generated}`, theme by theme in dependency order: kernel, then iris, schema and provenance, then persistence, files, migrations, access, tenancy, events, collaboration, messaging, api | It is the ted-sws/MSSDK two-level pattern. The theme graph is already acyclic, so this is a move, not a redesign | 5.3 |
| E-3 | Import-linter: one layers contract per theme, plus one contract ordering the themes | It enforces the new shape. The 39-module bus contract collapses to one line | 5.3 |
| E-4 | Keep consumers stable while moving: the 141-name re-export in `rdf_persistence/__init__.py`, shims for `domain.base` and `adapters.fuseki`, and `model/rp_*.yaml` flat at their path | MWBv2 imports 5 modules and its schemas import the YAML paths | 5.3 |
| E-5 | Split `FusekiStore` into a generic SPARQL 1.1 Protocol base (query and update POST, Graph Store PUT, status mapping) and a Fuseki part (`/$/datasets` admin, dataset N-Quads, TDB2) | Half the class is protocol-generic, and `second-store` needs that half too. A rename alone would mislead | 2.1 |
| E-6 | Retire the module-level wrappers in `iris.py:57-205` in favour of `Iris` instances | They predate the policy and only delegate to `DEFAULT_IRIS` | 2.3 |

## F. Generators as their own distribution

| # | Change | Why | § |
|---|---|---|---|
| F-1 | First, make the dependency one-way (generator → library). Move the testkit's `generation` users (freshness, conformance, model_shape, shape_snapshot, guards, markers) into the generator package as a pytest plugin, or move the small shared records into the library | Today the testkit, which MWBv2 imports, depends on the generator | 5.4 |
| F-2 | Make the generator a **second distribution** (e.g. `rdf-persistence-generate`) in a uv workspace in this repository, with its own `tests/{unit,feature,integration,e2e}` and CI path filter. Move it to a **sibling repository** later, if independent release cadence is wanted (Q-3) | The developer's goal (reliable generators usable outside, separate full test pyramid) is met by a separate distribution. Generator and metamodel change together, so one repository keeps those changes atomic, and the later move is a mechanical `git filter-repo` | 5.4 |
| F-3 | Give the generator the missing tiers. Feature: Gherkin over the toy library. Integration: generated shapes and context against pyshacl, PyLD and `tsc`. E2E: generate the toy library and serve it through the kit on Fuseki | It has 38 unit files and nothing above them; acceptance is "regenerate and diff" | 5.4 |
| F-4 | Make `TOOLKIT_PACKAGE`/`PUBLIC_PACKAGE` generator configuration | Needed for both E-1 and a standalone generator | 5.3, 5.4 |

## G. Decisions to record

| # | Record | Why | § |
|---|---|---|---|
| G-1 | "Own async httpx SPARQL client, not SPARQLStore/SPARQLWrapper", superseding DEC-4's client clause. Reasons: async port, test transport and timeouts (PD-28a), 4 of 8 port methods outside the Graph Store Protocol, error mapping, the guarded single-request commit | DEC-4 says the opposite of what was built, and nothing records why | 2.1, 4.4 |
| G-2 | "Own JWKS cache over PyJWT, not `PyJWKClient`". Reasons: sync urllib blocks the event loop, no discovery, no transport or clock injection, cooldown keyed on success. Post-quantum path: follow the IdP | PD-28a records behaviour, not the choice | 1.2 |
| G-3 | "FastAPI with a spec generated from LinkML, not connexion". Reasons: no OpenAPI 3.1, double routing, scheme-level security only, JSON-Schema-only validation, routes built at run time | Connexion was never evaluated on record | 3.2 |
| G-4 | Correct the mapper docstring's reason for not using linkml-runtime's loader and dumper (`mapper.py:7-10`), after re-checking against 1.12.1 | The stated reason is inaccurate; the true ones are stronger | 4.3 |

## H. Candidates for separate EPICs (outside this one)

- **LDES view** over the provenance graph, as an optional, harvestable read route for EU and
  SEMIC consumers. Honour the specification; Python has no mature library to depend on (Q-4).
- **More representations:** N-Triples, TriG, RDF/XML (Q-5, DEC-27).
- **ML-DSA tokens** once Zitadel and PyJWT support them. Raise TLS hybrid key exchange (ML-KEM)
  on the Zitadel, Fuseki and S3 links with infrastructure (Q-6).

## Suggested order

1. **A and G.** Small, independent, immediate value.
2. **B-1 to B-3, C and D.** Medium; touch many files but no structure.
3. **B-4 and D-3 together** (logging and tracing).
4. **F-1, then E-1 and F-4.** The generator changes that unblock both the themes and the split.
5. **E-2 to E-5, then F-2 and F-3.** The large moves, staged theme by theme.
