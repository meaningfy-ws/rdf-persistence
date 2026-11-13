# Changelog

All notable changes to **RDF Persistence** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/meaningfy-ws/rdf-persistence/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/meaningfy-ws/rdf-persistence/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/meaningfy-ws/rdf-persistence/releases/tag/v0.1.0
