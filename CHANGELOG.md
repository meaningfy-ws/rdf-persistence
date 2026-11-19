# Changelog

All notable changes to **RDF Persistence** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- **BREAKING: a target's kind is derived from its modules, and its package must sit in a folder that
  kind allows** (`target-kind-from-the-model`). A target is `technical` when every module it
  generates is annotated `module_kind: technical`, and `domain` otherwise. The `kind` key of
  `[[tool.rp-generate]]` is gone, and an entry that still has it is refused as an unknown key. Rule
  `TARGET_KIND` now applies to every target, a consumer's included: the package has `domain` (a
  domain target) or `services`, `adapters` or `entrypoints` (a technical one) before `generated`,
  and a target that generates technical modules beside others fails, naming them. The toolkit's own
  theme check stays for its own targets. The toy library and the getting-started example moved to
  `domain/generated/`.
  - Migrate in three steps. (1) Package: change each `package` to
    `<your package>.<layer>.generated`, for example `app.generated` to `app.domain.generated`, and
    move the generated folder (`python`, `diagrams`) to match. (2) The `kind` key: delete it from
    every entry. (3) A technical module: annotate it `module_kind: technical` and put it in a target
    of its own whose package is in `services`, `adapters` or `entrypoints`; a technical module left
    unannotated is derived as `domain`, and the error says to annotate it. Then run `rp-generate`.

- **BREAKING: the domain model is generated per theme** (`domain-model-per-theme`). Each theme that
  owns domain concepts has its own `<theme>.domain.generated` package, and seven modules moved out
  of `rdf_persistence.core.domain.generated`:
  - `rp_access`, `rp_tenancy`: `rdf_persistence.core.domain.generated.<module>` →
    `rdf_persistence.access.domain.generated.<module>`
  - `rp_provenance` → `rdf_persistence.provenance.domain.generated.rp_provenance`
  - `rp_files` → `rdf_persistence.files.domain.generated.rp_files`
  - `rp_collections`, `rp_discussion`, `rp_workflow`:
    `rdf_persistence.core.domain.generated.<module>` →
    `rdf_persistence.collaboration.domain.generated.<module>`

  `rdf_persistence.core.domain.generated` keeps `rp_core` and `rp_annotations`;
  `rdf_persistence.core.domain.generated.rp`, the module that re-exported every class, is gone. The
  names exported from `rdf_persistence` are the same objects (148): only a deep import of a moved
  path breaks, with `ModuleNotFoundError`, and no old path keeps a re-export shim. The combined
  `shapes.ttl`, `context.jsonld` and frames stay in `core/domain/generated/` and are the ones to
  load; the new theme targets write partial copies beside their classes, which are not loaded.
  `rp_tenancy` generates in `access`, and `themes-ordered` ranks `files` above `provenance`. A
  consumer's generated code does not change; run `rp-generate` once and rewrite any deep import of
  a moved path.
- **A module beside the root that names another package is imported from it**
  (`domain-model-per-theme`). The generator imports a module in the root's folder from its own
  `python_package` when that differs from the root's, and on the toolkit's run checks that a toolkit
  target generates that package.

## [0.6.0] - 2026-11-19

### Added
- **Imports between generation targets** (`thematic-structure`): a schema that imports a module of
  another target, where that module declares `python_package`, imports its classes from
  `<python_package>.<module>` and does not generate them again; the manifest lists the imported
  YAML as an input. A module without `python_package` is generated as before.
- **A toolkit target's folder follows its kind** (`thematic-structure`): in the toolkit's own run,
  rule `TARGET_KIND` also refuses a target whose `package` does not have `domain` (for a `domain`
  target) or `services`, `adapters` or `entrypoints` (for a `technical` one) before `generated`,
  and a theme of the library (`rdf_persistence.<theme>.<layer>.generated`) before that layer.
  `rdf_persistence.testkit` and `rdf_persistence_generation` are exempt. A consumer's run is not
  checked.

### Changed
- **The library is organised in thirteen themes** (`thematic-structure`). Every module moved from
  `rdf_persistence/{domain,services,adapters,entrypoints}/` to
  `rdf_persistence/<theme>/<layer>/`: `core`, `iris`, `schema`, `files`, `provenance`,
  `persistence`, `migrations`, `access`, `tenancy`, `events`, `collaboration`, `messaging` and
  `api` (the map: `docs/modules/ROOT/pages/architecture/index.adoc`, "Where a module lives"). The names of `rdf_persistence`
  are the same objects (148 once `mint_aggregate_iri` is removed, see Removed); only a deep import
  of an old module path breaks, with `ModuleNotFoundError`, and no old path keeps a shim:
  `rdf_persistence.services.session`, `rdf_persistence.services.messagebus`,
  `rdf_persistence.services.{events,event_hub,event_stream,relay}`,
  `rdf_persistence.services.{collaboration,discussion,reference_collections,transitions,workflows,write_guards}`,
  `rdf_persistence.adapters.redis_events` or `rdf_persistence.entrypoints.kit` are gone. The
  metamodel's generated package moved from `rdf_persistence.domain.generated` to
  `rdf_persistence.core.domain.generated`.
- **The technical schemas are split by theme** (`thematic-structure`). `model/technical/{service,
  settings,telemetry,templates,wire}/` are now `model/technical/<theme>/rp_<theme>_<layer>.yaml`
  (`rp_<theme>_settings.yaml` or `rp_<theme>_templates.yaml` for a non-served group), each generated
  into `rdf_persistence/<theme>/<layer>/generated/` (a group into `generated/settings/` or
  `generated/templates/`; `testkit` is unchanged). The
  top-level names are unchanged; a deep import moves:
  - from `rdf_persistence.services.generated.service.rp_service`: `ServiceSettings`, `IriPolicy`,
    `IdSpec`, `IdKind` to `rdf_persistence.iris.services.generated.rp_iris_services`; `Page`,
    `Filter`, `ListRequest`, `Condition`, `ListPlan`, `AggregateHead` to
    `rdf_persistence.persistence.services.generated.rp_persistence_services`; `Migration`,
    `MigrationStep` to `rdf_persistence.migrations.services.generated.rp_migrations_services`;
    `VerifiedCaller`, `GrantSet`, `CallerAccess`, `AccountSummary` to
    `rdf_persistence.access.services.generated.rp_access_services`; `TenantDump`, `TenantSummary`
    to `rdf_persistence.tenancy.services.generated.rp_tenancy_services`; `EventEnvelope` to
    `rdf_persistence.events.services.generated.rp_events_services`; `Referrer`, `ReferrerList`,
    `MemberList` to `rdf_persistence.collaboration.services.generated.rp_collaboration_services`;
    `TenantCreate`, `LabelUpdate`, `Authorised`, `Problem`, `ProblemKind`, `ProblemSlug` to
    `rdf_persistence.api.entrypoints.generated.rp_api_entrypoints`;
  - from `rdf_persistence.services.generated.settings.rp_settings`: `HttpSettings` to
    `rdf_persistence.core.services.generated.rp_core_services`; `LimitSettings` to
    `rdf_persistence.persistence.services.generated.settings.rp_persistence_settings`;
    `JwksSettings` and `DirectorySettings` to
    `rdf_persistence.access.services.generated.settings.rp_access_settings`; `EventSettings` to
    `rdf_persistence.events.services.generated.settings.rp_events_settings`; `SseSettings` and
    `ToolkitSettings` to `rdf_persistence.api.entrypoints.generated.settings.rp_api_settings`;
  - `LogContext`, from `rdf_persistence.services.generated.telemetry.rp_telemetry`, to
    `rdf_persistence.core.services.generated.rp_core_services`; the SPARQL term bundles, from
    `rdf_persistence.services.generated.templates.rp_templates`, to
    `rdf_persistence.schema.services.generated.templates.rp_schema_templates`, and
    `IriTemplateVariables`, `IriParts` to
    `rdf_persistence.iris.services.generated.templates.rp_iris_templates`;
  - from `rdf_persistence.adapters.generated.rp_wire`: the `Zitadel*` records, `JwtClaims`,
    `DiscoveryDocument` and `BadRequestMeans` to
    `rdf_persistence.access.adapters.generated.rp_access_adapters`; `FusekiDatasetList` and
    `FusekiDataset` to `rdf_persistence.persistence.adapters.generated.rp_persistence_adapters`.
- **The served types come from eight schemas** (`thematic-structure`). `/openapi.json` is
  unchanged. `rp_service.ts`, which every consumer's TypeScript output carries, holds the same
  declarations in a new order: that of the served schemas (`iris`, `persistence`, `migrations`,
  `access`, `tenancy`, `events`, `collaboration`, `api`).
- **A consumer's generated code imports `RpModel` from `rdf_persistence`** (`thematic-structure`),
  where it named `rdf_persistence.domain.base`. Its freshness check fails once after the upgrade:
  run your regenerate command.
- **`FusekiStore` is built on `SparqlProtocolStore`** (`thematic-structure`), a base in
  `rdf_persistence.persistence.adapters.sparql_protocol` that holds the SPARQL 1.1 Protocol;
  neither is a new public name, and `FusekiStore` behaves and is built as before. Its error
  messages name its `service` ("Fuseki"), so they read as before.
- **BREAKING for log readers: logger names follow the new module paths** (`thematic-structure`).
  Each module logs under `__name__`, so a configuration on an old name no longer matches; one on
  `rdf_persistence` still does. Old → new:
  `rdf_persistence.adapters.fuseki` → `rdf_persistence.persistence.adapters.sparql_protocol`;
  `adapters.redis_events` → `events.adapters.redis_events`; `adapters.s3` → `files.adapters.s3`;
  `adapters.zitadel` → `access.adapters.zitadel`; `entrypoints.kit` → `api.entrypoints.kit`;
  `entrypoints.problems` → `api.entrypoints.problems`; `services.file_removal` →
  `api.services.file_removal`; `services.iri_policy_guard` → `tenancy.services.iri_policy_guard`;
  `services.messagebus` → `messaging.services.messagebus`; `services.migration_runner` →
  `tenancy.services.migration_runner`; `services.relay` → `events.services.relay`;
  `services.session` → `persistence.services.session`; `services.sweep` →
  `tenancy.services.sweep`; `services.tenancy` → `tenancy.services.tenancy`;
  `services.tenant_dump` → `tenancy.services.tenant_dump`; `services.tenant_sweep` →
  `tenancy.services.tenant_sweep` (each under `rdf_persistence.`).
- **The store's 400 log line** (`thematic-structure`): "Fuseki refused a request with 400" is now
  "A SPARQL Protocol store refused a request with 400", under the logger
  `rdf_persistence.persistence.adapters.sparql_protocol`. `BAD_QUERY_MESSAGE` and `UNREADABLE` are
  no longer in the new module, and no old module keeps them (see Removed).
- **`error.type` names the new module** (`thematic-structure`): the attribute is the exception's
  module and class, so `rdf_persistence.domain.exceptions.Conflict` is now
  `rdf_persistence.core.domain.exceptions.Conflict`, and so for every toolkit exception. A
  dashboard or alert that matches the old value must change.
- **The documentation is restructured** (#180, #182) into a tutorial, a user manual, guides and
  the specification; `howto/adopt.adoc` is split into `user-manual/*` pages (its old address
  redirects), and `make check-docs` resolves every `xref` and its anchor.
- **`rp-generate --help` names the real configuration keys** (#182), and the description of
  `max_document_nodes` says what it limits. The tests' example IRI policy is generic.

### Removed
- **BREAKING: the four generator testkit shims** (`generator-package`, #165). The modules
  `rdf_persistence.testkit.{freshness,conformance,roundtrip,strategies}` are gone, and so are the
  names `Conformance`, `conformance_problems`, `round_trip` and `aggregate` of
  `rdf_persistence.testkit`: an import of an old path fails with `ModuleNotFoundError`. Use
  `rdf_persistence_generation.testkit.*` (`pytest_plugins =
  ["rdf_persistence_generation.testkit.freshness"]`). `assert_isomorphic` stays in
  `rdf_persistence.testkit.graphs`. The contract `library-never-imports-the-generator` now has no
  ignored edge.
- **BREAKING: `rdf_persistence.domain.base`, `rdf_persistence.adapters.fuseki` and
  `mint_aggregate_iri`** (`thematic-structure`). No release ever shipped them as deprecated: they
  are removed in the release that ships the move, with no deprecation period.
  - `rdf_persistence.domain.base` is gone (`ModuleNotFoundError`), and with it the `domain/` and
    `adapters/` folders at the top of the package. `RpModel` is the same class: import it with
    `from rdf_persistence import RpModel` (it is defined in `rdf_persistence.core.domain.base`). A
    consumer's old generated code that names `rdf_persistence.domain.base` fails at import: run
    your regenerate command. The model guard still names a class derived from the old path.
  - `rdf_persistence.adapters.fuseki` is gone: import `FusekiStore` from `rdf_persistence`, or from
    `rdf_persistence.persistence.adapters.fuseki`. The module's other names are not re-exported:
    the SPARQL Protocol constants (`SPARQL_QUERY`, `SPARQL_UPDATE`, `RESULTS_JSON`, `GRAPH_PARAM`)
    are in `rdf_persistence.persistence.adapters.sparql_protocol`; `BAD_QUERY_MESSAGE` and
    `UNREADABLE` have no module that holds them any more.
  - `mint_aggregate_iri` is removed with its top-level export, so `rdf_persistence.__all__` holds
    148 names. Call `Iris.mint_aggregate` on the service's `Iris`
    (`DEFAULT_IRIS.mint_aggregate(tenant, cls_type="", rp_path=path)` mints the same IRI).
- **The eleven IRI wrappers that only called `DEFAULT_IRIS`** (`thematic-structure`), from
  `rdf_persistence.services.iris` (none was a top-level name): `mint_tenant_iri`, `tenant_iri`,
  `aggregate_iri`, `is_aggregate_iri`, `is_aggregate_graph_iri`, `is_loaded_graph_of`,
  `mint_part_iri`, `loaded_graph_iri`, `tenant_resource_name`, `principal_iri` and the helper
  `_default_iris`. Call the `Iris` of the service instead (`mint_tenant`, `tenant`, `aggregate`,
  `is_aggregate`, `is_aggregate_graph`, `is_loaded_graph`, `mint_part`, `mint_loaded_graph`,
  `resource_name`, `principal`). `Iris.resource_name` takes the tenant's IRI, not its id, and reads
  the id through the policy, so it is stricter than `tenant_resource_name(prefix, id)`; a bad tenant segment is refused by `ServiceSettings` (`ValidationError`), where a wrapper raised
  `InvalidIri`. The twelve layout functions that no policy changes stay, in
  `rdf_persistence.iris.domain.layout`.

### Fixed
- **The generator's guards are harder to fool** (#164): the check that library tests never load
  the generator reads every form of `pytest_plugins`, `__import__` and `importorskip`;
  `rp-generate --list-python-folders` works without `linkml` installed; the freshness report names
  a stale generator module once, with the targets it affects, instead of once per target.

## [0.5.0] - 2026-11-18

### Added
- **A generation target declares its `kind`** (`technical-models`): the optional `kind` key of a
  `[[tool.rp-generate]]` entry is `domain` or `technical`; `rp-generate` fails, naming the target
  and the module, when a technical target holds a module not annotated `module_kind: technical`,
  or a domain target holds one annotated `technical`. A target without `kind` generates as before.
- **The toolkit's deployment values are settings** (`technical-models`): `HttpSettings`,
  `JwksSettings`, `DirectorySettings`, `EventSettings`, `SseSettings` and `LimitSettings`, held
  together by `ToolkitSettings`, are generated from `model/technical/settings/rp_settings.yaml` into
  `rdf_persistence.services.generated.settings` and exported from `rdf_persistence`. Every value
  defaults to the one the toolkit used before, with bounds (a zero timeout, a shared-secret
  algorithm or a leeway outside 0 to 300 seconds is refused). Each adapter and service takes its
  group as a constructor argument; `ServiceKit` and `install_service` take `toolkit=` and hand each
  object it builds its group.
- **`settings_from_env`** reads any generated settings model, `ToolkitSettings` included, from
  environment variables (`RP_HTTP__READ_TIMEOUT_SECONDS=60`), validated once through the model. It
  needs the new `settings` extra (`rdf-persistence[settings]`, pydantic-settings); importing the
  toolkit reads no variable and loads no dotenv file.
- **Generation: `default_instance` and list defaults** (`technical-models`): a slot annotated
  `default_instance: 'true'` defaults to a fresh instance of its range class (checked by a hard
  rule: the range must be a class that can be built with no argument and be declared first); the
  `ifabsent: string(a, b, ...)` of a multivalued slot is generated as the list `['a', 'b']`, where
  the stock generator wrote the one string.
- **`fill_terms` and `fragment_terms`** (`rdf_persistence.domain.sparql`): they fill a query
  template from a bundle of `SparqlTerm` fields and render a fragment from one.
- **Generation: `field_name: slot`** (`technical-models`): a slot annotated `field_name: slot` (a
  `GenerationAnnotation`) is named after the slot in Python and in the JSON-LD context, and keeps its
  alias. Every other field keeps its name.
- **Generation: `python_import`** (`technical-models`): a LinkML type annotated `python_import`
  with a module name, together with `repr`, generates its field as the `repr` class imported from
  that module.
- **Four more RDF representations** (`manual-revision-notes`): a route that answers one aggregate
  also serves N-Triples, N-Quads, TriG and RDF/XML, chosen by `Accept`; a listing stays JSON and
  JSON-LD. RDF/XML is 406 for a predicate with no XML local name or a value XML 1.0 cannot hold,
  and on a create or replace that 406 comes before anything is written. The LinkML `RdfFormat`
  enum declares each serialisation's media type.
- **`If-Match` takes `*` and a list of tags** (`manual-revision-notes`, RFC 9110 §13.1.1).
- **The token verifier's algorithms and leeway are configurable** (`manual-revision-notes`):
  RS, PS and ES 256 to 512 and EdDSA by default, `none` and shared-secret algorithms always refused,
  with a leeway on `exp` and `nbf` (about 30 s by default); through `JwksSettings` since
  `technical-models`. Each key is bound to the token's algorithm, and only signature keys verify.
- **Tracing through the OpenTelemetry API** (`otel-observability`): spans around every store call,
  the commit, the migrations, both sweeps, the relay rounds and the message bus's handlers and
  observers. They are no-ops until the application installs a provider; a span records an
  exception's type, never its message. `opentelemetry-api>=1.44,<2` is a declared dependency.
  `RedisEventBus(middlewares=...)` lets the application add FastStream's broker telemetry. The
  how-to "See what the toolkit is doing" (`howto/observability.adoc`) shows the set-up.
- **One log context** (`otel-observability`): `LogContext`, generated from
  `model/technical/telemetry/rp_telemetry.yaml`, names every log attribute after the OpenTelemetry
  semantic conventions (`db.*`, `error.type`, `messaging.*`) plus an `rp.*` namespace.
- **The generator is its own top-level package** (`generator-package`): `rdf_persistence_generation`,
  shipped in the same wheel behind the `generate` extra. The library never imports it, and the
  generator has its own unit, feature, integration and end-to-end tests (`make test-generator`).
- **The metamodel says where its classes live** (`generator-package`): each toolkit schema module
  declares `python_package`, and `rp.yaml` its `public_package`; the generator reads them in place
  of two hard-coded constants and checks them with two hard rules.
- **Decision records** (`manual-revision-notes`): ADR-001 to ADR-005 (own SPARQL client, own JWKS
  cache, FastAPI rather than connexion, signing algorithms, representations), and a contract test
  of every operation against the served OpenAPI (schemathesis).

### Changed
- **A `SparqlTerm` model field refuses a raw `str`** (`technical-models`): a field of that type
  raises a `ValidationError` when built with a plain string, before any query text is made. Build
  the term with the `domain.sparql` factories.
- **`ZitadelUserState` is a generated enum** (`technical-models`): the six user states of a Zitadel
  answer. A user state outside the six makes the directory answer unreadable
  (`IdentityUnavailable`) where the adapter accepted any string before.
- **`[[tool.rp-generate]]` keys are unchanged** (`technical-models`): the keys of a target are read
  as before; `field_name: slot` (Added) is the only new way to name a field after its slot.
- **BREAKING for a deployment that sets such a value: the settings are bounded tighter**
  (`technical-models`). Every duration is at most one year (31,536,000 seconds; an infinite or
  larger value is refused), `unknown_kid_cooldown_seconds` is at least 1 second (it was 0.001),
  and `JwksTokenVerifier` refuses a cooldown longer than `ttl_seconds`. A deployment that keeps the
  defaults is not affected. `settings_from_env` no longer repeats the input value in a
  `ValidationError`.
- **BREAKING: the testkit's records moved to `rdf_persistence.testkit.generated`**
  (`technical-models`). `ClassShape`, `SlotShape`, `ContainerMarker`, `Violation`, `MachineUser`,
  `ZitadelProject`, `ZitadelServer`, `ExecResult`, `FusekiServer` and `GarageServer` are generated
  from `model/technical/testkit/rp_testkit.yaml` and are imported from
  `rdf_persistence.testkit.generated.rp_testkit`, no longer from
  `rdf_persistence.generation.generated.rp_generation`; there is no shim. A new `FieldFlags`
  record (`required`, `multivalued`) is what the model-shape test compares. `ConstraintCase`,
  `ConstraintKind` and `GenerationTarget` stay in `rp_generation`.
- **BREAKING: the per-value keywords and constants the settings replace are removed**
  (`technical-models`). A caller that passes an old keyword gets a `TypeError` from every constructor, except `bootstrap`,
  which takes dependencies by keyword: `bootstrap(limit=...)` raises `ValueError` ("no handler or
  observer names the dependency limit"), or binds to a handler that declares a `limit` dependency.
  One that imports an old constant gets an `ImportError`. Pass the group instead:
  - `JwksTokenVerifier(algorithms=, leeway_seconds=)` is now `jwks=JwksSettings(allowed_algorithms=,
    leeway_seconds=, ...)`;
  - `RedisEventBus(stream=, retention=, claim_idle=)` is now `events=EventSettings(stream=,
    retention_seconds=, claim_idle_seconds=, ...)`;
  - `Relay(interval=, publish_timeout=)` is now `events=` (`relay_interval_seconds`,
    `publish_timeout_seconds`), and `EventHub(max_queue=)` is `events=` (`hub_queue_size`);
  - `MessageBus(limit=)` and `bootstrap(limit=)` are now `limits=LimitSettings(max_messages=)`;
  - `Mapper(max_roots=)` and `UnitOfWork(max_roots=)` are now `limits=LimitSettings(max_roots=)`
    on the `Mapper`; `UnitOfWork` reads it from the mapper and takes no limit of its own;
  - `add_events_route(access_ttl=, keep_alive=, resume_window=, max_lifetime=)` is now
    `sse=SseSettings(access_ttl_seconds=, keep_alive_seconds=, resume_window_seconds=,
    max_lifetime_seconds=)`;
  - `FusekiStore`, `JwksTokenVerifier`, `ZitadelIdentity` and `S3FileStore` take `http=HttpSettings(...)`
    (connect and read timeouts, attempts), and `ZitadelIdentity` also `directory=DirectorySettings(page_size=)`;
  - `Documents` takes its node limit, and `tenant_dump.restore` its manifest cap, from
    `limits=LimitSettings(max_document_nodes=, max_manifest_bytes=)`;
  - removed constants: `CONNECT_TIMEOUT_SECONDS` and `READ_TIMEOUT_SECONDS` (`adapters/_http.py`,
    `adapters/s3.py`), `MAX_ATTEMPTS` (`adapters/s3.py`), `JWKS_TTL_SECONDS`,
    `UNKNOWN_KID_COOLDOWN_SECONDS`, `DEFAULT_ALGORITHMS`, `DEFAULT_LEEWAY_SECONDS` and
    `MAX_LEEWAY_SECONDS` (`adapters/jwks.py`), `POLLING_INTERVAL_MS` (`adapters/redis_events.py`),
    `PAGE_SIZE`, `ACTIVE_STATE` and `INACTIVE_STATE` (`adapters/zitadel.py`), `MAX_LIFETIME`,
    `ACCESS_TTL`, `KEEP_ALIVE_SECONDS` and `RESUME_WINDOW` (`entrypoints/sse.py`), `MAX_NODES`
    (`services/documents.py`), `DEFAULT_MAX_ROOTS` (`services/mapper.py`), `MAX_MANIFEST_BYTES`
    (`services/tenant_dump.py`), `FIELD_OF_TOML_KEY` and `TOML_KEY_OF_FIELD`
    (`generation/config.py`; the aliases of `GenerationTarget` replace them); their values are the defaults of the groups;
  - the Zitadel slugs `PROJECTS`, `MACHINE_USERS`, `OWN_ORGANISATION` and `TOKEN_PATH`, only the
    testkit used, moved from `rdf_persistence.adapters.zitadel` to `rdf_persistence.testkit.zitadel`.
- **BREAKING: the technical models moved out of the domain layer** (`technical-models`). Every
  name still imports from `rdf_persistence`; only a deep import of an old module path breaks, with
  `ModuleNotFoundError`:
  - `rdf_persistence.domain.generated.service` is now `rdf_persistence.services.generated.service`
    (the service records, loaded lazily from the top level);
  - `rdf_persistence.domain.iris` is now `rdf_persistence.services.iris` (the IRI policy, `Iris`,
    `DEFAULT_IRIS`, `IdSource`, `mint_aggregate_iri`) and `rdf_persistence.domain.layout` (the
    fixed IRI and name layout functions, free of the policy);
  - `rdf_persistence.domain.tenant_move` is now `rdf_persistence.services.tenant_move`;
  - the schemas `model/service/` and `model/adapters/` are now `model/technical/service/` and
    `model/technical/wire/`; the domain schemas `model/rp_*.yaml` stay where they are, and a
    consumer schema still imports `rdf_persistence/model/rp_core` (no technical schema can be
    imported that way).
- **BREAKING: the generator moved to `rdf_persistence_generation`** (`generator-package`).
  `rdf_persistence.generation` is gone, with no shim; import the generator from
  `rdf_persistence_generation`, and the `rp-generate` entry point is
  `rdf_persistence_generation.cli:main`. Every manifest's input paths change, so run your
  regenerate command once after upgrading (`howto/adopt.adoc#upgrade-generator-package`). The
  testkit's freshness plugin, conformance suite, round-trip check and strategies moved to
  `rdf_persistence_generation.testkit`; their old paths in `rdf_persistence.testkit` warn and go in
  0.6.0 (#165). `assert_isomorphic` stays in `rdf_persistence.testkit.graphs`.
- **BREAKING for log readers: log attributes and messages** (`otel-observability`). Attribute names
  follow `LogContext` (`step` is `rp.step`, `tenant` is `rp.tenant.id`, ...) and every message is a
  constant; there are no aliases. `howto/observability.adoc` lists the old and new names. The
  library logs an error only where it handles it, so `MessageLimitExceeded` is logged once.
- **BREAKING: `FusekiDataset.ds_name` is now `fuseki_dataset_name`** (`otel-observability`): the
  generator names a field after its slot when the alias is no Python name.
- **BREAKING: `If-Match` is compared strongly** (`manual-revision-notes`): `W/"v"` is now 409 and
  an unquoted `v` 428 (both matched before); `expected_version` refuses `W/`, `*` and lists.
- **BREAKING: Accept** (`manual-revision-notes`). Parsing is python-mimeparse's (a new dependency,
  `python-mimeparse==2.0.0`): an unparsable or empty `q` reads as 1 (it read as 0) and a `q` above 1
  as 1 (it outranked `q=1`). A wildcard or a type range can now be answered with one of the four new
  serialisations where it was 406; a client that refuses every type by name must name the new ones
  too.
- **BREAKING: a language-tagged value keeps its tag in JSON-LD** (`manual-revision-notes`): it is a
  value object, where it lost the tag before; JSON still shows a plain string.
- **BREAKING: JSON-LD is read on one path, PyLD's** (`manual-revision-notes`). A body or loaded file
  with an invalid IRI, or that is not a JSON object or array, is refused where it gave fewer or no
  triples. A loaded file that names a graph or uses a relative IRI without `@base` is refused with
  `InvalidGraph`, and such a body with `InvalidBody`; those triples were dropped without a word.
- **BREAKING: token checks** (`manual-revision-notes`): `jwks.ALLOWED_ALGORITHMS` and `jwks.ES256`
  are removed (the algorithms are `JwksSettings.allowed_algorithms`), and a token expired by less
  than the leeway is now accepted.

### Fixed
- **Reference collections honour the mapper's `max_roots`** (`manual-revision-notes`); they used the
  default limit.
- **Models are built with keyword arguments, not `model_copy(update=...)`**
  (`manual-revision-notes`), so a misspelt field fails validation instead of being ignored.
- **rdflib's SPARQL parsing is safe across threads** (`manual-revision-notes` follow-ups): parsing
  goes through locked wrappers, which an import contract enforces; concurrent requests could fail
  in pyparsing before.
- **The RDF writers run off the event loop**, in a worker thread.
- **The OpenAPI document** gives the generated component schemas their `type` (#148) and each
  server-sent event its shape (#153).
- **A hung test times out with a signal**, so a test worker never crashes.

## [0.4.0] - 2026-11-16

### Added
- **Several stores** (`tenant-stores`): `install_service(..., stores={name: store})` wires named
  stores beside the default one; each tenant's access record names its store, and the kit routes
  the tenant's sessions, sweep and migrations there. A record naming a store the service does not
  wire raises `StoreNotWired`.
- **Events across deployments** (`aggregate-events`): every recorded activity is the outbox entry;
  a relay that runs with the service publishes it, as the generated JSON with a JSON-LD context
  link (`context_link`), to an `EventBus` (`install_service(..., event_bus=...)`). Incoming events
  of other deployments go to the message bus (`Receive`). The Redis Streams bus on FastStream is
  the optional extra `events` (`rdf-persistence[events]`). A tenant's events can be followed over
  server-sent events, resuming with `Last-Event-ID` within 7 days; the stream shows only what the
  caller may read. Exported: `EventBus`, `EventEnvelope`, `Receive`, `context_link`.

### Fixed
- **A literal holding `\u` is stored as sent** (#108): a backslash followed by `u` or `U` was
  read by the store as a code-point escape.
- **A failed tenant create or restore cleans up only what it made.**
- **Event logs carry no tenant values** (#125).

## [0.3.0] - 2026-11-15

### Added
- **Atomic commits** (`atomic-commit`, #83): `session.transaction()` commits the writes to several
  aggregates of one tenant as one guarded update request, all or nothing. `UnitOfWork` gained
  `remove`, `version` and `discard`. A commit is limited to 500 roots by default (`CommitTooLarge`,
  413); `commit(batches=True)` takes a larger one in several transactions.
- **Unique keys across aggregates** (`cross-aggregate-unique-keys`): a scoped `unique_keys`
  declaration is enforced at commit; a clash raises `KeyConflict` (409 `key-conflict`), and
  `Session.key_duplicates()` reports the values a tenant's aggregates already repeat.
- **Collaboration** (`collaboration-and-reference-collections`, #78–#81), through the
  `Collaboration` service opened from the kit: the aggregates that refer to a resource
  (`referrers`); reference collections by list or by rule (`ReferenceCollection`, `members`),
  guarded on every write and deleted with their members; comments and replies on any aggregate
  with the `annotate` action; workflows read from files, with a toolkit-owned state and recorded
  transitions (`Workflows`, `transition`, `transitions`).
- **Dump and restore a tenant** (`tenant-dump-restore`): `kit.dump_tenant` writes the tenant's
  database as N-Quads with a `TenantDump` manifest; `kit.restore_tenant` restores it into a new
  tenant, rewriting the tenant id in every IRI.
- **Application data** (`app-level-data`): one application database, `{prefix}-app`, for data that
  belongs to no tenant. A class annotated `database: application` lives there; open it with
  `kit.application_session` after `kit.require_application`.
- **Message bus and provenance** (`message-bus`): every commit records one PROV activity (`Add`,
  `Replace`, `Remove`, or the toolkit's and the application's own commands) with a `Generation` or
  `Invalidation` per aggregate, in the tenant's provenance graph. `MessageBus` and `bootstrap`
  hand a command to its nearest handler and the committed activity to its observers along the
  class hierarchy. `RecordingObserver` in the testkit.
- **Schema migrations** (`schema-migrations`): `rp-generate` keeps a schema lock and writes
  migration files; each database is stamped with its schema version and migrated at start-up
  (`MigrationFailed`, `TenantBehind`); a restore migrates a dump from an older version of the
  chain.

### Changed
- **BREAKING: commits are all or nothing.** A unit of work that touches several aggregates either
  commits all of them or none; before, each aggregate committed on its own.
- **BREAKING: every commit writes a provenance graph** (`<tenant>/provenance`). Tests that compare
  a whole dataset will see it.
- **BREAKING: `TransitionRecord` is replaced by `Transition`.** Records written by an earlier
  `develop` build are no longer read by `transitions()` and are kept when their aggregate is
  deleted.
- **BREAKING: `install_service` and `ServiceKit` require `migrations`**, the folder of the
  application's migration files.
- **BREAKING: a restore refuses a dump whose schema stamps are outside the service's chain**; a dump
  made before the stamps existed no longer restores.

### Fixed
- **The tenant root is found whatever string type its IRI has** (#76).

## [0.2.0] - 2026-11-13

### Added
- **IRI policy** (`iri-policy`, #26): `ServiceSettings.iri_policy` sets the template and id kind
  of every IRI the toolkit mints: tenants, aggregates, parts, loaded graphs, access records, meta and
  registry graphs, and principals (short random ids, flat IRIs, a `{type}` from the class or its
  `rp_iri_type`, a `{deployment}` segment). One `Iris` per service mints and checks them; ownership
  follows the stored graph and the registry, not IRI nesting. At start-up the effective policy is
  recorded in the system database, and a later start under another policy refuses with
  `IriPolicyChanged` naming the fields. Exported: `Iris`, `IriPolicy`, `IdSpec`, `IdKind`,
  `DEFAULT_IRIS`, `AccessRules.with_iris`. With no policy, IRIs are minted as before.
- **Waiting helpers** (`testkit-wait-until`, #24): `wait_until` and the new `wait_until_async` are
  exported from `rdf_persistence.testkit`.

- **Sweep of a live tenant** (`live-tenant-sweep`): `kit.sweep_tenant(tenant, remove=False,
  remove_blobs=False, older_than=1 hour)` finds the loaded graphs no commit owns and the blobs no
  `file_key` names, older than the grace period, and returns a `TenantSweepReport`. It is a dry run
  by default; `remove` deletes the graphs and `remove_blobs` the blobs (pass it only when every blob
  key is stored in `file_key`). `Session.load_graph` now writes a load marker (`rp:loadedAt`) in the
  registry graph; a graph loaded before the upgrade has none and counts as old, so do not sweep with
  removal during a deploy. Exported: `sweep_tenant`, `TenantSweepReport`, `BlobEntry`, `PendingLoad`.
- **`remove_with_files`**: `kit.remove_with_files(tenant, principal, iri, if_version)` removes a file
  aggregate and the blobs only it names; a failed blob delete is logged and left to the sweep.
  `Session.named_file_keys(keys)` reads which keys a graph still names.

### Changed
- **The boundary REFERENCE problem names its fixes** (`boundary-owned-hint`, #72): annotate the
  slot `owned: true`, make the range an aggregate root, or point the slot at a root, `Principal`
  or `Activity`. Rule id unchanged; the old text stays a prefix.
- **BREAKING for third-party adapters: `FileStore.list_blobs(bucket)`**: the `FileStore` protocol
  gained `list_blobs`, returning `BlobEntry` (`file_key`, `modified`) in key order. Adapter authors
  add it; the `file_store_conformance` suite has a case for it. `FakeFileStore` takes a `clock` to
  stamp `modified`.
- **BREAKING: `TokenVerifier.iris`** (`iri-policy`): a token verifier exposes the `Iris` it mints
  principals with, and `install_service` refuses a verifier whose principal template differs from
  the settings'. `JwksTokenVerifier` takes `iris=Iris(settings)`.
- **Freshness hint** (`generation-fix-hint`, #25): a failed freshness check now names
  `rp-generate`, or the `regenerate-command` of each stale `[tool.rp-generate]` entry, instead of
  `make generate`. A configuration error no longer prints a hint.
- **Releases** (`release-pipeline`): releases are proposed by release-please; `VERSION` removed,
  the version lives in `pyproject.toml`.

## [0.1.0] - 2026-11-06

The first version: the toolkit of change `toolkit-v1-foundation`, archived in
`openspec/changes/archive/2026-11-06-toolkit-v1-foundation/`. Its requirements are the `rp-*`
capabilities in `openspec/specs/`.

### Added
- **Metamodel** in LinkML (`rdf_persistence/model/`): aggregate roots, owned parts, provenance,
  tenancy, ODRL-based access (grants, prohibitions, role definitions) and stored files.
- **Generation** (`rp-generate`). It generates Pydantic classes, SHACL shapes, the JSON-LD context
  and frames, TypeScript types, JSON Schema, OpenAPI components and diagrams from a consumer's
  LinkML schemas. It adds:
  - generator extensions, each with its own test;
  - hard and boundary checks;
  - a manifest with `rp-generate --check`, a freshness pytest plugin and a pre-commit hook.
- **Aggregate store**:
  - sessions and a unit of work over a SPARQL store, with optimistic concurrency, skolemised
    parts, loaded graphs and provenance;
  - the Fuseki adapter.
- **Tenancy**: a database and a bucket per tenant, access records, creation and deletion steps, and
  a start-up sweep.
- **File store**: the `FileStore` port and the S3 adapter (Garage-tested).
- **Identity and tokens**: JWKS token verification and the Zitadel identity adapter.
- **Access check**:
  - per tenant and per aggregate, in a fixed order (scope, state, prohibition, permission,
    action);
  - prohibitions and global roles.
- **Service kit** (`install_service`, `ServiceKit`):
  - a generic router per aggregate root, with JSON, JSON-LD and Turtle by content negotiation;
  - strict bodies with size limits, ETags and `If-Match`, and problem responses;
  - listings with paging, filters and sorting, and an OpenAPI document.
- **Testkit**:
  - fakes of every port;
  - conformance suites for the store, the file store and identity, and a round trip with
    Hypothesis;
  - model and file guards, token signing, and containers for Fuseki, Garage and Zitadel.
- **Docs**: the build guide, the architecture pages, the common questions, and the developer guide
  with the check timings.

<!-- Release process: docs/modules/ROOT/pages/develop/index.adoc#release -->

[Unreleased]: https://github.com/meaningfy-ws/rdf-persistence/compare/v0.6.0...HEAD
[0.6.0]: https://github.com/meaningfy-ws/rdf-persistence/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/meaningfy-ws/rdf-persistence/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/meaningfy-ws/rdf-persistence/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/meaningfy-ws/rdf-persistence/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/meaningfy-ws/rdf-persistence/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/meaningfy-ws/rdf-persistence/releases/tag/v0.1.0
