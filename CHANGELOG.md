# Changelog

All notable changes to **RDF Persistence** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

### Changed
- **BREAKING: `TokenVerifier.iris`** (`iri-policy`): a token verifier exposes the `Iris` it mints
  principals with, and `install_service` refuses a verifier whose principal template differs from
  the settings'. `JwksTokenVerifier` takes `iris=Iris(settings)`.
- **Freshness hint** (`generation-fix-hint`, #25): a failed freshness check now names
  `rp-generate`, or the `regenerate-command` of each stale `[tool.rp-generate]` entry, instead of
  `make generate`. A configuration error no longer prints a hint.

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

<!--
Release process:
1. Move the Unreleased entries under a new `## [X.Y.Z] - YYYY-MM-DD` heading.
2. Bump the version in VERSION / pyproject.toml.
3. Update the comparison links below.
-->

[Unreleased]: https://github.com/meaningfy-ws/rdf-persistence/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/meaningfy-ws/rdf-persistence/releases/tag/v0.1.0
