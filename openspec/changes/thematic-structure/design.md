> Derives from: EPIC `thematic-structure` ([proposal.md](proposal.md)), capabilities
> `rp-package-boundaries` and `rp-generation`. Seeds: [inputs/seed.md](inputs/seed.md).
> Type: Implementation (a staged move).

## Context

On `docs/manual-revision-notes` (48f80c6) the library has four layer packages and four generation
targets (`pyproject.toml:91-118`). After the four earlier changes (ASM-1 to ASM-3 of the EPIC) it
will have the metamodel in `domain/generated/`; the technical groups in the `generated/` folder of
the lowest layer that uses them (`technical-models` DEC-1): `services/generated/{service,settings,templates}/`,
`services/generated/telemetry/` (`otel-observability` PD-1), `adapters/generated/` (`wire`) and
`testkit/generated/` (`testkit`, its PD-11); `domain/layout.py` and `services/iris.py` split from
`domain/iris.py`, and `services/tenant_move.py` (`technical-models` DEC-3); and the generator in
`rdf_persistence_generation/`. So every technical model already sits in the layer DEC-3 asks for,
and this change adds the theme. This PLAN starts from that state; stage 1's task 1.1 checks it.

What the brief asked to check against the code:

| Claim | Found | In this PLAN |
|---|---|---|
| The theme graph is acyclic (analysis §5.3) | Holds for the hand-written modules (grimp, 2026-11-17). Order: core; iris, schema, files; provenance; persistence; migrations, access; tenancy; collaboration, events; messaging; api | DEC-1, PD-1, PD-6 |
| The generated code can mirror the themes | Holds for `rp_service` and `rp_wire` (every class has one lowest-user theme, table PD-2); fails for the metamodel (cycles) | DEC-2, PD-2 |
| The consumer imports 5 modules | 3 by hand; the `domain.base` lines are its generated files; the `adapters.fuseki` line is a test string | DEC-5, PD-8 |
| The 141-name re-export | Holds | PD-8, TC-03 |
| The iris wrappers only delegate | 11 of 23 do | DEC-8, PD-5 |
| `FusekiStore` is half generic | Holds: `query`, `update`, `put_graph`, `_raise_for_status`, `_read_result` are SPARQL 1.1 Protocol; the endpoint layout (`_dataset_path`), `create_dataset`, `drop_dataset`, `list_datasets` and dataset-level `export_quads`/`import_quads` are Fuseki's (`fuseki.py:25-160`) | DEC-7, PD-7 |
| Contracts exist to carry over | `.importlinter`: 10 contracts. import-linter 2.11 has `containers`, `exhaustive` and wildcard module expressions in `forbidden` and `layers` | DEC-6, PD-6 |

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
  | core | `base`, `exceptions`, `media`, `sparql`; metamodel `generated/` | `artifacts`, `yaml_files`, `telemetry`† | `_http` | |
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
  | api | | `aggregates`, `documents`, `file_removal`, `components` | | `auth`, `environment`†, `kit`, `negotiation`, `openapi`, `problems`, `responses`, `router`, `service`, `sse` |

  † A module an earlier change creates or moves: `services/jsonld.py` (`manual-revision-notes`,
  the one JSON-LD path; its users are `loading`, persistence, and `documents`, api);
  `domain/layout.py`, `services/iris.py`, `services/tenant_move.py` (`technical-models` DEC-3, the
  `iris.py` split) and `entrypoints/environment.py` (`technical-models` PD-12, `settings_from_env`);
  `services/telemetry.py` (`otel-observability` PD-3; every theme logs through it). Task 1.1
  re-reads the tree on `develop` and adds any other module those changes created.

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
  agrees with its `[[tool.rp-generate]]` entry is `generator-package` PD-6 (b)'s hard check, which
  already covers the technical groups; this change adds no check of its own, and each new per-theme
  schema carries the annotation that check asks for. A consumer's run uses the same map, so a
  consumer's technical target can import its own domain target.
- **PD-4 Kind and folder (DEC-3).** A new hard-check function `kind_folder_problems(target)` in
  `rdf_persistence_generation/checks/boundary.py`, beside `technical-models`' `target_kind_problems`
  (which checks the modules' `module_kind`; this one checks the folder): in the target's `package`,
  the segment before `generated` is `domain` for a `domain` target, and `services`, `adapters` or
  `entrypoints` for a `technical` one (a group segment after `generated` is allowed, so the old
  layout's `rdf_persistence.services.generated.service` passes during the move). Packages outside
  the themes are exempt: `rdf_persistence.testkit` (the `testkit` group; No-go: the testkit is
  outside the themes) and `rdf_persistence_generation` (the generator's own target). It runs **on
  the toolkit's own run only**, like `generator-package` PD-6 (b): a consumer that already declares
  `kind` (allowed since `technical-models` DEC-4) keeps its own folder layout, so the upgrade breaks
  no consumer. It is built, tested and **wired into `steps.py` in stage 1**: `technical-models`
  already put every toolkit technical target in a layer's `generated/` folder, so the toolkit's own
  targets pass it from the start and it guards every stage of the move.

  **The model guard** (`testkit/guards.py`, rp-generation "a hand-written domain class") keeps its
  consumer-facing default `SCANNED_LAYERS` and its scope (every layer it scans today, not only
  `domain`). Three things change with the move: (a) `FORBIDDEN_BASES` gains
  `rdf_persistence.core.domain.base.RpModel` in stage 2, because `_top_level_exports` resolves a
  consumer's `from rdf_persistence import RpModel` to the defining module, and without the new name
  the guard stops seeing any class derived from `RpModel`, silently (TC-24); the old name stays
  until stage 8 (the shim's users). (b) `DEFAULT_ALLOW` names `rdf_persistence/core/domain/base.py:RpModel`.
  (c) The toolkit's own guard test (`test_model_guard.py`) scans each moved theme as a whole
  (`layers=(*moved_themes, *old_layers_left, "generation", "testkit")`), and its `HAND_WRITTEN`
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
  - `layers-across-themes` (forbidden, three contracts): `rdf_persistence.*.domain` imports no
    `rdf_persistence.*.{services,adapters,entrypoints}`; `rdf_persistence.*.services` imports no
    `rdf_persistence.*.{adapters,entrypoints}`; `rdf_persistence.*.adapters` and
    `rdf_persistence.*.entrypoints` import neither the other.
  - `domain-pure`, `runtime-without-extras`, `works-without-the-generate-extra`,
    `event-bus-libraries-in-one-module`, `collaboration-layers`, `session-and-provenance-without-mapper`,
    `tenancy-without-the-runner`, `library-never-imports-the-generator` (generator-package): same
    meaning, sources by wildcard or new path.
  - Gone: `layers` (replaced by the three above), `nothing-in-services-imports-the-bus` and
    `migrations-below-the-runner` (implied by `themes-ordered`), `technical-models`'
    `domain-never-imports-technical-models` (implied by `layers-across-themes`: every technical
    package sits in a `services`, `adapters` or `entrypoints` layer, which no `*.domain` imports).

  During stages 2 to 6 the old `layers` contract and the new ones run side by side; a stage adds its
  themes to `containers` and `themes-ordered` (a theme not yet moved is absent, not empty).
- **PD-7 The store split (DEC-7).** `persistence/adapters/sparql_protocol.py`:
  `SparqlProtocolStore(HttpAdapter)` with `query`, `update`, `put_graph`, `_send`,
  `_raise_for_status`, `_read_result`, and abstract `query_path(dataset)`, `update_path(dataset)`,
  `graph_store_path(dataset)`, `create_dataset`, `drop_dataset`, `list_datasets`, `export_quads`,
  `import_quads`. `_raise_for_status` and `_read_result` are module functions today
  (`fuseki.py:46`, `:62`); they become methods so the messages (`BAD_QUERY_MESSAGE`, `UNREADABLE`,
  "answered {status}") say `self.service`, not "Fuseki". The 400 debug line then logs under
  `rdf_persistence.persistence.adapters.sparql_protocol`, and the `caplog` logger string in
  `test_fuseki_store.py:237` changes with it. The SPARQL protocol media
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
  that differs is a failure, not a new golden) (`manifest.py:89` and
  `extensions/typescript.py:183` read `SERVICE_SCHEMA` today). `vocabulary.TOTAL` reads `total`
  from the schema that declares it (`persistence/services`, with `Page`), and
  `vocabulary.IRI_POLICY` reads `iri_policy` from `iris/services` (with `ServiceSettings`); both
  are file reads of schemas of the same or a lower theme than their users.
- **PD-11 Tests follow (DEC-9).** `tests/unit/{domain,services,adapters,entrypoints}/test_*.py` move
  by the module they test to `tests/unit/<theme>/`. A test of several themes goes to the highest.
  Helpers (`builders.py`, `scene.py`, `conftest.py`) go where their users are; one used by two
  themes goes to `tests/unit/` root. `tests/changed.py`: `LAYERS` becomes `THEMES` plus `generation`
  and `testkit`, and `rdf_persistence/<theme>/...` maps to `tests/unit/<theme>/`; a change in `core`
  runs `make test-fast` (it replaces today's rule for `domain`).
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
