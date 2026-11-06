> Derives from: EPIC `toolkit-v1-foundation` ([proposal.md](proposal.md)); design in [design.md](design.md) · Type: implementation

Every task is written test-first. A task is done when its tests and `make check-quality` are green,
and it ends in one commit citing `toolkit-v1-foundation` and the task id. Each stage ends with a PR
into `develop` (DEC-3).

Notation:
- References are `capability: requirement`; `PD-n` refers to design.md.
- "Exports" means the names are added to the top-level `rdf_persistence` package (DEC-6). Names
  meant for tests go to `rdf_persistence.testkit`.

## 0. Ground

- [x] 0.1 Delete the empty `rdf_persistence/commons/` and rewrite `.importlinter` (PD-1): the layers contract `entrypoints | adapters > services > domain`, and the forbidden contract for `domain` with `include_external_packages = True`. `make check-architecture` passes (rp-package-boundaries: Layers import downward only).
- [x] 0.2 Dependencies (PD-2): runtime pins, the `generate` extra with `linkml==1.12.1`, and `linkml==1.10.0` removed from dev. `make install` becomes `uv sync --all-extras`. Run `uv lock`; `make install` and the smoke test pass.
- [x] 0.3 The toy library schema in `tests/fixtures/library/` (PD-17), as hand-written YAML.
  - Includes `library_roles.yaml` (the role definitions of PD-9's matrix) and `partial.yaml` (imports only `rp_core` and `rp_annotations`).
  - `linkml-lint` passes.
- [x] 0.4 Test containers (PD-16):
  - `rdf_persistence/testkit/containers/compose.yaml`, with the Fuseki Dockerfile vendored at a pinned Jena 5.x release, and Garage and Zitadel pinned by digest.
  - The bootstrap for each container.
  - `rdf_persistence/testkit/containers/` as package data behind the extra `rdf-persistence[testkit]`, imported lazily; the markers `store`, `files` and `identity` added to `tests/conftest.py`'s path table and registered by the fixtures plugin (PD-16).
  - `make test` runs `unit or feature` with the coverage floor, `.coveragerc` omitting `rdf_persistence/adapters/*` and `rdf_persistence/testkit/containers/*`; a new `make test-containers` runs `integration or e2e` with `--cov-fail-under=0`; the `conftest.py` hook applies every marker of a row; the CI container job.
  - One smoke test per container: it starts and answers.

- [x] 0.5 A CI workflow for changes under `docs/**`: `make check-docs` and the Antora build. `check_docs.py` also scans `rdf_persistence/` and `tests/` for consumer terms, run by `make check-quality` (PD-20).

## 1. Metamodel and generation (stage 1)

- [x] 1.1 `rdf_persistence/model/rp_core.yaml`: `AggregateRoot`, `Principal` (PD-21), `version`, `RegistryEntry` (`graph`, `kind`, `owned_by`: PD-8), `loaded_graph`, and the annotations `owned`, `internal`, `database`, `graph`, `module_kind`, `rp_path`, `rp_unlabelled`.
- [x] 1.2 `rp_annotations.yaml` (`Described`, `Tracked`) and `rp_provenance.yaml` (`Provenanced`, `Activity`; it uses `rp_core`'s `Principal` as its agent).
- [x] 1.3 `rp_access.yaml`:
  - the ODRL subset and `RoleDefinition`;
  - `RoleDefinition` with the slots of PD-9;
  - `Grant` with the slots of PD-10 and `unique_keys: {grant_key: [assignee, target, role, action]}`;
  - `TenantAccess` includes `Described` (PD-21).

  Also `rp_tenancy.yaml` (`TenantAccess` owning `grants` — role or direct-action — and `prohibitions`, plus `TenantState`), `rp_files.yaml` (`StoredFile`) and `rp.yaml`.
- [x] 1.4 Generate the metamodel's own Python classes into `rdf_persistence/domain/generated/` with plain `gen-pydantic` (task 1.10 regenerates them through `rp-generate`). Exports: the metamodel classes and `RpModel`.
- [x] 1.5 `rp-generate` skeleton:
  - reads `[tool.rp-generate]` with the keys and flags of PD-18;
  - writes to temporary files and moves them into place on success;
  - runs lint with the raised rules.

  Exports: the `rp-generate` command, always installed; it exits with code 2 and a clear message when the `generate` extra is missing (PD-2).
- [x] 1.6 The hard check:
  - IRIs, titles, descriptions and meanings;
  - `rp_path` on every aggregate root;
  - `Described` on roots and owned classes;
  - `rp_unlabelled` applied as in PD-11.
- [x] 1.7 The boundary check: aggregate reachability, ownership, and `module_kind` imports.
- [x] 1.8 Steps 3 and 4:
  - split `gen-pydantic` with the toolkit's base template;
  - a `gen-shacl` subclass that ignores the toolkit's bookkeeping predicates (`rp:version`, `dcterms:created`, `dcterms:modified`, `dcterms:creator`, `dcterms:contributor`), and translates `exactly_one_of` to `sh:xone`, `any_of` to `sh:or` and `unique_keys` to a SPARQL constraint on the owning class (PD-24).
- [x] 1.9 Steps 5 to 7:
  - `gen-jsonld-context`: `id`/`type` aliases, `internal` slots left out, and one frame per aggregate type (PD-12);
  - the `gen-typescript` subclass and its template: enums, dates, `internal` skipped;
  - `gen-mermaid-class-diagram` per module, with the template that marks roots and owned parts.
- [x] 1.10 Generate the toy library and regenerate the metamodel classes through `rp-generate`, with generator metadata switched off and `**/generated/**` excluded from Ruff, mypy and Xenon (PD-19); commit the output; add `make check-generated` and run it in CI.

### 1b. Single source of specification (PD-24 to PD-28; developer, 2026-11-05)

Order: 1.11 at any time; 1.12 and 1.16 after 1.10; 1.13 after 1.8 and 1.12; 1.14 after 1.9, 1.12 and 1.13; 1.15 after 1.12;
1.17 after 1.9; 1.18 after 1.9 and 1.11. Tasks 1.12 and 1.13 regenerate and recommit the output of
1.10. Hypothesis is added to the test group, pinned, in task 1.14.

- [x] 1.11 Embed the rule: `AGENTS.md` states it (done with the plan); `open-decisions.adoc` records it as D-13, with a link to the MWBv2 Developer Runbook; `generation.adoc` gets anchors on its sections (`#extensions`, `#guarding`), rewrites "Guarding the generated code" to PD-26 to PD-28, and its extension table gains a first column with each extension's module path and rows for the validators and shape constraints of PD-24. `make check-docs` passes.
- [x] 1.12 The manifest and `rp-generate --check` (PD-26): `rp_generation.yaml` with `GenerationManifest` (also `ConstraintCase` and `ClassShape`, used by 1.14 and 1.15), generated; stale input, edited output, a changed `linkml` version and a fresh run each tested; `rdf_persistence/testkit/freshness.py` with the ini option `rp_generate_projects`; the repo's `[[tool.rp-generate]]` entries for `rp.yaml` and `rp_generation.yaml` in `pyproject.toml` (1.13 adds `rp_service.yaml`); `make check-quality` runs the check; the pre-commit hook; `make generate`, run first by `make build`.
- [x] 1.13 The gen-pydantic template extension that generates model validators for `exactly_one_of`, `any_of` and `unique_keys`, placed as PD-24 says; a schema using `rules` makes `rp-generate` exit 1. The three strict xfails of task 1.4 pass and lose their marks. Also `rp_service.yaml` (`ServiceSettings`, `VerifiedCaller` and the bodies of PD-13), as its own `[[tool.rp-generate]]` entry into `domain/generated/service/`.
- [x] 1.14 The conformance suite (PD-27 items 3 to 5): the constraint-case table with the classes-versus-shapes verdict test and the coverage test; the JSON-LD round trip with Hypothesis; the model-shape test. In `testkit`, run on the metamodel and the toy library.
- [x] 1.15 The model-shape snapshot under `tests/fixtures/`, its test and `make refresh-snapshot` (PD-27 item 6).
- [x] 1.16 The model guard and the file guard (PD-28) as `testkit.assert_models_generated`, run on this package.
- [x] 1.17 Generated code compiles (PD-27 item 7): an import test of every generated module; `mypy-generated.ini` and its run in `make check-quality`; `tsc --noEmit --strict` (typescript 5.9.3) on the TypeScript output in CI.
- [x] 1.18 The extension register test (PD-25): every extension module under `rdf_persistence/generation/` has a row in `generation.adoc#extensions` whose first column is its module path, and a golden test `tests/unit/generation/test_ext_<module>.py` with goldens in `tests/fixtures/library/golden/<module>/`.
- [x] 1.19 The stage 1 docs (developer, 2026-11-05): bring `generation.adoc` in line with what stage 1 built and the stage 1 review's decisions (PD-22, PD-24, PD-26 to PD-28), with _(spike)_ kept only on what stage 2 still has to build; and `docs/modules/ROOT/pages/develop/index.adoc`, how to work on the toolkit itself (the generation loop, adding a schema entry or an extension, the guards), added to the nav. `make check-docs` and the extension register test pass.
- [x] 1.20 The user guide, part 1 (developer, 2026-11-05): `docs/modules/ROOT/pages/howto/adopt.adoc` covers what stage 1 gives an application (install, model, `rp-generate`, the generated classes, the testkit guards), each example run against the toolkit, and lists the parts still to come; added to the nav. `make check-docs` passes.

## 2. Store, session and tenancy (stage 2)

- [x] 2.1 `domain/sparql.py` (PD-3) and `domain/iris.py` (`graph_iri`, minting: PD-4, PD-6), with an injection test per template.
- [x] 2.2 The store port in `services`. The Fuseki adapter: query, update, Graph Store `PUT`, dataset create, drop and list, and the 405 mapping.
- [x] 2.3 The session:
  - the graph-level methods of PD-7a;
  - the guarded commit with UUID tokens and `ASK` (PD-5), with a test of the two-editor race;
  - tracking carried across commits (PD-7) and registry entries in the same update (PD-8);
  - the tenant root in `{tenant_iri}/meta`, versioned the same way (PD-8).

  Exports: `open_session`, the store port, `FusekiStore`, `Conflict`, `NotFound`, `DatabaseGone`.
- [x] 2.4 Graph loading, with the parser in a worker thread and the loaded graph registered by the caller's commit. `Session.load_graph` (a method, so nothing extra is exported); exports: `InvalidGraph`, `RdfFormat`.
- [x] 2.5 The mapper over `SchemaView`, for domain services, with the object-level methods of PD-7a: graph to generated classes and back, with a round trip on the toy library. Known trap: linkml's `rdflib_dumper` fails on a slot whose range is a class but whose value is an IRI string (`Grant.assignee`, range `Principal`); the mapper must handle IRI references, with a test.
- [x] 2.6 Tenancy:
  - the system database, created at start-up if missing, and access records, named as in PD-6a;
  - create, which writes the record last and grants the creator `creator_role`, and delete, which marks `deleting` first;
  - the file store port and the testkit's fake file store, defined here; buckets through the port (the S3 adapter comes in 3.1).

  Exports: `Tenancy`.
- [x] 2.7 The start-up sweep, over databases and buckets named `{prefix}-t-…` only (PD-6a).
- [x] 2.8 Testkit:
  - the fake store and fake session;
  - the store conformance suite, run against both the fake and Fuseki;
  - `testkit.no_network`, a fixture that makes any socket connection fail, used by the fake-based tests.

  Exports: the fakes, in `rdf_persistence.testkit`.

## 3. Files and identity (stage 3)

- [x] 3.1 The S3 adapter of the file store port (`boto3` in a worker thread), including bucket create, delete and list by prefix for tenancy and the sweep; the tenancy tests of 2.6 and 2.7 re-run against Garage. Exports: `S3FileStore` (the file store port and `TenantGone` are exported since 2.6).
- [x] 3.2 The `TokenVerifier` port and `JwksTokenVerifier` (PD-1): JWT access tokens only, cached JWKS, one refresh on an unknown `kid`, and the configurable roles claim (PD-9). Also the testkit token signer and an in-memory JWKS. Exports: `TokenVerifier`, `JwksTokenVerifier`; testkit `TokenSigner`.
- [x] 3.3 The identity port and the Zitadel adapter:
  - find by email, list, disable, re-enable, and grant or remove a global role;
  - fixture provisioning of the project and the machine users with JWT access tokens (PD-16);
  - a test that a disabled service account's token request is refused.

  Exports: the identity port, `ZitadelIdentity`, `IdentityUnavailable`.
- [x] 3.4 The testkit fake of the identity port.

## 4. Access (stage 4)

- [x] 4.1 Loading the role definitions (PD-9), with an invalid file refused. Validating a grant set against `rp_access`, including the `grant_key` uniqueness enforced by the 1.13 validator on `GrantSet` (422 on a duplicate). Also loading a caller's grants (role or direct action) and prohibitions for one tenant in one query.
- [x] 4.2 The check: global roles, prohibitions, permissions at tenant and aggregate scope, and role definitions; it answers 403 or 404. Exports: `AccessRules`.
- [x] 4.3 PD-9's matrix as one table-driven test, every cell including the `deleting` tenant row.

## 5. Service kit and generic router (stage 5)

- [x] 5.1 The service kit:
  - `install_service(app, …)` as in PD-13: router, problem handlers for every toolkit error (a test checks a 401 carries `application/problem+json`), and the lifespan start-up order; `ETag`/`If-Match` (428, 409);
  - the token dependency (on the `TokenVerifier` port) and the access dependency.

  Exports: `install_service`.
- [x] 5.2 The generic router (PD-13):
  - the tenant routes of PD-13, including grants and label, and aggregate routes over `SchemaView`;
  - IRIs minted on create (PD-6);
  - bodies handled as in PD-14, including the refused replace with a different `id`.
- [x] 5.3 Content negotiation: JSON with the `Link` header, JSON-LD and Turtle; 406 and 415; the context served at a fixed path.
- [x] 5.4 Listings: `?<slot>=<value>` filters, `limit`, `offset`, `sort` (PD-15), the page object, 400 on a bad query, and an injection attempt through a filter that leaves the store unchanged.
- [x] 5.5 The OpenAPI hook over the schema, with bookkeeping stripped; its component schemas are generated from the LinkML schema, never written by hand (PD-24).
- [x] 5.6 Spike linkml-openapi on the toy library; record in `api.adoc` whether it can replace 5.5.
- [x] 5.7 The end-to-end test: the toy library served over the API against Fuseki, Garage and Zitadel, with JWT access tokens of the machine users obtained by the JWT-profile grant (PD-16).

## 6. Close

- [x] 6.1 Complete `docs/modules/ROOT/pages/howto/adopt.adoc` (part 1 is task 1.20): the session, tenancy, files, access, the composition root and the router, using the toy library, replacing its "Not yet available" section.
- [x] 6.2 Update the architecture pages with what stages 2 to 5 taught (`generation.adoc`'s stage 1 parts are done by 1.19): replace _(spike)_ marks with "implemented", and update the public API table and the metamodel slot table (`prohibitions`, `RoleDefinition`). `make check-docs` passes.
- [x] 6.3 Run `openspec validate --all --strict`, then archive the change into `openspec/specs/`.

## Scenario map

Every scenario of the specs, the task that satisfies it, and the test that proves it.

| Capability: scenario | Task | Test |
|---|---|---|
| rp-metamodel: an application imports only what it uses | 1.10 | `tests/unit/generation/test_partial_import.py` (fixture `partial.yaml`) |
| rp-metamodel: an instance without a label is refused | 1.8 | `tests/unit/generation/test_shapes.py` |
| rp-metamodel: an owned value class opts out | 1.6, 1.8 | `tests/unit/generation/test_shapes.py` |
| rp-metamodel: a commit records who and when | 2.3 | `tests/integration/store/test_session.py` |
| rp-metamodel: a grant is ODRL | 2.6 | `tests/integration/tenancy/test_tenancy.py` |
| rp-generation: a slot without a description | 1.6 | `tests/unit/generation/test_hard_check.py` |
| rp-generation: a domain module imports the access module | 1.7 | `tests/unit/generation/test_boundary_check.py` |
| rp-generation: placement from the table | 1.10 | `tests/unit/generation/test_placement.py` |
| rp-generation: regeneration in CI | 1.10 | `make check-generated` in CI |
| rp-aggregate-store: graph name | 2.3 | `tests/integration/store/test_session.py` |
| rp-aggregate-store: two editors | 2.3 | `tests/integration/store/test_session.py` |
| rp-aggregate-store: an injection attempt | 2.1, 5.4 | `tests/unit/domain/test_sparql.py`; `tests/integration/api/test_listing.py` |
| rp-aggregate-store: a broken file | 2.4 | `tests/integration/store/test_loading.py` |
| rp-tenancy: create then delete | 2.6, 3.1 | `tests/integration/tenancy/test_tenancy.py` |
| rp-tenancy: a crash during creation | 2.7, 3.1 | `tests/integration/tenancy/test_sweep.py` |
| rp-file-store: round trip | 3.1 | `tests/integration/files/test_s3.py` |
| rp-file-store: a put after the tenant is gone | 3.1 | `tests/integration/files/test_s3.py` |
| rp-identity: an expired token | 3.2, 5.1 | `tests/unit/services/test_token_verifier.py`; `tests/unit/entrypoints/test_service_kit.py` (401, no handler runs) |
| rp-identity: a service account | 3.2, 5.7 | `tests/e2e/test_library.py` |
| rp-identity: disable an account | 3.3 | `tests/integration/identity/test_zitadel.py` |
| rp-access: a reader may not modify | 4.3, 5.7 | `tests/unit/services/test_access_matrix.py` (the 403); `tests/e2e/test_library.py` (the book unchanged) |
| rp-access: a permission on one aggregate only | 4.3 | `tests/unit/services/test_access_matrix.py` |
| rp-access: an outsider | 4.3 | `tests/unit/services/test_access_matrix.py` |
| rp-access: a tenant being deleted | 4.3 | `tests/unit/services/test_access_matrix.py` |
| rp-service-api: a new class in the model | 5.2 | `tests/integration/api/test_router.py` |
| rp-service-api: the same book three ways | 5.3 | `tests/integration/api/test_negotiation.py` |
| rp-service-api: a stale replace | 5.1 | `tests/integration/api/test_router.py` |
| rp-service-api: a page of books | 5.4 | `tests/integration/api/test_listing.py` |
| rp-service-api: the document lists the routes | 5.5 | `tests/unit/entrypoints/test_openapi.py` |
| rp-testkit: a unit test of a domain service | 2.8, 3.4 | `tests/unit/testkit/test_fakes.py` (with `testkit.no_network`) |
| rp-testkit: the end-to-end proof | 5.7 | `tests/e2e/test_library.py` |
| rp-generation: a hand-written domain class | 1.16 | `tests/unit/generation/test_model_guard.py` |
| rp-generation: classes and shapes agree on a declared rule | 1.13, 1.14 | `tests/unit/generation/test_conformance.py` |
| rp-generation: a schema changed without regenerating | 1.12 | `tests/unit/generation/test_freshness_plugin.py` |
| rp-generation: a generated file edited by hand | 1.12 | `tests/unit/generation/test_freshness.py` |
| rp-generation: a model change is acknowledged | 1.15 | `tests/unit/generation/test_shape_snapshot.py` |
| rp-package-boundaries: a consumer term in code | 0.5 | `make check-quality` (`check_docs.py`) |
| rp-package-boundaries: a consumer term in an architecture page | 0.5 | `make check-docs` in the docs CI workflow |
| rp-package-boundaries: tested alone | 0.2 | CI (no consumer installed) |
| rp-package-boundaries: a service imports an adapter | 0.1 | `make check-architecture` |
| rp-package-boundaries: a name used by the toy library | 5.7 | `tests/e2e/test_library.py` with `testkit.assert_public_imports` (PD-20) |

## Roadmap

- [x] 0.1 · [x] 0.2 · [x] 0.3 · [x] 0.4 · [x] 0.5
- [x] 1.1 · [x] 1.2 · [x] 1.3 · [x] 1.4 · [x] 1.5 · [x] 1.6 · [x] 1.7 · [x] 1.8 · [x] 1.9 · [x] 1.10 · [x] 1.11 · [x] 1.12 · [x] 1.13 · [x] 1.14 · [x] 1.15 · [x] 1.16 · [x] 1.17 · [x] 1.18 · [x] 1.19 · [x] 1.20
- [x] 2.1 · [x] 2.2 · [x] 2.3 · [x] 2.4 · [x] 2.5 · [x] 2.6 · [x] 2.7 · [x] 2.8
- [x] 3.1 · [x] 3.2 · [x] 3.3 · [x] 3.4
- [x] 4.1 · [x] 4.2 · [x] 4.3
- [x] 5.1 · [x] 5.2 · [x] 5.3 · [x] 5.4 · [x] 5.5 · [x] 5.6 · [x] 5.7
- [x] 6.1 · [x] 6.2 · [x] 6.3

## Verification

The change is complete when:
- `make check-all` and `make test-containers` are green;
- the toy library's generated output is fresh;
- `openspec validate --all --strict` passes;
- every row of the scenario map has its test.
