> Derives from: EPIC `toolkit-v1-foundation` ([proposal.md](proposal.md)); design in [design.md](design.md) · Type: implementation

Every task is test-first. It ends with `make check-quality` and the tests named in it green, and one
commit citing `toolkit-v1-foundation` and the task id. Each stage ends with a PR into `develop`
(DEC-3). Spec references are `capability: requirement`.

## 0. Ground

- [ ] 0.1 Rewrite `.importlinter` to PD-1: the layers contract `entrypoints | adapters > services > domain`, and the forbidden contract for `domain`; `make check-architecture` passes on the empty layers (rp-package-boundaries: Layers import downward only)
- [ ] 0.2 Dependencies per PD-2 in `pyproject.toml` (runtime pins, the `generate` extra, linkml 1.12.x pair; drop `linkml==1.10.0` from dev); `uv lock`; `make install` and the smoke test pass
- [ ] 0.3 The toy library schema in `tests/fixtures/library/` per PD-8 (domain modules, access module, `[tool.rp-generate]` fragment), hand-written YAML only, linted by `linkml-lint`
- [ ] 0.4 `tests/containers/compose.yaml` and `testkit/containers.py` per PD-7, with markers `store`, `files`, `identity`; a test per container that it starts and answers; the CI integration job

## 1. Metamodel and generation (stage 1)

- [ ] 1.1 `rdf_persistence/model/rp_core.yaml`: `AggregateRoot`, `version`, `RegistryEntry`, `loaded_graph`, the annotations `owned`, `internal`, `database`, `graph`, `module_kind` (rp-metamodel: The metamodel ships as separate modules)
- [ ] 1.2 `rp_annotations.yaml` (`Described`, `Tracked`) and `rp_provenance.yaml` (`Provenanced`, `Activity`; `Principal` as `prov:Agent`) (rp-metamodel: Instances … are described; Write tracking is stated about the graph)
- [ ] 1.3 `rp_access.yaml` (the ODRL subset and `RoleDefinition`), `rp_tenancy.yaml` (`TenantAccess`, `Grant` as a `Permission`, `TenantState`), `rp_files.yaml` (`StoredFile`), and `rp.yaml` (rp-metamodel: Access is modelled with an ODRL subset)
- [ ] 1.4 The metamodel's own Python classes generated into `rdf_persistence/domain/generated/` and exported at the top level (DEC-6)
- [ ] 1.5 `rp-generate` skeleton: reads `[tool.rp-generate]`, flags override, temporary files moved on success; lint with the raised rules (rp-generation: Each artefact goes to its declared place)
- [ ] 1.6 The hard check (IRIs, titles, descriptions, meanings, `Described` on roots and owned classes, `rp_unlabelled`) (rp-generation: Generation fails on missing IRIs, labels or definitions)
- [ ] 1.7 The boundary check (aggregate reachability, ownership, `module_kind` imports) (rp-generation: Generation fails on boundary violations)
- [ ] 1.8 Steps 3–4: split `gen-pydantic` with the toolkit's base template; `gen-shacl` subclass ignoring the toolkit's bookkeeping predicates
- [ ] 1.9 Steps 5–7: `gen-jsonld-context` with `id`/`type` aliases, `internal` slots left out and one frame per aggregate type (PD-6); the `gen-typescript` subclass and template (enums, dates, `internal` skipped); `gen-mermaid-class-diagram` per module with the roots-and-owned template
- [ ] 1.10 Generate the toy library, commit its output, and add the freshness check to CI (rp-generation: Generated output is reproducible)

## 2. Store, session and tenancy (stage 2)

- [ ] 2.1 `domain/sparql.py` (PD-3) and `graph_iri` (PD-4), with injection tests per template (rp-aggregate-store: SPARQL is never built by concatenating input)
- [ ] 2.2 Store port in `services`; the Fuseki adapter: query, update, Graph Store `PUT`, dataset create/drop/list, the 405 mapping (container image pinned by digest)
- [ ] 2.3 The session: get, add, replace, remove an aggregate; guarded commit with `ASK`; version and `Tracked` statements about the graph IRI (rp-aggregate-store: One named graph per aggregate…; Stale writes are refused; rp-metamodel: Write tracking is stated about the graph)
- [ ] 2.4 The registry and graph loading, with the parser in a worker thread (rp-aggregate-store: RDF files load into a graph of their own)
- [ ] 2.5 The mapper over `SchemaView`, for domain services: graph ↔ generated classes, round trip on the toy library
- [ ] 2.6 Tenancy: system database, access records, create (record last) and delete (`deleting` first) (rp-tenancy: Each tenant has its own database)
- [ ] 2.7 The start-up sweep (rp-tenancy: The start-up sweep finishes interrupted work)
- [ ] 2.8 Testkit: the fake store and fake session, with the store conformance suite run against both the fake and Fuseki (rp-testkit: Consumers test without servers)

## 3. Files and identity (stage 3)

- [ ] 3.1 File store port; the S3 adapter (`boto3` in a worker thread), with bucket create and delete for tenancy; Garage pinned (rp-file-store: Files are kept byte for byte…)
- [ ] 3.2 Token validation with cached JWKS and one refresh on an unknown `kid`; the testkit token signer and in-memory JWKS (rp-identity: Every request carries a valid token)
- [ ] 3.3 The identity port; the Zitadel adapter (find by email, list, disable, re-enable, grant and remove a global role); fixture provisioning per PD-9 (rp-identity: Accounts are administered through the identity port)
- [ ] 3.4 Testkit fakes of the file store and identity ports

## 4. Access (stage 4)

- [ ] 4.1 Loading a caller's permissions and prohibitions for a tenant and an aggregate in one query (system database)
- [ ] 4.2 The check: global roles, prohibitions, permissions at tenant and aggregate scope, role definitions, 403 or 404 (rp-access: Access is decided per tenant and per aggregate; Tenants without a grant stay hidden)
- [ ] 4.3 The toy library's role matrix as one table-driven test (librarian, reader, outsider, administrator × read, modify, delete × tenant, aggregate)

## 5. Service kit and generic router (stage 5)

- [ ] 5.1 Service kit: problem responses, `ETag`/`If-Match` (428, 409), token and access dependencies (rp-service-api: Writes are versioned)
- [ ] 5.2 The generic router over `SchemaView`: `/{type}` and `/{type}/{id}`, bodies to triples and validated per PD-5 (rp-service-api: One generic router serves every aggregate type)
- [ ] 5.3 Content negotiation: JSON with the `Link` header, JSON-LD, Turtle; the context served at a fixed path (rp-service-api: Plain JSON by default…)
- [ ] 5.4 Listings: equality filters, `limit`, `offset`, one sort key, the page object (rp-service-api: Listings are filtered and paged)
- [ ] 5.5 The OpenAPI hook over the schema, bookkeeping stripped (rp-service-api: The contract is published)
- [ ] 5.6 Spike: linkml-openapi on the toy library; record whether it can replace 5.5 in `api.adoc`
- [ ] 5.7 The end-to-end test: the toy library served over the API against Fuseki, Garage and test tokens (rp-testkit: Adapters are tested against real containers)

## 6. Close

- [ ] 6.1 `docs/modules/ROOT/pages/howto/adopt.adoc`: how an application adopts the toolkit (schema, `rp-generate`, composition root, router), from the toy library; in the nav
- [ ] 6.2 Architecture pages updated with what implementation taught (spike marks replaced by "implemented"); `make check-docs` passes
- [ ] 6.3 `openspec validate --all --strict`; archive the change into `openspec/specs/`

## Roadmap

- [ ] 0.1 · [ ] 0.2 · [ ] 0.3 · [ ] 0.4
- [ ] 1.1 · [ ] 1.2 · [ ] 1.3 · [ ] 1.4 · [ ] 1.5 · [ ] 1.6 · [ ] 1.7 · [ ] 1.8 · [ ] 1.9 · [ ] 1.10
- [ ] 2.1 · [ ] 2.2 · [ ] 2.3 · [ ] 2.4 · [ ] 2.5 · [ ] 2.6 · [ ] 2.7 · [ ] 2.8
- [ ] 3.1 · [ ] 3.2 · [ ] 3.3 · [ ] 3.4
- [ ] 4.1 · [ ] 4.2 · [ ] 4.3
- [ ] 5.1 · [ ] 5.2 · [ ] 5.3 · [ ] 5.4 · [ ] 5.5 · [ ] 5.6 · [ ] 5.7
- [ ] 6.1 · [ ] 6.2 · [ ] 6.3

## Verification

`make check-all` and the integration and end-to-end suites green; the toy library's generated
output fresh; `openspec validate --all --strict`; every scenario of the ten specs covered by a named
test.
