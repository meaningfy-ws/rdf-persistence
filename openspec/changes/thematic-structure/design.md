> Derives from: EPIC `thematic-structure` ([proposal.md](proposal.md)), capabilities
> `rp-package-boundaries` and `rp-generation`. Seeds: [inputs/seed.md](inputs/seed.md).
> Type: Implementation (a staged move).

## Context

On `develop` at 79c6837 (after `generator-package` stages 1 to 3) the library has four layer packages and
eight generation targets (`pyproject.toml:105-159`: the metamodel, the generator's own, and the
technical groups `service`, `templates`, `telemetry`, `settings`, `testkit`, `wire`, each with
`kind` and `python_package`). The four earlier changes (ASM-1 to ASM-3 of the EPIC) left the
metamodel in `domain/generated/`; the technical groups in the `generated/` folder of
the lowest layer that uses them (`technical-models` DEC-1): `services/generated/{service,settings,templates}/`,
`services/generated/telemetry/` (`otel-observability` PD-1), `adapters/generated/` (`wire`) and
`testkit/generated/` (`testkit`, its PD-11); `domain/layout.py` and `services/iris.py` split from
`domain/iris.py`, and `services/tenant_move.py` (`technical-models` DEC-3); and the generator in
`rdf_persistence_generation/`, a sibling top-level package. So every technical model already sits in
the layer DEC-3 asks for, and this change adds the theme. This PLAN starts from that state; task 1.1
checked it on 2026-11-18 (D-1 under Delivery decisions).

What the brief asked to check against the code:

| Claim | Found | In this PLAN |
|---|---|---|
| The theme graph is acyclic (analysis §5.3) | Holds for the hand-written modules (grimp, 2026-11-17). Order (PD-6 as built, D-16 W1): core; iris, schema; provenance, files; persistence; access, migrations; tenancy; collaboration, events; messaging; api | DEC-1, PD-1, PD-6 |
| The generated code can mirror the themes | Holds for `rp_service` and `rp_wire` (every class has one lowest-user theme, table PD-2); fails for the metamodel (cycles) | DEC-2, PD-2 |
| The consumer imports 5 modules | 3 by hand; the `domain.base` lines are its generated files; the `adapters.fuseki` line is a test string | DEC-5, PD-8 |
| The 149-name re-export (`__all__`, `rdf_persistence/__init__.py:274`; the EPIC says 141) | Holds, 149 names | PD-8, TC-03 |
| The iris wrappers only delegate | 11 of 23 do | DEC-8, PD-5 |
| `FusekiStore` is half generic | Holds: `query`, `update`, `put_graph`, `_raise_for_status`, `_read_result` are SPARQL 1.1 Protocol; the endpoint layout (`_dataset_path`), `create_dataset`, `drop_dataset`, `list_datasets` and dataset-level `export_quads`/`import_quads` are Fuseki's (`fuseki.py:25-160`) | DEC-7, PD-7 |
| Contracts exist to carry over | `.importlinter`: 14 contracts (the 10 of the EPIC, `domain-never-imports-technical-models`, and from `generator-package` `library-never-imports-the-generator`, `domain-tests-stay-in-the-domain`, `sparql-parser-only-through-the-wrappers`; PD-6 places each). import-linter 2.11 has `containers`, `exhaustive` and wildcard module expressions in `forbidden` and `layers` | DEC-6, PD-6 |

## Goals / Non-Goals

**Goals:**

- Every library module lives at `rdf_persistence/<theme>/<layer>/`, and its unit tests at
  `tests/unit/<theme>/`, with `git log --follow` reaching its history before the move.
- Domain and technical models are told apart by path, and the generator and import-linter refuse a
  misplaced one (DEC-3).
- Each stage merges green with `make check-all`, `make check-generation` and `make test-containers`.
- A consumer that imports the public package sees nothing; one with old generated code is warned
  for one release.

**Non-Goals:** everything in the EPIC's No-gos. Also: re-sorting functions inside a module; new
names in the public API; moving the integration, feature or e2e tests.

## Decisions

Settled in the EPIC and cited, not re-argued: DEC-1 to DEC-10. The new ones:

- **PD-1 The module map.** Every hand-written module, its theme and layer (old path → new path; a
  module keeps its file name unless stated):

  | Theme | domain | services | adapters | entrypoints |
  |---|---|---|---|---|
  | core | `base`, `exceptions`, `media`, `sparql`, `sparql_parsing`†; metamodel `generated/` | `artifacts`, `yaml_files`, `telemetry`† | `_http` | |
  | iris | `layout`† (`domain/layout.py`) | `iris`† (`services/iris.py`) | | |
  | schema | | `schema`, `schema_structure`, `vocabulary` | | |
  | files | `blob_keys` | `files` (port) | `s3` | |
  | provenance | | `provenance`, `visible_part` | | |
  | persistence | | `store` (port), `session`, `unique_keys`, `listing`, `loading`, `jsonld`†, `mapper`, `decoding` | `sparql_protocol` (new), `fuseki` | |
  | migrations | | `migrations` | | |
  | access | | `access`, `identity`, `tokens` | `jwks`, `zitadel` | |
  | tenancy | | `tenancy`, `sweep`, `tenant_sweep`, `tenant_dump`, `migration_runner`, `iri_policy_guard`, `tenant_move`† (`services/tenant_move.py`) | | |
  | events | | `events` (port), `event_hub`, `event_stream`, `relay` | `redis_events` | |
  | collaboration | | `discussion`, `reference_collections`, `workflows`, `transitions`, `write_guards`, `collaboration` | | |
  | messaging | | `messagebus` | | |
  | api | | `aggregates`, `documents`, `file_removal`, `components`, `shacl`† | | `auth`, `environment`†, `kit`, `negotiation`, `openapi`, `problems`, `responses`, `router`, `service`, `sse` |

  † A module an earlier change creates or moves: `services/jsonld.py` (`manual-revision-notes`,
  the one JSON-LD path; its users are `loading`, persistence, and `documents`, api);
  `domain/layout.py`, `services/iris.py`, `services/tenant_move.py` (`technical-models` DEC-3, the
  `iris.py` split) and `entrypoints/environment.py` (`technical-models` PD-12, `settings_from_env`);
  `services/telemetry.py` (`otel-observability` PD-3; every theme logs through it);
  `domain/sparql_parsing.py` and `services/shacl.py` (`generator-package`'s lock on the SPARQL parser).
  The rule for a module is the one PD-2 gives a technical class: the lowest theme that uses it, in
  the layer it already has. `sparql_parsing` is imported by `domain/sparql` (core), `migrations`,
  `migration_runner` and the testkit, so its lowest user is `core`: `core/domain`. `shacl` is imported
  by `services/documents` (api) and by the generator's testkit (outside the themes), and imports only
  `sparql_parsing` (core), so its lowest in-theme user is `api`: `api/services`. (`schema` would also
  satisfy `themes-ordered`; the rule picks `api`, and moving it down later is one more `git mv`.) Its
  test, `tests/unit/services/test_shacl.py`, goes to `tests/unit/api/`; `tests/unit/domain/test_sparql_parsing.py`
  to `tests/unit/core/`; the helper `tests/unit/sparql_threads.py` and its one user `tests/unit/test_sparql_parser_threads.py` stay at the root (a subprocess test of the parser lock, not of one module; PD-11's "a test of several themes" rule leaves it where it is).
  The four testkit shims (`testkit/{freshness,conformance,roundtrip,strategies}.py`, generator-package PD-8)
  import only `rdf_persistence_generation`; the testkit is outside the themes, so the move does not
  touch them, and `generator-package` removes them in 0.6.0.

  The six technical groups the earlier changes leave, and where they go (classes in PD-2):

  | Group | Today (after the earlier changes) | After this change |
  |---|---|---|
  | `service` | `services/generated/service/` | split over the `services` and `entrypoints` targets of eight themes |
  | `wire` | `adapters/generated/` | `persistence/adapters`, `access/adapters` |
  | `settings` | `services/generated/settings/` | `core`, `persistence`, `access`, `events` `services`; `api/entrypoints` |
  | `templates` | `services/generated/templates/` | `iris`, `persistence`, `migrations` `services` |
  | `telemetry` | `services/generated/telemetry/` | `core/services` |
  | `testkit` | `testkit/generated/` | unchanged: the testkit is outside the themes (No-go) |

  The table is data too: `tests/unit/test_theme_layout.py::LAYOUT` holds it, and each stage turns
  its rows on (TC-01).
- **PD-2 The technical split (E-1).** A technical class goes to the lowest theme that uses it, in
  the lowest layer of that theme that **every** user may import (DEC-3): a class used only by
  adapters goes to `adapters`, only by entrypoints to `entrypoints`; a class used by an adapter
  and by an entrypoint, directly or through a class that composes it (`ToolkitSettings` composes
  every settings group), goes to `services`, since adapters and entrypoints import neither the
  other (PD-6). So every settings group sits in a `services` layer, and "a setting with the
  constructor that takes it" (DEC-3) holds for the theme, not the layer. Schema files are
  `model/technical/<theme>/rp_<theme>_<layer>.yaml`, generated into
  `rdf_persistence/<theme>/<layer>/generated/`. Each split schema keeps the `default_prefix` and
  prefixes of the group schema it leaves, so every class and slot URI stays the same (TC-07).
  From the users found on 2026-11-17 (an AST scan of every `from ...generated... import`), plus
  the classes `technical-models` and `otel-observability` add (marked †):

  | Target | Classes |
  |---|---|
  | `core/services` | `HttpSettings`† (users: `core/adapters/_http`, `files/adapters/s3`, and `ToolkitSettings`), `LogContext`† (every theme) |
  | `iris/services` | `IdKind`, `IdSpec`, `IriPolicy`, `ServiceSettings`, `IriTemplateVariables`†, `IriParts`† |
  | `persistence/services` | `Any`, `Filter`, `Condition`, `ListRequest`, `ListPlan`, `AggregateHead`, `Page` (its `total` slot is the predicate `listing` reads through `vocabulary.TOTAL`), `LimitSettings`†, the term bundles of `unique_keys`, `session`, `listing`† |
  | `persistence/adapters` | `FusekiDatasetList`, `FusekiDataset` |
  | `migrations/services` | `Migration`, `MigrationStep`, the migration guard's terms† |
  | `access/services` | `VerifiedCaller`, `CallerAccess`, `GrantSet`, `AccountSummary`, `JwksSettings`†, `DirectorySettings`† |
  | `access/adapters` | `JwtClaims`, `DiscoveryDocument`, `BadRequestMeans`, every `Zitadel*` record, `ZitadelUserState`†, and `rp_wire`'s own `Any` (range of `JwtClaims`) |
  | `tenancy/services` | `TenantDump`, `TenantSummary` |
  | `events/services` | `EventEnvelope`, `EventSettings`† |
  | `collaboration/services` | `Referrer`, `ReferrerList`, `MemberList` |
  | `api/entrypoints` | `Problem`, `ProblemKind`, `ProblemSlug`, `Authorised`, `LabelUpdate`, `TenantCreate`, `SseSettings`†, `ToolkitSettings`† |
  | unchanged | the `testkit` group (`rdf_persistence/testkit/generated/`): the testkit is outside the themes (No-go) |

  A served class whose range is `Any` (`Page`, `TenantCreate`) imports the one `Any` of
  `persistence/services`; a second served `Any` would be a duplicate component (PD-10). A slot used by several targets is declared in the lowest of them and imported by the others. A
  class whose slot ranges over a class of a higher theme is a placement error (error matrix). The
  `rp_*` names of the old technical schemas disappear; their `id` IRIs change too (they are
  technical, never stored, so no lock or migration is affected; TC-08).
- **PD-3 Cross-target imports (DEC-10).** `pydantic_split` builds one map `schema module name →
  python_package` from every module that declares `python_package` (the metamodel's, from
  `generator-package` PD-6, and now each technical schema's). When a schema imports a module in
  that map, the generated code imports its classes from that package and does not generate them;
  the manifest lists the imported module's YAML as an input. That every technical `python_package`
  agrees with its `[[tool.rp-generate]]` entry is `generator-package` PD-6 (b)'s hard check
  (`python_package_problems`, `rdf_persistence_generation/checks/python_package.py:29`, called from
  `_hard_problems` in `steps.py:110`), which already covers the technical groups; this change adds no check of its own, and each new per-theme
  schema carries the annotation that check asks for. A consumer's run uses the same map, so a
  consumer's technical target can import its own domain target.
- **PD-4 Kind and folder (DEC-3).** A new hard-check function `kind_folder_problems(target)` in
  `rdf_persistence_generation/checks/boundary.py`, beside `technical-models`' `target_kind_problems`
  (`boundary.py:193`; it checks the modules' `module_kind`, this one checks the folder): in the target's `package`,
  the segment before `generated` is `domain` for a `domain` target, and `services`, `adapters` or
  `entrypoints` for a `technical` one (a group segment after `generated` is allowed, so the old
  layout's `rdf_persistence.services.generated.service` passes during the move). Packages outside
  the themes are exempt: `rdf_persistence.testkit` (the `testkit` group; No-go: the testkit is
  outside the themes) and `rdf_persistence_generation` (the generator's own target,
  `rdf_persistence_generation.generated`). It runs **on
  the toolkit's own run only**, like `generator-package` PD-6 (b): a consumer that already declares
  `kind` (allowed since `technical-models` DEC-4) keeps its own folder layout, so the upgrade breaks
  no consumer. It is built, tested and **wired into `steps.py` in stage 1**, in `_boundary_problems`
  (`steps.py:96-101`) beside the `target_kind_problems` call: `technical-models`
  already put every toolkit technical target in a layer's `generated/` folder, so the toolkit's own
  targets pass it from the start and it guards every stage of the move.

  **The model guard** (`testkit/guards.py`, rp-generation "a hand-written domain class") keeps its
  consumer-facing default `SCANNED_LAYERS` and its scope (every layer it scans today, not only
  `domain`). Three things change with the move: (a) `FORBIDDEN_BASES` gains
  `rdf_persistence.core.domain.base.RpModel` in stage 2, because `_top_level_exports` resolves a
  consumer's `from rdf_persistence import RpModel` to the defining module, and without the new name
  the guard stops seeing any class derived from `RpModel`, silently (TC-24); the old name stays
  until stage 8 (the shim's users). (b) `DEFAULT_ALLOW` names `rdf_persistence/core/domain/base.py:RpModel`.
  (c) The toolkit's own guard test (`tests/unit/testkit/test_model_guard.py`) scans the library with
  `layers=LIBRARY_LAYERS` and the generator in a second call, as a package of its own
  (`GENERATOR = "rdf_persistence_generation"`, `layers=("",)`, lines 11 and 89). From stage 2 the
  library call becomes `layers=(*moved_themes, *old_layers_left, "testkit")` (each moved theme as a
  whole); the generator call stays as it is, since the generator is not a theme. Its `HAND_WRITTEN`
  allow-list entries are rewritten with each stage's path table.
- **PD-5 The `iris` theme and the wrappers (DEC-3, DEC-8).** `technical-models` (its PD-2) already
  split `iris.py` in the old layout: `domain/layout.py` holds the layout constants, `_segment`,
  `_prefix` and the 12 policy-free functions (`graph_iri`, `root_of_graph`, `skolem_iri`,
  `is_skolem_of`, `toolkit_principal_iri`, `policy_record_iri`, `stamps_graph_iri`,
  `is_inside_tenant`, `is_canonical_uuid`, `system_database_name`, `application_database_name`,
  `tenant_name_prefix`), and `services/iris.py` the rest (`Iris`, `DEFAULT_IRIS`, `IdSource`,
  `effective_policy`, `check_iri_policy`, the template machinery, the wrappers). Here the recipe
  moves them to `iris/domain/layout.py` (it imports nothing but `core.domain`) and
  `iris/services/iris.py`, and the wrappers go. Removed: `_default_iris`, `mint_tenant_iri`,
  `tenant_iri`, `aggregate_iri`, `is_aggregate_iri`, `is_aggregate_graph_iri`, `is_loaded_graph_of`,
  `mint_part_iri`, `loaded_graph_iri`, `tenant_resource_name`, `principal_iri`. `mint_aggregate_iri`
  stays in `iris/services/iris.py`, warning, until stage 8.
  Ten of the eleven call `DEFAULT_IRIS` (`_default_iris` is their helper); `tenant_resource_name`
  does not, but it assumes the default policy's UUID ids, and `Iris.resource_name` replaces it.
  No library module imports any of the eleven; their users are tests and fixtures, all rewritten
  in task 3.1: `tests/unit/services/test_iris.py` (moved there by `technical-models`), seven unit tests and three integration tests of
  `tenant_resource_name` (`tests/integration/tenancy/test_{tenancy,tenant_stores,sweep}.py`),
  `loaded_graph_iri` in `tests/integration/store/test_session.py` and
  `tests/perf/test_session_performance.py`, `principal_iri` in `tests/toy_service.py`.
- **PD-6 The contracts (DEC-6).** At the end of stage 7, `.importlinter` holds:
  - `themes-layered` (layers, `containers` = the 13 theme packages, `exhaustive = true`):
    `(entrypoints) | (adapters)` / `(services)` / `(domain)`. Exhaustive means a theme holds no
    module outside its layers.
  - `themes-ordered` (layers): `api` / `messaging` / `collaboration | events` / `tenancy` /
    `access | migrations` / `persistence` / `provenance | files` / `iris | schema` / `core`.
  - `layers-across-themes` (forbidden, three rules in four contracts, D-12 (4)): `rdf_persistence.*.domain` imports no
    `rdf_persistence.*.{services,adapters,entrypoints}`; `rdf_persistence.*.services` imports no
    `rdf_persistence.*.{adapters,entrypoints}`; `rdf_persistence.*.adapters` and
    `rdf_persistence.*.entrypoints` import neither the other.
  - `domain-pure`, `collaboration-layers`, `session-and-provenance-without-mapper`,
    `tenancy-without-the-runner`: same meaning, sources by wildcard or new path.
  - The `generator-package` contracts and the two the first list missed, each by the same rule (same
    meaning; only a path that names a moved module changes):
    - `runtime-without-extras`: sources become `rdf_persistence.*.{domain,services,adapters,entrypoints}`
      (and the two shims while they exist); the forbidden list (testkit, generator, pytest,
      testcontainers, linkml) names no moved path, so it stays.
    - `works-without-the-generate-extra`: its sources `rdf_persistence.services.schema` and
      `schema_structure` become `rdf_persistence.schema.services.schema` and `.schema_structure`
      (stage 3); the generator sources, `rdf_persistence.testkit` and the `ignore_imports` line on
      `rdf_persistence_generation.cli` name no moved path, so they stay.
    - `event-bus-libraries-in-one-module`: its `ignore_imports` entry
      `rdf_persistence.adapters.redis_events -> faststream` becomes
      `rdf_persistence.events.adapters.redis_events -> faststream` (stage 6); sources and forbidden
      modules stay.
    - `library-never-imports-the-generator`: unchanged. Its source is the whole `rdf_persistence`
      package and its four `ignore_imports` edges are the testkit shims, which the move does not touch.
    - `domain-tests-stay-in-the-domain`: kept, retargeted. Its source `tests.unit.domain` stops
      existing once the domain tests move to `tests/unit/<theme>/`, where they sit beside the tests of
      services. Each stage lists the domain-layer test modules it moves (for example
      `tests.unit.core.test_rp_model`, `tests.unit.core.test_sparql_parsing`) as `source_modules`
      and turns the forbidden list into `rdf_persistence.*.{services,adapters,entrypoints}`,
      `rdf_persistence.testkit`, `tests.toy`, `tests.toy_service`; `allow_indirect_imports = True`
      stays. After stage 7 `tests.unit.domain` is gone and the explicit list is the contract.
    - `sparql-parser-only-through-the-wrappers`: kept; its sources (`rdf_persistence`,
      `rdf_persistence_generation`) and forbidden modules stay, and the two wrapper entries of
      `ignore_imports` move: `rdf_persistence.domain.sparql_parsing -> ...` (two lines) becomes
      `rdf_persistence.core.domain.sparql_parsing -> ...` (stage 2), and
      `rdf_persistence.services.shacl -> pyshacl` becomes
      `rdf_persistence.api.services.shacl -> pyshacl` (stage 7, PD-1).
  - Gone: `layers` (replaced by the three above), `nothing-in-services-imports-the-bus` and
    `migrations-below-the-runner` (implied by `themes-ordered`), `technical-models`'
    `domain-never-imports-technical-models` (implied by `layers-across-themes`: every technical
    package sits in a `services`, `adapters` or `entrypoints` layer, which no `*.domain` imports).
    `themes-ordered` implies the bus rule only for the themes below `messaging`; for `api`, above
    it, `api-services-never-import-the-bus` (D-23) keeps
    `rdf_persistence.api.services.{aggregates,components,documents,file_removal}` off
    `rdf_persistence.messaging`.

  The 14 contracts of today therefore end as 17: ten carry over, four are gone, seven are new
  (`themes-layered`, `themes-ordered`, the four sections of `layers-across-themes` (D-12 (4)
  split the third in two) and `api-services-never-import-the-bus` (D-23)).

  During stages 2 to 6 the old `layers` contract and the new ones run side by side; a stage adds its
  themes to `containers` and `themes-ordered` (a theme not yet moved is absent, not empty).
- **PD-7 The store split (DEC-7).** `persistence/adapters/sparql_protocol.py`:
  `SparqlProtocolStore(HttpAdapter)` with `query`, `update`, `put_graph`, `_send`,
  `_raise_for_status`, `_read_result`, and abstract `query_path(dataset)`, `update_path(dataset)`,
  `graph_store_path(dataset)`, `create_dataset`, `drop_dataset`, `list_datasets`, `export_quads`,
  `import_quads`. `_raise_for_status` and `_read_result` are module functions today
  (`fuseki.py:47` and `:73`); they become methods so the messages (`BAD_QUERY_MESSAGE`, `UNREADABLE`,
  "answered {status}") say `self.service`, not "Fuseki". The 400 debug line then logs under
  `rdf_persistence.persistence.adapters.sparql_protocol`, and the two `caplog` logger strings in
  `tests/unit/adapters/test_fuseki_store.py:275` and `:292` change with it. The SPARQL protocol media
  types (`SPARQL_QUERY`, `SPARQL_UPDATE`, `RESULTS_JSON`) and `GRAPH_PARAM` move with it (protocol
  constants stay next to their use, P-0009). `FusekiStore(SparqlProtocolStore)` keeps the
  constructor, `service = "Fuseki"`, the layout, `ADMIN_DATASETS`, the form fields and the
  dataset-level N-Quads. Neither is a new public name; `second-store` imports the base by path.
- **PD-8 Shims and the template (DEC-5).** `rdf_persistence/domain/base.py` and
  `rdf_persistence/adapters/fuseki.py` become modules that `warnings.warn(..., DeprecationWarning,
  stacklevel=2)` naming the new path and the release that removes them, then re-export `RpModel`,
  resp. `FusekiStore` (and the module's other names, `SPARQL_QUERY` etc.). `domain/__init__.py` and
  `adapters/__init__.py` stay, docstring only. No library module imports a shim (TC-05). In a
  consumer run the base-model template writes `from rdf_persistence import RpModel as ...`; in the
  toolkit's own run it writes `from rdf_persistence.core.domain.base import RpModel as ...`
  (the top package imports the generated metamodel, so the toolkit's own code cannot use it).
- **PD-9 Theme packages.** Each `<theme>/__init__.py` and `<theme>/<layer>/__init__.py` holds a
  docstring only, so importing a theme imports nothing else and no cycle can hide in an
  `__init__`. The top `__init__.py` keeps its eager imports (domain and generated) and its
  `_LAZY_MODULES` map, on the new paths.
- **PD-10 The served set.** The technical targets whose classes the HTTP API serves carry
  `openapi = true` (`iris/services`, `persistence/services`, `access/services`, `tenancy/services`,
  `events/services`, `collaboration/services`, `api/entrypoints`). `services/components.py` (now
  `api/services/components.py`) reads the `openapi-components.json` of each, in that order, and
  merges them; a name in two files is an error. `SERVICE_SCHEMA` becomes `SERVED_SCHEMAS`, the tuple
  of their YAML paths; the TypeScript step copies the types of all of them, in the order today's
  single `rp_service.yaml` gives them (the golden files of TC-07 hold that order; a merged order
  that differs is a failure, not a new golden) (`rdf_persistence_generation/manifest.py:94` and
  `extensions/typescript.py:184`, `:209`, `:217` read `SERVICE_SCHEMA` today, as do
  `services/vocabulary.py:197` and `:200`, below). `vocabulary.TOTAL` reads `total`
  from the schema that declares it (`persistence/services`, with `Page`), and
  `vocabulary.IRI_POLICY` reads `iri_policy` from `iris/services` (with `ServiceSettings`); both
  are file reads of schemas of the same or a lower theme than their users.
- **PD-11 Tests follow (DEC-9).** `tests/unit/{domain,services,adapters,entrypoints}/test_*.py` move
  by the module they test to `tests/unit/<theme>/`. A test of several themes goes to the highest. The generator's tests
  (`tests/generator/`) and the testkit's (`tests/unit/testkit/`) do not move.
  Helpers (`builders.py`, `scene.py`, `conftest.py`) go where their users are; one used by two
  themes goes to `tests/unit/` root. `tests/changed.py` today has `LAYERS = {domain, services,
  adapters, entrypoints, testkit}` (line 16) and handles the generator apart, by `GENERATOR_PACKAGE`
  and `GENERATOR_TESTS` (lines 21-22; rule at 67-70: a change in `rdf_persistence_generation/` or
  `tests/generator/` selects `tests/generator/`). The move makes `LAYERS` the `THEMES` plus
  `testkit`, keeps the two generator constants and their rules as they are (`generation` is no
  member of the set), and maps `rdf_persistence/<theme>/...` to `tests/unit/<theme>/`; a change in
  `core` runs `make test-fast` (it replaces today's rule for `domain`, `DOMAIN_FOLDER`).
- **PD-12 One path table per stage.** Each stage's PR body lists old → new module paths, and
  `temp/` holds the ast-grep rule that rewrites them; the stage's last commit removes `temp/` files.
  The lead posts the table on every open PR of the repository.
- **PD-13 The release.** Stage 7 ends with a minor release that carries the shims and the warning
  of `mint_aggregate_iri` (CHANGELOG "Deprecated"). Stage 8 merges only after that release is
  published, and goes into the next minor release (CHANGELOG "Removed"; **BREAKING**).

## Algorithm / approach

**One stage, the same recipe** (stages 2 to 7; PD-12 for the table):

1. Turn on the stage's rows in `LAYOUT` (TC-01 fails: the new paths do not exist).
2. Split the technical schemas of the stage's themes out of the group files (PD-2), add their
   `[[tool.rp-generate]]` entries with `kind` and `python_package`, `make generate`. The diff is
   only moved classes and changed import lines; the served `/openapi.json` is unchanged (TC-07).
3. Commit A, the move only: `git mv` each module and its unit tests to their new folders.
4. Commit B, the rewrite: the ast-grep rule rewrites every `from rdf_persistence.<old> import` and
   `import rdf_persistence.<old>` in `rdf_persistence/`, `rdf_persistence_generation/`, `tests/`;
   then the strings (`mock.patch`, `caplog` logger names, `_LAZY_MODULES`, `ruff.toml`,
   `.coveragerc`, `.importlinter`, docs, the guard test's `HAND_WRITTEN` entries, the
   `test_lazy_exports.py` module list, and the module paths inside schema annotations, such as
   `technical-models`' `python_import: rdf_persistence.domain.sparql` in the templates schema).
   TC-04 finds any string left.
5. Contracts: add the themes to `themes-layered` and `themes-ordered`; retarget the fine-grained
   ones (PD-6).
6. Gate, then the lead's full gates, review, PR. `git log --follow` on two moved files is in the
   PR body (TC-02).

Commits A and B stay separate in the PR, and the PR merges with a merge commit, so rename
detection sees a pure rename. Rerunning a stage's rule is a no-op (it matches old paths only), so
a rebase onto a `develop` that gained new imports is: rerun the rule.

Worked example, stage 4 (persistence, migrations): `LAYOUT` gains
`rdf_persistence.persistence.services.session` and 10 more rows; TC-01 fails. The persistence
classes leave `model/technical/service/rp_service.yaml` for
`model/technical/persistence/rp_persistence_services.yaml` (`python_package:
rdf_persistence.persistence.services.generated`; its target `kind = "technical"`), and
`FusekiDatasetList` leaves `rp_wire.yaml` for `rp_persistence_adapters.yaml`; what stays in
`rp_service.yaml` imports them (it is higher). `git mv rdf_persistence/services/session.py
rdf_persistence/persistence/services/session.py`, and the rest; `git mv
tests/unit/services/test_session*.py tests/unit/persistence/`. The rule rewrites
`rdf_persistence.services.session` to `rdf_persistence.persistence.services.session` everywhere.
`themes-layered.containers` gains `rdf_persistence.persistence` and `rdf_persistence.migrations`;
`themes-ordered` gains them below `access`. `testkit/fakes.py` changes only its imports.

### Anti-patterns

| Don't | Do instead | Why |
|---|---|---|
| Edit a module's content in the move commit | Commit A renames only; B rewrites imports | `--follow` needs a near-identical file |
| Leave a re-export at the old path "for now" | Rewrite every importer (DEC-4); only PD-8's two shims | A second path lives forever |
| Re-export names in a theme's `__init__.py` | Import from the module (PD-9) | Hides cycles, doubles the paths |
| A technical model in `domain/generated/`, a domain class anywhere else | DEC-3, checked by PD-4 | Q-2: the kind shows in the path |
| Pass a setting into a domain function as a dict so it can stay in `domain` | Move the function up a layer (DEC-3) | P-0007 |
| Edit a generated file after a move | Fix `python_package` or the schema, `make generate` | LinkML is the single source |
| Rewrite imports with `sed -i` | The ast-grep rule (AGENTS.md) | It edits strings and comments blindly |
| Add a theme to `themes-ordered` before it exists | Add it in its stage (PD-6) | import-linter refuses a missing module |
| Silence a contract with `ignore_imports` | Move the importer or the imported (error matrix) | The order is the design |

## Error matrix

| Failure mode | How it is detected | Expected handling |
|---|---|---|
| A module was left at its old path | TC-01 (`LAYOUT`) | Stage not done; move it |
| An import or a string still names an old path | TC-04 (ast over the repository, text search of docs and configs) | Rewrite it in the same PR |
| A theme imports a theme above it | `themes-ordered` | A placement error: move the used thing down or the user up; never `ignore_imports` |
| A module sits outside a theme's layers | `themes-layered` (`exhaustive`) | Place it in a layer |
| A domain-layer module imports a technical model | `layers-across-themes` | Move the module up a layer (DEC-3) |
| A technical target's package is a `domain` folder, or the reverse | PD-4 hard check: `rp-generate` fails naming target and package | Fix `pyproject.toml` |
| A technical class's slot ranges over a class of a higher theme | `rp-generate` (unknown import) or `themes-ordered` on the generated code | Move the class to the higher theme's target |
| Two served targets declare one component name | PD-10 merge raises at install; TC-07 | The class was declared twice: keep one |
| `/openapi.json` or a consumer's TypeScript differs after a split | TC-07; the toy's `check-generated` | Fix the schema, never the output |
| A `python_package` disagrees with its target | Hard check (PD-3) | Problem naming both; nothing written |
| A consumer's old generated code imports `domain.base` | The shim | Works, warns once per process; its freshness check asks for `rp-generate` |
| A consumer imports a removed path after stage 8 | `ImportError` | Listed in the notes of the stage 7 and stage 8 releases |
| An open branch merges after a stage | Its CI fails on old imports | Rerun the stage's rule (PD-12) |
| A cycle at import time through an `__init__` | TC-06 (every theme and layer `__init__.py` is a docstring only, read with `ast`) | Empty the `__init__` (PD-9) |
| The model guard no longer sees a consumer's class derived from `RpModel` after `RpModel` moves | TC-24 (a fixture class `class X(RpModel)` imported from `rdf_persistence` is flagged) | `FORBIDDEN_BASES` names the new defining module (PD-4 a) |
| A technical class used by an adapter and an entrypoint is put in `adapters` | `layers-across-themes` on the generated code (entrypoints → adapters) | Move it to the theme's `services` target (PD-2) |
| A split schema gets a new `default_prefix`, so class or slot URIs change | TC-07 (the served JSON-LD context and `/openapi.json` differ) | Keep the group schema's prefixes (PD-2) |
| The Fuseki split changes behaviour | The store conformance suite on `FakeStore` and on Fuseki; `test_fuseki_store.py` unchanged apart from imports | Fix the split; the tests are the contract |

## Risks / Trade-offs

- **RISK-1 Parallel branches collide with each move.** Likelihood high (five changes open), impact
  medium: each rebase costs time. Mitigation: stages in order and small, the path table and rule
  on every open PR (PD-12), and E-5 first if `second-store` is first (DEC-7). The rest accepted.
- **RISK-2 A consumer's freshness check fails on upgrade.** The template line changes (PD-8), so
  its committed generated code is stale. Likelihood certain, impact low: one `rp-generate`.
  Mitigation: release notes; `generator-package` already makes every consumer regenerate once
  (its manifests), so stage 1 should ship in that same release if the timing allows.
- **RISK-3 Logger names in a consumer's configuration.** Every logger below `rdf_persistence` gets
  a new name. Likelihood medium, impact low. Mitigation: release notes list them; the parent
  logger `rdf_persistence` is unchanged. Accepted.
- **RISK-4 Rename detection lost on squash.** A squash folds commits A and B; a short module whose
  imports are half its lines would show as delete and add. Likelihood low, impact: `--follow`
  breaks for that file. Mitigation: merge commits for these PRs; TC-02 per stage.
- **RISK-5 The sibling changes landed differently** (ASM-1, ASM-2). Likelihood low after the
  cross-change reconciliation of 2026-11-17, impact: PD-2's
  table and PD-3's mechanism change. Mitigation: task 1.1 re-checks and amends this design before
  any move; DEC-3 holds whatever the technical groups are.
- **RISK-6 Tool indexes go stale.** GitNexus and Serena answer with old paths after a stage.
  Likelihood certain, impact low. Mitigation: the lead re-indexes after each merge.
- **RISK-7 Stage 8 lands before the deprecation release.** Likelihood low, impact high for a
  consumer that has not regenerated. Mitigation: PD-13; task 8.1 checks the published version.
- **RISK-8 The model guard goes blind for consumers.** `RpModel` changes its defining module in
  stage 2; the guard matches bases by fully qualified name. Likelihood certain if forgotten,
  impact high and silent (hand-written models pass every consumer's guard). Mitigation: PD-4 (a)
  and TC-24 in stage 2.
- **RISK-9 The kind/folder rule reaches consumers.** A consumer that declared `kind` after
  `technical-models` with a package such as `app.generated` would fail on upgrade. Likelihood
  medium, impact medium. Mitigation: the rule runs on the toolkit's own run only (PD-4); extending
  it to consumers is a developer's decision, not taken here.
- **Trade-off:** moving unit tests (DEC-9) roughly doubles each stage's file count, in return for
  `tests/unit/<theme>/` matching the code. Rejected: tests by layer (the layer folders no longer
  exist at the top, so the folders would name nothing).

## Open Questions

None blocks the PLAN. The leader's choices (DEC-1 to DEC-3, DEC-5, DEC-8, DEC-9) go to the
developer in the initiative's next round, each with the recommendation to keep it. The placement
conflict with `technical-models` (an innermost `technical` package against DEC-3) was settled in
the cross-change reconciliation of 2026-11-17: that change now applies DEC-3's rule to today's
layers. One question remains for the developer: whether the kind/folder rule should bind
consumers that declare `kind` (RISK-9); the recommendation is toolkit-only now, opt-in for
consumers later.

## Delivery decisions

- **D-1 PLAN amended at task 1.1** (builder, 2026-11-18, on 79c6837; the lead reviews). ASM-1 to ASM-3
  hold; what changed, one line each:
  - Context: targets `pyproject.toml:91-118` (four) became `:105-159` (eight); the base is `develop`
    after `generator-package`, not `docs/manual-revision-notes`.
  - Context table: 141 names became 149 (`__all__`); 10 contracts became 14.
  - PD-1: `domain/sparql_parsing.py` placed in `core/domain` and `services/shacl.py` in `api/services`
    (lowest theme that uses it), with their tests; the four testkit shims noted as untouched.
  - PD-3: the hard check cited at `checks/python_package.py:29`, wired at `steps.py:110`.
  - PD-4: `target_kind_problems` at `boundary.py:193`; wiring is `_boundary_problems`, `steps.py:96-101`;
    (c) follows `test_model_guard.py` (`GENERATOR`, a separate call, `LIBRARY_LAYERS`).
  - PD-6: the two uncovered contracts and the four of `generator-package` placed one by one; the count
    14 to 15 stated.
  - PD-7: `fuseki.py:46,:62` became `:47,:73`; `test_fuseki_store.py:237` became
    `tests/unit/adapters/test_fuseki_store.py:275,:292`.
  - PD-10: `manifest.py:89` became `:94`, `typescript.py:183` became `:184,:209,:217`, and
    `vocabulary.py:197,:200` named as readers of `SERVICE_SCHEMA`.
  - PD-11: `tests/changed.py` keeps `GENERATOR_PACKAGE`/`GENERATOR_TESTS`; `LAYERS` is the themes plus
    `testkit`, no `generation`.
  - tasks.md: 141 to 149 (success line, task 1.6, TC-03 twice), 140 to 148 (task 8.1, TC-03); task 1.3
    and TC-12 cite the code; task 1.4's test file marked new; task 1.5 extends
    `test_components_folder.py` (`test_components.py` never existed); task 1.6's new test renamed
    `test_no_old_module_paths.py` (`test_old_paths_gone.py` is `generator-package`'s); tasks 2.1 and
    7.1 carry the two new modules.
  - `proposal.md` (the EPIC) says 149 names at its three mentions, amended by the lead.
- **D-2 One session for both EPICs** (developer, 2026-11-17). `generator-package` and this change
  are delivered in one autonomous session, every stage, overriding "one EPIC per session, fresh
  session per stage". Mitigation: after each merge the lead re-reads this change's `handover.md`
  and `tasks.md` before the next stage; after any compaction it re-reads `handover.md` first.
  Stages 1–7 only: stage 8 needs a published release containing stage 7 (PD-13).
- **D-3 The acceptance demo is waived** (developer, 2026-11-17 and again 2026-11-18, before the
  autonomous run), although VERY LARGE makes it mandatory. Recorded in `evidence/acceptance.md`.
- **D-4 `second-store` is not planned first** (developer, 2026-11-17): task 4.1 takes the branch
  where the store split is built inside stage 4.
- **D-5 Open PRs before stage 1** (lead, under the developer's "take the decisions for me"). The
  ordering rule allows only release-please (#134) and the lead's own PRs before each stage. Open:
  #161 (the developer's, `.gitignore` only) and #167 (another session's, `CHANGELOG.md` only).
  Neither touches a file a move stage changes, so stage 1 starts; the rule is re-checked before
  every stage, and a PR touching moved files makes the stage wait for it.
- **D-6 Stage 1 built while `generator-package` closed** (lead, under the developer's "run things in
  parallel"). Its builders started from `generator-package` stage 4's head (79c6837); the branch is
  cut from `develop` after that change's archive merges, and the work is rebased onto it (the
  archive touches only `openspec/`).
- **D-7 Review set** (lead). As `generator-package` D-3 and rule P-0005: each stage gets one pass of
  L2 and L3; the full review (L1, L2, L3 apart, L4+L5 one pass) runs once, on stage 7, over the
  EPIC's diff. The tester runs on every stage that moves code (no `## Invariants` section at VERY
  LARGE).
- **D-8 Stage 1 placements and readings** (lead, from the builders). `services/shacl.py` goes to
  `api/services` (PD-2: the lowest theme that uses it is `api`; the generator's testkit is outside
  the themes). `LAYOUT` holds a row per generated technical class (one old generated package splits
  over several themes), the new module named `rp_<theme>_<layer>` (to confirm at stage 2). Six term
  bundles PD-2 places by module only are placed by their users: `RegistryTerms`, `KeyHeldTerms`,
  `KeyBranchTerms`, `OwnerTerms`, `ListingTerms` in `persistence/services`, `StampGuardTerms` in
  `migrations/services`; `schema/vocabulary` builds bundles of higher themes, to settle when stage
  3 moves `schema`. TC-11: a module outside the target's folder without `python_package` is still
  refused (only a module beside the root is generated into the target). TC-72 uses `rp_service`
  instead of a literal the old-path test bans. Four `Callable` aliases of the public surface have
  no `__module__`; their home is the lazy map.
- **D-9 Stage 1 review and tester, accepted** (lead; review 11 findings, tester 149 tests, 23
  failed first, 9 findings; one fixer pass). Re-labelled Critical, with the reason: review W1 (one
  TypeScript file per served schema cannot keep TC-07 byte-identical once stage 3 splits
  `rp_service.yaml`: the step merges every served schema's types into `rp_service.ts` in
  `SERVED_SCHEMAS` order, as PD-10 says); review W5 (`refresh-golden`/`refresh-snapshot` now rewrite
  the move's baselines TC-07 and TC-03, a gate that can be reset by accident: TC-07's refresh gets
  its own target and the `-k "ext_"` line leaves it alone, the docs and help strings say what each
  rewrites); tester U1 (the stage's own head fails
  `test_a_toy_generation_writes_rp_service_ts`: the toy copy ignores `golden/`). Accepted below
  Critical: review W2 (TC-18 calls `assert_public_imports` on the toy's modules); tester F1 = review
  S5 (the kind/folder exemptions match whole package segments); F2 (a malformed `python_package` —
  empty, blank, not a dotted identifier — is a `SchemaGenerationError` naming the module); F3 (the
  old-path scan reports an unparsable file instead of skipping it); F4 = review S4 (the scan covers
  the root `*.md` and `setup.cfg`, `CHANGELOG.md` exempt); F8 (`tests.changed` falls back to
  `test-fast` with a reason when a theme's test folder does not exist, instead of running nothing).
  Owed to task 7.2's docs: review W3 (`generation.adoc` ~361 and the `pydantic_split` row: the
  cross-target import and the consumer's `from rdf_persistence import RpModel`), W4 (the kind/folder
  rule and its `TARGET_KIND` id). Under the floor: review S1 (the in-process mypy test is not
  `slow`), S2 (`SERVED_SCHEMAS` vs the `openapi = true` targets), S3 (a stale comment); tester F5
  (concatenated `mock.patch` strings), F6 (the `LAYOUT` guard misses modules in subpackages), F7
  (relative imports of an old module).
- **D-10 Imports between merged served schemas** (lead, from the fix pass of D-9). Every served
  schema's TypeScript now lands in `rp_service.ts`; a type that refers to a type of another served
  schema would still import from `./<that schema>`, a file that is no longer written. Harmless while
  only `rp_service` is served; the stage that serves a second schema (stage 3, the split of
  `rp_service.yaml`) rewrites such imports to the merged file, with a test, before its TC-07 check.
- **D-11 Stage 1 checker: verdict fail, fixed now** (lead; 5 findings). C1 (Critical, agreed): `make
  refresh-snapshot`, which every model change runs, also rewrites the TC-03 public-surface snapshot,
  so a name left in the wrong module could be written into the baseline; the public-surface refresh
  moves to its own target (`refresh-surface`), pinned like `refresh-served-golden`. W2: the OpenAPI
  golden test names `make refresh-served-golden`. W3: a served schema imported by another served
  schema is merged once, not also written as its own file (with an import edge in the W1 test).
  Under the floor: S4 (the kind/folder problem names only the package; no end-to-end "writes
  nothing"). S5: the new tests' scenario-map rows are added before this change's archive.
- **D-12 Stage 2 (`core`) as built** (builder of 2.1, accepted by the lead). (1) `rp_settings.yaml`
  imports `../core/rp_core_services` by a relative path: the library's `metamodel_importmap` maps
  only `model/*.yaml`, and the relative path needs no library change. (2) The move and the
  `domain.base` shim are two commits, so `git log --follow` sees `core/domain/base.py` as a rename
  (TC-02). (3) `test_theme_layout.py` gains a `SHIMS` set (a listed shim may stand at its old path)
  and `test_no_old_module_paths.py`'s `EXEMPT` lists the five files that name the shim's old path
  on purpose. (4) `layers-across-themes` is four contracts, not three: a forbidden contract cannot
  state the entrypoints/adapters independence both ways in one. (5) PD-4 (c) needs no change yet:
  the library guard already scans every layer folder. (6) `tests/unit/services/test_telemetry.py`
  and `tests/unit/adapters/test_http.py` stay until their themes' test folders exist (PD-11).
  (7) The telemetry attribute `error.type` of the toolkit's exceptions now names
  `rdf_persistence.core.domain.exceptions.X` (RISK-3's family; the release notes say so). (8) The
  ast-grep pattern `from a.b.c import $$$A` also matched submodules and partial name lists; the
  builder repaired ~270 lines and checked every import's names against the original — later
  stages use explicit patterns and read the diff. (9) The model guard misses a consumer class whose
  base comes through `from rdf_persistence import RpModel`; it predates the move: #173.
- **D-13 Stage 2 review and tester, accepted** (lead; review 9 findings, tester 87 tests, 11 failed
  first, 6 findings; one fixer pass). The review disagreed with D-12 (5), (6), (9); the lead agrees
  and those readings are replaced here. Critical: C1 = tester F2 (since the move nothing forbids
  `core` importing the unmoved old layout — `themes-ordered` has one theme, the old `layers` and
  `domain-never-imports-technical-models` name only the old packages — so two old contracts were
  weakened): a temporary forbidden contract, source `rdf_persistence.core`, forbidden the old
  `domain`, `services`, `adapters`, `entrypoints` packages (removed at stage 7 when the old layout is
  gone), and `domain-never-imports-technical-models` gains `rdf_persistence.core.domain` (tester
  F3); TC-09 and TC-53 plant their imports at `core/domain/generated/`. C2 = tester F1 (the
  library's model guard no longer scans `core`; D-12 (5) was wrong): `LIBRARY_LAYERS` gains `core`,
  with a planted record in `core/services`. Accepted below Critical: W1 (TC-24 is not met for a real
  consumer; D-12 (9) deferred it): `rdf_persistence.RpModel` joins `FORBIDDEN_BASES`, tested on a
  consumer fixture package, closing #173; W2 (D-12 (6) was wrong, `tests/unit/core/` exists): the
  telemetry and HTTP tests move there; W3 (docs naming moved paths: `architecture/index.adoc`
  ~292, ~344, `questions.adoc` ~274, `generation.adoc` ~304, ~320, ~322, `develop/index.adoc` ~26);
  S2 (`test_technical_split.py`'s historical paths were rewritten into paths that never existed:
  restored and exempt). The tester's `xfail(strict=True)` tests are not kept as xfails (no new
  xfail): the fix makes the accepted ones pass; the rest are sorted. Under the floor: review S1
  (contract labels "3/3"), S3 (two stale docstrings), S4 (the move and the import rewrite were one
  commit; TC-02 holds; later stages keep them apart); tester F4 (`rp_settings.py` re-exports
  `HttpSettings` at the old generated path), F5 (TC-06's checker errors without naming a file on a
  syntax error), F6 (it reads without `utf-8-sig`); a consumer `python_import` naming a gone module
  is written as is.
- **D-14 Stage 2 checker: verdict fail, fixed now** (lead; 6 findings). C1 (Critical, agreed: the
  other direction of D-13 C1): an unmoved module can import upward into `core` (old `domain` into
  `core.services`/`core.adapters`/`core.services.generated`, old `services` into `core.adapters`,
  old `entrypoints` into `core.adapters`) with no contract breaking, where the old `layers` and
  `domain-never-imports-technical-models` broke two. A temporary forbidden contract set (removed at
  stage 7) states the old layers' order against the moved themes' layers: `rdf_persistence.domain`
  never imports `rdf_persistence.*.{services,adapters,entrypoints}`; `rdf_persistence.services`
  never `rdf_persistence.*.{adapters,entrypoints}`; `rdf_persistence.adapters` never
  `rdf_persistence.*.entrypoints`; `rdf_persistence.entrypoints` never `rdf_persistence.*.adapters`,
  each with a planted test. W1: `howto/settings.adoc` (~235) names `core/adapters/_http.py`. S1:
  `test_theme_contracts.py` checks every `core` layer is covered. Under the floor: S2 (TC-53's name
  vs its plant), S4 (no planted test exercises `themes-layered` or `layers-across-themes` in
  stage 2; later stages' TC-35, TC-45, TC-51 do). S3: D-12 (7)'s release-note line for `error.type`
  goes into stage 7's CHANGELOG entry (task 7.2).
- **D-15 Stage 3 as built** (builders of 3.1 and 3.2, accepted by the lead; built from stage 2's
  head before D-13/D-14 and combined on `develop` after #174). (1) PD-2 vs PD-10/TC-07: a technical
  class that would add TypeScript to the served `rp_service.ts` (the IRI models `IriTemplateVariables`,
  `IriParts`; the six term bundles) is generated as a non-served target under
  `<theme>/services/generated/<group>/`, so TC-07 stays byte-identical; `PLACED` rows carry that
  group. (2) Two served schemas: `components.py` leaves out a class another served schema declares,
  and the iris schema repeats the `url_segment` pattern for `tenant_segment` instead of importing
  `rp_core` (a test pins the two equal). (3) The merged TypeScript file is named `rp_service`
  (`SERVICE_MODULE`), not after the first served schema. (4) TC-33: a bad tenant segment, once
  refused by a wrapper with `InvalidIri`, is now refused by `ServiceSettings` with
  `ValidationError`. (5) Only the iris-only tests moved to `tests/unit/iris/`; the IRI policy tests
  of `api` and `tenancy` move with their themes. (6) D-8 closed: the six term bundles live in
  `schema/services/generated/templates/` (`vocabulary` builds them; `schema` is their lowest user),
  and `persistence`/`migrations` import them from below; PD-2's table is amended by this line.
  (7) D-10 closed: TypeScript that names a served type imports the merged file. (8) Logger names
  change with the move (`rdf_persistence.files.adapters.s3` …), RISK-3's list for the CHANGELOG of
  stage 7. (9) `vocabulary.TOTAL` and `IRI_POLICY` read the schema files of higher themes; a file
  read, not an import, as PD-10 states.
- **D-16 Stage 3 review and tester, accepted** (lead; review 9 findings, tester 242 tests, 18
  failed first, 4 findings; one fixer pass). Critical, the holes D-13 closed for `core` reopened
  for the four new themes: C1 = tester F1 (`core-never-imports-the-old-layout` and
  `domain-never-imports-technical-models` do not cover `iris`, `schema`, `files`, `provenance`), C2
  = F2 (the model guard does not scan them). So that no later stage repeats it, both lists are
  derived from the turned-on themes: the contract's sources name every turned-on theme
  (`rdf_persistence.<theme>`), `domain-never-imports-technical-models` takes
  `rdf_persistence.*.domain`, `LIBRARY_LAYERS` adds every name of `TURNED_ON`, and a test fails when
  a turned-on theme is missing from any of them. Accepted below Critical: W1 (the spec delta orders
  `core`; `iris`, `schema`, `files`; `provenance`, while PD-6 and the contract order
  `iris | schema` below `provenance | files`: the spec delta is amended to PD-6, the gated design
  decision the code holds, and stated as the order every later stage keeps); W2 (TC-35 gets planted
  tests: `files` → `provenance`, `iris` → `schema`, `iris.domain` → `iris.services.generated`); W3
  (docs naming moved paths: `architecture/index.adoc` ~309, ~322, ~326, ~342–351,
  `generation.adoc` ~373, `develop/index.adoc` ~26, ~28); W4 (`setup.cfg`'s mutation scope
  follows the domain modules into the themes, `rdf_persistence/*/domain/*` without `generated`, with
  their tests; `develop/index.adoc` ~70 says so); W5 (`tests/unit/services/test_aggregate_keys.py`
  moves to `tests/unit/schema/`); S1 (one planted old-vs-themes case per new theme). Under the
  floor: F3 (the S3 logger rename silences an old logging configuration: stage 7's CHANGELOG says
  so, D-15 (8)), F4 (`Iris.resource_name` is stricter than the old function, as designed).
- **D-17 Stage 3 checker: pass** (lead; 5 findings, none Critical). W1: stage 3's commits hold the
  move and the import rewrite together (the recipe's commits A and B); rename detection holds
  (R086–R100) and `git log --follow` reaches each file's history, so it is recorded, not split;
  from stage 4 a shim at an old path is committed apart from its move. W2 (no test ties
  `themes-layered`/`themes-ordered` to `TURNED_ON`): done in stage 4, where the next themes join
  those contracts. S1 (a scenario-map row) and S2 (this file's order line) fixed here. Under the
  floor: S3 (`tests/unit/schema/test_schema.py` was recreated, not renamed, so its history starts
  here).
- **D-18 Stage 4 as built** (builder of 4.1 and 4.2, accepted by the lead; built in parallel from
  stage 3's build and combined on `develop` after #175). (1) TC-07's TypeScript: with
  `persistence` and `migrations` served from their own schemas, the merged `rp_service.ts` holds
  the same declarations in the order of `SERVED_SCHEMAS`; no rule over the served schemas gives
  the old single file's interleaved order, so PD-10's "the order today's `rp_service.yaml` gives"
  cannot hold once a theme has its own file. The golden is refreshed deliberately (`make
  refresh-served-golden`) after proving the sorted lines identical; `/openapi.json` stays
  byte-identical; later stages do the same, order-only, proven the same way. (2) `migrations/services`
  is served (PD-10's list amended): `Migration` and `MigrationStep` are in the served TypeScript.
  (3) `components.py` also leaves out a class an earlier served schema generates (the migrations
  schema pulls in the metamodel through `rp_annotations`), tested. (4) `LimitSettings` is a
  non-served target. (5) The 400 log line is a constant message ("A SPARQL Protocol store refused a
  request with 400"); `BAD_QUERY_MESSAGE`/`UNREADABLE` are gone from `fuseki.py`. (6) The
  `model_copy` guard scans the themes' layers. (7) Fixtures shared by persistence and api tests move
  to `tests/unit/conftest.py`. (8) A created `LAYOUT` row stands at its new path. (9) `fuseki.py`'s
  history is cut: half of it moved to `sparql_protocol.py`, so git sees no rename; the shim at the
  old path is its own commit. (10) TC-45 is probed with `persistence` → `migrations` (`access` is
  not a theme until stage 5). (11) Short-form paths in the architecture docs are owed to task 7.2.
  (12) Combining on `develop`: the D-16 tests derived from `TURNED_ON` found `persistence` and
  `migrations` missing from the old-layout contract's sources — fixed in the integration pass, with
  the D-17 W2 test that ties `themes-layered`/`themes-ordered` to `TURNED_ON`. (13) Lesson for the
  run: `gh pr merge --delete-branch` run while the PR's branch is checked out in `.worktrees/lead`
  removed that worktree; the lead detaches from the branch before merging.
- **D-19 Stage 4 review and tester, accepted** (lead; review 7 findings, tester 190 tests, 7
  failed first, 5 findings; one fixer pass). Re-labelled Critical, with the reason: tester F1 (a
  class declared, not imported, by two served schemas is left out of both by `render`, so it
  vanishes from `/openapi.json` and its `$ref`s dangle; PD-10's error matrix says a name in two
  files is an error, and the guard never fires): `render` leaves out only a class another served
  schema imports or generates earlier, and a class declared by two served schemas is a
  `DuplicateComponentError` naming both. Accepted below Critical: F4 (a served schema listed before
  the one it imports silently loses that one's classes: an error naming both); F2 = review S1
  (`SparqlProtocolStore` requires `db_system_name` when a store is instantiated, so an abstract
  subclass in between may omit it; stage 4's checker W-1 corrected this wording); F3 (the `adapters.fuseki`
  shim keeps `BAD_QUERY_MESSAGE` and `UNREADABLE` as PD-8's "the module's other names", with their
  old values; D-18 (5) is amended); review W1 (TC-45 as a planted test: `persistence` →
  `migrations`); W2, W3 (the architecture page, `generation.adoc` and `howto/adopt.adoc` state where
  persistence and migrations live, the four served schemas and the groups' classes); S2 (TC-40
  checks the Turtle body). Under the floor: review S3 (a commit's trace line), S4 (stage 7's
  CHANGELOG names the dropped log constant change, D-18 (5)), tester F5 (the 400 log line, as
  PD-7 intends). Stage 4's checker: pass (3 findings); W-1 corrected the F2 wording above; under
  the floor S-1 (TC-45's test checks the contract broke, not that both modules are named), S-2
  (the move commit adds the shim test before the shim's own commit).
- **D-20 Stage 5 (`access`, `tenancy`) as built** (builder of 5.1, accepted by the lead; built on an
  older base and combined onto stage 4 by an integration fixer). (1) No shim (PD-8 names only
  `domain.base` and `adapters.fuseki`). (2) Schemas: `rp_access_services.yaml` and
  `rp_tenancy_services.yaml` served; `rp_access_settings.yaml` not served (D-15 (1));
  `rp_access_adapters.yaml` is the former wire schema renamed (its `id`, `name`, `description`
  and `python_package` changed; the generated module for the Zitadel records and `JwtClaims` is
  byte-identical, TC-50); the persistence half of the wire schema went to
  `rp_persistence_adapters.yaml` in stage 4. `SERVED_SCHEMAS`: iris, persistence, migrations,
  access, tenancy, service. (3) Tests by PD-11: `test_session_find` to access,
  `test_session_activity` to tenancy; `test_http` stays in `tests/unit/core/` (it tests
  `core/adapters/_http.py`), its verifier-timeout case split to `tests/unit/access/test_jwks.py`
  and its store half dropped as already asserted by TC-28 in `test_fuseki_store.py`.
  (4) `domain-never-imports-technical-models` keeps a forbidden entry for the gone
  `rdf_persistence.adapters.generated` (scratch tests need it); stage 7 removes the contract.
  (5) The ast-grep single-name rule dropped a second imported name in five files (D-12 (8) again),
  repaired. (6) Combining: the D-16 derived test found `access`/`tenancy` missing from
  `themes-never-import-the-old-layout`'s sources — added; `make generate` changed three manifests
  only (stage 4's `components.py` fix postdates stage 5's base); the TypeScript golden refresh is
  order-only, sorted lines identical to stage 4's. (7) As D-17 W1: the move and the import rewrite
  are one commit; rename detection holds.
- **D-21 Stage 5 review and tester** (lead; review 6 findings, none Critical; tester 183 tests, 0
  failed first, 0 findings). Accepted below Critical, one fixer pass: review W1 (TC-51 and the
  "a service imports an adapter" scenario planted on the theme layout in
  `test_theme_contracts.py`; the scenario-map rows of those scenarios point at the new tests, as the
  old-layout ones go with stage 7); W2 (`architecture/index.adoc` ~159, ~189 name
  `tenancy/services/migration_runner.py` and `access/services/access.py`); W3 (`testkit/zitadel.py`'s
  docstring names `access.adapters.generated.rp_access_adapters`, and TC-04's scan also covers
  moved generated modules such as `rdf_persistence.adapters.generated.rp_wire`); S2 (one
  old-vs-themes case for `access`); S3 (TC-45's original probe `persistence.services` →
  `access.services`). The tester's tests are not kept: none failed first, and three read the base
  commit with `git show`, which fails in a shallow clone; the rows they cover are tested elsewhere.
  The W3 scan found `tests/feature/test_technical_models.py`, which plants the old layout in a
  scratch copy on purpose; it joins `test_technical_split.py` in TC-04's `EXEMPT`, and stage 7
  removes both entries with the old layout.
- **D-22 Stage 6 (`events`, `collaboration`, `messaging`) as built** (builder of 6.1, accepted by
  the lead; built on an older base and combined onto stage 5 by an integration fixer). (1) No shim.
  (2) Schemas: `rp_events_services.yaml` (`EventEnvelope`) and `rp_collaboration_services.yaml`
  (`Referrer`, `ReferrerList`, `MemberList`) served; `rp_events_settings.yaml` (`EventSettings`)
  not served (D-15 (1)). `SERVED_SCHEMAS`: iris, persistence, migrations, access, tenancy, events,
  collaboration, service. (3) `nothing-in-services-imports-the-bus` removed (PD-6; the theme order
  puts `messaging` above every theme); `collaboration-layers` and `event-bus-libraries-in-one-module`
  retargeted. (4) TC-60 and TC-61 are planted tests in `test_theme_contracts.py`, merged with the
  earlier stages' tests on one `_lint` helper; the builder's own "themes are in the order" test is
  dropped, covered by D-17 W2's derived test. (5) Tests left in `tests/unit/services/` that test
  several themes (`test_service_model`, `test_settings_model*`, `test_relayed_since`) move with
  stage 7. (6) Combining: `events`, `collaboration`, `messaging` added to
  `themes-never-import-the-old-layout`'s sources; `make generate` changed three manifests only; the
  TypeScript golden refresh is order-only, sorted lines identical to stage 5's. (7) As D-17 W1: the
  move, the rewrite and the schema split are one commit; rename detection holds (R093–R100).
- **D-23 Stage 6 review and tester, accepted** (lead; review 6 findings, tester 158 tests, 1 failed
  first, 1 finding; one fixer pass). Re-labelled Critical, with the reason: review W1 (removing
  `nothing-in-services-imports-the-bus` relied on the theme order, which does not reach the four
  `api` services modules the contract named — `aggregates`, `components`, `documents`,
  `file_removal` — since `api` sits above `messaging`: a narrowed gate). A narrow forbidden contract
  keeps them off the bus: sources `rdf_persistence.services.{aggregates,components,documents,file_removal}`
  (stage 7 moves them to `rdf_persistence.api.services`), forbidden `rdf_persistence.messaging`, with
  a planted test; D-22 (3) is amended by this line. Accepted below Critical: W2 (the docs name the
  `events` and `collaboration` themes, their schemas and classes, and eight served schemas in
  `SERVED_SCHEMAS` order: `architecture/generation.adoc` ~318–319, `architecture/index.adoc`
  ~314–324 and ~360–369, `develop/index.adoc` ~28, `howto/adopt.adoc` ~294–297); W3
  (`tests/unit/services/test_relayed_since.py` moves to `tests/unit/tenancy/`, the highest theme
  it uses; D-22 (5) is amended); S1 (a same-rank planted test: `events` → `collaboration` breaks
  `themes-ordered`); S2 (TC-60's map row at scenario level); tester F1 (the
  `event-bus-libraries-in-one-module` title says the Redis adapter may import `faststream` or
  `redis`, but only `faststream` is exempt: the title is reworded to what the contract enforces,
  rather than widening the exemption). Under the floor: S3 (recorded in D-22 (7)). The tester's
  tests are not kept: none failed first on production code but F1's, which the reworded title
  resolves. The checker found PD-6 and task 7.1 silent on the new contract: both now name it
  (17 contracts at the end, PD-6). Under the floor: the stage's unplanted control does not lint the
  new contract (its four planted tests do); the stage changelog items go to `evidence/docs-owed.md`.
- **D-24 Stage 7 (`api`, the end of the old layers) as built** (builder of 7.1 and 7.2, accepted
  by the lead; 7.1 built on an older base and combined onto stage 6 by an integration fixer). (1)
  The five temporary contracts (`themes-never-import-the-old-layout`, the four `old-vs-themes`)
  and their own planted tests removed; the D-16 derived test of `domain-never-imports-technical-models`
  retargeted to `domain-of-a-theme-imports-no-upper-layer`. (2) `api-services-never-import-the-bus`
  retargeted to `api.services` (D-23); its planted tests re-pointed. (3) The served schema of the
  service is `model/technical/api/rp_api_entrypoints.yaml`; `rp_service.ts` keeps its name
  (`SERVICE_MODULE`). (4) TC-04's `EXEMPT`: `tests/feature/test_technical_models.py` removed (D-21);
  `tests/unit/test_technical_split.py` kept, as its probe that an old path raises
  `ModuleNotFoundError` names `rdf_persistence.domain.generated`. (5) The CHANGELOG lists the
  logger names under Changed (BREAKING), not Deprecated as task 7.2 says: the old names stop at
  once, with no warning. (6) The 15 tests 7.1 added without a map row are mapped.
- **D-25 Stage 7 full review and tester** (lead; L1, L2, L3 apart, L4+L5 one pass, D-7; 34
  findings, none Critical as reported; tester 57 tests, 3 failed, 2 findings). Re-labelled
  Critical: L2 W1 (`domain-pure` lost `rdf_persistence.domain` as a source while the shim lives:
  a narrowed gate; restored until stage 8). Accepted below Critical, one fixer pass: PD-6's count
  (17, above) and the four `layers-across-themes` labels `(1/4)`–`(4/4)`, the `:84` name, the
  `:100` comment; spec deltas for `rp-developer-checks` (theme folders in `make test-changed`) and
  `rp-generation` (the service's TypeScript types from the served schemas, `rp_api_entrypoints.yaml`;
  the schema file name `rp_<theme>_<layer>.yaml`, or `rp_<theme>_<group>.yaml` for a non-served
  group, D-15 (1), in the delta and the pages that repeat it); `make test-changed` runs a shim's own
  tests; the stale test-file paths the tester found (four places) and its guard test kept; the dead
  scratch line in `test_theme_contracts.py`; `SERVICE_SETTINGS` in `test_technical_models.py` names a
  module holding `ServiceSettings`; the stale boundary-test name; `typescript.py`'s message built
  from `SERVICE_MODULE`; planted tests for "a domain module imports a service of another theme" and
  "two themes of one rank" mapped at scenario level. Under the floor, for stage 8 or later: one
  shared `_lint` helper; the names `LAYERS`, `SHIM_FOLDERS` (twice), `_ENTRYPOINTS`,
  `_SERVICE_MODELS`, `SERVICE_SCHEMA`; the bus contract on the whole `api.services` package; PD-4's
  folder check requiring a theme before the layer (the tester's probe); the shims' warnings naming
  a version (PD-8; named when the release is cut). The tester's other tests are not kept: none
  failed first on production code.
