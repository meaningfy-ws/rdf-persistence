# Changelog

All notable changes to **RDF Persistence** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **A generation target declares its `kind`** (`technical-models`): the optional `kind` key of a
  `[[tool.rp-generate]]` entry is `domain` or `technical`; `rp-generate` fails, naming the target
  and the module, when a technical target holds a module not annotated `module_kind: technical`,
  or a domain target holds one annotated `technical`. A target without `kind` generates as before.

### Changed
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

[Unreleased]: https://github.com/meaningfy-ws/rdf-persistence/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/meaningfy-ws/rdf-persistence/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/meaningfy-ws/rdf-persistence/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/meaningfy-ws/rdf-persistence/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/meaningfy-ws/rdf-persistence/releases/tag/v0.1.0
