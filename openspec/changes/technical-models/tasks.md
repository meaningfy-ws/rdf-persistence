> Derives from: EPIC `technical-models` (proposal.md). Four stages, one PR each into `develop`.
> Type: Implementation. Starts after `manual-revision-notes` has merged.

`PD-n` is a decision of [design.md](design.md). Every task is test first: the TC rows are written
as failing tests before the code. Its gate is `make test-changed check-quality`, or
`make test-fast check-quality` where the task says so (it changes `domain`, a port, or generated
paths many modules import). After a schema change the lead runs `make generate` and
`make check-generated`.

**How the work succeeds:** every TC passes; `make check-all` and `make test-containers` are green
at each stage's end; `git grep` finds no `domain.generated.service`, `domain.iris`,
`domain.tenant_move`, `FIELD_OF_TOML_KEY` or removed constant; `rp-generate` on the toy library writes the same files as
before. **How it fails:** a default differs from today's (the TC of 3.1 compare each to the old
constant), a guard or contract stays silent on its counterexample (each has a TC), or a generated
file differs from the committed one (`check-generated`).

## Stage 1: technical models in the layer that uses them (PR 1)

- [x] 1.1 PD-9: `TargetKind`, `GenerationTarget.target_kind` (TOML key `kind` through
  `FIELD_OF_TOML_KEY` until 4.1), the `BoundaryRule` value `target_kind` in
  `generation/model/rp_generation.yaml`; `target_kind_problems` in `generation/checks/boundary.py`,
  called from `steps.py::_boundary_problems`. Tests in `tests/unit/generation/test_boundary_check.py`
  (beside the module-kind tests) and `tests/unit/generation/test_generate_config.py`. Gate:
  `make test-changed check-quality`.

| ID | Input | Expected |
|---|---|---|
| TC-01 | a target `kind = "technical"` whose folder holds one module annotated `technical` | no problem |
| TC-02 | a target `kind = "technical"` with a second module annotated `domain` | one `target_kind` problem naming the module |
| TC-03 | a target `kind = "domain"` whose folder holds a module annotated `technical` | one `target_kind` problem naming it |
| TC-04 | the toy library's table, no `kind` | no problem; generated files unchanged |
| TC-05 | `kind = "access"` in a table | `ConfigError` naming `kind` |

- [x] 1.2 PD-2 (the `iris.py` split), DEC-3, DEC-9: commit A `git mv rdf_persistence/domain/iris.py
  rdf_persistence/services/iris.py` and `domain/tenant_move.py` → `services/tenant_move.py`, with
  their tests (PD-2's list) → `tests/unit/services/`; commit B cuts `domain/layout.py` out of
  `services/iris.py` and rewrites every importer (one ast-grep rule per name group over
  `rdf_persistence/` and `tests/`; `__init__.py`'s eager import; `generation/checks/hard.py`'s
  `LAYOUT_WORDS`; `caplog` and `mock.patch` strings found by `grep`); `services.iris` and
  `services.tenant_move` added to `nothing-in-services-imports-the-bus` in `.importlinter`. No behaviour changes. Layer:
  domain, services. Tests: the moved tests unchanged apart from imports, plus
  `tests/unit/domain/test_layout.py` (new). Gate: `make test-fast check-quality`.

| ID | Input | Expected |
|---|---|---|
| TC-61 | `rdf_persistence.domain.layout`, read with `ast` | the 12 functions of PD-2; it imports nothing of `rdf_persistence` outside `rdf_persistence.domain`, and no `generated` package |
| TC-62 | `rdf_persistence.Iris`, `DEFAULT_IRIS`, `mint_aggregate_iri`, `IdSource` | the objects defined in `rdf_persistence.services.iris`; `test_public_api.py` green |
| TC-63 | `git log --follow --oneline rdf_persistence/services/iris.py` | reaches the commit that created `domain/iris.py` |

- [x] 1.3 PD-1, PD-2, PD-3, DEC-1, DEC-9: `git mv` `model/service/rp_service.yaml` →
  `model/technical/service/`, `model/adapters/rp_wire.yaml` → `model/technical/wire/`; the
  `[[tool.rp-generate]]` entries with their `package` (`rdf_persistence.services.generated.service`;
  `rdf_persistence.adapters.generated` unchanged for `wire`) and `kind` (the metamodel and
  generator targets get `kind` too); the old `rdf_persistence/domain/generated/service/` folder
  deleted after `make generate` writes the new one (TC-08); `SERVICE_SCHEMA` and `services/components.py::TOOLKIT_FOLDER`;
  the segment-built paths (`grep`, PD-1) such as `tests/unit/services/test_iris_follow_schema.py:8`;
  every import of `domain.generated.service` (`ast-grep` over `rdf_persistence/` and `tests/`);
  `.importlinter`: the contract `domain-never-imports-technical-models`. Tests:
  `tests/unit/test_technical_split.py` (new) and `tests/unit/testkit/` beside the guard tests.
  Gate: `make test-fast check-quality`, then the lead's `make check-architecture check-generated`.

| ID | Input | Expected |
|---|---|---|
| TC-06 | every `*.yaml` under `rdf_persistence/model/technical/` | each annotated `module_kind: technical` |
| TC-07 | every `rdf_persistence/model/*.yaml` | none annotated `technical` |
| TC-08 | `rdf_persistence.domain.generated`, `rdf_persistence.services.generated.service`, `rdf_persistence.adapters.generated.rp_wire` | the first has no `service` subpackage; the second defines `ServiceSettings`; the third still defines `JwtClaims` |
| TC-09 | a scratch copy where `domain/generated/rp_core.py` imports `rdf_persistence.services.generated.service` | `lint-imports` fails `domain-never-imports-technical-models` |
| TC-10 | a scratch copy where `services/session.py` imports `adapters.generated.rp_wire` | `lint-imports` fails `layers` |
| TC-11 | the model guard over the moved tree; a hand-written `class X(RpModel)` in `services/x.py` (tmp tree) | no class under `services/generated/` flagged; `X` named |
| TC-12 | `rdf_persistence.ServiceSettings`, `rdf_persistence.JwtClaims`, and every other name of `__all__` | each still imports (existing `test_public_api.py` stays green) |
| TC-13 | the TypeScript of the toy library | identical to before the move (the service types come from the moved schema) |
| TC-53 | a scratch copy where `domain/layout.py` imports `rdf_persistence.services.generated.service` | `lint-imports` fails `domain-never-imports-technical-models` (hand-written domain modules may not either) |
| TC-54 | `services/components.py::TOOLKIT_FOLDER / "openapi-components.json"` | exists, and the served OpenAPI holds the toolkit's request and response bodies as before (`tests/unit/entrypoints/test_openapi.py` stays green unchanged) |

Stage 1 closes with the lead's `make check-all` and `make test-containers`, review L1 to L3
separate and L4+L5 one pass, the fix pass, PR 1.

## Stage 2: the templates' variables as models (PR 2)

- [x] 2.1 PD-4: `SparqlTerm.__get_pydantic_core_schema__`, `fill_terms`, `fragment_terms` in
  `domain/sparql.py`; `GenerationAnnotation.python_import` and the import in
  `SplitPydanticGenerator._get_imports`. Tests: `tests/unit/domain/test_sparql.py`,
  `tests/unit/generation/test_ext_pydantic_split.py`. Gate: `make test-fast check-quality`.

| ID | Input | Expected |
|---|---|---|
| TC-14 | a model with a `SparqlTerm` field given `term(URIRef("urn:x"))` | the field keeps a `SparqlTerm` instance |
| TC-15 | the same field given the `str` `"<urn:x>"` | `ValidationError` |
| TC-16 | a schema type `{typeof: string, repr: SparqlTerm}` annotated `python_import: rdf_persistence.domain.sparql` | the generated module imports `SparqlTerm` from there and types the field `SparqlTerm`; it compiles |
| TC-17 | `fill_terms("$a $b", M(a=t1, b=None))` where the template names `b` | `SparqlError` "missing terms for ['b']" (None is left out, `fill`'s check holds) |
| TC-55 | `fill_terms("$a $c", M(a=t1), c=t2)`; `fill_terms("$a", M(a=t1), a=t2)` | `"<t1> <t2>"`; `SparqlError` "term given twice: ['a']" |

- [x] 2.2 PD-5 (D-1): `model/technical/templates/rp_templates.yaml` (target `kind = "technical"`,
  `openapi = false`) with the term models; the factories in `services/vocabulary.py`;
  `unique_keys.py`, `session.py`, `listing.py`, `migrations.py` use them; the placeholders
  `$class` → `$target`, `$from` → `$from_version`. Tests: the existing
  `tests/unit/services/test_session_unique_keys*.py`, `test_listing_query.py`,
  `test_migration_files*.py`, `test_session_*.py` stay green unchanged (the query text is the same up to the renamed
  placeholders), plus `tests/unit/services/test_term_models.py`. Gate: `make test-fast check-quality`.

| ID | Input | Expected |
|---|---|---|
| TC-18 | `key_held_terms(R, values=v, excluded=[a, b])` | a `KeyHeldTerms` whose fields are the old dict's values, key for key |
| TC-19 | `guard`, `diagnosis`, `duplicates_query`, `listing_query`, the migration request, the owner patterns, each for a fixed input | the same SPARQL text as before the change (golden strings captured first) |
| TC-20 | `KeyHeldTerms(values="raw", ...)` | `ValidationError` |
| TC-21 | `ast-grep` for a dict literal whose keys are a template's placeholders in the four modules | no match |

- [x] 2.3 PD-5 (D-2): `IriTemplateVariables`, `IriParts` in `rp_templates.yaml`; `services/iris.py`
  (`effective_policy`, `Iris._fixed`, the matchers, today's `iris.py:636-747`). Tests: the
  `test_iris*.py` and `test_iri_policy*.py` that task 1.2 moved to `tests/unit/services/` stay
  green, plus TC rows in `tests/unit/services/test_iris.py`. Gate: `make test-fast check-quality`.

| ID | Input | Expected |
|---|---|---|
| TC-22 | settings `base=https://ex.org/`, `deployment=None`, `tenant_segment=t` | `IriTemplateVariables(base="https://ex.org/", deployment="", tenant_segment="t")` from one helper used by both sites |
| TC-23 | `Iris.tenant_id_of` of a tenant IRI and of a reserved word | the id; `None`/refusal as today |
| TC-24 | `IriParts.model_validate({"tenant_id": "x", "unknown": "y"})` | `ValidationError` (a regex group the model does not name is a bug) |

Stage 2 closes like stage 1.

## Stage 3: central settings (PR 3)

- [ ] 3.1 PD-6: `model/technical/settings/rp_settings.yaml` (target `kind = "technical"`,
  `openapi = false`); the `default_instance` annotation in `GenerationAnnotation`,
  `SplitPydanticGenerator` and its generation check. Tests: `tests/unit/domain/test_settings_model.py`,
  `tests/unit/generation/test_ext_pydantic_split.py`. Gate: `make test-fast check-quality`.

| ID | Input | Expected |
|---|---|---|
| TC-25 | `ToolkitSettings()` | every value equals the constant or keyword default it replaces (one assert per row of PD-6's table, against the value written in the test, not the old constant) |
| TC-26 | `HttpSettings(read_timeout_seconds=0)`, `LimitSettings(max_roots=0)`, `JwksSettings(allowed_algorithms=["HS256"])`, `["hs512"]`, `["none"]`, `["NONE"]` | each a `ValidationError` |
| TC-27 | `JwksSettings(allowed_algorithms=["EdDSA", "PS384"])` | valid |
| TC-59 | `JwksSettings(allowed_algorithms=["ML-DSA-44", "RS256"])` | valid (the schema does not close the list, PD-6) |
| TC-56 | `ToolkitSettings().http`; two `ToolkitSettings()` | an `HttpSettings` with the defaults; the two hold distinct group instances |
| TC-57 | `JwksSettings(leeway_seconds=0)`, `(leeway_seconds=301)`, `(allowed_algorithms=[])` | valid; `ValidationError`; `ValidationError` |
| TC-58 | a toy schema with `default_instance` on a slot ranging over `string` | `rp-generate` fails naming the slot |

- [ ] 3.2 PD-7, PD-8 (C-2, C-3, C-4): `HttpAdapter`, `FusekiStore`, `JwksTokenVerifier`,
  `ZitadelIdentity`, `S3FileStore` take their groups; `_http.py`, `s3.py`, `jwks.py`, `zitadel.py`
  constants removed; `ZitadelUserState`; the four slugs in `testkit/zitadel.py`. Tests:
  `tests/unit/adapters/test_http.py`, `test_jwks.py`, `test_zitadel.py`, `test_s3_file_store.py`; the
  container tests of 3.5. Gate: `make test-changed check-quality`.

| ID | Input | Expected |
|---|---|---|
| TC-28 | `FusekiStore(url, u, p, http=HttpSettings(read_timeout_seconds=7))` | its client's timeout is read 7, connect 5 |
| TC-29 | `S3FileStore(..., http=HttpSettings(max_attempts=5))` | the boto3 client's config has those timeouts and 5 attempts |
| TC-30 | `JwksTokenVerifier(..., jwks=JwksSettings(ttl_seconds=1))`, the clock advanced 2 s | the keys are fetched again |
| TC-31 | A-3's and A-4's existing tests | pass through `jwks=` instead of the constructor parameters |
| TC-60 | `JwksTokenVerifier(..., jwks=JwksSettings(allowed_algorithms=["ML-DSA-44"]))` on the pinned PyJWT 2.15.1 | `ValueError` at construction naming `ML-DSA-44` (the start-up check of `manual-revision-notes` PD-1) |
| TC-32 | a Zitadel user answer with `state: USER_STATE_LOCKED`; with `USER_STATE_NEW_ONE` | read, `active` false; `IdentityUnavailable` |
| TC-33 | `ZitadelIdentity(..., directory=DirectorySettings(page_size=2))` over 5 users | 3 requests, 5 accounts |
| TC-34 | `grep` for `PROJECTS`, `MACHINE_USERS`, `OWN_ORGANISATION`, `TOKEN_PATH` in `adapters/` | none |

- [ ] 3.3 PD-7: `RedisEventBus`, `Relay`, `EventHub`, `MessageBus`/`bootstrap`, `Mapper` (the
  roots limit A-2 put there; `UnitOfWork`'s `max_roots=` and `DEFAULT_MAX_ROOTS` deleted),
  `Documents`, `tenant_dump.restore`, `add_events_route` take their groups; `ServiceKit` and
  `install_service` take `toolkit=` and pass them on. Tests: the existing tests of each, moved to
  the group parameter, plus `tests/unit/entrypoints/test_service_kit.py`. Gate:
  `make test-fast check-quality`.

| ID | Input | Expected |
|---|---|---|
| TC-35 | `install_service(..., toolkit=ToolkitSettings(limits=LimitSettings(max_roots=2)))`; a unit of work committing 3 roots | `CommitTooLarge` |
| TC-36 | `toolkit` with `sse.keep_alive_seconds=0.05` and the fake clock | a keep-alive comment within the window |
| TC-37 | `toolkit` with `limits.max_document_nodes=3`; a body of 4 objects | 413 |
| TC-38 | `EventHub(events=EventSettings(hub_queue_size=1))`, two activities unread | the existing overflow behaviour at the second |
| TC-39 | `RedisEventBus(url, deployment="d", stream="x")` | `TypeError` (the keyword is gone) |

- [ ] 3.4 PD-12 (B-8): `entrypoints/environment.py::settings_from_env`, the `settings` extra, the
  lazy export. Tests: `tests/unit/entrypoints/test_environment.py`, and
  `tests/unit/test_packaging.py` for the extra. Gate: `make test-changed check-quality`.

| ID | Input | Expected |
|---|---|---|
| TC-40 | `environ={"RP_HTTP__READ_TIMEOUT_SECONDS": "60"}`, `ToolkitSettings` | `http.read_timeout_seconds == 60.0`, every other value its default |
| TC-41 | `environ={"RP_JWKS__ALLOWED_ALGORITHMS": '["HS256"]'}` | `ValidationError` naming the field |
| TC-42 | `import rdf_persistence` in a subprocess with `RP_HTTP__READ_TIMEOUT_SECONDS=abc` set | no error, and `pydantic_settings` not in `sys.modules` |
| TC-43 | `pydantic_settings` hidden (`sys.modules` patched to `None`) | `ImportError` naming `rdf-persistence[settings]` |
| TC-44 | `settings_from_env(ServiceSettings, environ={...required fields...})` | a valid `ServiceSettings` (any generated settings model works) |

- [ ] 3.5 The container lane over the new wiring: `tests/integration/` fixtures build every adapter
  from `ToolkitSettings()`. Gate: `make test-containers`, then `make check-quality`.

Stage 3 closes like stage 1. **The adversarial tester runs after 3.3** (an old keyword still
accepted somewhere, a default that drifted, a group not passed on by the kit).

## Stage 4: testkit records, BDD and docs (PR 4)

- [ ] 4.1 PD-10, PD-11 (D-4): the `testkit` target and `model/technical/testkit/rp_testkit.yaml`,
  the ten records of PD-11 moved out of `rp_generation.yaml` with their slots (re-listed first by
  `grep` over `rdf_persistence/testkit/`, so a record added since joins them), their imports in `testkit/` and
  `generation/` updated; aliases in `rp_generation.yaml`; `config.py`; `FieldFlags` in
  `model_shape.py`; `RpModel.replaced()` (`manual-revision-notes` PD-8) at
  `testkit/conformance.py:51`, `testkit/zitadel.py:235` and `generation/pipeline.py:143`;
  `testkit/tokens.py` through `JwtClaims`. Tests:
  `tests/unit/generation/test_generate_config.py`, `tests/unit/generation/test_shape_snapshot.py`,
  `tests/unit/generation/test_conformance.py`, `tests/unit/testkit/test_tokens.py`,
  `tests/unit/testkit/test_container_records.py`, `tests/unit/test_technical_split.py`. Gate:
  `make test-fast check-quality`.

| ID | Input | Expected |
|---|---|---|
| TC-45 | a row `schema = "a.yaml"`, `regenerate-command = "make g"` | `schema_file`, `regenerate_command` set |
| TC-46 | a row `schema_file = "a.yaml"` | `ConfigError` "invalid entry: schema_file: Extra inputs are not permitted" (today's text) |
| TC-47 | a row with a bad `regenerate-command` type | the message names `regenerate-command`, not the field |
| TC-48 | a signed test token with `sub`, `expires_in`, `roles` | the same claims as before, key for key |
| TC-49 | `ast-grep` for `model_copy(update=` in `testkit/` and `generation/` | no match |
| TC-52 | `load_cases` on a cases file whose row names an `invalid` path; a `CheckProblem` given a misspelt field through `replaced` | absolute paths; `ValidationError` (was silently ignored) |
| TC-50 | every module of `rdf_persistence/testkit/` but `freshness.py` and `conformance.py` (F-1) | none imports `rdf_persistence.generation.generated` (records come from `testkit.generated`) |
| TC-51 | `rp_generation.yaml` | declares none of the ten moved classes nor their own slots, and still declares `ConstraintCase`, `ConstraintKind` and the slot `kind`; the TOML key `kind` still sets `target_kind`; `make check-generated` clean |

- [ ] 4.2 BDD: `tests/feature/technical_models.feature` with the spec deltas' scenarios and steps
  in `tests/feature/test_technical_models.py` (toy library, tmp copies). Gate:
  `make test-changed check-quality`.

- [ ] 4.3 Docs: `architecture/generation.adoc` (the two kinds, the five groups and where each
  generates, the `kind` key, the `python_import` annotation); `architecture/index.adoc` (the
  generated packages inside the layers, the `iris.py` split, the contract);
  `architecture/data-flows.adoc` (paths); a new `howto/settings.adoc` (the groups, the composition
  root, `settings_from_env`, each removed keyword and its replacement); its question in
  `questions.adoc` and the nav; `adopt.adoc` (the `kind` key, a consumer's technical target).
  Gate: `make check-docs`.

Stage 4 closes like stage 1, then the reconciliation of `proposal.md` (P-0004) in PR 4.

## Roadmap

- [x] 1.1 · [x] 1.2 · [x] 1.3 · PR 1 · [x] 2.1 · [x] 2.2 · [x] 2.3 · PR 2 · [ ] 3.1 · [ ] 3.2 · [ ] 3.3 ·
  (tester) · [ ] 3.4 · [ ] 3.5 · PR 3 · [ ] 4.1 · [ ] 4.2 · [ ] 4.3 · reconcile · PR 4

## Verification

The TC tables as tests; `make check-all` and `make test-containers` before each PR;
`openspec validate technical-models --strict`; the clarity gate on this pair (≥ 9/10).
