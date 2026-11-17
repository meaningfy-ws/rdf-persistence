> Derives from: EPIC `technical-models` ([proposal.md](proposal.md)), capabilities `rp-generation`,
> `rp-package-boundaries`, `rp-settings` (new). Seeds: [inputs/seed.md](inputs/seed.md).
> Type: Implementation. Depends on `manual-revision-notes` (A-3, A-4) being merged.

## Context

What the brief asked to check against the code (branch `docs/manual-revision-notes`, 48f80c6):

| Claim | In the code | In this PLAN |
|---|---|---|
| Technical schemas are told apart from domain ones | Already, at schema level: `module_kind` (`rp_core.yaml:330`, `ModuleKind` domain/technical/access); `rp_service.yaml`, `rp_wire.yaml` and `rp_generation.yaml` say `technical`. The boundary check refuses a domain module importing a technical or access one (`generation/checks/boundary.py:_module_problems`). Not in the package tree: `rp_service` generates into `domain/generated/service/` | DEC-1, PD-1 |
| Generated code goes to the layer that imports it (PD-18) | `[[tool.rp-generate]]` in `pyproject.toml` has four targets. `domain/iris.py` and `domain/tenant_move.py` import `rp_service` (`IriPolicy`, `IdSpec`, `ServiceSettings`); only `adapters/` and `testkit/` import `rp_wire` | PD-2 |
| `pydantic_split` imports from beside the root or the metamodel only | `SplitPydanticGenerator.generate_module_import` raises otherwise; metamodel classes map to `TOOLKIT_PACKAGE` (`rdf_persistence.domain.generated`) in the toolkit's runs | Why DEC-4 stops at the check |
| The guards need a `generated` segment | `testkit/guards.py`: `GENERATED = "generated"`, `SCANNED_LAYERS = ("domain", "services", "entrypoints")` | PD-1, PD-3 |
| ~27 values at 15 sites (analysis §5.1) | Confirmed, with one correction: `max_roots` is a parameter of `UnitOfWork` (`mapper.py:306`), not of `Mapper`; `manual-revision-notes` A-2 (its PD-7) puts it on the `Mapper`, which every unit of work and the reference collections share. The message-bus limit is on `MessageBus.__init__` and `bootstrap` (`messagebus.py:109,266`); the SSE values are keyword defaults of `add_events_route` (`sse.py:52-61`) | PD-6 |
| A term bundle can be a generated model of strings | No: pydantic 2.14.2 turns a `SparqlTerm` into a plain `str` in a `str` field, strict or not (checked in `.venv`). `fill` would then refuse it | DEC-7, PD-4 |
| (attack, 2026-11-17) The move touches imports only | No: `services/components.py:16` builds the service folder's path from segments; the global slot `kind` exists in `rp_generation.yaml:738`; `containers/fixtures.py` imports three more records; `ToolkitSettings()` would hold `None` groups; the term bundles are spread together with per-call terms (`session.py:493`, `migrations.py:251-265`) | PD-1, PD-9, PD-11, PD-6, PD-4 |
| `ZitadelUser.state` is a bare `str` | `rp_wire.yaml:631` `zitadel_state`, alias `state`; `zitadel.py:44,61,203,206` compare it | PD-8 |

## Goals / Non-Goals

**Goals:** a reader sees each model's kind in its path; the split is checked by the generator and
by import-linter; settings are generated and passed in; the bare-key bundles of D-1, D-2, D-4 become
models; behaviour and defaults do not change.

**Non-Goals:** the EPIC's No-gos.

## Decisions

Settled in the EPIC and cited, not re-argued: DEC-1 to DEC-9. The new ones:

- **PD-1 Paths.** Schemas: `rdf_persistence/model/technical/{service,wire,settings,templates,testkit}/rp_<group>.yaml`,
  each annotated `module_kind: technical`. Packages (DEC-1): `rdf_persistence/services/generated/__init__.py`
  (empty) and `rdf_persistence/services/generated/{service,settings,templates}/`;
  `rdf_persistence/adapters/generated/` for `wire`, unchanged; `rdf_persistence/testkit/generated/`
  for `testkit` (DEC-2, PD-11). `services/schema.py::SERVICE_SCHEMA` points at the new schema path,
  and `services/components.py::TOOLKIT_FOLDER` (`:16`, `PACKAGE_DIR / "domain" / "generated" / "service"`,
  where the served OpenAPI's components are read) becomes
  `PACKAGE_DIR / "services" / "generated" / "service"`; paths built from segments are found by `grep`
  for `"service"` and `"adapters"` beside `"model"` or `"generated"`, not by an import search
  (`tests/unit/services/test_iris_follow_schema.py:8` is one);
  `metamodel_importmap()` still globs `model/*.yaml` only, so a consumer cannot import a technical
  schema (unchanged).
- **PD-2 Layers.** The `.importlinter` `layers` contract does not change
  (`entrypoints | adapters > services > domain`): every generated technical package sits inside a
  layer (DEC-1), so the contract already orders it. `services.generated.*` may import `domain` (a
  request body carrying a domain value) and is imported by services, adapters and entrypoints;
  `adapters.generated` (wire) is imported by adapters and the testkit only, as today, since no
  service or entrypoint may import an adapters package. One new forbidden contract,
  `domain-never-imports-technical-models`: source `rdf_persistence.domain`; forbidden
  `rdf_persistence.services.generated`, `rdf_persistence.adapters.generated`,
  `rdf_persistence.testkit.generated` (direct or indirect, import-linter's default). It repeats a
  part of `layers` and `runtime-without-extras` on purpose: it names Q-2's rule, so a failure says
  which rule broke, and `thematic-structure` replaces it with `layers-across-themes`.
  `domain-pure` and `runtime-without-extras` are unchanged. `rp-package-boundaries` is updated.
  **The `iris.py` split (DEC-3).** Two commits, so `git log --follow` tracks the larger half:
  first `git mv domain/iris.py services/iris.py`; then `domain/layout.py` is cut from it with the
  constants the layout needs (`_SEGMENT`, `_PREFIX`, `SYSTEM_SUFFIX`, `TENANT_INFIX`,
  `APPLICATION_ID`, `APPLICATION_SUFFIX`, `TOOLKIT_SEGMENT`, `POLICY_SEGMENT`, `STAMPS_SEGMENT`,
  `GENID`, `LOADED_GRAPH_TYPE`, `LAYOUT_WORDS`; the placeholder, alphabet and pattern constants of
  `iris.py:34-40` and `:244-257` stay with the template machinery), `_segment`, `_prefix` and the
  12 policy-free functions: `graph_iri`,
  `root_of_graph`, `skolem_iri`, `is_skolem_of`, `toolkit_principal_iri`, `policy_record_iri`,
  `stamps_graph_iri`, `is_inside_tenant`, `is_canonical_uuid`, `system_database_name`,
  `application_database_name`, `tenant_name_prefix`. `domain/layout.py` imports nothing outside
  `domain`. `services/iris.py` keeps `Iris`, `DEFAULT_IRIS`, `IdSource`, `draw_id`,
  `effective_policy`, `policy_differences`, `check_iri_policy`, the template machinery
  (`_compile`, `_TEMPLATE_SLOTS`, ...), the ten wrappers over `DEFAULT_IRIS` with their helper
  `_default_iris` (`mint_tenant_iri`, `tenant_iri`, `aggregate_iri`, `mint_aggregate_iri`,
  `is_aggregate_iri`, `is_aggregate_graph_iri`, `is_loaded_graph_of`, `mint_part_iri`,
  `loaded_graph_iri`, `principal_iri`), and `tenant_resource_name` with `_resource_name`, which
  `Iris` uses (`iris.py:706`): eleven top-level helpers. `services/iris.py` imports from
  `domain.layout` what `Iris` reads (`_segment`, `_SEGMENT`, `APPLICATION_ID`, `LAYOUT_WORDS`,
  `LOADED_GRAPH_TYPE`, `graph_iri`, ...), the two private names kept as they are (no ruff rule
  refuses a private import; `thematic-structure` may rename them). `git mv
  domain/tenant_move.py services/tenant_move.py`. `services.iris` and `services.tenant_move` join
  the module list of the `.importlinter` contract `nothing-in-services-imports-the-bus` (its
  comment: a new services module joins it). The importers are rewritten by one ast-grep rule
  per name group: the library (`services/*`, `entrypoints/kit.py`, `entrypoints/service.py`,
  `entrypoints/router.py`, `adapters/jwks.py`, `testkit/fakes.py`, `__init__.py`), the generator
  (`generation/checks/hard.py` reads `LAYOUT_WORDS` from `domain.layout`) and the tests (94 files
  import `domain.iris` or `domain.tenant_move` today). The tests of `Iris`, the policy and
  `tenant_move` move with their modules to `tests/unit/services/` (`test_iris*.py`,
  `test_iri_policy_*.py`, `test_tenant_move.py` of `tests/unit/domain/`; a name already taken
  there, `test_iri_policy_adversarial.py`, arrives as `test_iri_policy_model_adversarial.py`); the
  layout functions' tests go to `tests/unit/domain/test_layout.py`. This is `thematic-structure` PD-5's split in the
  present layers; that change then moves the two files into the `iris` theme and retires the
  wrappers. Rejected: keeping `Iris` in `domain` behind a layer line that pairs `domain` with technical models (first shaped
  here; Q-2 forbids it, DEC-3).
- **PD-3 The guards.** No guard change. `services/generated/` is skipped by the `generated`
  segment as `domain/generated/` is (`testkit/guards.py`: `GENERATED`), and a hand-written model
  anywhere else in `services/` is flagged as today (`SCANNED_LAYERS` holds `services`).
- **PD-4 Term models (DEC-7).** `SparqlTerm.__get_pydantic_core_schema__` returns
  `core_schema.is_instance_schema(cls)`: a raw `str` fails validation when the model is built.
  `rp_templates.yaml` declares `types: sparql_term: {typeof: string, repr: SparqlTerm, uri: rp:SparqlTerm}`.
  The stock generator already uses a type's `repr` as the Python range (`pydanticgen._get_pyrange`);
  `SplitPydanticGenerator._get_imports` adds `from rdf_persistence.domain.sparql import SparqlTerm`
  when a slot ranges over a type whose `repr` is `SparqlTerm`, read from a type annotation
  `python_import: rdf_persistence.domain.sparql` (a new `GenerationAnnotation` value). A consumer
  schema may use the annotation too. `domain/sparql.py` gains
  `fill_terms(template: str, terms: BaseModel, **more: SparqlTerm) -> str`:
  `fill(template, **{n: v for n, v in terms if v is not None}, **more)`, and `fragment_terms` the
  same over `fragment`. Iterating the model yields its attribute values, so each stays a
  `SparqlTerm`. `more` carries the terms a single call adds to a shared bundle (the migration
  step's `delete`, `insert`, `where`; `_fill_marked`'s `graph`, `marker`): a bundle is the set of
  terms several templates share, not every placeholder of one template. A name both in `terms` and
  in `more` raises `SparqlError("term given twice: [...]")`.
- **PD-5 The template models.** In `rp_templates.yaml`:
  - `RegistryTerms` (mixin): `registry`, `p_kind`, `p_owned_by`, all `sparql_term`.
  - `KeyHeldTerms` (`mixins: RegistryTerms`): `values`, `aggregate`, `excluded`; `KeyBranchTerms`
    (`is_a: KeyHeldTerms`): `index`. Replace `_held`/`_held_around` (`unique_keys.py:120-132`).
  - `OwnerTerms` (no `registry`, so not a `RegistryTerms`): `root`, `p_owned_by`, `p_kind`,
    `loaded`. Replaces `session._owner_terms` (`:433-439`). Its two callers (`:493`, `:513`) pass it
    to `_fill_marked(template, graph, registry, marker, owner, **more)`, which calls
    `fill_terms(template, owner, graph=..., registry=..., marker=..., commit_marker=..., **more)`.
  - `ListingTerms` (`mixins: RegistryTerms`): `aggregate`, `target`, `patterns`, `hidden`,
    `p_listed_in`, `p_total`, `order`, `limit`, `offset`, optional `p_sort`. The template's
    `$class` becomes `$target` (`listing.py:281-293`, no more `**{"class": ...}`).
  - `StampGuardTerms`: `stamps`, `schema_id` (D-19), `p_stamp`, `from_version`; the templates' `$schema` becomes `$schema_id` and `$from`
    becomes `$from_version` in `_STEP`, `_ROTATION` and `_STAMP_MOVE` (`migrations.py:45-63`), all
    internal (no consumer file names a placeholder). Replaces the `guard` dict (`:242-247`); the
    three operations add their own terms through `more`: `_STEP` `delete`, `insert`, `where`,
    `p_kind`, `loaded` (`:258-266`); `_ROTATION` `p_version`; `_STAMP_MOVE` `to` (`:251-252`).
  - `IriTemplateVariables`: `base`, `deployment`, `tenant_segment` (strings, `deployment` may be
    empty). Replaces `effective_policy`'s `fixed` and `Iris._fixed`, in `services/iris.py` after
    task 1.2 (line numbers below are today's `domain/iris.py`: `:274-278`, `:417-421`);
    `str.format(**variables.model_dump())`. The fields are plain strings, so the dump is safe here
    (unlike a term model), and `str.format` and `_compile(template, fixed, groups)` (`:325`) are the
    library boundary that takes the mapping: the uses at `:282`, `:426`, `:440`, `:462`, `:608` and
    `:700` read the model or its dump, merged with the call's own values as today.
  - `IriParts`: `tenant`, `tenant_id`, `id`, `type`, `rp_path`, `root`, all optional. A match's
    `groupdict()` (a library boundary) is validated at once into `IriParts`; the readers
    (`iris.py:636-770`; `groupdict()` at `:719`, `:747`, `:768`) use attributes.
  One hand-written factory per bundle builds the fixed vocabulary terms (for example
  `registry_terms(registry)` in `services/vocabulary.py`), so the vocabulary IRIs stay in one place.
- **PD-6 The settings (DEC-5).** `rp_settings.yaml`, every slot with `ifabsent` set to today's value:

  | Class | Slot | Default | Replaces |
  |---|---|---|---|
  | `HttpSettings` | `connect_timeout_seconds` | 5.0 | `_http.py:17`, `s3.py:33` |
  | | `read_timeout_seconds` | 30.0 | `_http.py:18`, `s3.py:33` |
  | | `max_attempts` | 3 | `s3.py:33` (boto3 retries) |
  | `JwksSettings` | `ttl_seconds` | 600.0 | `jwks.py:26` |
  | | `unknown_kid_cooldown_seconds` | 10.0 | `jwks.py:29` |
  | | `allowed_algorithms` (multivalued) | A-3's default list | A-3's constructor parameter |
  | | `leeway_seconds` | 30.0 | A-4's constructor parameter |
  | `DirectorySettings` | `page_size` | 100 | `zitadel.py:43` |
  | `EventSettings` | `stream` | `rp-events` | `RedisEventBus(stream=)` |
  | | `retention_seconds` | 604800 | `RedisEventBus(retention=)` |
  | | `claim_idle_seconds` | 30.0 | `RedisEventBus(claim_idle=)` |
  | | `polling_interval_ms` | 100 | `redis_events.py:27` |
  | | `relay_interval_seconds` | 5.0 | `Relay(interval=)` |
  | | `publish_timeout_seconds` | 10.0 | `Relay(publish_timeout=)` |
  | | `hub_queue_size` | 1000 | `EventHub(max_queue=)` |
  | `SseSettings` | `max_lifetime_seconds` | 300.0 | `sse.py:36` |
  | | `access_ttl_seconds` | 1.0 | `sse.py:37` |
  | | `keep_alive_seconds` | 15.0 | `sse.py:38` |
  | | `resume_window_seconds` | 604800 | `sse.py:39` |
  | `LimitSettings` | `max_messages` | 100 | `messagebus.py:109,266` |
  | | `max_roots` | 500 | `mapper.py:291` (`DEFAULT_MAX_ROOTS`, the default of A-2's `Mapper(max_roots=)`) |
  | | `max_document_nodes` | 10000 | `documents.py:59` |
  | | `max_manifest_bytes` | 65536 | `tenant_dump.py:51` |
  | `ToolkitSettings` | `http`, `jwks`, `directory`, `events`, `sse`, `limits` | each group's defaults | — |

  Bounds. LinkML's `minimum_value` is inclusive and has no exclusive form, so every duration but
  the leeway carries `minimum_value: 0.001` (a zero timeout or interval is refused); the leeway
  carries `minimum_value: 0`, `maximum_value: 300` (A-4's range, `manual-revision-notes` PD-3);
  every count and size `minimum_value: 1`. The algorithm list is `required`, `minimum_cardinality: 1`,
  and each value matches `(?i)^(?!none$|hs)\S+$`: `none` and every `HS*` name, in any case, are
  refused (as the verifier refuses them, `manual-revision-notes` PD-1), and **any
  other JWS algorithm name is accepted by the schema**, so a post-quantum name (`ML-DSA-44`) needs
  no schema change (`manual-revision-notes` DEC-1, the developer's Q-6). The generated validator
  applies the pattern with Python's `re` (LinkML's pydantic generator writes one `field_validator`
  per pattern, as `rp_service.py`'s `pattern_base` shows), so the look-ahead works. Whether the
  installed PyJWT implements a name is checked at start-up, by the verifier's constructor
  (`manual-revision-notes` PD-1 keeps that check), which fails fast naming the algorithm and the
  installed PyJWT version. Rejected: a positive pattern listing today's names (it closes the list
  that DEC-1 of `manual-revision-notes` keeps open; RISK-8). The target's `shapes.ttl` carries the
  same `sh:pattern`, which SHACL's XPath regex cannot read (no look-ahead, no inline flag); accepted:
  no shape validation runs over settings (the conformance suite covers the metamodel and the toy
  library only), and the settings are never a request body.
  `max_body_bytes` and `max_restore_bytes` stay in `ServiceSettings` (DEC-2).

  Group defaults. `ifabsent` cannot name a class instance, and the stock generator gives an optional
  inlined slot `default=None`, so `ToolkitSettings().http` would be `None`. A new
  `GenerationAnnotation` value `default_instance` on a slot makes `SplitPydanticGenerator` emit
  `Field(default_factory=<Range>)`; it is refused (generation check) on a slot whose range is not a
  class or whose range has a required slot without `ifabsent`. The six group slots of
  `ToolkitSettings` carry it, so `ToolkitSettings()` holds six default groups and
  `settings_from_env` keeps the factory through `create_model`.
- **PD-7 Wiring.** Each constructor takes the group it uses, defaulting to a fresh default
  instance: `HttpAdapter(..., http: HttpSettings | None = None)` builds its `httpx.Timeout` from it;
  `FusekiStore`, `ZitadelIdentity(..., http=, directory=)`, `JwksTokenVerifier(..., jwks=, http=)`,
  `S3FileStore(..., http=)` (boto `Config(connect_timeout, read_timeout, retries={"max_attempts"})`),
  `RedisEventBus(..., events=)`, `Relay(..., events=)`, `EventHub(events=)`,
  `MessageBus(..., limits=)` and `bootstrap(..., limits=)`, `Mapper(..., limits=)`,
  `Documents(..., limits=)`, `tenant_dump.restore(..., limits=)`, `add_events_route(..., sse=)`.
  The roots limit is read where `manual-revision-notes` A-2 puts it (its PD-7): the `Mapper`,
  which the kit builds (`entrypoints/kit.py:174`) and every unit of work and the reference
  collections share; `UnitOfWork` reads `mapper.max_roots`, and the `max_roots=` keyword A-2 left
  on it goes with the other per-value keywords. `DEFAULT_MAX_ROOTS` (`mapper.py:291`) is deleted:
  after A-2 its only use is the `Mapper` default, which `LimitSettings` now gives.
  `ServiceKit`/`install_service(..., toolkit: ToolkitSettings | None = None)` pass the kit-built
  objects their groups. Durations become `timedelta(seconds=...)` inside the constructor. The old
  keyword arguments and module constants go (DEC-5).
- **PD-8 Wire (DEC-8).** `ZitadelUserState`: `USER_STATE_UNSPECIFIED`, `USER_STATE_ACTIVE`,
  `USER_STATE_INACTIVE`, `USER_STATE_DELETED`, `USER_STATE_LOCKED`, `USER_STATE_INITIAL`, each with
  a `meaning`. `zitadel_state` ranges over it. `PROJECTS`, `MACHINE_USERS`, `OWN_ORGANISATION`,
  `TOKEN_PATH` move to `testkit/zitadel.py`; `PAGE_SIZE` goes (PD-6).
- **PD-9 The `kind` check (DEC-4).** `rp_generation.yaml`: enum `TargetKind` (`domain`,
  `technical`); optional slot `target_kind` (range `TargetKind`) on `GenerationTarget`, whose TOML
  key is `kind`; the permissible value `target_kind` of the enum `BoundaryRule` (`:1157`). The slot
  cannot be called `kind`: that global slot exists (`rp_generation.yaml:738`, range
  `ConstraintKind`, used by `ConstraintCase`) and stays, since `ConstraintCase` stays with the
  conformance suite (PD-11). In stage 1 the key is mapped by one more `FIELD_OF_TOML_KEY` entry
  (`"kind": "target_kind"`); in stage 4 it becomes `slot_usage: target_kind: {alias: kind}` on
  `GenerationTarget` with the other aliases (PD-10); an alias names a field, not a slot, so it
  does not clash with the global slot. In `checks/boundary.py`, `target_kind_problems(view, folder, kind)`: for
  `technical`, every own module annotated `module_kind: technical`; for `domain`, no own module
  annotated `technical`. Run by `steps.py::_boundary_problems` with `run.target.target_kind`. All four toolkit technical targets
  say `kind = "technical"`, the metamodel target `kind = "domain"`, the generator's own target
  `kind = "technical"`.
- **PD-10 Aliases (D-4).** `schema_file` gets `alias: schema`, `regenerate_command` gets
  `alias: regenerate-command`; `config.py` validates rows by alias (`RpModel` has
  `validate_by_name`), and `_problems` names the alias from the error's `loc`. `FIELD_OF_TOML_KEY`,
  `TOML_KEY_OF_FIELD` and `_field` go. `RpModel` validates by name as well as by
  alias, so a row that names a field whose alias differs (`schema_file`) is refused by one check
  before validation, comparing the row's keys with the model's aliases, with today's error text.
- **PD-11 Testkit records (D-4, DEC-2).** New target `model/technical/testkit/rp_testkit.yaml`
  (`kind = "technical"`, `openapi = false`, package `rdf_persistence.testkit.generated`). This is
  the **one** move of the testkit's records (`generator-package` stage 1 only cuts the imports
  left, its PD-1). Every record that a testkit module which stays in the library (`guards`,
  `markers`, `model_shape`, `shape_snapshot`, `zitadel`, `containers/fixtures`) imports from
  `rp_generation` moves there, slots and enums with them, found by `grep` on 48f80c6: `ClassShape`,
  `SlotShape` (`model_shape`, `shape_snapshot`), `ContainerMarker` (`markers`), `Violation`
  (`guards`), `MachineUser`, `ZitadelProject`, `ZitadelServer` (`zitadel`, `containers/fixtures`),
  and `ExecResult`, `FusekiServer`, `GarageServer` (`containers/fixtures.py:22-28`): ten. Their
  slots go with them, among them `slots` (`:779`), `server` (`:1040`) and `machine_users`
  (`:1053`), which only these classes use. `ConstraintCase` and `ConstraintKind` stay in
  `rp_generation.yaml`, with the global slot `kind` (`:738`): their only user is
  `testkit/conformance.py`, which `generator-package` (DEC-4) moves to the generator. `freshness.py`
  and `conformance.py` keep importing `rp_generation` until F-1 (a No-go here). The generator's
  modules that use a moved record import it from the testkit's package (generator → library, the
  allowed direction). `GenerationTarget` stays in `rp_generation.yaml`. New: `FieldFlags`
  (`required`, `multivalued`) for `model_shape.py:67`.
  The three `model_copy(update=...)` sites A-6 left here use `RpModel.replaced()`
  (`manual-revision-notes` PD-8), which validates: `testkit/conformance.py:51` (the case's
  instance paths made absolute), `testkit/zitadel.py:235` (`machine_users`) and
  `generation/pipeline.py:143` (`schema_file`, `step` on a `CheckProblem`).
  `testkit/tokens.py:86-92` builds `JwtClaims` (wire) and dumps it by alias with
  `exclude_none=True`; the `roles` claim and `extra` stay a merge at the PyJWT boundary.
- **PD-12 From the environment (DEC-6).** `rdf_persistence/entrypoints/environment.py`:
  `settings_from_env(model: type[M], *, prefix: str = "RP_", environ: Mapping[str, str] | None = None) -> M`.
  It imports `pydantic_settings` inside the function; missing, it raises `ImportError` naming the
  `settings` extra. It builds a `BaseSettings` subclass with `pydantic.create_model` over `model`'s
  fields, `env_prefix=prefix`, `env_nested_delimiter="__"`, reads `environ` (default `os.environ`),
  and returns `model.model_validate(read.model_dump())`. `pyproject.toml`:
  `settings = ["pydantic-settings==2.16.2"]`. Exported from `rdf_persistence` lazily.

## Algorithm / approach

Worked example, the key guard of `unique_keys.py` after the change:

```python
# services/vocabulary.py: the fixed terms in one place
def key_held_terms(registry: URIRef, *, values: SparqlTerm, excluded: Iterable[URIRef]) -> KeyHeldTerms:
    return KeyHeldTerms(
        registry=term(registry), p_kind=term(REGISTRY_KIND), p_owned_by=term(REGISTRY_OWNED_BY),
        aggregate=term(REGISTRY_KIND_IRIS[RegistryKind.AGGREGATE]),
        values=values, excluded=term_list(excluded),
    )

# services/unique_keys.py
def guard(claim, registry, excluded) -> SparqlTerm:
    return fragment_terms(_GUARD, key_held_terms(registry, values=_values(claim), excluded=excluded))
```

`fragment_terms` is `fragment` over a model, as `fill_terms` is `fill` (PD-4). A factory takes the
varying fields as keywords; it never spreads `model_dump()`, which serialises `SparqlTerm` to
`str`. `KeyBranchTerms` adds `index` the same way (`key_branch_terms(..., index=count(n))`).

Worked example, settings from the environment:
`RP_HTTP__READ_TIMEOUT_SECONDS=60 RP_JWKS__ALLOWED_ALGORITHMS='["RS256"]'` and
`settings_from_env(ToolkitSettings)` give `http.read_timeout_seconds == 60.0`,
`jwks.allowed_algorithms == ["RS256"]`, every other value its default.

Idempotency: no stored data changes. Generation is reproducible (rp-generation); moving the
schemas changes manifests and generated paths only. Settings are values, built once.

### Anti-patterns

| Don't | Do instead | Why |
|---|---|---|
| Put a settings or template class in `rp_service.yaml` | Its own group (DEC-2) | It would reach the served OpenAPI and the consumer's TypeScript |
| Build a term bundle with `**some_model.model_dump()` | A factory that takes the extra fields | `model_dump` turns `SparqlTerm` into `str`; `fill` then refuses it |
| Read `os.environ` in a constructor or at import | `settings_from_env` at the composition root | A library must not reach into the host (analysis §5.1) |
| A per-value keyword beside the group parameter | The group only | Two spellings of one value (DEC-5) |
| Move a protocol slug or IRI into settings | Leave it next to its use | P-0009, keep.md |
| A hand-written shim at the old generated paths | Import from `rdf_persistence` | DEC-9; a shim in a `generated` folder is deleted by the next run |

## Error matrix

| Failure mode | How it is detected | Expected handling |
|---|---|---|
| A technical target holds a module not annotated `technical` | `target_kind_problems` | `rp-generate` fails, rule `target_kind`, naming target and module; nothing written |
| A domain target holds a technical module | same | same |
| A domain model, or a hand-written domain module, imports a technical one (toolkit) | `domain-never-imports-technical-models`, and the boundary check for a generated one | `make check-architecture` / `rp-generate` fails naming both |
| A service or entrypoint imports a wire model | `layers` (as today: `adapters.generated` is in the adapters layer) | `make check-architecture` fails |
| A hand-written model in `services/` outside `generated/` | model guard (PD-3, unchanged) | fails naming the class |
| A layout function in `domain/layout.py` needs the policy | `domain-never-imports-technical-models` | it belongs in `services/iris.py`; move it (DEC-3) |
| An algorithm name the installed PyJWT does not implement (`ML-DSA-44` on 2.15.1) | the verifier's constructor (`manual-revision-notes` PD-1) | `ValueError` at start-up naming the algorithm; the settings model accepted it (PD-6) |
| A term given in the bundle and again in `more` | `fill_terms` | `SparqlError` "term given twice", before any query text exists |
| `default_instance` on a slot whose range is a type, or a class with a required slot without default | the generation check of PD-6 | `rp-generate` fails naming the slot; nothing written |
| The served OpenAPI's components after the move | `TOOLKIT_FOLDER` (PD-1) | TC-54; a stale path fails at start, never silently serves nothing |
| A raw `str` reaches a term model | `SparqlTerm`'s schema | `ValidationError` at build, before any SPARQL text exists |
| A schema uses `repr` with no `python_import` | the generated module fails to import | caught by `check-generated`'s mypy run; the extension's unit test covers the import |
| `settings_from_env` without the extra | `ImportError` | message names `rdf-persistence[settings]` |
| An environment value fails validation (`RP_HTTP__READ_TIMEOUT_SECONDS=-1`, `RP_JWKS__ALLOWED_ALGORITHMS='["HS256"]'`) | the generated model | `ValidationError` naming the field; nothing built |
| Zitadel answers a state outside the six | `ZitadelUserState` validation | `IdentityUnavailable` ("unreadable"), as for any unreadable answer (RISK-2) |
| A consumer passes a removed keyword (`stream=`, `limit=`) | `TypeError` at construction | Documented as BREAKING; the how-to shows the group |

## Risks / Trade-offs

- **RISK-1 A consumer imports a moved generated path.** Likelihood low (analysis §5.3: the known
  consumer imports `rdf_persistence`, `.testkit`, `.domain.base`, `.adapters.fuseki`,
  `.testkit.fakes`; the local checkout could not confirm it), impact: an `ImportError` at start-up.
  Mitigation: the release notes list the old and new paths; every name stays top-level (DEC-9).
- **RISK-2 Zitadel adds a user state.** Likelihood low, impact high: every account read answers
  503. Mitigation: all six v2 states listed; an integration test reads a real Zitadel's users.
  Accepted beyond that: an unknown answer is unreadable by design.
- **RISK-3 The settings break every composition root at once.** Likelihood certain for a consumer
  using the removed keywords, impact low (`TypeError` at start). Mitigation: defaults equal
  today's, so most roots change nothing; the how-to shows each replacement.
- **RISK-4 `pydantic_split` relies on `repr`.** A linkml upgrade could change `_get_pyrange`.
  Likelihood low (pinned 1.12.1), impact: term models typed `str`, caught by the TC of task 2.1 and
  by `fill` at run time. Mitigation: the test pins the behaviour.
- **RISK-5 The `iris.py` split breaks a deep import or an open branch.** A consumer importing
  `rdf_persistence.domain.iris` by path, or a branch editing `iris.py`, meets a moved file.
  Likelihood low for consumers (analysis §5.3: the known consumer takes `Iris`, `DEFAULT_IRIS` and
  `mint_aggregate_iri` from the top package), medium for branches; impact an `ImportError` at
  start, or a rebase. Mitigation: every name stays top-level (DEC-9); the split is two commits,
  rename first (PD-2), so a rebase follows the file; the release notes list old and new paths.
- **RISK-6 This change conflicts with `manual-revision-notes` on `jwks.py`.** Mitigation: it starts
  after that change merges, and task 3.2 moves A-3/A-4's parameters as they landed.

- **RISK-7 `generator-package` relies on `model/technical/testkit/rp_testkit.yaml`** (its DEC-4,
  PD-1, and its DEC-3: the library, testkit included, never imports the generator). Likelihood: a
  drift if either change renames the group; impact: F-1 cannot cut the dependency. Mitigation: the
  path and the record list are fixed here (PD-11, settled in the cross-change reconciliation of
  2026-11-17), and TC-50 asserts that no testkit module but `freshness.py` and `conformance.py`
  imports `generation.generated`.
- **RISK-8 The algorithm setting closes the list to new names.** A positive pattern would make
  ML-DSA (Q-6) need a schema change and a release. Avoided: the pattern refuses only `none` and
  `HS*` (PD-6), and the verifier checks every other name against the installed PyJWT at start-up.
  Residual, accepted: a family the pinned PyJWT lacks still needs a toolkit release that bumps the
  pin (`manual-revision-notes` DEC-1, RISK-1); a misspelt name passes the settings model and fails
  at start-up, with the name in the message (TC-60).

## Delivery decisions

The lead's, recorded as taken (R-0007); the developer may overrule any of them.

- **D-1 (stage 1, task 1.1)** GitNexus rated `GenerationTarget` CRITICAL (30 direct importers).
  Not taken to the developer: the task adds one optional slot defaulting to `None`, so no importer
  changes.
- **D-2 (stage 1)** The adversarial tester runs in every stage: the PLAN has no `## Invariants`
  section, and the appetite is LARGE (epic-delivery's tester condition). In stage 1 it runs after
  task 1.3, the riskiest task (`develop/agents.adoc`, keeping the challenge cheap), over the `kind`
  check and the new contract.
- **D-3 (stage 1)** The review set is the one `tasks.md` names for stage 1: L1, L2, L3 as separate
  passes, L4 and L5 as one. It is wider than P-0005's per-stage L2 and L3 pass; the PLAN is newer
  and names it, and stage 1 carries RISK-1 and RISK-5.
- **D-4 (stage 1, RISK-6)** After the rebase on `cc1b283` (PR #141), A-3 and A-4 sit in
  `adapters/jwks.py` as `JwksTokenVerifier(algorithms=DEFAULT_ALGORITHMS, leeway_seconds=30.0)`,
  the leeway finite and within 0 to 300, the ten asymmetric names as the default. They agree with
  PD-6's defaults and bounds; task 3.2 moves them as planned.
- **D-5 (stage 1, task 1.2)** GitNexus rated `domain/iris.py` HIGH (24 direct importers). This is
  RISK-5, accepted at the PLAN gate; not taken to the developer again.
- **D-6 (stage 1, task 1.3)** GitNexus rated the generated service package CRITICAL (36 direct
  importers). This is RISK-1, accepted at the PLAN gate; every name stays top-level (DEC-9). The
  service models moved from eager to lazy top-level imports, as `Iris` did in task 1.2, because
  importing `rdf_persistence` must not load `services` (`test_lazy_exports.py`).
- **D-7 (stage 1, tester finding 1, withdrawn)** Reported as: the model guard misses
  `from rdf_persistence import Page; class P(Page)` in `services/` once D-6 made the service models
  lazy. Not a defect: `_import_names` walks the whole `__init__`, so it reads the imports under
  `if TYPE_CHECKING:` that declare `rdf_persistence`'s lazy names. The tester's fixture declared its
  lazy name only in a dict, a shape the guard does not support and the toolkit does not use. The
  fixture now has the standard form, the test stays as the probe of D-6, and `_top_level_exports`'
  docstring says where lazy exports are read. Accepted residual: a package that declares lazy
  names only in a dict is invisible to the guard.
- **D-8 (stage 1, tester finding 2, re-labelled Critical)** `questions.adoc` and
  `architecture/data-flows.adoc` still named `model/service/`. Re-labelled from a docs Warning:
  task 1.3 owned the paths, and a reader following `questions.adoc` lands on a file that no
  longer exists. Fixed before the PR.
- **D-9 (stage 1)** The tester ran before the full gates, so its two findings are fixed, and its
  tests sorted, in a fix pass before the PR. The review findings get the stage's one fix pass
  after the PR, as the stage loop sets.
- **D-10 (stage 1, L2 W5 and L4+L5 W2, re-labelled Critical)** RISK-1 and RISK-5 were accepted on
  the mitigation "the release notes list the old and new paths", but no task writes them, the
  changelog is hand-written (`skip-changelog`), and only `7687f91` carries a `BREAKING CHANGE:`
  footer. Without it the accepted risks lose their mitigation. Fix: a BREAKING entry under
  `[Unreleased]` in `CHANGELOG.md` listing the three moves, carried by a commit whose footer names
  the `iris` and `tenant_move` moves. No history rewrite.
- **D-11 (stage 1, L2 W4, re-labelled Critical)** `tests/audit/scenario-map.csv` still maps 115
  rows to the test files task 1.2 moved, and the stage's new tests have no rows; the next
  `make refresh-map` would drop those mappings as vanished. The moves are this stage's, and the map
  is what the traceability check reads. Fix: rewrite the moved paths, refresh, map the new ids.
- **D-12 (stage 1, L2 W2 and W3, L3 W1, re-labelled Critical)** Pages the stage changed now
  disagree with the code: `architecture/index.adoc`'s layer-map row (edited by task 1.3) lists
  `Iris` and the service records under `domain`; `develop/index.adoc` and the Makefile's `mutation`
  help still say only the domain is mutated. Every builder brief said to update the docs its task
  changed; this is that item unmet. Fix: move the names to the `services` row and add
  `domain/layout.py` to the `domain` row (task 4.3 still rewrites the page); reword the mutation
  lines to `setup.cfg`.
- **D-13 (stage 1, L2 W1, re-labelled Critical)** The `rp-generation` delta's scenario "the
  schemas a consumer imports" has no test: a `glob` turned `rglob` in `metamodel_importmap` would
  expose the technical schemas unnoticed. A signed scenario without a test fails the traceability
  check. Fix: one unit test.
- **D-14 (stage 2, task 2.1)** GitNexus rated `SparqlTerm` HIGH (17 direct) and
  `GenerationAnnotation` CRITICAL (30 importers of `rp_generation.py`). Not taken to the
  developer: the task adds a pydantic schema hook (validation only, no change for code that uses
  `SparqlTerm` as a `str`) and one enum value, so no importer changes (as D-1).
- **D-15 (stage 2)** The review set is P-0005's one L2 and L3 pass for the stage, as the
  hand-over proposed. Stage 2 carries RISK-4 (`pydantic_split` relies on `repr`), which TC-16 pins;
  likelihood low on the pinned linkml, so it does not call for the full set. The full review runs
  after stage 4.
- **D-16 (stage 2)** The adversarial tester runs once, after task 2.2, as `tasks.md` names it
  (D-2: every stage). Task 2.1 adds a generator type (`python_import`), so its builder bootstraps
  the generator (stub the new import, `make generate`, restore, `make generate` again; hand-over
  of stage 1).
- **D-17 (stage 2, task 2.1, upstream finding, external)** The Context row "pydantic turns a
  `SparqlTerm` into a plain `str`" does not hold for a field typed `SparqlTerm` on pydantic
  2.14.2: without the schema hook, building the model raises `PydanticSchemaGenerationError`
  (a field typed `str` still turns a `SparqlTerm` into a `str`, so `model_dump` stays unsafe). DEC-7
  holds either way: the hook is what lets the field exist and refuse a raw `str`. No code change;
  no upstream issue (pydantic behaves as documented).
- **D-18 (stage 2, task 2.2)** GitNexus rated `session._owner_terms` HIGH (it reaches `remove`,
  `replace_graph`, `replace_parts`, `remove_parts`); `unique_keys.py` and `migrations.py` MEDIUM,
  `listing_query` LOW. Not taken to the developer: the query text must not change (TC-19's golden
  strings, captured before the change, pin every template the task touches), and the existing
  session, key, listing and migration tests stay unchanged.
- **D-19 (stage 2, task 2.2, divergence from PD-5)** `StampGuardTerms`' field is `schema_id`, not
  `schema`: a pydantic field named `schema` shadows `BaseModel.schema` and warns at import. The
  placeholder in `_STEP`, `_ROTATION` and `_STAMP_MOVE` follows (`$schema_id`); `SELECT_STAMPS` and
  the stamp insert keep `$schema` (not term models). The query text is unchanged: the lead ran
  TC-19's goldens against the code before the change (all ten equal).
- **D-20 (stage 2, task 2.2)** One existing test changed beyond the PLAN's list:
  `test_hard_check.py` counted the toolkit's targets (`== 4`); the templates target makes five.
- **D-21 (stage 2, task 2.3)** GitNexus rated `Iris` HIGH (22 direct); `effective_policy` LOW.
  Not taken to the developer: the task changes `Iris`' internals (`_fixed`, the matchers), not its
  public methods, and the `test_iris*` and `test_iri_policy*` tests stay unchanged. The tester
  runs in its own worktree on 2.1 and 2.2 (`7968110`) while 2.3 is built (R-0004).
- **D-22 (stage 2, task 2.3, as built)** `IriParts` forbids unknown keys through `RpModel`'s
  `extra="forbid"`, with no annotation. `Iris._fixed` is the model, and it is dumped only at the
  library boundaries (`str.format`, `_compile`). The helper is `iri_template_variables`. Two
  readers now test `is None` where they tested a key's presence: `_belongs` (a `tenant` group that
  did not take part in the match) and `tenant_of_access` (an access template with neither `tenant`
  nor `tenant_id`, which used to raise `KeyError` and now reaches `self.tenant("None")`). The
  builder holds that both paths need an invalid policy; the stage's review judges it. The review
  (S1) agrees: `_compile` makes every named group mandatory, so `_belongs` behaves as before for
  any policy; `tenant_of_access` needs a policy built with `model_construct`, and then refuses
  with `InvalidIri`. The review (S2) adds GitNexus ratings missing here: `Iris._belongs` CRITICAL
  (3 direct, 37 processes), `session._fill_marked` CRITICAL (3 direct), `Iris.tenant_of_access`
  HIGH (4 direct). Not taken to the developer: `_belongs` is behaviour-preserving (S1), and TC-19's
  goldens pin `_fill_marked`'s text.
- **D-23 (stage 2, L2 W1, re-labelled Critical)** `architecture/generation.adoc`,
  `architecture/index.adoc` and `rp_templates.yaml`'s description (which flows into the generated
  docstrings) say every field of the templates group is a `SparqlTerm`; task 2.3 added
  `IriTemplateVariables` and `IriParts`, of plain strings. Re-labelled as D-12 was in stage 1: the
  stage changed these pages and they now disagree with the code. Fix: name the IRI models in both
  pages and reword the schema description; `make generate`.
- **D-24 (stage 2, L2 W2, re-labelled Critical)** Five tests task 2.1 added to
  `tests/unit/domain/test_sparql.py` (TC-14, TC-17, TC-55) have no row in
  `tests/audit/scenario-map.csv`. Re-labelled as D-11 was: the map is what the traceability check
  reads. Fix: map them; `make refresh-map` lists none of this stage's ids.
- **D-25 (stage 2, L2 W3, re-labelled Critical)** TC-23's reserved-word test passes with the
  reserved-word check deleted: the default UUID4 tenant id never matches `app` or `books`, so the
  check is never reached. A PLAN TC that does not test its row is that brief item unmet. Fix: a
  policy whose `tenant_id` spec can spell the word; assert `InvalidIri` when it is reserved and
  acceptance when it is not.
- **D-26 (stage 2, checker F-C1, the developer's decision 2026-11-17)** `Iris.tenant_id_of` still
  reads the match by a string key (`found["tenant_id"]`), the one matcher of task 2.3 not read
  through `IriParts` (P-0007). Fixed now (one fixer, one full-gates run) rather than left under
  the floor. On the same day the developer granted the lead push, PR and merge on green CI for
  `technical-models` until the change ends (epic-delivery, Authority).
- **D-27 (stage 2 merge, the developer's decision 2026-11-17)** PR #145 and its follow-up #146
  were merged as admin, before CI. The rebase onto #143 left the new templates target's manifest
  with a stale input hash (`generation/checks/hard.py`, changed by #143), which stopped every test
  target on `develop` until #146 regenerated it. Lesson for later stages: after a rebase, run
  `make generate` and `make check-generated` before the PR's gates.
- **D-28 (stage 3, Prepare)** RISK-6 re-checked on `dca21ae`, after `manual-revision-notes`
  stage 2 (#143): `adapters/jwks.py` still holds A-3/A-4 as D-4 recorded
  (`algorithms=DEFAULT_ALGORITHMS`, `leeway_seconds`, bounds 0 to 300), and `Mapper(max_roots=)`
  with `DEFAULT_MAX_ROOTS` (A-2) as PD-7 expects; #143 touched `fuseki.py` and `documents.py`
  (media types), which tasks 3.2 and 3.3 build on as they now are. `manual-revision-notes`
  stage 3 is in progress in another session; the stage 3 PR rebases on it if it lands first.
- **D-29 (stage 3, the developer's instruction: run in parallel, R-0004)** Task 3.1 runs alone
  (every other task takes its groups). Then 3.2, 3.3 and 3.4 run in parallel, each in its own
  worktree, because their files are disjoint: the kit builds only `Documents`, `Mapper`,
  `EventHub`, `Relay`, `restore` and the SSE route (task 3.3), the adapters of 3.2 are built by a
  consumer's composition root, and 3.4 owns `entrypoints/environment.py`, the `settings` extra and
  its lazy export. The lead merges the three into the stage branch and re-runs the task gate (T2).
  The tester runs after 3.3 (tasks.md); 3.5 last. GitNexus indexes the main checkout, which
  another session holds on `change/manual-revision-notes-s3`; impact reads that state.
- **D-30 (stage 3, Prepare)** GitNexus: `Mapper` MEDIUM (14 direct), `HttpAdapter` MEDIUM (7),
  `ServiceKit` MEDIUM (6), `MessageBus` LOW, `JwksTokenVerifier` LOW, `FusekiStore` LOW;
  `GenerationAnnotation` as D-14. None HIGH or CRITICAL; not taken to the developer.
- **D-31 (stage 3, task 3.1, external library: LinkML 1.12.1)** The stock pydantic generator
  writes `ifabsent: string(RS256)` on a multivalued slot as `Field(default="RS256")`, a scalar
  default on a list field that pydantic does not validate; PD-6 assumed a list default. The lead's
  choice among contribute / fork / work around: a work-around in the one place AGENTS.md names for
  it, `SplitPydanticGenerator` (`generation/extensions/pydantic_split.py`, with its own test): a
  multivalued `ifabsent: string(a, b, ...)` becomes the list `['a', 'b']`, anything else on a
  multivalued slot is refused. An upstream issue to LinkML is offered to the developer (Open).
- **D-32 (stage 3, task 3.1, as built, divergences from PD-6)** (1) Every scalar settings slot is
  `required: true` as well as `ifabsent`, so `HttpSettings(read_timeout_seconds=None)` is refused
  (without it the generator types the field `Optional`). (2) `polling_interval_ms` is an integer,
  `minimum_value: 1`; every `*_seconds` slot is a float, `retention_seconds` and
  `resume_window_seconds` included. (3) The `default_instance` check is the `HardRule`
  `default_instance` (`checks/default_instance.py`) and also refuses a multivalued slot and a range
  class declared after its holder in the same module (the generated `default_factory` would raise
  `NameError` at import). (4) The settings tests are in `tests/unit/services/test_settings_model.py`:
  `.importlinter`'s `domain-tests-stay-in-the-domain` forbids a domain test importing `services`.
  (5) `test_hard_check.py` counts six targets (as D-20). Every default equals the code it replaces
  (the builder compared all 25; only the type of `s3.py`'s ints differs).
- **D-33 (stage 3, task 3.1, spec gap, for the developer)** The `rp-generation` delta has no
  requirement for `default_instance` or the list default; their tests are mapped, at medium
  confidence, to the `rp-settings` requirement "Deployment values are generated settings with
  today's defaults". Adding a requirement changes a signed spec, so it waits for the developer
  (Open): recommended, an `rp-generation` requirement "A slot can default to an instance of its
  class" with the type-range, required-slot and declaration-order refusals as scenarios, in task 4.2.
- **D-34 (stage 3, task 3.4, external library: pydantic-settings 2.16.2)** `BaseSettings` reads
  only `os.environ`, so `settings_from_env(..., environ=)` injects the mapping by overriding
  `EnvSettingsSource._load_env_vars`, a private method (the library's own dotenv, AWS and Azure
  sources override it the same way), wired through `settings_customise_sources`, so no dotenv file
  or secrets directory is read. The lead's choice: a work-around in this one module, pinned by
  `==2.16.2` and covered by TC-40, so an upgrade that changes the method fails a test. Also exported
  lazily from `rdf_persistence`: `ToolkitSettings` and its six groups (a consumer builds them).
- **D-35 (stage 3, task 3.2, as built)** `generation/lint.yaml` excludes the six `USER_STATE_*`
  values from `standard_naming`: they are Zitadel's wire values and cannot be snake_case. The
  verifier's leeway bounds now come from `JwksSettings` alone; its `none`/`HS*`/empty-list refusal
  stays as defence in depth beside the PyJWT check (TC-60). TC-30 also sets
  `unknown_kid_cooldown_seconds=1`: the cooldown spaces the refresh of stale keys too, as before.
  boto turns `max_attempts=N` into `total_max_attempts=N+1`, as today. `jwks.RS256` stays (the
  testkit imports it).
- **D-36 (stage 3, task 3.3, as built, and an incident)** TC-36 reads the events route in real
  time (`keep_alive_seconds=0.05`, a comment within 3 s): `install_service` takes no clock. The
  constructors' `limit < 1` / `max_roots < 1` checks are gone; `LimitSettings` refuses those values.
  Incident: the builder's Serena `replace_content` resolved a relative path against the main
  checkout (held by another session) and edited two test files there; it reverse-applied its own
  diff and the lead confirmed the main checkout has no tracked change. A repo-wide `ruff --fix`
  also touched four probe scripts of `test-debt-paydown`; the lead restored them. Briefs for later
  tasks name absolute worktree paths for Serena. Parallel merge (D-29): the three tasks were
  cherry-picked onto the stage branch; one conflict (`scenario-map.csv`, rows both appended)
  resolved by keeping both.
- **D-37 (stage 3, rebase onto `otel-observability` stage 1, #149)** `develop` moved 15 commits
  while stage 3 was built. Every conflict was additive: `pyproject.toml` keeps both the telemetry
  and the settings targets; `pydantic_split.py` keeps #149's field-name fix and 3.1's list
  defaults; the rest were import lines, unioned by a script that refused any other hunk; the
  generated manifests took `develop`'s side and `make generate` rewrote them (P-0003). Two slips,
  both the lead's: `test_hard_check.py` was committed with its markers inside the 3.1 commit
  (`e0b40fc`; fixed by its own commit, the toolkit now having seven targets, since history cannot
  be squashed here), and #149's new Redis test still built `RedisPair(redis)`, which 3.5 changed to
  take the `toolkit` fixture (a semantic conflict, fixed in the test). Both were caught by the
  stage's full gates before any push.
- **D-38 (stage 3, L2 W1 with S2 and S3, re-labelled Critical)** The `rp-settings` scenario "a
  timeout set by the consumer" has no test: nothing builds `JwksTokenVerifier` with a non-default
  `HttpSettings`, so dropping `http=` at `jwks.py:100` passes the suite. Also unmapped: the RISK-2
  test `test_the_states_of_a_live_zitadels_users_are_all_known_states` (S3); TC-60's verifier test
  is mapped as a requirement, not as its scenario (S2). Re-labelled as D-11 and D-24: the map is
  what the traceability check reads. Fix: one unit test, `FusekiStore` and `JwksTokenVerifier`
  from `HttpSettings(read_timeout_seconds=60)`, both reading 60, mapped as the scenario; the S2 and
  S3 rows.
- **D-39 (stage 3, L2 W2, re-labelled Critical)** `RedisPair` builds its group with
  `model_copy(update=...)`, which skips validation: an old option name (`claim_idle=`) passes
  silently and the test runs on the 30 s default. Our library's validated `RpModel.replaced()`
  exists for this (`manual-revision-notes` PD-8, PD-11, TC-49); not using it is a work-around of
  our own library. Fix: `toolkit.events.replaced(...)` and the conftest docstring.
- **D-40 (stage 3, L2+L3 W3, re-labelled Critical)** D-31 accepted the LinkML work-around on
  AGENTS.md's condition "with its own test"; its refusal (a multivalued `ifabsent` not of the
  form `string(a, b, ...)`) is untested, as is the `default_instance` refusal of a multivalued slot
  (D-32 (3)). The accepted decision loses half its mitigation (as D-10). Fix: one test of each
  refusal, naming the slot.
- **D-41 (stage 3, L2 W4, re-labelled Critical)** `architecture/index.adoc`, edited by this
  stage, does not list `rdf_persistence.services.generated.settings` nor the seven new top-level
  names (as D-12, D-23). Fix: add them to the services row.
- **D-42 (stage 3, L2 W5, re-labelled Critical)** `CHANGELOG.md` `[Unreleased]` names none of the
  stage's BREAKING removals nor its additions; RISK-3's mitigation and the Error-matrix row
  "Documented as BREAKING" depend on it (as D-10). Fix: under `[Unreleased]`, Changed (BREAKING:
  each removed keyword and public constant with its group) and Added (the settings groups,
  `ToolkitSettings`, `settings_from_env`, the `settings` extra, `default_instance`, the list
  default), plus stage 2's owed `python_import` line (stage 2 floor, L2 W4), the same file and
  section.
- **D-43 (stage 3, checker F-1 with F-2, the developer's decision 2026-11-17)** Two pages still
  describe removed keywords: `howto/event-driven.adoc` (the relay interval as a constructor
  argument `install_service` cannot set; it is `events.relay_interval_seconds` through
  `install_service(toolkit=)`) and `architecture/data-flows.adoc` (`limit` commands per `handle`;
  it is `limits.max_messages`). The new changelog line says every removed keyword raises
  `TypeError`; `bootstrap(limit=)` raises `ValueError` (tester F-3). Fixed now: one fixer, one
  full-gates run. The checker's F-3 (a kept tester test repeats TC-25's property) is under the
  floor.
- **D-44 (stage 4, Prepare, the developer's answers 2026-11-17)** D-33: yes. The `rp-generation`
  delta gains the requirement "A slot can default to an instance of its class" with four
  scenarios (a group defaults to its own defaults; a slot that cannot default to an instance; a
  list default; a list default in another form), written by the lead; task 4.2 covers them and
  remaps the stage 3 tests from `rp-settings` to it. D-31: yes, file it. The defect was already
  reported upstream (linkml/linkml#4160, open, same reproduction), so the lead added a comment
  instead of a duplicate: confirmed on linkml 1.12.1 with pydantic 2.14.2, and the case of a
  default of several values, which #4160's option (b) would make inexpressible
  (issuecomment-6960813182). The work-around of D-31 stays until #4160 is settled.
- **D-45 (stage 4, Prepare)** GitNexus rated `ClassShape` and `FusekiServer` CRITICAL (30
  direct, the importers of `generation/generated/rp_generation.py`, as D-14) and `read_targets`
  HIGH (the conformance and freshness flows). Not taken to the developer: the move is RISK-7,
  accepted at the PLAN gate; `read_targets`' messages are pinned by TC-46 and TC-47; the release
  notes list the moved records' new path (as D-42).
- **D-46 (stage 4, Prepare: parallel tasks, R-0004 and the developer's instruction)** Tasks 4.1,
  4.2 and 4.3 run in parallel, each in its own worktree: 4.1 owns `rdf_persistence/` and the unit
  tests of the moved records, and edits no docs page; 4.2 owns `tests/feature/technical_models.feature`
  and its steps; 4.3 owns every docs page of its list and writes the `testkit` group from PD-11 as
  planned (the checker compares it with 4.1 as built). All three append to
  `tests/audit/scenario-map.csv`; the lead merges them and re-runs the task gate (T2).
- **D-47 (stage 4, review set)** Stage 4 closes the change, so it takes the full review once, as
  P-0005 and `tasks.md` say: L1, L2 and L3 as separate passes, L4 and L5 as one, over the whole
  change (`36f5b25..`, the four stages), plus the adversarial tester on stage 4's own diff (D-2)
  after the three tasks are merged, and a checker. Then the reconciliation of `proposal.md`
  (P-0004) in PR 4.
- **D-48 (stage 4, task 4.1, the developer's decision 2026-11-17: PD-10)** LinkML 1.12.1
  (external) refuses an `alias` in `slot_usage`, and its pydantic generator names a field after an
  alias that is a Python identifier (`alias: schema` makes a field `schema`, `alias: kind` renames
  `target_kind`). Task 4.1 made `regenerate-command` an alias and kept `schema` and `kind` in the
  key map of `config.py`, with a strict xfail on TC-45. The developer chose to extend our generator
  instead: `SplitPydanticGenerator` names every field after its slot and keeps the alias apart (as
  it already does for a non-identifier alias), so `schema` and `kind` become slot aliases and the
  key map goes, as PD-10 planned. The field names of every generated class with an identifier
  alias are checked by `check-generated` and the suite. Both LinkML behaviours are reported
  upstream.
- **D-49 (stage 4, task 4.2's finding; Critical against `rp-generation`)** A consumer's
  technical module cannot use a slot ranging over a class, so neither `default_instance` nor any
  nested technical record: the boundary check refuses the reference (`[reference]`, asks for
  `owned`) and the hard check then asks the owned class to include `Described`. The toolkit's own
  schemas escape both only through the PD-23 exemption. A technical class is never stored, so the
  root, owned and reference rules do not apply to the classes of a module annotated
  `module_kind: technical`; the fix exempts them, as `_technical_classes` already does for
  ownership. 4.2's `default_instance` scenarios then run through `rp-generate` end to end.
- **D-50 (stage 4, task 4.1)** `TokenSigner.issue` builds `JwtClaims` with `model_construct`, not
  validation: the testkit must make tokens that lack `sub` or `exp`, or carry a refused subject, for
  the verifier to refuse. Accepted: the testkit is outside the layers and its purpose is that.
- **D-51 (stage 4, T1 after the merge)** 4.3 ran `check-docs` and `check-quality`, not the suite:
  `test_no_live_file_still_names_an_old_path` fails on the deep-import breaks that
  `architecture/index.adoc` and `howto/settings.adoc` list by their old path. The pages point to
  the changelog for the old paths instead (the guard's exemption, D-10). Fixed with the cold
  reader's Criticals and Warnings on `howto/settings.adoc` and `howto/adopt.adoc` in one docs
  fixer; the code fixer takes D-48 and D-49.
- **D-52 (stage 4, D-48 as built; the lead's choice under the developer's "do not ask")** Naming
  every field after its slot, as D-48 wrote it, renames 80 generated fields: the wire and service
  schemas give a slot an identifier alias on purpose, to name the field (`IdSpec.kind`,
  `ProblemDetails.title`, the Zitadel wire names), and every user of them breaks. So the rule is
  opt-in: a slot annotated `field_name: slot` (a `GenerationAnnotation`) is named after the slot and
  keeps its alias; every other field keeps today's name. `schema_file` (alias `schema`) and
  `target_kind` (alias `kind`) carry it, and `FIELD_OF_TOML_KEY` goes, as PD-10 planned. The fixer's
  first attempt is kept as a patch in the session scratchpad, not in the repository. D-49 as built
  also skips the other hard class rules (key, reserved segment, workflow, application, `iri_type`)
  for a technical class, as PD-23 does for the toolkit's own; the direction rule still runs.
- **D-53 (stage 4, the developer's instruction 2026-11-17)** Merge the fixes, skip the demo (the
  developer accepts the change), open PR 4, merge it as admin and close the change without asking.
  The review set of D-47 still runs, in parallel with the D-52 fixer; the checker covers the fix
  pass. The two LinkML issues of D-48 are drafted, not filed: the permission check refused the
  filing and the instruction did not name it.
- **D-54 (stage 4, L2 W1, re-labelled Critical; the lead's slip)** The rebase onto #152 met a
  whole-file conflict in `tests/audit/scenario-map.csv` at task 4.1's commit, and the lead's union
  script kept both sides: every row twice (3,794 ids). Rebuilt by a row-wise three-way merge of the
  stage's own map changes (3,820 rows, no duplicate id); the renamed reference test's old row
  dropped. A union script must refuse a hunk that spans the file, as D-37's refused any non-import
  hunk.
- **D-55 (stage 4, the full review's decision)** Re-labelled Critical and fixed in one fix pass:
  1. **Non-finite and unbounded durations** (L1 W1, L2 W2, L4+L5 W1, tester F-4; stage 3 tester
     F-1, worse than recorded): `inf` or `1e309` passes every `*_seconds` slot but the leeway. An
     infinite JWKS cooldown stops authentication about ten minutes after start; `timedelta` of a
     huge value raises `OverflowError`, so the events route answers 500. Fix: every duration slot
     gets a finite `maximum_value` (one year, 31,536,000 s, generous enough to change no deployment
     and small enough for `timedelta`), and a test per group.
  2. **The JWKS cooldown** (L1 W2, L4+L5 W2): its floor goes from 0.001 to 1 s (it was a fixed
     10 s; it is what holds forged key ids off the identity provider), and `JwksTokenVerifier`
     refuses a cooldown longer than the TTL (the verifier would refuse every token for the
     difference, each cycle), as `_checked_algorithms` refuses a bad list.
  3. **Secrets in `settings_from_env`'s errors** (L4+L5 W3, L1 S1, reproduced): the synthetic
     class sets `hide_input_in_errors=True`.
  4. **D-49's holes** (tester F-1, F-2): a module with no `module_kind` that imports a technical
     module and holds its class passes; a technical class with `AggregateRoot` escapes the root
     rules yet `root_classes` returns it. Fix: the import rule refuses any non-technical module
     holding a technical class, and a technical module may declare no root.
  5. **`default_instance: true` unquoted is ignored** (tester F-3, with stage 3 tester F-4): the
     spec writes `true`; YAML's boolean and `'True'` silently generate no default. Fix: the flag is
     read case-blind from either form, and a value that is not a boolean is refused, naming the slot.
  6. **Docs that disagree with the code** (L3 W1, W2, S1, S2): `architecture/generation.adoc` still
     asks a nested technical class for `owned: true`; it and `rp_testkit.yaml` say the testkit never
     imports the generator's models (`freshness.py`, `conformance.py` do, until `generator-package`
     F-1); `.importlinter` says `testkit.generated` does not exist; `architecture/index.adoc`
     overstates what the `layers` contract covers.
  7. **Release notes** (L4+L5 S3, as D-42): `CHANGELOG.md` gains stage 2's `fill_terms`,
     `fragment_terms` and the `SparqlTerm` field that refuses a raw `str`, and moves
     `ZitadelUserState` under Changed with its consequence (an unknown state makes the answer
     unreadable).
  8. **Scenario steps that cannot fail** (L2 S1, S2, as D-25): "no token verifier is built" asserts
     a list nothing fills; "is refused" imports a path that never existed. Fix both steps.
  The fix pass's builder sorts the tester's 334 tests (keep, merge or drop) and the lead confirms.

Under the floor (not fixed in stage 4):

- L2 S3: "the defaults" scenario reads 8 of about 20 slots through `ToyService`; TC-25 covers each.
- L3 S3: TC-50's rule could be an import-linter contract; F-1 of `generator-package` removes it.
- L4+L5 S1: one `Seconds` type for the eleven duration slots.
- L4+L5 S2: `"RP_"` as a literal; a misspelt `RP_` group is ignored without a word (the how-to says
  so).
- L1 S2: `secret` is missing from the allowed annotation values (a misspelt value leaves a
  testkit credential in a repr); `python_import` is not checked as a dotted name. Only a schema
  author meets either.
- L1 W1's tighter maxima (SSE lifetime, access TTL): a deployment choice; the bound of D-55 1 only
  keeps the values finite.
- Tester F-5: `ifabsent: string()` on a multivalued slot defaults to `['']`.
- Tester F-6: `issue(sub=123)` emits a pydantic serialisation warning.

Under the floor (not fixed in stage 3):

- Tester F-1 (Warning): `+inf` accepted for every duration (`nan`, `-inf` refused). Only an
  operator who sets `inf` reaches it; flagged for the full review after stage 4 (an infinite JWKS
  TTL keeps a rotated-out key).
- Tester F-2 (Warning): malformed JSON in an `RP_` variable raises pydantic-settings'
  `SettingsError`, naming the group, not a `ValidationError`; start-up still fails loudly.
- Tester F-3 (Suggestion): `bootstrap(limit=5)` raises `ValueError`, not `TypeError`; with a
  handler that declares a `limit` dependency it binds there, which is `bootstrap`'s dependency
  injection working as designed.
- Tester F-4 (Warning): `default_instance` is missing from the hard check's allowed annotation
  values, so a misspelt value (`'True'`) passes and generates no default; only a schema author
  meets it, and the toolkit's schema is correct.
- L2 S1: the `default_instance` check reads `slot_usage` only through the generator, so an
  annotation given in `slot_usage` on a type-ranged slot is caught by `check-generated`'s mypy,
  not by `rp-generate` naming the slot.
- L2 S4: TC-39 needs no container but sits in `tests/integration/`.
- L2 S5: `settings_from_env` validates twice (the synthetic settings class, then the model); the
  docstring says once.
- L2 S6: `pydantic_split.py`'s module docstring says "five things" and names neither
  `default_instance` nor the list default. Task 4.3's docs pass.
- L2 S8: `develop/index.adoc:194` writes "`max_roots=500`" like the removed keyword.
- L2 S7 (fixed by the lead with this record): the roadmap line in `tasks.md` ticks 3.5.

Under the floor (not fixed in stage 2):

- L2 W4: `CHANGELOG.md` has no line for the `python_import` annotation. Owed to stage 4 with the
  other release-note lines (task 4.3 or the PR 4 reconciliation).
- L2 S1 (optional): an explicit `InvalidIri` in `tenant_of_access` when both parts are `None`.
- L2 S3: no test of the error-matrix row "`repr` with no `python_import`"; the stage's tester
  wrote one (`repr` alone adds no import), which the fix pass keeps.
- L2 S4: TC-19's golden names an uncommitted capture script; the docstring should say the golden
  is frozen.
- Tester F-1: `model_json_schema()` fails on a term model (`is_instance_schema`). The templates
  group is never served (`openapi = false`), and nothing asks for its JSON Schema.
- Tester F-2: `fill_terms` given a plain dict raises `ValueError`, not `SparqlError`; the
  parameter is typed `BaseModel`.

Under the floor (not fixed in stage 1):

- L1 S1, L4+L5 S2: `boundary.py:147` re-validates `kind`; the reviewers disagree on whether the
  model holds the member or the string (the 1.1 builder saw a `str`). Harmless either way.
- L3 S1: three docstrings (`services/iris.py:1`, `domain/layout.py:3`, `InvalidIri`) describe the
  pre-split layout. Task 4.3's docs pass.
- L4+L5 W1: nothing checks that `__init__.py`'s `TYPE_CHECKING` imports equal `_LAZY_MODULES`.
- L4+L5 W3: the generator imports its own generated output (`rp_generation`, the service
  package) at start, so adding a type it uses or moving a target needs a hand bootstrap. Noted in
  the hand-over for stages 2 to 4; a follow-up documents the order.
- L4+L5 W4: `services.iris` imports the private `_SEGMENT`/`_segment` from `domain.layout` (PD-2
  kept them private on purpose; `thematic-structure` may rename them).
- L4+L5 S1: the new contract's forbidden list and the `kind = "technical"` targets are two lists.
- L4+L5 S3: no `__dir__` for the lazy names.
- L2 S1, S2, S3, S5: a parametrized kind table, the target named in the domain CLI test,
  `lint-imports` output naming both modules, assert messages.
- L2 S4 (stage 1): TC-12 names `rdf_persistence.JwtClaims`, which was never top-level; the wire
  models are adapters-only (PD-2).

## Open Questions

- Whether `ServiceSettings` should join `rp_settings.yaml` (one settings home) once E-1 can import
  across targets. Recommendation: yes, in `thematic-structure`.
