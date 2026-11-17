> Derives from: EPIC `manual-revision-notes` (proposal.md). Three stages, one PR each into `develop`.
> Type: Implementation.

`PD-n` is a decision of [design.md](design.md). `T` is a tenant of the toy library
(`tests/toy.py`, `tests/toy_service.py`), `B` a `Book` at version `v3`. `signer` is the testkit
`TokenSigner`, `clock` the testkit `ManualClock`.

Every task is test first: the TC rows are written and seen failing before the code. Its gate is
`make test-changed check-quality`, or `make test-fast check-quality` where the task says so (it
changes `domain` or a port, or its reach is wide). After a schema change: `make check-generated`.

## Stage 1: defects (PR 1)

- [x] 1.1 PD-1, PD-3 (A-3, A-4, DEC-1 to DEC-3): `algorithms=` and `leeway_seconds=` on
  `JwksTokenVerifier`, `DEFAULT_ALGORITHMS`, `DEFAULT_LEEWAY_SECONDS`; `TokenSigner(algorithm=...)`
  in `testkit/tokens.py`, generating an RSA, EC (P-256/384/521) or Ed25519 key to fit, the JWK
  naming `alg`; `jwks.RS256` stays (the testkit imports it), `ALLOWED_ALGORITHMS` and `ES256` go
  (breaking, design "Breaking changes"). Layer: adapters, testkit. Tests in `tests/unit/adapters/test_jwks.py`; the existing
  refusals in `tests/unit/services/test_token_verifier.py` stay green. Gate:
  `make test-changed check-quality`.

| ID | Input | Expected |
|---|---|---|
| TC-01 | default verifier; tokens signed RS384, RS512, PS256, PS384, PS512, ES256, ES384, ES512, EdDSA | each accepted |
| TC-02 | `algorithms=` each of `["none"]`, `["NONE"]`, `["HS256"]`, `["hs512"]`, `[]`, `["ML-DSA-65"]`, `["RS256", "HS512"]` | each a `ValueError` naming the entry (or "empty") |
| TC-07 | `algorithms=["ES256"]`; a token signed RS256 | `InvalidToken`, no key fetch (`signer.jwks_requests` unchanged) |
| TC-08 | clock 1000; `exp` 990, 971, 970, 940 with the default leeway | 990 and 971 accepted; 970 and 940 refused "expired" |
| TC-09 | clock 1000; `nbf` 1020, 1031 | 1020 accepted; 1031 refused "not yet valid" |
| TC-10 | `leeway_seconds=` -1, 301, `inf`, `nan` | each a `ValueError` |
| TC-11 | `leeway_seconds=0`; `exp` 1000 at clock 1000 | refused (today's behaviour) |

- [x] 1.2 PD-2: the JWK mappings cached, the key bound to the token's algorithm. Layer: adapters.
  Tests in `tests/unit/adapters/test_jwks.py` with a JWKS served by `httpx.MockTransport`. Gate:
  `make test-changed check-quality`.

| ID | Input | Expected |
|---|---|---|
| TC-03 | an RSA JWK with no `alg`; tokens PS256 and RS384 signed with its key | both accepted |
| TC-04 | an RSA JWK naming `RS256`; a PS256 token with its `kid` | `InvalidToken` "does not match its key" |
| TC-05 | an EC P-256 JWK with no `alg`; a token with header `RS256` and that `kid` | `InvalidToken` |
| TC-06 | a JWKS whose only key has no `kty` | `IdentityUnavailable` at refresh, as today |
| TC-06b | a JWKS of a key with no `kty` (`kid` `bad`) and a good RSA key (`kid` `k1`) | a token for `k1` accepted; one for `bad` `InvalidToken` "unknown to the issuer" |

- [x] 1.3 PD-4 (A-5, DEC-4): `matched_version`; `expected_version` kept, strict. The five callers
  in `entrypoints/router.py` (`DocumentApi.replace`, `remove`; `TenantApi.delete`, `set_grants`,
  `set_label`) call `matched_version` with `current` as PD-4 names it. `howto/workflow.adoc:189`
  says what `expected_version` now refuses. Layer: entrypoints, docs. Tests in
  `tests/unit/entrypoints/test_negotiation.py` (functions) and `tests/unit/entrypoints/test_router.py`
  (routes). `test_if_match_names_the_version_it_expects` (`:94`) **changes**: `W/"7f3a"` becomes a
  `Conflict` row and `7f3a` a `PreconditionRequired` row (breaking, design "Breaking changes"; the
  commit carries the footer). Gate: `make test-changed check-quality`.

| ID | Input | Expected |
|---|---|---|
| TC-12 | `"v3"`; `current` counting its calls | `v3`; `current` not called |
| TC-13 | `W/"v3"`, current `v3` | `Conflict` |
| TC-14 | `*`, current `v3` | `v3` |
| TC-15 | `"v1", "v3"` and `"v1",W/"v2" , "v3"`, current `v3` | `v3` |
| TC-16 | `"v1", "v2"`, current `v3` | `Conflict` |
| TC-17 | `None`, `""`, `"  "`, `v3`, `"v3`, `*, "v3"` | each `PreconditionRequired` |
| TC-18 | `PUT` of `B` with `If-Match: *` | 200; `B` replaced |
| TC-19 | `DELETE` of `B` with `If-Match: "v1", "v2"` | 409; `B` still there |
| TC-20 | `PUT` of a tenant's grants with `If-Match: *` | 200 |
| TC-21 | `PUT` of `B` with `If-Match: W/"v3"` | 409 |
| TC-21b | `expected_version` of `"v3"`; `W/"v3"`; `*`; `"v1", "v3"` | `v3`; `Conflict`; `PreconditionRequired` naming `matched_version`; the same |
| TC-21c | `"v1", , "v3"`, current `v3` | `v3` (the empty member skipped) |

- [x] 1.4 PD-6 part (A-1): `dataset_of` emits `language` and `rdf:langString` for a tagged literal
  (still in `documents.py`; it moves in 2.2); `render` for plain JSON turns a language value object
  into its value. Layer: services. Tests in `tests/unit/services/test_documents.py`. Gate:
  `make test-changed check-quality`.

| ID | Input | Expected |
|---|---|---|
| TC-22 | a graph with `"Dune"@en` | `dataset_of` holds `{"type": "literal", "value": "Dune", "language": "en", "datatype": rdf:langString}` |
| TC-23 | that graph framed with a frame of a string slot | the JSON-LD value keeps `@language: en`; `jsonld.to_rdf` of it is isomorphic to the graph |
| TC-24 | `"a\\r"` (backslash, r) and `"x"^^xsd:integer` | unchanged from today (the PyLD workaround holds) |
| TC-24b | a book whose title is `"Dune"@en`, rendered as JSON and as JSON-LD | JSON: `"title": "Dune"`; JSON-LD: `{"@value": "Dune", "@language": "en"}` |

- [x] 1.5 PD-7, PD-8 (A-2, A-6): `Mapper(max_roots=)` and its property; `UnitOfWork` falls back
  to it; `_require_room` uses it; `RpModel.replaced`; the eight sites. Layer: domain, services.
  Tests in `tests/unit/domain/test_rp_model.py`, `tests/unit/services/test_mapper.py`,
  `tests/unit/services/test_collaboration_collections.py`, and the existing tests of the eight
  sites (`test_iris*.py`, `test_visible_part.py`, `test_collaboration_workflow.py`,
  `test_collaboration_discussion.py`, `test_session_activity.py`) unchanged. Gate:
  `make test-fast check-quality`.

| ID | Input | Expected |
|---|---|---|
| TC-25 | a mapper with `max_roots=3`; a cascade of a collection holding 3 members | `CommitTooLarge` naming 3 |
| TC-26 | `max_roots=1000`; a collection of 600 members | no `CommitTooLarge` from `_require_room` |
| TC-26b | `UnitOfWork(session, Mapper(..., max_roots=2))` committing 3 roots; the same with `UnitOfWork(..., max_roots=5)`; `Mapper(..., max_roots=0)` | `CommitTooLarge`; committed; `ValueError` |
| TC-27 | `Principal(id=…).replaced(id=…)` with a new IRI | a new `Principal`; the old one unchanged |
| TC-28 | `replaced(idd=…)` | `ValidationError` |
| TC-29 | `IdSpec(...).replaced(length="x")` | `ValidationError` (`model_copy` accepted it) |
| TC-30 | `ast-grep` for `model_copy(update=` in `rdf_persistence/domain` and `rdf_persistence/services` | only `mapper.py` (schema-keyed, keep.md) |

- [x] 1.6 PD-9 (A-7, DEC-12): the bus raises without logging; `MessageLimitExceeded(limit,
  command=)`; the problem handler logs each 500 once. Layer: domain, services, entrypoints. Tests in
  `tests/unit/services/test_messagebus.py` (the caplog test at :445 changes: no ERROR record from
  the bus, the class and id in the exception), `tests/unit/entrypoints/test_receive.py` (unchanged:
  one ERROR), `tests/unit/entrypoints/test_problems.py`. Gate: `make test-fast check-quality`.

| ID | Input | Expected |
|---|---|---|
| TC-31 | `MessageBus(..., limit=2)` with a looping observer | `MessageLimitExceeded` whose message ends `by Replace <id>`; no record from `rdf_persistence.services.messagebus` |
| TC-32 | an observer exceeding the limit in `kit.receive` | exactly one ERROR record in the whole run |
| TC-33 | a route raising `MessageLimitExceeded`, and one raising `StoredDataInvalid` | each a 500 problem and one ERROR record, message `internal error answered`, `exc_info` set, `error.type` the fully qualified class name (`rdf_persistence.domain.exceptions.StoredDataInvalid`) |
| TC-33b | a route raising `RuntimeError` (client with `raise_app_exceptions=False`) | a 500 problem; no record from `rdf_persistence.entrypoints.problems` (Starlette re-raises; the server logs) |
| TC-34 | a route raising `NotFound` | 404; no ERROR record |

Stage 1 closes with the lead's `make check-all` and `make test-containers`, the review set of
`develop/agents.adoc`, the fix pass, rebase on `develop`, PR 1.

## Stage 2: reuse (PR 2)

- [x] 2.1 PD-5 (B-1, DEC-5): `python-mimeparse==2.0.0` in `[project] dependencies` (`make lock`);
  `_negotiate` over `mimeparse.parse_media_range` and `quality_parsed` (PD-5, not `best_match`);
  the old helpers deleted. Layer: entrypoints. Tests: the
  `ACCEPT` table and the other tests of `tests/unit/entrypoints/test_negotiation.py` run first
  against the new code, unchanged; then the rows below. Gate: `make test-changed check-quality`.

| ID | Input | Expected |
|---|---|---|
| TC-35 | the existing `ACCEPT` table, all 18 rows | as today |
| TC-36 | `application/ld+json;profile="http://www.w3.org/ns/json-ld#compacted"` | JSON-LD |
| TC-37 | `text/turtle;q=0.5, application/ld+json;q=0.5` | JSON-LD (first offered of the tie) |
| TC-38 | `text`, `;q=1`, `a/b/c` | each `NotAcceptable` |
| TC-38b | `text/turtle, */*` and `application/*, text/turtle` | JSON, both (a quality tie; `best_match` would give Turtle) |
| TC-38c | `text/turtle;q=abc` | Turtle (mimeparse reads the bad `q` as 1; today 406), an accepted change (F-3 adds an empty `q` and a `q` above 1) |

- [x] 2.2 PD-6 (B-2, DEC-6): `services/jsonld.py` (`LOADER`, `dataset_of`, `triples_of`); bodies
  and loaded JSON-LD both through it; `_refers_outside` and its helpers deleted. Layer: services.
  Tests: `tests/unit/services/test_loading.py` and `test_documents.py` unchanged first, then the
  rows below in `tests/unit/services/test_jsonld.py`. Gate: `make test-changed check-quality`.

| ID | Input | Expected |
|---|---|---|
| TC-39 | the existing remote-context rows of `test_loading.py:201` (remote, `file:`, relative, `@import`, nested) | `InvalidGraph` `NOT_INLINE`; no request leaves (`no_network`) |
| TC-40 | a loaded JSON-LD file `{"@id": "urn:g", "@graph": [...]}` | `InvalidGraph` "a loaded file holds one graph"; nothing sent to the store |
| TC-41 | a JSON body naming a graph | `InvalidBody` "a body describes one graph" |
| TC-42 | a loaded JSON-LD file with a top-level `@graph` and no `@id` | loads; the triples are the default graph's |
| TC-42b | a loaded JSON-LD file `{"@id": "book1", ...}` with no `@base`; the same with `"@context": {"@base": "https://ex.org/"}` | `InvalidGraph` "a JSON-LD document must use absolute IRIs"; loads as `<https://ex.org/book1>` |
| TC-42c | a JSON-LD body whose reference slot holds a relative IRI | `InvalidBody`, same message (before: the triple was dropped) |
| TC-43 | every good sample of `test_loading.py:68` in JSON-LD | isomorphic to what rdflib's parser gave (read before the swap and kept as a golden in the test) |

- [x] 2.3 PD-10 (B-3): media types as rdflib format names in `fuseki.py`, `documents.py`,
  `loading.py`; `EVENT_STREAM` replaced by `EventSourceResponse.media_type`. Layer: adapters,
  services, entrypoints. Tests: `tests/unit/adapters/test_fuseki_store.py`,
  `tests/unit/entrypoints/test_openapi.py`, `tests/unit/entrypoints/test_events_route.py`
  unchanged; one new row. Gate: `make test-changed check-quality`.

| ID | Input | Expected |
|---|---|---|
| TC-44 | `grep -rnE 'format="(nt|turtle|xml|json|json-ld|nquads)"'` and the names `RDFLIB_`, `EVENT_STREAM` in `rdf_persistence/` (a test in `tests/unit/test_packaging.py`) | no match |
| TC-45 | the OpenAPI document's events route | content type `text/event-stream`, as today |

- [x] 2.4 PD-11 (C-5, DEC-7): the `media_type` tag in `RpAnnotation`, the four annotations on
  `RdfFormat`, `make generate`; `vocabulary.media_types`; `loading._parse` reads it,
  `_RDFLIB_FORMATS` deleted. Read the lock diff: if the change is not `SAFE`, stop and ask the lead.
  `make refresh-snapshot` and read its diff. Layer: model, services. Tests in
  `tests/unit/services/test_vocabulary.py`. Gate: `make test-fast check-quality`.

| ID | Input | Expected |
|---|---|---|
| TC-46 | `media_types(RdfFormat)` | `{TURTLE: text/turtle, RDFXML: application/rdf+xml, NTRIPLES: application/n-triples, JSONLD: application/ld+json}` |
| TC-47 | each value of TC-46 | registered by rdflib as a parser (`rdflib.plugin.get(value, Parser)`) |
| TC-48 | `media_types(RdfFormat, view=...)` over a fixture copy of the metamodel whose `ntriples` lacks the annotation | `ValueError` naming `ntriples` |
| TC-49 | the toolkit lock after `make generate` | version unchanged; change `SAFE` |

- [x] 2.5 PD-13 (B-7, DEC-8): `FakeStore` on pyoxigraph; `pyoxigraph==0.5.13` declared. Layer:
  testkit. Run first: every `CASES` entry (`tests/unit/testkit/test_fake_store.py`) and
  `make test-fast` with **no test edited**. If both pass, delete `_operations`, `_SPARQL_TOKENS`,
  `_PROLOGUE`, `_plain_strings`. If not, revert the engine, keep rdflib, and add a PD to design.md
  naming the failing tests and the reason; the task is then done. **The adversarial tester runs
  after this task.** Gate: `make test-fast check-quality`.

| ID | Input | Expected |
|---|---|---|
| TC-50 | every `store_conformance.CASES` entry on the new `FakeStore` | pass |
| TC-51 | an update of 200 `INSERT DATA` operations joined by `;` | applied; no `RecursionError` |
| TC-52 | the existing `test_an_xsd_string_literal_enters_as_the_plain_literal` rows | pass, with `_plain_strings` gone |
| TC-53 | a SELECT through the new fake | an rdflib `Result` whose rows hold rdflib terms |
| TC-54 | `make test-fast` wall-clock time against the run before the task | reported; more than 20 % slower is a reason to keep rdflib, recorded |

Stage 2 closes like stage 1, then PR 2.

## Stage 3: representations, contract and decisions (PR 3)

- [x] 3.1 PD-12 (Q-5, DEC-9): `N_TRIPLES`, `TRIG`, `RDF_XML`, `DATASET_REPRESENTATIONS`, the longer
  `REPRESENTATIONS` in `domain/media.py`; `Documents.render` for each; `openapi._document_media`
  documents them. Layer: domain, services, entrypoints. Tests in
  `tests/unit/services/test_documents.py`, `tests/unit/entrypoints/test_router.py`,
  `tests/unit/entrypoints/test_openapi.py`, `tests/integration/api/test_negotiation.py` (Fuseki).
  Two existing tests **change**, since a wildcard now reaches four more types:
  `test_a_client_that_refuses_every_representation_by_name_gets_nothing`
  (`test_negotiation.py`) refuses the four new types by name too, and `test_openapi.py:207` expects
  the seven types. Gate: `make test-fast check-quality`, then
  `make test-containers TEST_PATH=tests/integration/api/test_negotiation.py`.

| ID | Input | Expected |
|---|---|---|
| TC-55 | `GET B` with `Accept` each of the seven representations | 200; `Content-Type` as asked; each RDF body parsed by rdflib is isomorphic to the Turtle body's triples |
| TC-56 | `GET B` as N-Quads, and as TriG | every quad is in the graph `graph_iri(B)`; no statement about the graph IRI; no internal slot |
| TC-57 | `GET` of the tenant root as N-Quads | the quads are in the graph the root was read from |
| TC-58 | `POST` and `PUT` of `B` with `Accept: application/n-quads` | 201 and 200, N-Quads bodies |
| TC-59 | a listing with `Accept: application/n-quads` | 406 |
| TC-60 | `Documents.render` called directly with a graph holding `<…/b7> <https://ex.org/p/> "x"` (no XML local name; the toy schema has no such slot) as `application/rdf+xml` | `NotAcceptable` naming `application/rdf+xml` (406 through the problem handler) |
| TC-61 | the OpenAPI document, a read operation's 200 | the seven media types |
| TC-62 | `Accept: */*`, `text/*`, `application/*` | JSON, Turtle, JSON (unchanged) |

- [x] 3.2 PD-15 (B-5, DEC-10): schemathesis in the `test` group (`make lock`);
  `tests/unit/entrypoints/test_contract.py`, marked `slow`. If `make lock` cannot resolve
  schemathesis beside the pins, stop and report (RISK-10). Fix each finding that is a small change
  in `openapi.py` or a route; list the rest as issues in the PR. Layer: tests, entrypoints. Gate:
  `make test-changed check-quality`.

| ID | Input | Expected |
|---|---|---|
| TC-63 | every operation of the toy service's `/openapi.json`, 25 derandomised examples each | no server error; every status and content type documented; every JSON body valid against its schema |
| TC-64 | the toy service with a route made to answer an undocumented 418 (a fixture) | the contract test fails (the check is live) |

- [x] 3.3 PD-14, PD-16 (G-1 to G-4, Q-6, DEC-11): `adr/adr-001` to `adr-005` and the index,
  `nav.adoc`, `questions.adoc` (one question each, and the "as of" date), the pointer in
  `architecture/open-decisions.adoc`; `architecture/api.adoc` (the representations),
  `howto/adopt.adoc` (the verifier's `algorithms` and `leeway_seconds`, ADR-004; a reverse proxy
  must not weaken the `ETag`, RISK-9); the mapper
  docstring after the re-check script in `temp/`. Layer: docs, services (docstring). Gate:
  `make check-docs check-quality`.

| ID | Input | Expected |
|---|---|---|
| TC-65 | `make check-docs` | every new page in the nav; no consumer term |
| TC-66 | the re-check script on linkml-runtime 1.12.1 | each reason the docstring keeps is shown by the script's output, pasted into the PR |

- [x] 3.4 BDD: `tests/feature/representations.feature` (a book read in each RDF representation
  describes the same triples; N-Quads names the book's graph; a listing refuses N-Quads) and
  `tests/feature/token_algorithms.feature` (the spec delta's rp-identity scenarios), steps in
  `tests/feature/test_representations.py` and `test_token_algorithms.py` on fakes. The spec's
  `If-Match` and loading scenarios are covered by TC-14 to TC-21 and TC-40. Gate:
  `make test-changed check-quality`.

Stage 3 closes like stage 1. Then P-0004: the reconciliation of `proposal.md` (an "As built"
section), in PR 3 before it merges.

## Roadmap

- [x] 1.1 · [x] 1.2 · [x] 1.3 · [x] 1.4 · [x] 1.5 · [x] 1.6 · PR 1 · [x] 2.1 · [x] 2.2 · [x] 2.3 ·
  [x] 2.4 · [x] 2.5 (kept rdflib, PD-17) · (tester) · PR 2 · [x] 3.1 · [x] 3.2 (schema xfail per operation, #148, #153) · [x] 3.3 · [x] 3.4 · [x] reconcile · PR 3

## Verification

The TC tables above as tests; `make check-all` and `make test-containers` before each PR;
`openspec validate manual-revision-notes --strict`; the clarity gate on this pair (≥ 9/10).
