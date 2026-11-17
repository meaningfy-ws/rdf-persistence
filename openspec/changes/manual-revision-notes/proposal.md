<!-- Parents: capabilities rp-identity (every request carries a valid token), rp-service-api
     (representations by content negotiation; versioned writes; the published contract),
     rp-aggregate-store (RDF files load into a graph of their own); decisions D-1 and D-3
     (architecture/open-decisions.adoc), research DEC-4 and DEC-27
     (archive/2026-11-05-soa-python-rdf-orm/proposal.md); rules P-0007 to P-0010 (docs/rules/).
     Seeds: inputs/seed.md, inputs/answers-2026-11-17.md, inputs/improvements.md (A, B-1/2/3/5/7,
     C-5, G), inputs/keep.md, inputs/analysis.md. -->

# EPIC: Defects, library reuse and more representations from the manual revision

> Shaped 2026-11-17 from the developer's manual revision notes (inputs/seed.md) and answers
> (inputs/answers-2026-11-17.md: "I agree with all improvement suggestions"). The developer was not
> available during shaping: every `DEC` marked "leader's choice" may be overruled. **Position:
> 1st** of the five changes of the initiative, plus `ldes-view` later; it depends on nothing.
> `technical-models` (second) follows it and takes over the deployment values this change
> introduces (DEC-3).

**Golden-thread parent:** capabilities `rp-identity`, `rp-service-api` and `rp-aggregate-store`,
and the developer's notes: "feel free to adopt a mature library", "media types could be more",
"keep the pre-quantum encryption, but stay open to post quantum", "nquad is particularly important".

## Appetite

**MEDIUM.** Seven small defects, five library swaps behind unchanged ports, four more
serialisations on the routes that serve one aggregate, and five decision records. No structural
move, no new port, no change to the settings model. Three stages, one PR each.

## Why

The manual revision found defects that will bite in production: a provider that switches its
signing key to anything but RS256 or ES256 locks every user out (401 for every token); a few
seconds of clock drift between host and provider refuse valid tokens; `If-Match` ignores `*`, lists
and the strong comparison RFC 9110 asks for; a language-tagged literal loses its tag when it is
framed; a consumer's `max_roots` is ignored by reference collections; `model_copy(update=...)`
skips validation at eight sites; one error is logged twice. It also found hand-written code where
a mature library already does the job (Accept parsing, JSON-LD loading, rdflib format names) and
choices that were made well but never recorded (our own SPARQL client and JWKS cache, FastAPI over
connexion). The developer asked for more serialisations, N-Quads first. These are small and
independent, so they go first, before the large structural changes of the initiative.

## Solution outline

**Stage 1, defects.** The token verifier takes its allowed algorithms and its clock leeway as
constructor parameters, with an asymmetric-only default that covers every key type the provider
offers. `If-Match` is read as RFC 9110 says. Language tags survive framing; reference collections
honour `max_roots`; models are rebuilt with validation; the duplicate log goes.

**Stage 2, reuse.** `python-mimeparse` ranks `Accept`. PyLD, with the same refusing document
loader, turns every JSON-LD into RDF, so loading and bodies behave alike. rdflib and FastAPI take
media types directly, so the parallel keyword sets go. The LinkML `RdfFormat` enum carries each
value's media type, and loading reads it from there. The testkit's `FakeStore` moves to the
pyoxigraph engine, if and only if the store conformance suite and every test that uses it pass.

**Stage 3, representations and decisions.** Every route that answers one aggregate also serves
N-Triples, RDF/XML, N-Quads and TriG. In N-Quads and TriG the triples sit in the aggregate's named
graph, so a client can load the answer into a quad store as the toolkit stores it. Schemathesis
checks the service against its own OpenAPI document. Five decision records go into the ADR section
of the docs.

```text
GET /libraries/t1/books/b7   Accept: application/n-quads
<https://ex.org/t1/books/b7> <https://ex.org/m#title> "Dune" <https://ex.org/t1/books/b7/graph> .
```

## Key decisions

- **DEC-1** (A-3, Q-6; developer's answer Q-6): the verifier's allow-list is a parameter.
  Default: RS256, RS384, RS512, PS256, PS384, PS512, ES256, ES384, ES512, EdDSA. `none` and every
  HS* name are refused at construction, even when a deployment lists them. A name the verification
  library does not implement is also refused at construction. So ML-DSA joins the day the provider
  and PyJWT ship it: since PyJWT is pinned exactly, adding it needs a toolkit release that bumps
  the PyJWT pin, then a configuration change; no liboqs, no own cryptography. An algorithm the
  pinned PyJWT already implements joins by configuration alone. (re-shaped 2026-11-17 by the lead
  in the cross-change reconciliation: "no toolkit release" held only for a family the pinned PyJWT
  already implements, design RISK-1.) Rejected: post-quantum signatures now (the provider cannot
  sign them); HS512 (it hands the signing secret to every verifier).
- **DEC-2** (A-4): a clock leeway of 30 seconds by default, a parameter, applied to `exp` and
  `nbf`. Rejected: no leeway (drift refuses valid tokens); PyJWT's own `exp` check (it would bypass
  the injected clock the testkit relies on).
- **DEC-3** (leader's choice): the allow-list and the leeway are **constructor parameters with
  defaults** now; `technical-models` moves them into the generated settings model with the other
  JWKS values (P-0009, improvements C-1). Rejected: a settings class now (the central settings home
  is that change's subject; two homes would follow).
- **DEC-4** (A-5; leader's choice): `If-Match` uses strong comparison. A weak tag never matches. `*`
  matches any current version. A list matches when it holds the current version. A single strong
  tag goes straight to the guarded write as today. For `*` or a list, the route first reads the
  current version. A stale or unmatched value stays **409** as the spec says. Rejected: 412 (it
  would change the status a consumer already handles).
- **DEC-5** (B-1): `python-mimeparse` 2.0 replaces the Accept parser; the wrappers that raise
  `NotAcceptable` stay. JSON still wins a tie. Rejected: werkzeug `MIMEAccept` (all of werkzeug).
- **DEC-6** (B-2): one JSON-LD to RDF path, PyLD with the refusing loader, for bodies and loaded
  files. A loaded JSON-LD file that names a graph is refused: today rdflib drops those triples
  silently. Rejected: keeping rdflib's JSON-LD parser for loading (two behaviours, two guards).
- **DEC-7** (C-5; leader's choice): each `RdfFormat` value carries its media type as a
  `media_type` annotation, read through SchemaView like the enum meanings. The served
  representations do **not** derive from it: `RdfFormat` lists what a graph is *loaded* from, and
  the representations add JSON (not RDF) and dataset formats (not loadable into one graph). Header
  names and SPARQL protocol types stay Python constants (keep.md).
- **DEC-8** (B-7; leader's choice, as the brief set it): pyoxigraph becomes the `FakeStore` engine
  only if the store conformance suite and `make test-fast` pass on it, unchanged. Otherwise the task
  records why in design.md and rdflib stays. Results still leave the fake as rdflib types, through
  the same SPARQL JSON parser the Fuseki adapter uses. pyoxigraph is never a production store
  (second-store DEC-6, DEC-9).
- **DEC-9** (Q-5; leader's choice on the routes): N-Triples, RDF/XML, N-Quads and TriG are served by
  every route that answers **one aggregate**: read, create, replace, and the tenant root. N-Quads
  and TriG name the graph the aggregate was read from. A **listing** stays JSON and JSON-LD: a page
  carries its total and paging, which no RDF serialisation holds. JSON stays the default, then
  JSON-LD, Turtle, N-Triples, N-Quads, TriG, RDF/XML on a tie. Rejected: N-Quads for listings now
  (open question to the developer); a dump route over HTTP (not asked).
- **DEC-10** (B-5): schemathesis runs against the toy service's `/openapi.json` in process, on
  fakes. A finding is fixed in the contract or the code in this change when it is small; otherwise
  it becomes an issue named in the PR. Rejected: connexion or openapi-core at run time (G-3).
- **DEC-11** (G-1 to G-4, Q-6; leader's choice on the place): the decisions go into
  `docs/modules/ROOT/pages/adr/`, which its own index reserves for "a decision that outlives its
  change", one record each, `ADR-001` to `ADR-005`. They are the first records there. The research
  epic's candidate ADRs stay archived and are not renumbered. G-4 is a docstring correction in
  `services/mapper.py`, after a re-check against linkml-runtime 1.12.1.
- **DEC-12** (A-7; leader's choice): log or raise, not both. The message bus raises
  `MessageLimitExceeded` without logging, and the message names the command class and id. The kit's
  observer path, which swallows it, logs it once. The HTTP problem handler logs every error it
  answers as 500 once at ERROR, with a constant message and `exc_info` (P-0010). Today nothing logs
  a 500 there.

## Rabbit-holes

- **JWKS keys that name no algorithm.** PyJWT binds a key to one algorithm and infers RS256 for an
  RSA key without `alg`, so an RS384 or PS256 token would still be refused. The verifier binds the
  key to the token's algorithm when the JWK names none, and refuses a token whose algorithm differs
  from the one the JWK names (design PD-2). Do not go further into key management.
- **pyoxigraph** may differ from rdflib in ways the suite does not cover (blank-node labels in
  results, literal canonical forms). The gate is the whole fast suite, not the conformance cases
  alone; do not patch tests to fit the engine.
- **Schemathesis findings.** The fuzzer will find real mismatches. Fix what is small; file the rest.
  Do not let it grow the change (DEC-10).
- **RDF/XML cannot write every predicate IRI.** An aggregate it cannot write answers 406, never 500
  (design error matrix).
- **The `If-Match: *` read** adds one read per such request; the guarded write still decides. A
  race between the read and the write answers 409, which is correct.

## No-gos

- Moving the allow-list, the leeway or any other value into a settings model (`technical-models`).
- Post-quantum algorithms in code, liboqs, or a custom PyJWT `Algorithm`; TLS changes
  (infrastructure).
- Replacing `_http.py`, `jwks.py`'s cache, `FusekiStore`, `SparqlTerm` or the router (keep.md).
- N-Quads or TriG for listings; a tenant dump or export route; accepting Turtle, N-Quads or other
  RDF bodies on writes; loading N-Quads or TriG into a graph.
- 412 for `If-Match`; weak ETags emitted by the service.
- pyoxigraph as a production store.
- OpenTelemetry spans or log-attribute renames beyond DEC-12 (`otel-observability`); models for the
  SPARQL term bundles (`technical-models`); `rdflib.contrib` GraphDB clients (`second-store` input
  B-6).

---

## What Changes

- `adapters/jwks.py`: `algorithms=` and `leeway_seconds=` on `JwksTokenVerifier`; keys bound to
  the token's algorithm when the JWK names none. `testkit/tokens.py`: `TokenSigner` signs with any
  allowed algorithm.
- `entrypoints/negotiation.py`: `If-Match` by RFC 9110 (strong, `*`, lists); Accept through
  `mimeparse`. `entrypoints/router.py`: the version read for `*` and lists.
- `services/documents.py` and a new `services/jsonld.py`: one PyLD path; `language` kept in
  `dataset_of`; four more representations in `render`. `services/loading.py`: JSON-LD through
  PyLD; formats by media type; `_refers_outside` and `_RDFLIB_FORMATS` deleted.
- `services/mapper.py`: `max_roots` moves to the `Mapper` (`UnitOfWork` falls back to it);
  `services/reference_collections.py`: the mapper's `max_roots`. `domain/base.py`:
  `RpModel.replaced(**changes)`, used at the eight `model_copy(update=...)` sites.
- `services/messagebus.py`, `entrypoints/kit.py`, `entrypoints/problems.py`: one log per error.
- `adapters/fuseki.py`, `entrypoints/negotiation.py`: rdflib format names and `EVENT_STREAM`
  replaced by media types and `EventSourceResponse.media_type`.
- `model/rp_files.yaml`, `model/rp_core.yaml`: `media_type` annotations on `RdfFormat`, a
  `media_type` tag in `RpAnnotation`; `services/vocabulary.py`: `media_types()`.
- `domain/media.py`: `N_TRIPLES`, `TRIG`, `RDF_XML`, the longer `REPRESENTATIONS`;
  `entrypoints/openapi.py`: the new media types documented.
- `testkit/fakes.py`: `FakeStore` on pyoxigraph, its update splitter and `_plain_strings` deleted,
  if DEC-8's gate passes.
- `pyproject.toml`: `python-mimeparse` (runtime), `schemathesis` (test group), `pyoxigraph`
  declared if DEC-8 holds.
- `services/mapper.py`: the corrected docstring (G-4).
- Docs: `adr/` records ADR-001 to ADR-005 and their index; `architecture/api.adoc` representations;
  `howto/adopt.adoc` the verifier's parameters; `questions.adoc` entries.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `rp-identity`: the verifier follows the provider's asymmetric algorithm and tolerates clock skew
  (ADDED).
- `rp-service-api`: more representations for one aggregate; `If-Match` by RFC 9110; the contract
  is checked against the implementation (MODIFIED, RENAMED).
- `rp-aggregate-store`: JSON-LD loading refuses named graphs and remote contexts alike (MODIFIED).

## Impact

- Consumers: **BREAKING** in six places, each listed in design.md "Breaking changes" and marked
  by a `BREAKING CHANGE:` footer: `If-Match` is strict (a weak tag `W/"v"` is 409, an unquoted
  value 428; both matched before); `expected_version` refuses `W/`, `*` and lists, which a
  consumer's own route may call; `jwks.ALLOWED_ALGORITHMS` and `jwks.ES256` are removed; a loaded
  JSON-LD file that names a graph or uses a relative IRI is refused, and so is a body with a
  relative IRI; a language-tagged value changes shape in JSON and JSON-LD; `REPRESENTATIONS` holds
  seven members. Otherwise: a consumer that builds `JwksTokenVerifier` gets the wider algorithm
  default and a 30 s leeway without changing code, and `If-Match: *` and lists, refused as stale
  today, now work.
- Dependencies: `python-mimeparse` 2.0.x (pure Python, no dependencies) at run time; `schemathesis`
  in tests; `pyoxigraph` declared at the locked 0.5.13 if DEC-8 holds (already installed through
  linkml-runtime).
- Metamodel: one enum value added to `RpAnnotation` and four annotations on `RdfFormat`; the lock
  change is expected `SAFE` (checked in task 2.4).
- The later changes: `technical-models` takes DEC-3's parameters into settings; `otel-observability`
  builds on DEC-12.
