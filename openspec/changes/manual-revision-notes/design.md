> Derives from: EPIC `manual-revision-notes` ([proposal.md](proposal.md)), capabilities
> `rp-identity`, `rp-service-api`, `rp-aggregate-store`. Seeds and answers in [inputs/](inputs/).
> Type: Implementation.

## Context

Read against `develop` at 48f80c6. What the brief and the inputs claim, checked in the code:

| Claim | In the code | In this PLAN |
|---|---|---|
| The allow-list is `RS256`, `ES256` (A-3) | `adapters/jwks.py:31-32`, checked on the header (`_header`) and in `jwt.decode(algorithms=[algorithm])` | PD-1 |
| A wider allow-list is enough (A-3) | **Not quite.** PyJWT 2.15 binds a `PyJWK` to one algorithm and infers `RS256` for an RSA JWK without `alg` (`jwt/api_jwk.py`), then refuses a token whose `alg` differs (`api_jws.py` `_verify_signature`). PS256 on an RSA key without `alg` would still fail | PD-2 |
| No clock leeway (A-4) | `_decode`: `claims.exp <= now`, `claims.nbf > now` against the injected clock | PD-3 |
| `If-Match` strips `W/`, ignores `*` and lists (A-5) | `negotiation.py:131-140` `expected_version`; **five** callers in `router.py`: `DocumentApi.replace` (182, also reached by `TenantApi.replace_root`), `DocumentApi.remove` (192), `TenantApi.delete` (248), `set_grants` (260), `set_label` (271). `expected_version` is public: `howto/workflow.adoc:189` tells a consumer's own route to call it | PD-4 |
| Unquoted and weak tags work today | `test_negotiation.py:94` asserts `"7f3a"`, `W/"7f3a"`, `7f3a` all give `7f3a`. Every other test sends the `ETag` it read (quoted, strong) | PD-4, Breaking changes |
| `RS256` is only the verifier's | `testkit/tokens.py:16` and `testkit/zitadel.py:35` import `RS256` from `jwks.py` | PD-1 |
| `PyJWKSet` refuses a set with a bad key | **No.** `PyJWKSet.__init__` skips an unusable key and raises only when none is usable | PD-2, TC-06 |
| mimeparse ranks like our parser | **Not quite.** `best_match` sorts by (quality, fitness), so `text/turtle, */*` gives Turtle where we give JSON (a quality tie); it does not lower-case (`TEXT/Turtle` matches nothing); an unparsable `q` reads as 1, ours as 0. `parse_media_range` and `quality_parsed` give the quality alone | PD-5 |
| A 500 is not logged (A-7) | Half true. A mapped kind with status 500 (`SparqlError`, `StoredDataInvalid`, `MessageLimitExceeded`) is answered by `toolkit_error` and logged by no one. Any other exception reaches `server_error`, which Starlette 1.10 registers in `ServerErrorMiddleware`; it re-raises after answering (`middleware/errors.py:183-186`), and the server logs it | PD-9 |
| PyLD reports what it cannot read | **No.** JSON-LD to RDF drops a triple with a relative IRI without a word, and the loaded file has no base; rdflib kept the relative IRI | PD-6 |
| A language tag survives framing harmlessly (A-1) | The library context gives string slots no `@type`, so a tagged value frames as `{"@value": "Dune", "@language": "en"}`; the plain JSON body would then break the published schema (`string`) | PD-6 |
| `dataset_of` drops the language (A-1) | `services/documents.py:68-85`, literal branch emits `value` and `datatype` only | PD-6 |
| Reference collections use `DEFAULT_MAX_ROOTS` (A-2) | `services/reference_collections.py:266-269`. The analysis says "the mapper's configured `max_roots`", but the `Mapper` has none: the limit is a keyword of `UnitOfWork` (`mapper.py:306-319`, private `_max_roots`), and `ReferenceCollections` holds a `Mapper` (`self._mapper`), no unit of work. The bus (`messagebus.py:73`) and the tenancy (`tenancy.py:278,701,731`) build units of work from the mapper without the keyword | PD-7 |
| 8 `model_copy(update=...)` sites (A-6) | `provenance.py:168`, `transitions.py:194`, `transitions.py:237`, `visible_part.py:30`, `discussion.py:288`, `domain/iris.py:73`, `:263`, `:286`. Also outside the list: `mapper.py:168,171` (schema-keyed, generic by design, keep.md), `generation/pipeline.py:143`, `testkit/zitadel.py:235`, `testkit/conformance.py:51` (D-4, `technical-models`) | PD-8 |
| Logged twice (A-7) | `messagebus.py:150` logs then raises; `kit.py:279` logs again. `entrypoints/problems.py` logs nothing for a 500 | PD-9 (DEC-12) |
| JSON-LD parsed two ways (B-2) | `loading.py:26-62` rdflib plugin plus `_refers_outside`; `documents.py:302` PyLD then `Graph().parse(format="nt")`. Checked: rdflib drops the triples of a named `@graph` in a loaded file without a word | PD-6 |
| rdflib takes media types as format names (B-3) | `rdflib/plugin.py` registers `text/turtle`, `application/n-triples`, `application/n-quads`, `application/trig`, `application/rdf+xml`, `application/ld+json` and the result parser `application/sparql-results+json` | PD-10 |
| `RdfFormat` holds its media type only in text (C-5) | `model/rp_files.yaml:95-114`; read in `loading.py:14-19` and `session.py:1079` | PD-11 |
| Which routes return named graphs (Q-5) | No HTTP route returns a whole dataset. A document read, create, replace and the tenant root answer one aggregate, which is one named graph (`render(stored, graph_iri, ...)`, `documents.py:445`). Listings answer a page (`accepted_listing_type`). The tenant dump is Python only (`kit.dump_tenant`) | PD-12 (DEC-9) |
| Decisions have a home | `docs/modules/ROOT/pages/adr/index.adoc` is a placeholder that reserves the section for decisions that outlive their change; `architecture/open-decisions.adoc` holds D-1 to D-13 | PD-14 (DEC-11) |
| `FakeStore` is rdflib with its own splitter (B-7) | `testkit/fakes.py:91-113` `_operations`, `:116` `_plain_strings`; 68 test files use `FakeStore`; the suite is `testkit/store_conformance.py` (`CASES`, `run_case`) | PD-13 (DEC-8) |
| B-6 rdflib contrib clients | Already an input of `second-store` (`second-store/inputs/reuse-rdflib-contrib.md`) | not here |

## Goals / Non-Goals

**Goals:** the seven defects fixed with a failing test each; Accept parsing, JSON-LD loading and
rdflib format names delegated to the libraries; `RdfFormat` carrying its media types; four more
representations for one aggregate; a contract test; five recorded decisions; `FakeStore` on
pyoxigraph if the gate passes.

**Non-Goals:** the EPIC's No-gos. Also: renaming log attributes, a settings model, any change to
the `Store` port or to a consumer's composition root beyond optional parameters.

## How it succeeds, how it fails, how it is checked

- **Succeeds** when every TC in tasks.md passes, the existing suite passes unchanged except the
  tests this PLAN names as changing (TC tables say which), `make check-all` and
  `make test-containers` are green, and `openspec validate manual-revision-notes --strict` passes.
- **Fails** when a swap changes behaviour a consumer can see beyond what the spec deltas and
  "Breaking changes" say (an
  Accept header that picked JSON now picks something else; a JSON-LD body that parsed is now
  refused). The existing negotiation, loading and documents tests are the guard: they run unchanged
  before and after each swap, and a swap task that needs to edit one stops and records why.
- **Checked** test first per task; the swaps by running the old tests against the new code before
  deleting the old code.

## Decisions

Settled in the EPIC and cited, not re-argued: DEC-1 to DEC-12. The new ones:

- **PD-1 The allow-list** (DEC-1, DEC-3). `JwksTokenVerifier.__init__` gains
  `algorithms: Collection[str] = DEFAULT_ALGORITHMS` and `leeway_seconds: float =
  DEFAULT_LEEWAY_SECONDS`. `DEFAULT_ALGORITHMS` is the tuple of DEC-1 in `jwks.py`, replacing
  `ALLOWED_ALGORITHMS` and `ES256`; `RS256` stays, the testkit imports it. `_header` stops being a
  static method. The constructor raises `ValueError` naming the entry for:
  an empty collection; `none` (any case); a name starting `HS` (any case); a name not in
  `jwt.algorithms.get_default_algorithms()` (so `ML-DSA-65` today). The check on the header
  (`_header`) and `jwt.decode(algorithms=[algorithm])` use the instance's set. `DEFAULT_ALGORITHMS`
  and `DEFAULT_LEEWAY_SECONDS` stay module constants until `technical-models` (DEC-3); a comment says
  so.
- **PD-2 Keys bound to the token's algorithm.** The cache keeps the JWK mappings as fetched
  (`dict[str, Mapping[str, object]]` keyed by `kid`; a library boundary, P-0007), validated once at
  refresh by building a `jwt.PyJWK` of each. As `PyJWKSet` does today, a key that does not build,
  or has no `kid`, is skipped, and a set with no usable key is `IdentityUnavailable`.
  For a token: if the JWK names `alg` and it differs from the header's, `InvalidToken("the token's
  algorithm does not match its key")`; otherwise `jwt.PyJWK(jwk, algorithm=header_alg)`, and a key
  type that does not fit the algorithm (PyJWT's `InvalidKeyError`, `PyJWKError`) is
  `InvalidToken`. Rejected: trusting PyJWT's inference (refuses RS384, PS* on RSA keys without
  `alg`).
- **PD-3 The leeway** (DEC-2): `claims.exp + leeway <= now` is expired; `claims.nbf - leeway > now`
  is not yet valid; `leeway_seconds` must be finite and `0 <= leeway <= 300`, else `ValueError`.
- **PD-4 `If-Match`** (DEC-4). `negotiation.py` gains, for the service's own routes,
  `async matched_version(if_match: str | None, current: Callable[[], Awaitable[str]]) -> str`: the
  one version the guarded write takes. It returns a string, so no new record (P-0007) is needed.
  Rules: missing or blank is `PreconditionRequired`, as today. `*` alone matches any version.
  Otherwise the header is split on commas outside quotes. A strong tag `"v"` names `v`; a weak
  `W/"v"` names nothing. An entry that is neither raises
  `PreconditionRequired("If-Match must be * or entity tags")`, a 428 the spec already uses. A single
  strong tag returns at once, with no read. `*`, or more than one entry, awaits `current()` (a
  callable the route passes) and returns it if `*` or it is named. Otherwise it raises
  `Conflict("the version is not one If-Match names")` (409). A header with only weak tags is a
  `Conflict`. Empty list members (`"v1", , "v3"`) are skipped, as RFC 9110 §5.6.1 allows. `current`
  is, for `DocumentApi.replace` and `remove` (the tenant root included), the third member of
  `kit.aggregates.read(tenant, principal, iri, cls)` (`Stored`); for `TenantApi.delete`,
  `set_grants` and `set_label`, the second member of `kit.tenancy.get(tenant)` (the access record's
  version, the one those routes compare today). `expected_version(if_match) -> str` stays public
  for a consumer's own route (`howto/workflow.adoc:189`), now strict and with no read: a single
  strong tag gives its version; a weak one is `Conflict`; `*`, a list or anything else is
  `PreconditionRequired` naming `matched_version`. `matched_version` uses it for the one-tag case.
- **PD-5 Accept** (DEC-5). `_negotiate(accept, offered, refusal)` becomes:
  header `None` or blank → `*/*`; otherwise the header is lower-cased and each non-blank comma
  member parsed with `mimeparse.parse_media_range`; each offered type is scored with
  `mimeparse.quality_parsed(media_type, ranges)` (the quality of the most specific matching range,
  0 when none matches); the highest quality wins, the first offered on a tie; a best quality of 0,
  or `MimeTypeParseException`, → `NotAcceptable(refusal)`. Rejected: `mimeparse.best_match`, which
  breaks a quality tie by specificity (`text/turtle, */*` would give Turtle, not JSON, against the
  spec's tie order) and does not lower-case. One change is accepted: an unparsable `q`
  (`text/turtle;q=abc`) reads as 1 (mimeparse), not 0 (ours). `_quality`, `_ranges`,
  `_specificity`, `_quality_of` and the constants `_EXACT`, `_TYPE_WILDCARD`, `_ANY` are deleted. The
  dependency is `python-mimeparse==2.0.0` (pinned like the others, PD-2 of the foundation).
  *As built after F-3:* members are split outside quotes and read with `mimeparse.parse_mime_type`,
  a member that is no media range is skipped, and `q` is read by a small `_quality` (empty also
  reads as 1, negative as 0, above 1 as 1); scoring is still `quality_parsed`.
- **PD-6 One JSON-LD path** (DEC-6, A-1). New `services/jsonld.py` holds `LOADER` (the refusing
  document loader, moved from `documents.py`), `dataset_of` (moved, now emitting `language` and
  datatype `rdf:langString` for a tagged literal) and `triples_of(document) -> Graph`:
  `jsonld.to_rdf(document, {"format": N_QUADS, "base": NO_BASE, **LOADER})`, parsed into an rdflib `Dataset` with
  `format=N_QUADS`; a quad outside the default graph raises `NamedGraphRefused`; a loader refusal
  raises `RemoteContextRefused`. Both are private `ValueError` subclasses of the module.
  `documents._triples` maps them to `InvalidBody` (message `NOT_INLINE` as today, and
  "a body describes one graph"); `loading._parse` maps them to `InvalidGraph` (its `NOT_INLINE`
  text, and "a loaded file holds one graph"). Any other PyLD or parser error keeps today's mapping.
  `_refers_outside`, `_inline`, `_refuse_outside_contexts` and `IMPORT_KEY` are deleted.
  **Relative IRIs.** PyLD drops a triple with a relative IRI silently, so `triples_of` passes
  `base: NO_BASE` (`"https://no-base.invalid/"`, a reserved TLD) and raises a third private error,
  `RelativeIriRefused`, when any term starts with it: `InvalidBody` / `InvalidGraph` "a JSON-LD
  document must use absolute IRIs". A document's own `@base` still applies.
  **Language in plain JSON.** `render` for `JSON` (the context dropped) replaces each value object
  `{"@value": v, "@language": l}` by `v`, so the body keeps the published `string` schema; JSON-LD
  and every RDF type keep the tag. Plain JSON was lossy for tags before and stays so (RISK-11).
- **PD-7 `max_roots`.** The limit moves to the object every unit of work and the reference
  collections share, the `Mapper`: `Mapper(view, models, *, max_roots: int = DEFAULT_MAX_ROOTS)`
  (`ValueError` under 1, the check `UnitOfWork.__init__` has today) with a read-only property
  `max_roots`. `UnitOfWork(..., max_roots: int | None = None)` uses `mapper.max_roots` when it is
  `None` and keeps its `ValueError` for an explicit value under 1 (the parameter stays third,
  positional or keyword), so every existing call keeps working and the bus's and the tenancy's units of work
  follow the mapper. `_require_room` and its message use `self._mapper.max_roots`; the docstring at
  `reference_collections.py:216` names it. `technical-models` then replaces the keyword with its
  `limits=` group on the `Mapper` and deletes `DEFAULT_MAX_ROOTS` (its PD-7). Rejected: a
  `max_roots` parameter on `ReferenceCollections` (a second place to set one limit).
- **PD-8 Rebuilding a model** (A-6). `RpModel.replaced(self, **changes: object) -> Self` in
  `domain/base.py`: `type(self)(**({name: getattr(self, name) for name in self.model_fields_set}
  | changes))` (one merged mapping: two `**` would raise `TypeError` for a name in both), so every
  value is validated and `extra="forbid"` refuses a misspelt name with a
  `ValidationError`. The eight sites call it; the `update=` dicts go. A concrete class known at the
  site (`Transition` when no command is given) is built with its keyword arguments directly.
- **PD-9 One log per error** (DEC-12). `messagebus._start` drops its `log.error`; the
  `MessageLimitExceeded` it raises carries the class and id: the exception gains an optional
  `command: str` (`"Replace urn:uuid:..."`), message `message limit {limit} reached by {command}`
  (the existing `match="message limit 5 reached"` assertions still hold). `kit.py:279` keeps its one
  ERROR log. In `install_problem_handlers`, `toolkit_error` logs once, at ERROR, each mapped error
  whose kind's status is 500: message constant `"internal error answered"`, `exc_info=error`,
  `extra={"error.type": f"{type(error).__module__}.{type(error).__qualname__}"}` (an OTel
  semantic-convention name, P-0010, whose value is the fully qualified class name, as
  `otel-observability` DEC-7 spells it, so the value does not change when that change lands).
  `server_error` does **not** log: Starlette re-raises the exception after it answers and the
  server logs it (Context), so a log there would be the double log A-7 removes.
- **PD-10 Media types as format names** (B-3). `fuseki.py`: `RDFLIB_JSON` → `RESULTS_JSON`,
  `RDFLIB_TURTLE` → `TURTLE`. `documents.py`: the `"nt"` and `"turtle"` literals go (PD-6, PD-12).
  `loading.py`: `_RDFLIB_FORMATS` goes (PD-11). `negotiation.EVENT_STREAM` goes;
  `openapi.py:351` uses `EventSourceResponse.media_type`. `tenant_dump.py:321` already does this.
- **PD-11 `RdfFormat` media types** (DEC-7). `model/rp_core.yaml` `RpAnnotation` gains
  `media_type` ("Permissible value annotation: the IANA media type of a serialisation",
  `rp:AnnotationMediaType`). `model/rp_files.yaml` puts `annotations: {media_type: ...}` on each
  value: `text/turtle`, `application/rdf+xml`, `application/n-triples`, `application/ld+json`.
  `services/vocabulary.py` gains `media_types(members, view: SchemaView | None = None) ->
  Mapping[E, str]`, beside `meanings` (`view` defaults to `metamodel()`; a test passes another),
  read with `annotation_text` on each permissible value; a value without the annotation is a
  `ValueError` naming it, raised at import because `loading.py` builds its map at module level. `loading._parse` parses with `media_types(RdfFormat)[rdf_format]`.
  `make generate` regenerates; the lock change is expected `SAFE`, version unchanged (task 2.4 checks
  it and stops if not).
- **PD-12 The representations** (DEC-9). `domain/media.py` gains `N_TRIPLES =
  "application/n-triples"`, `TRIG = "application/trig"`, `RDF_XML = "application/rdf+xml"`,
  `DATASET_REPRESENTATIONS = (N_QUADS, TRIG)` and `REPRESENTATIONS = (JSON, JSON_LD, TURTLE,
  N_TRIPLES, N_QUADS, TRIG, RDF_XML)`. `Documents.render`: JSON and JSON-LD by framing as today;
  a dataset type serialises an rdflib `Dataset` holding `shown` in the graph `graph_iri`; any other
  RDF type serialises `shown` as a graph; `format=media_type` throughout. A serialiser `ValueError`
  (RDF/XML cannot write a predicate with no XML local name; rdflib's "Can't split") raises
  `NotAcceptable("this aggregate has no {media_type} form")`. `openapi._document_media` documents
  every member of `REPRESENTATIONS` after JSON as `string`; its `turtle=` flag becomes `rdf=`.
  `accepted_listing_type` is unchanged.
- **PD-13 `FakeStore` on pyoxigraph** (DEC-8). One `pyoxigraph.Store()` (in memory) per dataset
  name. `query`: `store.query(sparql)`; SELECT and ASK results are serialised with
  `QueryResultsFormat.JSON` and parsed by `Result.parse(format=RESULTS_JSON)`; CONSTRUCT and
  DESCRIBE triples are serialised as N-Triples into an rdflib `Graph` in a `Result("CONSTRUCT")`
  (the shape `fuseki._read_result` gives). `update`: `store.update(sparql)`, which applies a request
  atomically; `SyntaxError` and pyoxigraph's evaluation errors → `BadQuery`. `put_graph`,
  `export_quads`, `import_quads` through N-Triples or N-Quads text. `_operations`, `_SPARQL_TOKENS`,
  `_PROLOGUE` and `_plain_strings` are deleted (oxigraph reads `"1"^^xsd:string` and `"1"` as one
  term). Failure injection, `sent()` and `after_update` stay as they are. `pyproject.toml` declares
  `pyoxigraph==0.5.13` in `[project] dependencies`: the fakes ship in the wheel and import it, and
  linkml-runtime already installs it, so a consumer installs nothing new. Gate: every `CASES` entry and `make test-fast` green with **no test
  edited**. If the gate fails, the task reverts the engine, keeps rdflib and adds a PD here naming
  the failing tests and why.
- **PD-14 The decision records** (DEC-11). `adr/adr-001-sparql-client.adoc` (G-1: own async httpx
  client; supersedes the client clause of research DEC-4), `adr-002-jwks-cache.adoc` (G-2),
  `adr-003-fastapi-not-connexion.adoc` (G-3), `adr-004-signing-algorithms.adoc` (Q-6 with DEC-1,
  DEC-2), `adr-005-representations.adoc` (Q-5: DEC-9; narrows research DEC-27 and widens D-1). Each:
  context, decision, status (*Accepted*, developer 2026-11-17, or *Accepted, leader's choice*),
  consequences, the alternatives weighed, citing `inputs/analysis.md` §. The index lists them;
  `nav.adoc` lists them under the existing ADR entry; `questions.adoc` gains one question per record.
  `architecture/open-decisions.adoc` D-1 gets a one-line pointer to ADR-005.
- **PD-15 Contract test** (DEC-10). `schemathesis==4.*` pinned to the latest release on the day of
  the task, in the `test` group. `tests/unit/entrypoints/test_contract.py`, marked `slow`: the toy
  service (`tests/toy_service.py`) with a tenant and a book made in a fixture; schemathesis loads
  `/openapi.json` from the ASGI app, fills `{t}` and `{aggregate_id}` with the fixture's ids, sends a
  librarian's bearer, and runs the checks `not_a_server_error`, `status_code_conformance`,
  `content_type_conformance` and `response_schema_conformance` with `max_examples=25`, derandomised
  (testing.adoc rule 8).
- **PD-16 The mapper docstring** (G-4). Re-check against linkml-runtime 1.12.1 the four reasons
  of analysis §4.3 item 3 with a throwaway script in `temp/`; the docstring states only the ones that
  hold, and removes "they take linkml's own dataclass classes".

- **PD-17 `FakeStore` stays on rdflib** (task 2.5 gate, PD-13). With pyoxigraph 0.5.13 (already
  locked through linkml-runtime) every `CASES` entry passed, but `make test-fast` failed 3 tests
  with no test edited, each bound to the rdflib engine:
  `tests/unit/testkit/test_fakes.py::test_a_failure_that_is_not_the_stores_own_propagates_unchanged`
  (patches `fakes.prepareUpdate`);
  `test_fakes.py::test_a_semicolon_that_is_not_an_operation_separator_does_not_split_the_request[empty-operations]`
  (`A ; ; B ;`, which oxigraph's strict SPARQL 1.1 grammar refuses);
  `tests/unit/services/test_iri_policy_guard_adversarial.py::test_two_records_that_disagree_refuse_whichever_policy_is_configured`
  (reads `store._dataset(...).graph(...)`, rdflib's `Dataset` API). Reaching even those 3 took two
  workarounds in the fake: a rewrite of `FILTER (?x NOT IN ())`, which oxigraph evaluates to an
  error for a bound variable (the spec says true; `listing.py`, `unique_keys.py` and
  `session.py:169` can emit it; 160 tests fail without it), and a `base_iri` for tests that write
  relative IRIs. The swap was 43-57 % faster (`make test-fast` 1m05s-1m26s against 2m30s) and ran
  the #142 quarantined test in 0.3 s. Per PD-13 the engine is reverted; nothing of 2.5 is merged.
  TC status: TC-50 passed on the swap, TC-52 too (the existing rows), TC-54 measured above; TC-51
  and TC-53 are not written (they test the swapped engine). The attempt is kept in `evidence/spike-pyoxigraph-fakestore.patch` for a follow-up,
  which needs the developer's call on the three test edits and on the `NOT IN ()` workaround (an
  external-library shortcoming: contribute upstream, or work around it in the fake).

## Breaking changes

Found by the attack; the EPIC's Impact now lists them (it first said "no breaking change"). Each commit that
lands one carries a `BREAKING CHANGE:` footer (before 1.0.0 it bumps the MINOR, `develop/index.adoc`).

| Change | Who sees it | Task |
|---|---|---|
| `If-Match: W/"v"` is 409, an unquoted `v` is 428 (both matched before) | a client that echoes a weakened or unquoted tag | 1.3 |
| `expected_version` refuses `W/`, `*` and lists | a consumer route that calls it (`howto/workflow.adoc`) | 1.3 |
| `jwks.ALLOWED_ALGORITHMS` and `jwks.ES256` removed | code that imports them (none in the repo but the verifier) | 1.1 |
| A token expired by less than the leeway (30 s by default) is accepted | a client or test that counts on an exact expiry; `leeway_seconds=0` restores it | 1.1 |
| A loaded JSON-LD file that names a graph, or uses a relative IRI, is refused; so is a body with a relative IRI (its triple was dropped before) | a consumer loading such files or sending such bodies | 2.2 |
| A JSON-LD body or loaded file with an IRI that is not valid, or that is a scalar, is refused (it gave fewer or no triples before) | as above | 2.2, F-4 |
| `Accept`: an unparsable or empty `q` reads as 1 (it read as 0); a `q` above 1 reads as 1 (it outranked `q=1`) | a client sending such a `q` | 2.1, F-3 |
| A language-tagged value is a plain string in JSON and a value object in JSON-LD (it lost its tag in both) | a JSON-LD client | 1.4 |
| `REPRESENTATIONS` holds seven members | code that matches it exhaustively | 3.1 |
| An `Accept` that refuses JSON, JSON-LD and Turtle but admits a wildcard or a range is served one of the four new forms (it was 406) | a client that relies on that 406 | 3.1 |

## Algorithm / approach

Worked examples (toy library, tenant `t1`, book `b7` at version `v3`):

1. **A key rotation.** The provider's web key becomes ES384; its JWKS entry names `alg: ES384`. A
   token with header `{"alg": "ES384", "kid": "k2"}`: `ES384` is in the default set; `k2` is unknown,
   so one refresh fetches the set; the JWK names `ES384`, equal to the header; `PyJWK(jwk,
   algorithm="ES384")` verifies. Before this change: 401.
2. **An RSA key without `alg`, PS256 token.** Allowed; the JWK names none, so the key is bound to
   `PS256` and verifies. With the JWK naming `RS256`: 401, "does not match its key".
3. **A deployment that lists `HS512`.** `JwksTokenVerifier(..., algorithms=["RS256", "HS512"])`
   raises `ValueError` naming `HS512`; the service never starts. `["ML-DSA-65"]` raises too, naming
   it as unknown to PyJWT, until a toolkit release pins a PyJWT that ships it (DEC-1).
4. **Skew.** Clock at 1000; `exp` 990: accepted (990 + 30 > 1000); `exp` 940: refused.
5. **`If-Match`.** `"v3"`: write with `v3`, no read. `W/"v3"`: 409. `*`: read `v3`, write with
   `v3`. `"v1", "v3"`: read `v3`, named, write with `v3`. `"v1", "v2"`: read `v3`, 409, nothing
   written. `v3` (unquoted): 428.
6. **Accept.** `application/n-quads` → N-Quads; `text/*` → Turtle (first `text/` offered);
   `application/*` → JSON (first offered); `*/*` → JSON; `nonsense` → 406.
7. **N-Quads read.** `render(stored, <…/b7/graph>, Book, N_QUADS)`: the bookkeeping triples about
   the graph IRI and the internal slots are left out as today; the rest goes into a `Dataset` graph
   `<…/b7/graph>` and is serialised; each line ends with `<…/b7/graph> .`. TriG holds the same
   graph in one block.
8. **A loaded JSON-LD file with a named graph.** `{"@id": "urn:g", "@graph": [...]}` → PyLD gives
   quads in `<urn:g>` → `InvalidGraph("a loaded file holds one graph")`; nothing is sent to the
   store. Before: the named triples were dropped silently.

Idempotency: nothing here changes how writes are retried. `matched_version` reads before a guarded
write; the write stays the one check, so a retry after a 409 is safe. The JWKS refresh keeps its
single flight and cooldown.

Order of work: the swaps run the *old* tests against the new code before the old code is deleted
(B-1: `test_negotiation.py`; B-2: `test_loading.py` and `test_documents.py`; B-7: the suite).

### Anti-patterns

| Don't | Do instead | Why |
|---|---|---|
| Let a deployment's list re-admit `none` or HS* | Refuse at construction (PD-1) | One misconfiguration would hand out the signing secret |
| Trust PyJWT's algorithm inference for a JWK without `alg` | Bind the key to the token's checked algorithm (PD-2) | Inference says RS256 for every RSA key |
| Compare `If-Match` after stripping `W/` | Strong comparison; weak never matches (PD-4) | RFC 9110 §13.1.1 |
| A second JSON-LD parser or remote-context guard | `services/jsonld.py` only (PD-6) | One behaviour, one guard |
| Map media types to rdflib names (`"nt"`, `"turtle"`, `"xml"`) | Pass the media type (PD-10) | rdflib registers media types |
| Restate `RdfFormat`'s media types in Python | `vocabulary.media_types` (PD-11) | LinkML is the single source |
| `model_copy(update={"field": …})` | `model.replaced(field=…)` (PD-8) | `model_copy` skips validation |
| Log and raise the same error | Raise; the place that handles it logs (PD-9) | Logged twice |
| Edit a test to fit pyoxigraph | Record and keep rdflib (PD-13) | The suite is the gate |
| Fix a schemathesis finding by loosening the check | Fix the contract or the code, or file it (DEC-10) | The check is the point |

## Error matrix

| Failure mode | How it is detected | Expected handling |
|---|---|---|
| A token signed with an algorithm outside the instance's set | `_header` | 401, `InvalidToken`, no key fetch |
| A token whose `alg` differs from the JWK's `alg` | PD-2 | 401 |
| A JWK whose key type does not fit the token's algorithm | `PyJWK(...)` raises | 401 |
| A deployment lists `none`, HS*, an unknown name, or nothing | constructor | `ValueError`; the service does not build |
| `leeway_seconds` negative, above 300 or not finite | constructor | `ValueError` |
| `exp` past by less than the leeway | `_decode` | accepted |
| `If-Match` missing, blank or malformed | `matched_version` | 428 |
| `If-Match` with only weak tags, or naming no current version | `matched_version` | 409, nothing written |
| `If-Match: *` on an aggregate that is gone | `current()` raises `NotFound` | 404 |
| `If-Match: *` or a list from a caller who may delete or modify but not read the aggregate | `current()` reads in the caller's session | that read's answer (404 or 403); a single strong tag still works |
| A JWKS with one unusable key beside good ones | refresh | the bad key is skipped; its `kid` is unknown (401); the others verify |
| A JWKS with no usable key | refresh | `IdentityUnavailable` (503), as today |
| A JSON-LD body or loaded file with a relative IRI and no `@base` | `RelativeIriRefused` (PD-6) | `InvalidBody` (422) / `InvalidGraph`; nothing written |
| The aggregate changes between the version read and the write | guarded write | 409 |
| A malformed `Accept` range | `MimeTypeParseException` | 406 |
| RDF/XML cannot write a predicate | serialiser raises | 406 naming the type (PD-12) |
| A JSON-LD body or loaded file with a remote, file or `@import` context | `LOADER` refuses | `InvalidBody` (422) / `InvalidGraph`; nothing fetched |
| A JSON-LD body or loaded file that names a graph | `NamedGraphRefused` | `InvalidBody` / `InvalidGraph`; nothing written |
| An `RdfFormat` value without `media_type` | `media_types` at import | `ValueError`; a toolkit bug, caught by TC |
| `MessageLimitExceeded` in an observer | kit catch | one ERROR log, acked as today |
| `MessageLimitExceeded` over HTTP, or another mapped kind with status 500 | `toolkit_error` | 500 problem, one ERROR log with `exc_info` |
| An unmapped exception | `server_error`, then Starlette re-raises | 500 problem; the server's one ERROR log, none from the handler |
| pyoxigraph fails the gate | conformance or fast suite | revert to rdflib, record in a PD (PD-13) |
| A schemathesis finding | contract test | fixed in the change or an issue named in the PR |

## Risks / Trade-offs

- **RISK-1 The provider changes how it publishes keys** (outside the work: Zitadel releases).
  Likelihood medium over a year, impact high (every request 401). Mitigation: the default covers
  every algorithm Zitadel offers today, and PD-2 handles keys with and without `alg`; TC-03 to TC-06
  pin both. A new family (ML-DSA) needs a PyJWT release, and since PyJWT is pinned exactly
  (`pyjwt[crypto]==2.15.1`) also a toolkit release that bumps the pin, then a configuration change;
  ADR-004 and DEC-1 say so (DEC-1 re-shaped 2026-11-17). `technical-models`' setting refuses only `none` and `HS*` by pattern and leaves
  every other name to this constructor check (its PD-6, RISK-8), so the opening stays.
- **RISK-2 A wider default admits a weak key.** RS256 with a 1024-bit key would verify. Likelihood
  low (the provider generates the keys), impact medium. Accepted: key strength is the provider's;
  PyJWT warns on short keys.
- **RISK-3 Leeway extends a revoked token's life by 30 s.** Accepted: tokens live minutes; the
  leeway is a parameter.
- **RISK-4 mimeparse ranks a header differently from our parser.** Who is hurt: a client relying on
  a tie or an odd header. Likelihood low. Mitigation: the existing `ACCEPT` table runs unchanged, plus
  TC rows for ties and parameters; a difference stops the task (DEC-5's wrappers keep the refusal
  messages).
- **RISK-5 PyLD is stricter than rdflib's JSON-LD parser.** A file that loaded before may be
  refused (a named graph, a relative IRI). PyLD alone would drop relative IRIs silently; PD-6's
  `NO_BASE` check turns that into a refusal. Likelihood low, impact low (the consumer gets
  `InvalidGraph` with the reason instead of lost triples). Accepted; the spec delta says it.
- **RISK-6 pyoxigraph differs from rdflib in a way the suite does not cover**, so tests pass on the
  fake and fail on Fuseki. Likelihood low: oxigraph is closer to Fuseki than rdflib is (RDF 1.1
  literals, atomic updates). Mitigation: the container conformance run stays the authority.
- **RISK-7 A client that matched JSON on `*/*` with a type order of its own** is unaffected: JSON
  stays first. A client that sent `application/rdf+xml` and got 406 now gets RDF/XML. Accepted.
- **RISK-8 Logging every 500** may add log volume under an outage (a store down answers 503, not
  500, so the volume is bounded to real faults). Accepted.
- **RISK-9 A proxy weakens the ETag** (outside the work: nginx turns a strong `ETag` weak when it
  gzips a response). A client that echoes it then gets 409 on every write. Likelihood medium for a
  deployment behind nginx with gzip on JSON; impact high (no write succeeds). Mitigation:
  `howto/adopt.adoc` says the proxy must not compress the service's responses, or must pass the
  `ETag` through unchanged; TC-21 pins the 409 so the behaviour is known. Weak matching is DEC-4's
  call, raised with the developer (OQ-3).
- **RISK-10 schemathesis does not resolve beside the pins** (pytest 9.0.3, hypothesis 6.170.14).
  Likelihood low, impact low. Mitigation: task 3.2 stops at `make lock` and reports; the contract
  test is then shaped again, not forced.
- **RISK-11 Plain JSON drops a language tag** (PD-6): a client that reads JSON and writes it back
  loses the tag. Accepted: JSON-LD keeps it; plain JSON follows the published schema.
- **Trade-off:** `If-Match: *` and lists cost one read; a single strong tag, the common case,
  costs nothing new.

## Open Questions

For the developer, one round (each with the leader's recommendation; the PLAN proceeds on the
recommendation):

- **OQ-1** Serve a listing page as N-Quads or TriG (each item in its graph, the paging in `Link`
  and a total header)? Recommendation: not in this change; shape it with a dump or export route if a
  consumer asks.
- **OQ-2** Answer `If-Match` failures with 412, as RFC 9110 says, instead of 409? Recommendation:
  keep 409 (DEC-4); revisit at the next major version.
- **OQ-3** (from the attack) Match a weak tag after all, since a proxy may weaken the `ETag`
  (RISK-9)? Recommendation: keep strong comparison (DEC-4) and document the proxy rule; a version
  token is exact, so a weak match would hide nothing but the proxy's change.

## Delivery decisions

Taken by the lead (R-0007), shown to the developer at the end of each stage; the developer may
overrule any of them. D-1 to D-7 agreed by the developer, 2026-11-17.

- **D-1 Stage 1 review set.** Two read-only passes, L2 and L3, each its own reviewer (P-0005: one
  pass of L2 and L3 per stage; `develop/agents.adoc`: L1, L2 and L3 are never combined). The full
  review (L1, L2, L3, L4+L5) runs once, after stage 3. Then one fresh checker (MEDIUM).
- **D-2 Stage 1 tester: no.** The PLAN has no `## Invariants` section and the appetite is MEDIUM,
  so the stage-loop condition is not met; the PLAN schedules the tester after task 2.5.
- **D-3 Stage 1 builders in parallel** (R-0004). Five builders in their own worktrees from
  `b196bb8`, on disjoint files: 1.1 then 1.2 (`jwks.py`, one after the other), 1.3, 1.4, 1.5, 1.6.
  The lead commits each task in its worktree and cherry-picks it onto
  `change/manual-revision-notes-s1`; `rdf_persistence/__init__.py` and
  `tests/unit/test_public_api.py`, the only files two tasks may share, are merged by the lead and
  the task gate is re-run (T2).
- **D-4 Impact of task 1.6 read as low.** GitNexus rates `MessageLimitExceeded` CRITICAL (48
  direct): it counts every importer of `domain/exceptions.py`. The change only adds an optional
  `command=` keyword; the three call sites (`messagebus.py:153`, `:182`, `test_receive.py:266`)
  keep working unchanged. The other tasks rate LOW (`JwksTokenVerifier`, `dataset_of`,
  `install_problem_handlers`) or MEDIUM (`expected_version`, 5 direct; `Mapper`, 14 direct, all
  keeping their signatures).
- **D-5 Three expiry tests changed in task 1.1.** The PLAN said the existing refusals stay green
  (and named `tests/unit/services/`; the file is `tests/unit/adapters/test_token_verifier.py`).
  DEC-2's default leeway accepts a token that expired up to 30 s ago, so `test_an_expired_token` and
  the `expired` and `expires-this-instant` cases now issue tokens past the leeway; the exact-instant
  refusal is kept by TC-11 (`leeway_seconds=0`). The leeway is added to "Breaking changes".
- **D-6 Builder departures accepted.** TC-30 is a lasting `ast` scan in the suite, not a one-off
  ast-grep (ast-grep is no project dependency). TC-24b uses `label` (`skos:prefLabel`): the toy has
  no `title`, and the path is the same string slot. TC-26 calls `_require_room` directly: the TC
  names it, and a real cascade of 600 members on the fake store is too slow. Builder 1.3 edited
  three files with a python string replace instead of Edit; the lead read every changed site.

- **D-7 A CI timeout quarantined (#142).** `test_heads_of_hundreds_of_iris_is_one_query` times out
  at 120 s on the CI runner on unchanged code (develop's run for #140 failed, #139's passed; PR #141
  failed the same way) and passes locally. Per testing.adoc rule 14 it is marked `quarantine` with
  the issue linked; not a stage 1 defect. Candidate fix: task 2.5's pyoxigraph `FakeStore`, or
  `test-debt-paydown`.

- **D-8 Stage 2 base and order.** PR #141 (stage 1) was still open when stage 2 started, so the
  builders of 2.1 and 2.2 start from its head (`dea7058`); `change/manual-revision-notes-s2` was
  moved onto `develop` (`cc1b283`) once #141 merged, and their tasks are applied there. Builders in parallel on disjoint files (R-0004): 2.1 (`negotiation.py`,
  the lock) beside 2.2 (`services/jsonld.py`, `documents.py`, `loading.py`); then 2.4 beside 2.5
  (2.5 after 2.1 for the lock); 2.3 last, since it removes what 2.2 and 2.4 leave. Review set as
  D-1: L2 and L3, each its own reviewer, then one checker; tester after 2.5 (tasks.md).
- **D-9 Impact of task 2.1 read as low.** GitNexus rates `_negotiate` CRITICAL: it sits on every
  read and write route (11 processes). Its signature stays; the unchanged `ACCEPT` table (TC-35) is
  the guard, and any edit to an existing test stops the task (PD-5). 2.2's `dataset_of` and 2.5's
  `FakeStore` rate LOW (the latter a lower bound: 68 test files use it, the unchanged suite is its
  gate, PD-13).

- **D-10 One existing test changes in task 2.2.** `test_the_generic_put_cannot_set_a_state[accepted]`
  (`tests/unit/entrypoints/test_workflow_routes_adversarial.py`) PUTs a plain JSON body whose
  `workflow_status` is `"accepted"`, a relative IRI in an `@id`-typed slot. PyLD dropped that
  triple and the route answered 403; PD-6's `RelativeIriRefused` now answers 422 `invalid-body`
  (TC-42c, the Breaking changes row of 2.2). The test's point, a generic PUT cannot set a state,
  still holds, so the `accepted` row expects 422 and the near-miss IRI row keeps its 403. TC-41 is
  tested with a JSON-LD body: a plain JSON body cannot carry `@graph` (`_typed` refuses unknown
  keys first). `services/jsonld.py` parses PyLD's output with the media type
  `application/n-quads` (PD-10), not rdflib's name `nquads`.
- **D-11 Two existing tests change in task 2.4.** (a) `test_hard_check.py::
  test_every_annotation_the_toolkit_reads_has_an_allowed_value_rule_or_a_pattern` requires each
  `RpAnnotation` member in an allowed-value or a pattern group of `generation/checks/hard.py`. A
  media type fits neither, and the hard check reads a consumer's classes, slots and schema, never
  the toolkit metamodel's permissible values where `media_type` lives. So `hard.py` gains
  `METAMODEL_ANNOTATIONS = (RpAnnotation.MEDIA_TYPE,)` (read from the toolkit's own metamodel;
  `vocabulary.media_types` refuses a missing one at import, TC-46 to TC-48 pin the values) and
  the test's union includes it. Rejected: a media-type pattern check over permissible values
  (a new check for a tag no consumer writes). (b) `test_loading.py`'s `rdflib_message` helper read
  `_RDFLIB_FORMATS`; it now reads `media_types(RdfFormat)`, so the table is deleted as PD-11 says.
  Neither test's assertions change.
- **D-12 How F-4 finds what PyLD drops.** PyLD 3.3 has no option that reports dropped statements,
  so `triples_of` walks `jsonld.expand`'s output (every `@id`, `@type` and property IRI) before
  `to_rdf`. Expansion itself drops a property whose key holds a space, with its value, so a second
  walk reads the document's own keys outside `@context` and refuses one with a colon and a
  character `domain/sparql.FORBIDDEN_IRI_CHARS` forbids (a term named with both is refused too; a
  contrived case, accepted). An undefined term (`"name": "x"` with no context) is still dropped:
  that is JSON-LD's rule, rdflib's parser did the same, and bodies refuse unknown keys first. The
  fixers sorted the tester's tests: kept those that found T-1, T-2, T-3, T-5, T-6 and those that
  alone cover an error-matrix row or bound a cost; deleted the rest (listed in PR #143).
- **D-13 The checker's unmet items, fixed before the merge** (developer, 2026-11-17). The checker
  passed stage 2 with two items unmet: F-5's pages say a JSON-LD file is refused "with the reason"
  but quote no message (checker W2), and the cold reader read "refused for a named graph" as
  refusing the target graph; and the Accept changes of 2.1 and F-3 carry no `BREAKING CHANGE:`
  footer (W1). One fixer: the load section of `howto/adopt.adoc` names each refusal (a graph of
  its own declared in the document; a relative or invalid IRI, every IRI must be absolute as no
  base is applied; a `@context` not given in the document, alone or in an array; a document that
  is not an object or an array) with its exact `InvalidGraph` message in `str(error)`; the other
  pages and docstrings say the same in one line and point to it; `_entries`' docstring names both
  headers (S3); `architecture/api.adoc` row 9 adds the invalid IRI (S4). Its commit carries the
  Accept footer, so no pushed commit is rewritten. One full-gates run, then CI. The developer also
  granted the lead the merge on green CI until this EPIC ends.
- **D-14 Stage 3 team and order.** Base `8528251` (PR #143 merged). Builders in parallel on
  disjoint files (R-0004), each in its own worktree: 3.1 (`domain/media.py`, `documents.py`,
  `openapi.py`, their tests) beside 3.3 (docs pages and the mapper docstring only; 3.1 edits no
  page under `docs/`); then 3.2 beside 3.4, both after 3.1 (the contract test reads the OpenAPI
  document 3.1 widens; `representations.feature` needs the new types). Tester: no (MEDIUM, no
  `## Invariants`, as D-2). Last stage, so the full review runs now (D-1, P-0005): L1, L2, L3
  each its own reviewer, L4 with L5 one; then one checker; a cold reader for `howto/adopt.adoc`.
- **D-15 Impact of task 3.1 read as low.** GitNexus rates `Documents.render` CRITICAL (60
  processes, 2 direct callers): it sits on every document route, as `_negotiate` did (D-9). Its
  signature stays; `domain/media.py` (MEDIUM, 12 importers) only gains constants and a longer
  `REPRESENTATIONS`. `openapi._document_media` (not in the index; read by text) has 7 call
  sites, all in `openapi.py`, so its `turtle=` → `rdf=` rename stays in one file. The two tests the PLAN names are the only existing tests that may change;
  any other edit to an existing test stops the task.
- **D-16 Builder departures in 3.1 and 3.3 accepted.** 3.1: the refusal-by-name test is in the
  unit `tests/unit/entrypoints/test_negotiation.py`, not the integration file the PLAN named; four
  new `ACCEPT` rows are additions; TC-62 is held by the existing wildcard rows; TC-58 is tested on
  the unit router only; the builder edited with python string replaces and one `sed -i`, so the
  lead read every changed site and re-ran its gate (T1: its last `test-fast` ran before a fix in
  `documents.py`). 3.3: ADR-001 to ADR-003 are *Accepted* by the developer's "I agree with all
  improvement suggestions" (`inputs/answers-2026-11-17.md`); the docstring keeps three reasons,
  the re-check showed the blank-node and language-tag reasons do not hold. `tests/audit/scenario-map.csv`
  names the renamed requirement by its old title in 38 rows; it follows the RENAMED delta at archive.
- **D-17 The contract run's two findings** (task 3.2, PD-15). schemathesis 4.33.4 resolved beside
  the pins (RISK-10 did not occur). (1) `GET /context.jsonld` answered JSON-LD but was documented
  as JSON: a small route fix, made (`JsonLdResponse`, guarded by its own contract test). (2) A
  plain JSON read carries `type`, which the generated object component schemas
  (`additionalProperties: false`) do not list: every aggregate read fails the response-schema
  check. The fix is in the component generator, not a small change in `openapi.py` or a route, so
  per PD-15 it is issue #148; TC-63 is `xfail(strict=True)` naming #148, so the fix removes the
  marker by failing. TC-64 (an undocumented 418 fails the run) shows the check is live. A probe
  adding `type` made every operation pass, so these are the only two findings.

### Stage 1 review findings (L2, L3)

Accepted, re-labelled Critical (fixed in the one fix pass):

- **F-1** (L2 W1) `howto/event-driven.adoc:323` says the bus logs a `MessageLimitExceeded`; after
  PD-9 it raises without logging. Critical: a how-to that contradicts the code sends an operator
  looking for a log line that never comes (L2 doc agreement). Fix: the bus raises; the place that
  handles the error (the kit, or the problem handler for HTTP) logs it once.
- **F-2** (L2 W3) The rp-service-api scenario "a list of versions" has no route test; TC-19 covers
  only a list that names nothing, so a wrong `current` read would pass. Critical: a spec scenario
  without a test breaks the traceability the checker verifies (`bdd-gherkin`). Fix: a `DELETE` with
  `If-Match: "v0", <etag>` answers 204, then the `GET` answers 404.

Under the floor (not fixed in this stage):

- L3 W1 `RpModel.replaced` could be shadowed by a consumer slot named `replaced`; the full review
  after stage 3 weighs a `model_`-prefixed name or a function.
- L3 S2 the `current` closures read the whole aggregate for its version; a version-only read when
  stage 2 or `technical-models` touches `Aggregates`.
- L3 S3 TC-30 scans `domain` and `services` only; `adapters` and `entrypoints` are clean today.
- L2 W2 the `expires-this-instant` case id now tests the leeway's edge (recorded in D-5).
- L2 W4 the adversarial `small_limit` fixture patches `Mapper.max_roots` on the class instead of
  building `Mapper(max_roots=)`; its assertions are unchanged.
- L2 W5 asserts without a message in `test_negotiation.py` and `test_documents.py` (checklist rule 10).
- L2 S1 TC-05's `pytest.raises` has no `match`.
- L2 S2 TC-21 sends an unchanged body, so "the book is unchanged" is not observed.
- L2 S3 TC-26 reaches private members (recorded in D-6).
- L2 S4 `howto/commits.adoc:138` and `howto/adopt.adoc:906` do not name `Mapper(max_roots=)`,
  `algorithms=` or `leeway_seconds=`; task 3.3 updates `howto/adopt.adoc`.
- L3 to L4/L5 notes (positional `[2]`/`[1]` reads in `router.py`, `PyJWKSetError` raised to reach an
  `except`, the bare `"error.type"` string, `VALUE_KEY`/`LANGUAGE_KEY` beside the other JSON-LD keys)
  go to the full review after stage 3.

### Stage 2 review findings (L2, L3, tester)

Reviewers: L2 (10 findings), L3 (5), the adversarial tester (6: T-1 to T-6). No finding was labelled
Critical; the lead re-labels these, each with its reason. The PLAN's own failure test applies to
the swaps: "a swap changes behaviour a consumer can see beyond what the spec deltas and Breaking
changes say" ("How it succeeds, how it fails").

- **F-3** (T-2, T-3, L2 W1) The Accept swap changed more than PD-5 accepted: `*/turtle`, `*/json`,
  `*` and a header of only such members are served JSON (was 406); `text/turtle;q=-1` outranks a
  positive `q` (was not acceptable); one malformed member refuses the whole header (`text/turtle,
  foo` was Turtle, now 406); a comma inside a quoted parameter (`profile="a,b"`) splits the member
  (was JSON-LD, now 406). Critical: the PLAN's failure test. Fix in `_negotiate`, keeping
  mimeparse: split on commas outside quoted strings; skip a member that does not parse, whose type
  is `*` with a subtype other than `*`, or whose type or subtype is empty (as before PD-5: such a
  range matched nothing); a header with no usable member left is 406, as before. `q`: unparsable
  or empty reads as 1 (PD-5's accepted change, now naming the empty case), negative reads as 0
  (not acceptable, as before), above 1 reads as 1 (a tie with `q=1`; the one further accepted
  change, recorded in Breaking changes). Tests: the tester's failing rows for T-2 and T-3; the
  `/turtle, application/json` row expects JSON (as before PD-5), not 406; rows for the four L2 W1
  headers.
- **F-4** (T-1, T-5, T-6) `triples_of` still loses statements without a word: a relative `@id`
  under `"@base": null` (T-1), an IRI that is not valid (`https://ex.org/a b`, a control
  character: T-5) and a scalar document (`123`, `true`: T-6) all give an empty or shorter graph.
  A loaded file replaces its graph, so such a file empties it. Critical: the silent loss PD-6
  exists to end, and for loaded files a change beyond the Breaking changes row (rdflib's parser
  kept such IRIs). Fix in `services/jsonld.py`: refuse a document that is not a JSON object or
  array; refuse any IRI that is relative or not valid, found in the document PyLD expands (walk
  `jsonld.expand`'s output, or a PyLD option if one reports dropped statements; no hand-written
  JSON-LD processing beyond that walk); keep `NO_BASE` for the relative case. Callers map the new
  refusals as the others (`InvalidBody` / `InvalidGraph`, messages "a JSON-LD document must use
  absolute IRIs", "… holds an IRI that is not valid", "a JSON-LD document is an object or an
  array"). The Breaking changes row of 2.2 names them.
- **F-5** (L2 W4) A loaded JSON-LD file is now refused for a named graph, a relative IRI or a
  context that is not inline, but `howto/adopt.adoc:1187-1205`, `architecture/index.adoc:164-165`,
  `architecture/data-flows.adoc:807` and the docstrings of `Session.load_graph` and `parse_graph`
  still say only "data that does not parse raises `InvalidGraph`". Critical: a breaking change a
  consumer is not told about where they read (L2 doc agreement, as F-1). Fix: one sentence in
  each naming what a JSON-LD file is refused for and the message.
- **F-6** (L2 W5) TC-42c names a JSON-LD body; the test sends plain JSON and carries no TC tag.
  Critical: a TC row without its test breaks the traceability the checker verifies (as F-2). Fix:
  parametrise over JSON and JSON-LD bodies, tagged `# TC-42c`.

Fixed by the lead in the spine (no code): L2 W2 (Error matrix said 400; the code and D-10 say
422), L2 S1 (TC-35 counts 18 rows), L2 S2 (PD-17's TC status and `session.py:169`).

Under the floor (not fixed in this stage; the full review after stage 3 weighs them):

- T-4 a graph named `urn:x-rdflib:default` reads as the default graph: a contrived name, and its
  statements are kept, not lost.
- L3 W1 `services/jsonld.py` defines its own `N_QUADS`; `domain/media.py` has it.
- L3 W2 `triples_of` lets PyLD's and rdflib's exception types through, so both callers keep a
  broad `except Exception` that turns a bug of ours into a client error (as before PD-6 for
  bodies).
- L2 W3 no test feeds valid JSON that is not valid JSON-LD to `_parse_jsonld`; the JSON-LD row of
  `test_the_message_of_a_refused_file_is_the_parsers_own` compares with rdflib's parser; a loaded
  file's PyLD message is not truncated as a body's is.
- L3 S1 the three refusal mappings are written twice and the two `NOT_INLINE` texts differ.
- L3 S2 `METAMODEL_ANNOTATIONS` is read only by its test; its comment overstates.
- L3 S3 `test_documents.py` imports `dataset_of` from `documents`; `test_jsonld.py:124` uses
  `format="nt"`; TC-44's regex sees double quotes only.
- L2 S3 `test_jsonld.py:61`'s name contradicts its document; TC-40 does not assert
  `sent("query") == []` (the session-level "no graph is created" rows are now covered by
  `test_loading_formats_adversarial.py`, checker S5).
- Checker S2 (the PR body's decision range and Accept bullet) fixed in the PR body.
- Cold reader: the load section's older gaps (enum names of the four formats, the import of
  `InvalidGraph`, the HTTP status, the type of `data` and of the return, "the sweep") are not this
  change's; task 3.3 touches `howto/adopt.adoc` and may take them.
- L2 S4 `test_hard_check.py:728`'s name and message do not mention the metamodel group.
- L2 S5 TC-43's golden is one plain triple; richer samples would show where PyLD and rdflib differ.

### Full review findings (L1, L2, L3, L4+L5; cold reader)

The full review of the EPIC (D-1, P-0005) ran on PR #151 against the gate report of `f059d3d`.
Reviewers: L1 (3 findings), L2 (9), L3 (8), L4+L5 (11); the cold reader read `howto/adopt.adoc`.
Only L3 labelled one Critical; the lead re-labels the rest below, each with its reason.

Accepted, Critical (fixed in the one fix pass):

- **F-7** (L3 C1, L2 W2, L4+L5 W1, L1 note) A create or replace with `Accept: application/rdf+xml`
  commits, then `render` refuses RDF/XML with 406. The client is told the write failed although it
  was stored: a retried `POST` mints a second aggregate, a retried `PUT` gets 409. Critical: three
  lenses found it on their own, and it is a write a consumer cannot see, which PD-12's "answered
  406" never meant. Fix: the 406 comes before anything is written, on create, replace and the
  tenant root; the route-level tests show 406 and that nothing was stored.
- **F-8** (L1 W1) rdflib's RDF/XML writer passes characters XML 1.0 forbids (`\x00`–`\x08`, `\x0B`,
  `\x0C`, `\x0E`–`\x1F`) through raw: a read answers 200 with a body no XML parser accepts.
  Critical: the rp-service-api delta says an aggregate a serialisation cannot express SHALL be
  answered 406; this one is answered 200 and broken. Fix: such a literal is refused with the same
  `NotAcceptable` as a predicate with no XML local name, and the F-7 check covers it.
- **F-9** (L4+L5 W2, L3 W2 in part) The `except ValueError` in `_serialised` wraps all five RDF
  writers, so a defect in the Turtle, N-Triples, N-Quads or TriG path is answered 406 "no form"
  instead of 500. Critical: the Error matrix sends our own defects to 500, and the 406 is for
  RDF/XML only (PD-12). Fix: catch only for RDF/XML. The same lines change for F-7 and F-8.
- **F-10** (L3 W1, L1 W2) TC-63 runs every operation in one loop under `xfail(strict=True)`; the
  first #148 failure ends the loop, so no check (server error, status, content type, schema) runs
  on the operations after it. Critical: PD-15's contract test, ADR-003's confirmation, checks
  almost nothing until #148 is fixed. Fix: one case per operation; only the operations #148 hits
  expect a failure, and only of `response_schema_conformance`; every other check of every
  operation must pass. Still strict, so fixing #148 removes the markers by failing.
- **F-11** (L2 W3) `architecture/data-flows.adoc:394`, `architecture/index.adoc:204` and
  `questions.adoc:422` still name only JSON, JSON-LD and Turtle. Critical: doc agreement on what
  this stage delivers (PD-16, as F-1 and F-5). Fix: name the seven types or link
  `api.adoc#representations`.
- **F-12** (cold reader) The `#etag-proxy` test in `howto/adopt.adoc` reads through the proxy
  without `Accept-Encoding: gzip`, so nginx does not compress and the test passes behind the very
  proxy RISK-9 warns of. Critical: this stage's own text, and the check it gives cannot fail. Fix:
  the read sends `Accept-Encoding: gzip`, and the page says how to pass the `ETag` through
  unchanged or names the nginx setting.

- **D-18 The scenario map is mapped at archive** (L2 W1). `tests/audit/scenario-map.csv` has no row
  for any test this EPIC added (stages 1 to 3). `make refresh-map` is not part of `check-all`, so
  no gate is red; the map is brought up to date in the archive step, together with the 38 renamed
  rows (D-16), and the hand-over note names it.

Under the floor (not fixed; for the hand-over note and later changes):

- L1 S1 `adapters/jwks.py` keeps a JWK whose `use` is `enc` (PyJWT's client drops it); low risk, a
  provider that publishes an encryption key with a `kid`.
- L2 W4 TC-57 does not assert which graph holds the tenant root's quads; L2 S4 TC-58 checks only
  the replace response's media type.
- L2 S1 `questions.adoc:319` and `howto/adopt.adoc:1588` drop "after a toolkit release raises the
  PyJWT pin" from DEC-1's condition; L2 S2 `token_algorithms.feature:31` drops the spec's second
  THEN without saying it cannot be tested.
- L2 S3 only the read's 200 is asserted to list the seven types; F-10 covers the others once it
  passes.
- L2 S5 still open from stages 1 and 2: the class-level `Mapper.max_roots` patch,
  `howto/commits.adoc:138`, `test_jsonld.py:61`'s name.
- L3 W2 the broad `except Exception` around `triples_of` (`documents.py:301`, `loading.py:45`);
  L3 S4 the refusal mappings written twice; L3 S3 / stage 2 L3 W1 `jsonld.py`'s own `N_QUADS`.
- L3 S1, L4+L5 W4, L4+L5 S6 "the RDF serialisations" defined three ways (`REPRESENTATIONS[2:]`,
  `not in (JSON, JSON_LD)`, the `rdf=` flag); an `RDF_REPRESENTATIONS` constant when next touched.
- L3 S2, L4+L5 S7 the context route's OpenAPI entry and `JsonLdResponse` live in `router.py`.
- L3 S5 `RpModel.replaced` can be shadowed by a consumer slot; rename before 1.0.
- L4+L5 W3 the five RDF serialisations run on the event loop (framing runs in a worker); an
  aggregate near `MAX_NODES` stalls the loop while it serialises.
- L4+L5 S1 JSON-LD keywords in three modules; S2 positional `[2]`/`[1]` reads of `Stored`; S3
  `PyJWKSetError` raised to reach an `except`; S4 algorithm names repeated in the testkit; S5 the
  bare `"error.type"` string.
- Cold reader, older text: `loaded_graphs=[loaded]` replaces earlier loaded graphs (the next
  paragraph says so); the `rdf_format` table row versus the prose example; `max_roots` as the batch
  size; "`@context` not given"; the missing `CommitTooLarge` import and `book_iri` arguments; what
  a token whose algorithm is outside `algorithms=` gets.
- Stage 1 and stage 2 floor items not named above stay as they were listed.

- **D-19 The fix pass's departures and its one new finding.** F-7: `Documents.require_form` checks
  the graph to be stored for an RDF/XML form before any write (`Aggregates.create` and `replace`
  take `represented_as`); the route tests use a control-character title, because the closed
  shapes refuse an unknown predicate with 422 before any form is chosen, and the unit tests cover
  the predicate case. F-10: one case per operation, the schema check apart from the other three.
  Run apart, the events route also fails the schema check: it documents each SSE event as a
  string and sends an object first. It is not #148; filed as #153 and marked `xfail(strict=True)`
  naming it. The fixer used one `sed -i` for a two-call rename in `test_contract.py`; the lead read
  the whole diff. An intermittent pyparsing error (`Param.postParse2()`) seen once under two
  concurrent runs is SPARQL parsing's thread safety, not this change; noted for the hand-over.
- Checker W1 (the stage 3 As built row, What Changes and `tasks.md` after the fix pass) fixed by
  the lead in the spine. Under the floor: checker S1 the F-9 test runs N-Quads only, not TriG; S2
  `SSE_EVENT_SCHEMA` has no `raises=FailureGroup`; S3 `XML_FORBIDDEN` leaves out U+FFFE, U+FFFF and
  lone surrogates (not probed: what rdflib's writer and the response do with one is unchecked).
