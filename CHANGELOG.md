# Changelog

All notable changes to **RDF Persistence** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
