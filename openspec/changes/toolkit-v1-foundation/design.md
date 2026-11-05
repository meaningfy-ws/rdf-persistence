> Derives from: EPIC `toolkit-v1-foundation` ([proposal.md](proposal.md)) · Type: implementation

## Context

The package `rdf_persistence` is the uv scaffold. It has empty `domain/`, `services/`, `adapters/` and
`commons/` packages, a smoke test, an import-linter contract, CI (Ruff, mypy, import-linter, OpenSpec,
pytest with an 80% coverage floor, Xenon) and `testcontainers` in the test group.

The architecture it implements, all under `docs/modules/ROOT/pages/architecture/`:

| Page | What it fixes |
|---|---|
| `index.adoc` | needs N-1..N-11 (`#consumer-needs`), building blocks, public API (`#public-api`) |
| `generation.adoc` | metamodel (`#metamodel`), its revision (`#revision`), the toolchain |
| `api.adoc` | the generic router (`#mapper` for the classes question) |
| `access-control.adoc` | the ODRL check, identity (`#identity`) |
| `open-decisions.adoc` | the decisions of 2026-11-05, D-1..D-12 |

Generation steps 1–4 and Fuseki's behaviour were proven in a spike (LinkML 1.12.1, Fuseki 5.1.0),
marked _(spike)_ in `generation.adoc`.

## Goals / Non-Goals

**Goals:**
- the ten capabilities of the EPIC, each landing in its stage with its tests (DEC-3, DEC-4);
- the end-to-end proof on the toy library (DEC-2);
- every spec scenario mapped to a task and a test (tasks.md, Scenario map).

**Non-Goals:**
- the EPIC's no-gos;
- performance work beyond the toy library;
- any command-line tool other than `rp-generate`;
- documentation changes beyond those that tasks 1.11, 6.1 and 6.2 name.

## Decisions

New choices made while planning, grouped by topic; the numbers are stable ids, not an order. Settled
decisions are cited, not restated: EPIC DEC-1..DEC-6 and architecture D-1..D-12, O-1 and O-2.

### Layers and dependencies

- **PD-1 The layer contract.**
  - The scaffold orders the layers `entrypoints > services > adapters > domain`. The architecture puts
    ports in `services` and their implementations in `adapters`.
  - The contract becomes `entrypoints | adapters > services > domain`. `entrypoints` and `adapters`
    are independent siblings: neither imports the other.
  - The service kit needs token verification. It depends on the `TokenVerifier` port, which lives in
    `services`. The JWKS-based implementation, `JwksTokenVerifier`, is an adapter, and the consumer's
    composition root wires it in. The public API table in `index.adoc` already lists both.
  - `generation` and `testkit` sit outside the contract. The scaffold's empty `commons/` package is
    deleted (task 0.1): nothing needs a shared tier. The top-level `__init__.py` re-exports the
    public names.
  - A second contract forbids `domain` from importing `httpx`, `boto3`, `fastapi`, `jwt`,
    `pyshacl` and `anyio`. It sets `include_external_packages = True`.
  - A third contract forbids the four layers from importing `rdf_persistence.testkit`,
    `rdf_persistence.generation`, `pytest`, `testcontainers` and `linkml`: those come only with the
    extras, so a consumer's running service does not have them (stage 0 review).
- **PD-2 Dependencies (DEC-5).**
  - Runtime pins (`==`): `linkml-runtime`, `rdflib`, `pyld`, `pyshacl`, `pydantic`, `httpx`,
    `fastapi`, `pyjwt[crypto]`, `boto3`, `anyio`. Each is pinned to its latest release on the day
    task 0.2 runs, recorded in `uv.lock`; `linkml` is the exception (below).
  - An optional extra, `rdf-persistence[generate]`, brings `linkml==1.12.1`, so consumers' running
    services do not install the generators. `linkml-runtime` is pinned to the version that `linkml`
    1.12.1 resolves to in `uv.lock`.
  - `linkml==1.10.0` leaves the dev group. `make install` becomes `uv sync --all-extras`, so
    development and CI always have the generators.
  - The `rp-generate` script is always installed (a `[project.scripts]` entry cannot be limited to
    an extra). Without the extra, it exits with code 2 and the message
    "install rdf-persistence[generate]".
  - `boto3` calls run in a worker thread (`anyio.to_thread.run_sync`). Rejected: `aioboto3`, a second
    S3 stack to track.

### Store and session

- **PD-3 One SPARQL value function.**
  - `domain/sparql.py` holds `term(value) -> str`, covering IRIs, literals with datatype or language,
    and blank-node labels, and `fill(template, **terms)`.
  - Every query template in `adapters` is a module constant with `$name` placeholders. No other code
    produces SPARQL text.
- **PD-4 Graph IRI.** `graph_iri(root_iri) = root_iri + "/graph"`, defined only in `domain/iris.py`
  (DEC-29).
- **PD-5 Version tokens.** Each commit writes a fresh random UUID as the version, never a counter.
  - Two sessions that read the same version therefore write different new tokens.
  - The loser's `ASK` for its own token is false: a conflict, never a false success.
- **PD-6 IRIs and paths.**
  - A tenant's IRI is `{base}{tenant_segment}/{uuid4}`. `base` and `tenant_segment` are given by the
    consumer; the toy library uses `libraries`.
  - An aggregate's IRI is `{tenant_iri}/{rp_path}/{uuid4}`.
  - `rp_path` is a required annotation on every aggregate root (the hard check enforces it), for
    example `rp_path: books`. There is no automatic plural.
  - The toolkit mints IRIs; clients never send them on create.
- **PD-6a Names.** `prefix` is the consumer's short name (lower case, at most 20 characters; the toy
  library uses `lib`, with `base` = `https://example.org/library/`).

  | Thing | Name |
  |---|---|
  | System database | `{prefix}-system` |
  | Tenant database and bucket | `{prefix}-t-{uuid hex}` (the tenant UUID without hyphens; a valid S3 bucket name) |
  | Tenant's metadata graph | `{tenant_iri}/meta` |
  | Tenant's registry graph | `{tenant_iri}/registry` |
  | Aggregate's graph | `graph_iri(root)` = `{root_iri}/graph` |
  | Loaded graph | `{aggregate_iri}/content/{uuid4}` |
  | Tenant access record (an aggregate of the system database) | IRI `{tenant_iri}/access`; graph `graph_iri` of it, `{tenant_iri}/access/graph` |

  The sweep considers only databases and buckets whose names start with `{prefix}-t-`.

  `TenantAccess` is an aggregate root, so it carries `rp_path: access` to satisfy the hard check.
  Its IRI is the one in this table, never minted from `rp_path` (task 1.3).
- **PD-7 Tracking on update.** `dcterms:created` and `dcterms:creator` are written by the first
  commit and kept. Every later commit replaces `dcterms:modified` and adds the committer to
  `dcterms:contributor`. All of these are statements about the graph IRI (D-7). Because a commit
  replaces the whole graph, the session reads the existing tracking statements with the aggregate and
  writes back `created`, `creator` and every earlier contributor. `Tracked` is a class mixin, so the
  generated classes carry these slots, but the mapper (task 2.5) reads and writes them as statements
  about the graph IRI, never the root, and the shapes ignore them (task 1.8).
- **PD-7a The session's two levels.** Graph level, for the router (task 2.3): `get_graph(iri)` →
  triples and version; `add_graph(iri, triples)`; `replace_graph(iri, triples, if_version)`;
  `remove(iri, if_version)`. Object level, for domain services, on the mapper (task 2.5):
  `get(cls, iri)`, `add(obj)`, then `commit()`, which calls the graph-level methods.
- **PD-8 The registry and the tenant root.** The commit's update also deletes and inserts the
  aggregate's registry entries, one per graph it owns: its own graph and its loaded graphs. A
  `RegistryEntry` has `graph` (`rp:graph`), `kind` (`rp:kind`: `aggregate`, `loaded_graph`) and
  `owned_by` (`rp:ownedBy`: the root IRI).

  A tenant's root object (the toy `Library`) lives in `{tenant_iri}/meta`, which is its graph
  instead of `graph_iri(root)`. It is versioned and tracked the same way, with the statements made
  about `{tenant_iri}/meta`. It has no registry entry. Its IRI is the tenant IRI itself, it needs no
  `rp_path`, and the generic aggregate routes skip it: it is read and replaced through
  `GET`/`PUT /{tenant_segment}/{t}`, with action `modify` at tenant scope for the replace.

### Access

- **PD-9 Where access data lives.**
  - **Grants, per-aggregate Permissions and Prohibitions** are owned parts of the tenant's access
    record, in its graph in the system database. They are therefore read in one query per request
    and changed by one guarded commit.
  - **Role definitions** are the consumer's data, not stored data. They are instances of
    `RoleDefinition` in a YAML file beside the consumer's access module, validated against
    `rp_access` at start-up and held in memory. A `RoleDefinition` has three slots:

    | Slot | IRI | Range |
    |---|---|---|
    | `role` | `rp:role` | string, required: a tenant role name, or a global role name from the token |
    | `level` | `rp:level` | enum `system`, `tenant`, `aggregate`, required: where the role applies (`system` only for global roles) |
    | `actions` | `rp:permits` | `Action`, multivalued, required |

    The toy library's `library_roles.yaml`:

    ```yaml
    - {role: admin, level: system, actions: [read]}
    - {role: librarian, level: tenant, actions: [read, modify, delete, administer]}
    - {role: reader, level: tenant, actions: [read]}
    ```
  - **Global roles** come from a configurable token claim. The default is Zitadel's
    `urn:zitadel:iam:org:project:roles`, an object keyed by role name.
  - The toy library's roles are `librarian` and `reader` per library, plus the global role `admin`.
  - Actions are `read`, `modify` and `delete` (ODRL), and `administer` (the toolkit's
    `rp:administer`: change the tenant's grants). Creating an aggregate is `modify` at tenant scope.
    Creating a tenant needs only a valid token; the creator gets the role named by the consumer's
    `creator_role` (toy: `librarian`).
  - Listing a tenant's aggregates needs `read` at tenant scope. A permission on one aggregate
    allows that aggregate only.
  - `modify`, `delete` and `administer` each imply `read` at the same scope.
  - A *tenant grant* is a grant whose target is the tenant IRI. A caller with no tenant grant, no
    permission on the requested aggregate and no global role that a role definition allows gets
    404. A caller with one of them, but without the
    action, gets 403. A matching Prohibition gets 403 before anything else.

  The toy library's matrix, which task 4.3 tests (`allow`, or the status returned):

  | Caller | read book | modify/create book | delete book | administer grants | delete tenant | list books |
  |---|---|---|---|---|---|---|
  | `admin` (global, `read` at system level) | allow | 403 | 403 | 403 | 403 | allow |
  | `librarian` | allow | allow | allow | allow | allow | allow |
  | `reader` | allow | 403 | 403 | 403 | 403 | allow |
  | direct `modify` permission on book B only | B: allow; others: 404 | B: allow; others: 404 | B: 403; others: 404 | 404 | 404 | 404 |
  | `reader` + direct `modify` permission on book B | allow | B: allow; others: 403 | 403 | 403 | 403 | allow |
  | `librarian` + Prohibition of `modify` on book B | allow | B: 403; others: allow | allow | allow | allow | allow |
  | no grant (outsider) | 404 | 404 | 404 | 404 | 404 | 404 |
  | anyone, tenant `deleting` | 404 | 404 | 404 | 404 | 404 | 404 |
- **PD-10 One grant model.** A `Grant` is an `odrl:Permission` with:
  - `assignee` (`odrl:assignee`): always a `Principal` in v1 (no party collections);
  - `target` (`odrl:target`): an IRI, either the tenant's or an aggregate's graph IRI. The scope
    level follows from which it is;
  - `role` (`rp:role`) for a role grant, or `action` (`odrl:action`) for a direct permission;
    exactly one of the two. `role` is a string matched against `RoleDefinition.role` (PD-9); no
    subclassing is needed, and an application may narrow it to an enum by `slot_usage`.

  The access record owns two collections: `grants` (`rp:grant`, role or direct-action grants) and
  `prohibitions` (`rp:prohibition`), both owned and multivalued. Grant targets are tenant or
  aggregate-graph IRIs only. The system level exists only through
  global roles in the token claim (PD-9): no system grants are stored. A `Prohibition` has the same
  `assignee` and `target`, and an `action`. Uniqueness: one grant per assignee, target and
  role-or-action, declared as `unique_keys: {grant_key: [assignee, target, role, action]}` (task 1.3);
  `generation.adoc#metamodel` (slot table) and `index.adoc#building-blocks` (Tenancy row) say the same.

### Single source of specification (developer, 2026-11-05)

The developer's rule, from the model-driven method of the MWBv2 Developer Runbook: the domain is
specified once, in LinkML, and every artefact that restates it is generated. Nothing that restates
the model is written or edited by hand.

- **PD-24 What is generated, and what may be hand-written.**
  - Generated from LinkML: domain classes, SHACL shapes, the JSON-LD context and frames, TypeScript
    types, the OpenAPI component schemas, JSON Schema (if a consumer needs it) and the diagrams.
  - Hand-written, because it restates nothing: generic code that reads the schema through
    `SchemaView` at run time (the mapper, the router), the strict base `RpModel`, the generator
    extensions and templates, and infrastructure settings in `testkit` and `adapters` (such as a
    container's endpoint), which are not domain data.
  - A rule the schema declares (`exactly_one_of`, `unique_keys`, `rules`, patterns, cardinality) is
    enforced by the generated code too, not only by the shapes. Where a stock generator cannot do
    this, the toolkit extends it.
- **PD-25 Extending the generators.** Every gap in a stock LinkML generator is closed by an
  extension in `rdf_persistence/generation/`: a subclass or a template, never a patch to generated
  output. Each extension has a row in the extension table of `generation.adoc` (what the stock
  generator lacks, what the extension adds) and a golden test on the toy schema. A test fails if an
  extension module has no row or no test.
- **PD-26 Freshness and drift.**
  - `rp-generate` writes `generated/rp-manifest.json` beside its output: the pinned `linkml`
    version and the SHA-256 of every input (the schema and its whole import closure, the templates,
    the extension modules) and of every output.
  - `rp-generate --check` recomputes both. A changed input means *stale*; a changed output means
    *edited by hand*. Either exits 1, naming the files and the command that fixes them.
  - The check runs in four places: `make check-quality` (so before every PR and in CI); at the start
    of every pytest session, through a testkit plugin that consumers load too; a pre-commit hook on
    changes to schemas, templates, extensions or generated folders; and `make check-generated` in
    CI, which regenerates from scratch and diffs, catching what a hash cannot (a generator that is
    not deterministic).
  - Generation is part of the build: `make generate` regenerates everything, and `make build` runs
    it first.
- **PD-27 Correctness of the generated code.**
  1. *Schema gates first*: `linkml-lint` with the raised rules, then the hard and boundary checks;
     nothing is generated from a schema that fails them.
  2. *Golden tests per extension*: RDF output compared by graph isomorphism, other output as exact
     text, and the set of files compared exactly.
  3. *Cross-artefact conformance*: one table of constraint cases, each with a valid and an invalid
     instance. For every case the generated classes and the generated shapes must give the same
     verdict. A test fails if a constraint kind used by the metamodel or the toy schema has no row.
     The suite ships in `testkit`, so a consumer runs it on its own schema.
  4. *Round trips*: an instance goes to JSON, is expanded with the generated context to RDF, then
     framed and compacted back, and must come back equal; Hypothesis draws the instances from the
     toy schema.
  5. *Model shape*: for every generated class, the pydantic fields match `SchemaView`'s induced
     slots (name, required, multivalued, range). This catches stale or edited code even without the
     manifest.
  6. *A model change fails the tests until acknowledged* (runbook): a reviewed snapshot of the
     public shape of every class lives under `tests/fixtures/`. After a schema change and
     regeneration, the snapshot test fails until `make refresh-snapshot` is run and the diff is
     reviewed in the PR.
  7. *Generated code compiles*: the generated Python imports cleanly and passes mypy with a profile
     for generated code; the TypeScript passes `tsc --noEmit` in CI.
- **PD-28 Guards against hand-written models.**
  - An AST guard fails if a module of `domain`, `services` or `entrypoints` outside `generated/`
    defines a class deriving from `BaseModel`, `RpModel`, `Enum` or `TypedDict`, or a dataclass.
    `RpModel` is the only allowed exception.
  - A file guard fails if a shape, JSON-LD context, JSON Schema, OpenAPI or TypeScript model file
    exists outside a generated folder.
  - Both guards are in `testkit` (`assert_models_generated(package)`), so consumers get them too.

### Generation

- **PD-18 The `[tool.rp-generate]` table.** Paths are relative to the directory of the
  `pyproject.toml`. Each key has a command-line flag that overrides it.

  | Key | Flag | Default | Meaning |
  |---|---|---|---|
  | `schema` | `--schema` | required | root schema file |
  | `package` | `--package` | required | Python import path of the generated package |
  | `python` | `--python-out` | the folder of `package` | classes, shapes, context, frames, schema copy |
  | `typescript` | `--typescript-out` | not written | TypeScript types |
  | `diagrams` | `--diagrams-out` | not written | one Mermaid file per module |
  | — | `--check` | off | run lint and the checks only; write nothing |
- **PD-19 Reproducible output.** Generator metadata that changes between runs (generation dates,
  generator versions) is switched off in every generator call. Generated folders (`**/generated/**`)
  are excluded from Ruff and mypy in their config files, and from Xenon by an `--exclude` flag on
  the `clean-code` target in the `Makefile` (Xenon has no config file). `make check-generated` regenerates
  the toy library and the metamodel classes and fails on any difference; CI runs it.
- **PD-20 Boundary checks on code.** `docs/tools/check_docs.py` also scans `rdf_persistence/` and
  `tests/` for consumer terms, and `make check-quality` runs it. The end-to-end test uses
  `testkit.assert_public_imports(path)`, which parses a test file's imports with `ast` and fails on
  any `rdf_persistence.<sub>` import other than `rdf_persistence.testkit`.
- **PD-21 Shared metamodel classes.** `Principal` lives in `rp_core`, so `rp_access`,
  `rp_provenance`, `rp_tenancy` and `rp_files` can all use it; its `class_uri` is `prov:Agent`, with
  `odrl:Party` as an exact mapping. `TenantAccess` includes `Described`, so the tenant's label is
  the one `label` slot (`skos:prefLabel`); there is no `dcterms:title` slot in the metamodel.
- **PD-22 Importing the metamodel.** Application modules import metamodel modules as
  `rdf_persistence/model/<module>`. `generation/schema.py` has `load_schema(path)`, which opens a
  schema with `SchemaView` and an import map from that prefix to the installed package's `model/`
  folder. `rp-generate`, the mapper and the tests load schemas only through it; a unit test loads
  every toy library schema with it.
- **PD-23 What the hard and boundary checks cover.** The checks of tasks 1.6 and 1.7 apply to the
  classes the application's modules define. The metamodel's own classes are exempt (the toolkit's
  tests cover them), and so are an application class's slots and rules inherited from them; for
  example, `LibraryGrant` (`is_a: Grant`) needs no `Described`. Grants and prohibitions stay blank
  nodes. A class reached only by IRI (`Principal`, `Activity`) is a reference, not a part.
- **PD-11 Unlabelled classes.** Before running the generators, `rp-generate` gives every class
  annotated `rp_unlabelled: true` a `slot_usage` of `{label: {required: false}}`. The generated
  classes and shapes then agree, with no separate change to the shapes generator. In the same
  step it gives every aggregate root a `slot_usage` of `{description: {required: true}}`, as the
  rp-metamodel requirement asks (tests in tasks 1.6 and 1.8).
- **PD-12 Frames.** One JSON-LD frame per aggregate type nests owned parts under their root. It is
  generated in step 5 and placed beside the context.

### API

- **PD-13 Routes are tenant-scoped.**
  - Tenants: `/{tenant_segment}` (list mine, create) and `/{tenant_segment}/{t}` (read, delete),
    where `{t}` is the tenant IRI's UUID.
  - Aggregates: `/{tenant_segment}/{t}/{rp_path}` (list, create) and
    `/{tenant_segment}/{t}/{rp_path}/{id}` (read, replace, delete).
  - The consumer mounts the router under its own prefix. For the toy library this gives
    `/libraries/{t}/books/{id}`.
  - Tenant routes in detail:
    - `GET /{tenant_segment}`: the tenants where the caller has a grant (all, for a global `read`);
    - `POST /{tenant_segment}`: create a tenant, as in PD-9;
    - `GET` and `PUT /{tenant_segment}/{t}`: the tenant's root object (PD-8), with its `ETag`;
    - `DELETE /{tenant_segment}/{t}`: `If-Match` on the access record, action `delete`;
    - `GET` and `PUT /{tenant_segment}/{t}/grants`: the grant set, `If-Match` on the access record,
      action `administer`; `GET` returns the access record's `ETag`, which `DELETE` and `PUT …/label`
      use;
    - `PUT /{tenant_segment}/{t}/label`: the tenant's label in the access record, `If-Match` on the
      access record, action `modify`.
  - Bodies and construction:

    | Route | Request body | Response |
    |---|---|---|
    | `POST /{tenant_segment}` | `{"label": "…", "root": {…the tenant root's slots…}}` | 201, `Location`, `{"id", "label", "state"}` |
    | `PUT …/{t}/label` | `{"label": "…"}` | 200, new `ETag` |
    | `PUT …/{t}/grants` | `{"grants": [{"assignee", "target", "role" or "action"}], "prohibitions": [{"assignee", "target", "action"}]}` | 200, new `ETag`; 422 `invalid-body` on an unknown role or a duplicate key |
    | aggregate routes | the aggregate (PD-14) | the aggregate |

    The consumer's composition root calls
    `install_service(app, *, schema, store, files, identity, verifier, rules, settings, prefix="")`
    on its FastAPI app. It does three things:
    1. mounts the router;
    2. registers exception handlers that turn every toolkit error into a problem response
       (`application/problem+json`), so routes the consumer writes itself get the same answers
       (for example `InvalidGraph` → 422, `TenantGone` → 404, `IdentityUnavailable` → 503);
    3. adds a lifespan step that runs, before the app serves: create the system database if
       missing, then load and validate the role definitions, then the sweep.

    `settings` holds `base`, `prefix`, `tenant_segment`, `creator_role` and `roles_claim`. The
    JSON-LD context is served at `/context.jsonld` under the mount. Upload, graph loading and account
    administration are library calls for the consumer's own routes, not routes of the toolkit.

    Adapter constructors: `FusekiStore(url, user, password)`,
    `S3FileStore(endpoint, access_key_id, secret_access_key, region)`,
    `ZitadelIdentity(issuer, service_token, organisation_id, project_id)` (global roles are project-role
    grants),
    `JwksTokenVerifier(issuer, audience, roles_claim, *, jwks_uri=None, http_client=None)`: keys come
    from the issuer's OIDC discovery unless `jwks_uri` is given; the testkit passes an `http_client`
    that serves its in-memory JWKS.
- **PD-14 Body handling.**
  1. A JSON body is expanded with the generated context; a JSON-LD body is used as is. Either way it
     becomes triples whose root is the IRI from the path (on create, the minted IRI).
  2. The triples are validated against the type's shape.
  3. The session replaces the graph.
  4. The response is built from the stored graph: framed and compacted with the context for JSON
     and JSON-LD, serialised for Turtle.

  The generated classes are not used on this path (D-2). A replace whose body `id` differs from the
  path is refused (422 `invalid-body`).
- **PD-15 Problems and sorting.**
  - Problem `type` IRIs are `{base}problems/{slug}`, with these slugs: `invalid-token`, `forbidden`,
    `not-found`, `conflict`, `precondition-required`, `invalid-body`, `not-acceptable`,
    `unsupported-media-type`, `bad-query`, `unavailable`.
  - Each slug has a fixed `title`: "Invalid token", "Forbidden", "Not found", "Version
    conflict", "Precondition required", "Invalid body", "Not acceptable", "Unsupported media
    type", "Bad query", "Service unavailable".
  - Listings sort by IRI ascending unless `sort=<slot>` or `sort=-<slot>` is given.
  - Filters are query parameters `?<slot>=<value>`; repeated parameters on different slots combine
    with AND. `limit` defaults to 50 and is at most 200. `GET /{tenant_segment}` is paged the same
    way.
  - Cached JWKS keys are kept for 10 minutes; an unknown `kid` triggers one refresh.

### Tests

- **PD-16 Test containers.** `rdf_persistence/testkit/containers/compose.yaml` defines three
  containers:
  - **Fuseki**: built from Apache Jena's `jena-fuseki-docker` Dockerfile at the latest Jena 5.x
    release, pinned in task 0.4. Apache publishes the Dockerfile, not an image, so it is vendored in
    `rdf_persistence/testkit/containers/fuseki/`. A
    `shiro.ini` admits one test user, on every endpoint.
  - **Garage**, pinned by digest. The fixture bootstraps it with `garage layout assign`,
    `garage layout apply` and `garage key create`, through `docker exec`.
  - **Zitadel with Postgres**, pinned by digest. It starts with `ZITADEL_FIRSTINSTANCE_*`
    variables that create an admin machine user and write its personal access token to a mounted
    file. The fixture uses that token only to provision, through the management API:
    - a project with the roles `admin`, and an API application whose access-token type is *JWT*
      (Zitadel issues opaque tokens by default, which a JWKS check cannot verify);
    - one machine user per test principal (librarian, reader, outsider, admin), each with a key for
      the private-key JWT flow.

    Tests get tokens with the JWT-profile grant, requesting the scopes `openid`,
    `urn:zitadel:iam:org:project:id:{project}:aud` and
    `urn:zitadel:iam:org:projects:roles`, so the token carries the audience and the roles claim.
    No human user is needed: Zitadel has no password grant. Personal access tokens are opaque, so
    they are not supported in v1 (`access-control.adoc#identity`).

  Markers stay assigned by path in `tests/conftest.py`. Its hook is rewritten to apply every marker
  of a directory's row, not only the first:

  | Directory | Markers |
  |---|---|
  | `tests/unit/`, `tests/feature/` | `unit` / `feature` |
  | `tests/integration/store/`, `tests/integration/api/` | `integration`, `store` |
  | `tests/integration/tenancy/` | `integration`, `store`, `files` |
  | `tests/integration/files/` | `integration`, `files` |
  | `tests/integration/identity/` | `integration`, `identity` |
  | `tests/e2e/` | `e2e`, `store`, `files`, `identity` |

  The fixtures in `rdf_persistence/testkit/containers/` start the containers a marker needs. That
  folder ships as package data with the compose file and the vendored Fuseki Dockerfile, so
  consumers get the same fixtures. It is imported lazily and needs the extra
  `rdf-persistence[testkit]` (`testcontainers`); without it, importing the fixtures raises an
  error that names the extra. The marker names live in `rdf_persistence/testkit/markers.py`, which
  needs no extra; the fixtures plugin registers them, and only `tests/integration/` and `tests/e2e/`
  load the plugin, so the unit lane runs without `testcontainers`.
  - `make test` runs `unit or feature` with the 80% coverage floor. `.coveragerc` omits
    `rdf_persistence/adapters/*` and `rdf_persistence/testkit/containers/*` from that floor.
  - `make test-containers` runs `integration or e2e` with `--cov-fail-under=0`, reporting coverage
    without a floor, in a separate CI job.
  - The tenancy tests take the file store from a parametrised fixture: the fake in stage 2, and
    Garage added as a second parameter in task 3.1.
  - The router's unit tests use the fake session, and the session and tenancy logic also get unit
    tests on the fake store, so they count toward the floor.
  - A new CI workflow runs on changes under `docs/**` (which the main workflow ignores): it runs
    `make check-docs` and the Antora build.
- **PD-17 The toy library.** `tests/fixtures/library/` holds:
  - `library.yaml`, the root schema;
  - three domain modules: `library_tenant` (`Library`, the tenant root), `books` (`Book` with owned
    `Chapter`, which owns `Note` and is marked `rp_unlabelled`) and `scans` (`Scan`, with
    `StoredFile`);
  - `library_access.yaml` (`module_kind: access`), with `library_roles.yaml` holding the role
    definitions of PD-9's matrix;
  - `partial.yaml`, a schema importing only `rp_core` and `rp_annotations`;
  - a `pyproject.toml` fragment with the `[tool.rp-generate]` table.

  Its generated output is committed under `tests/fixtures/library/generated/`, and CI checks it is
  fresh.

## Algorithm / approach

### Stage order and what each stage proves

| Stage | Builds | Proven by |
|---|---|---|
| 0 Ground | layer contract, dependencies, toy library, containers | `make check-quality`; container smoke tests |
| 1 Metamodel and generation | six modules; `rp-generate` with checks, seven steps and placement | the toy library generates; planted faults fail, naming the element |
| 2 Store, session, tenancy | store port and Fuseki adapter, session, registry, loading, mapper, tenancy, sweep | integration tests against Fuseki |
| 3 Files and identity | file store and S3 adapter, token verification, identity port and Zitadel adapter | integration tests against Garage and Zitadel |
| 4 Access | permission loading and the check | the role-matrix test |
| 5 Service kit and router | router, negotiation, ETags, problems, listing, OpenAPI | the end-to-end test |

### Worked example: a guarded commit

The session holds `<g>` = `graph_iri(<b>)`, the version `"7f3a…"` it read, and the tracking
statements read with it (`created`, `creator <p0>`, contributors). The new token is
`"c91e…"`, a fresh UUID. It sends one update:

```sparql
DELETE { GRAPH <g> { ?s ?p ?o } . GRAPH <registry> { ?e ?ep ?eo } }
INSERT { GRAPH <g> { …new triples…
                     <g> rp:version "c91e…" ; dcterms:modified "…"^^xsd:dateTime ;
                         dcterms:created "…" ; dcterms:creator <p0> ; dcterms:contributor <p1>, <p> }
         GRAPH <registry> { …entries for <g> and its loaded graphs… } }
WHERE  { GRAPH <g> { <g> rp:version "7f3a…" . ?s ?p ?o }
         OPTIONAL { GRAPH <registry> { ?e rp:ownedBy <b> ; ?ep ?eo } } }
```

It then asks `ASK { GRAPH <g> { <g> rp:version "c91e…" } }`. True means the commit happened.
False means a conflict: Fuseki answers 204 even when `WHERE` matched nothing. A new aggregate uses
`INSERT DATA`, after an `ASK` that `<g>` does not exist. Random IRIs make a race on the same new IRI
practically impossible.

### Worked example: `PUT /libraries/{t}/books/{id}` with `If-Match: "7f3a…"`

1. The `TokenVerifier` gives principal `<p>` and global roles `[]`. The route declares `modify`.
2. The access check loads, in one query, the grants and prohibitions of `<p>` in tenant `<t>`'s
   access record, then applies PD-9's rules in order:
   - a tenant that is not `active` means 404;
   - a Prohibition on `modify` for the tenant or for `graph_iri(<book>)` means 403;
   - no tenant grant, no permission on the book and no global role a role definition allows means
     404;
   - a role definition of one of `<p>`'s tenant roles, or a direct permission on the book, that
     permits `modify` (or an action implying it) means allow;
   - otherwise 403.
3. The body is expanded and validated (PD-14), then the session commits under `"7f3a…"`.
4. The response is 200 with `ETag: "c91e…"`.

### Idempotency and retries

- **Commits** are not blindly retryable. A replay after a lost response gets 409, because the
  version has moved; the client re-reads.
- **Tenant creation** writes the access record last. A retry after a failure creates a new tenant,
  and the sweep removes the orphan.
- **Tenant deletion** is idempotent: a `deleting` record is finished by any later attempt, or by the
  sweep.
- **Blob puts** use a fresh key each time, so a retry leaves at most an orphan, erased with its
  tenant.
- **`rp-generate`** writes to temporary files and moves them into place on success, so it is safe to
  re-run.

### Anti-patterns

| Don't | Do instead | Why |
|---|---|---|
| Format SPARQL with f-strings | `fill()` with `term()` (PD-3) | Injection; one place to audit |
| Use the root IRI as a graph name | `graph_iri()` (PD-4) | DEC-29 |
| Use a counter as the version | A fresh UUID per commit (PD-5) | A counter gives false successes |
| Accept client-sent IRIs on create | Mint them (PD-6) | IRIs stay in the toolkit's namespace |
| Generate routes or repositories | The generic router reads `SchemaView` at run time | O-1, D-1 |
| Use generated classes in the router | Context, frame and shapes (PD-14) | D-2 |
| Import an adapter in `services`, `domain` or `entrypoints` | Depend on the port; the consumer wires the adapter | PD-1 |
| Mock Fuseki, Garage or Zitadel in integration tests | Containers (PD-16) | DEC-4 |
| Edit generated files | Change the schema or template; regenerate | Freshness check (PD-26) |
| Hand-write a model, shape, context or API schema | Declare it in LinkML; extend a generator if needed | PD-24, PD-28 guards |
| Put a consumer term in code, tests or architecture pages | Toy library terms | `rp-package-boundaries` |
| Add a login endpoint | The provider's flows | D-10 |

## Error matrix

| Failure mode | How it is detected | Expected handling |
|---|---|---|
| Stale `If-Match`, or the guard matched nothing | `ASK` for the new token is false | `Conflict` → 409 `conflict`; nothing changed |
| `If-Match` missing on update or delete | Service kit | 428 `precondition-required` |
| Unknown tenant, type or id | Router, session | 404 `not-found` |
| Body fails the shape, or a client sent an IRI on create | pySHACL report; router | 422 `invalid-body` with the report's messages |
| `Accept` not JSON, JSON-LD or Turtle | Router | 406 `not-acceptable` |
| `Content-Type` not JSON or JSON-LD | Router | 415 `unsupported-media-type` |
| Unknown filter slot, bad `limit`/`offset`, or unknown sort slot | Router | 400 `bad-query` |
| RDF file does not parse | rdflib | 422 `invalid-body` with the parser's message; no graph |
| Token missing, expired, wrong issuer or audience, or bad signature | `TokenVerifier` | 401 `invalid-token`; the JWKS is refreshed once on an unknown `kid` |
| The provider's JWKS is unreachable | httpx error | 503 `unavailable` once cached keys expire; until then, cached keys |
| Caller not permitted | Access check | 403 `forbidden`, or 404 `not-found` with no grant or an inactive tenant |
| The store is unreachable or answers 5xx | httpx error | 503 `unavailable`; no retry inside the request |
| The tenant database is gone mid-request (Fuseki 405) | Store adapter | `DatabaseGone` → 404 `not-found` |
| The object store is unreachable | botocore error | 503 `unavailable`; metadata not committed (blob before metadata) |
| Put into a missing bucket | `NoSuchBucket` | `TenantGone` → 404; no bucket created |
| Crash between tenant steps | Start-up sweep | Finish `deleting`; drop unnamed databases and buckets |
| Role definitions file invalid | Validation at start-up | The service refuses to start, naming the entry |
| `PUT …/grants` with an unknown role or a duplicate key | Validation against `rp_access` | 422 `invalid-body`; the access record is unchanged |
| The identity provider's management API is unreachable or answers 5xx | httpx error in the Zitadel adapter | `IdentityUnavailable` → 503 `unavailable` |
| No account for an email | Zitadel adapter | `NotFound` → 404 `not-found` |
| Schema fails the hard or boundary check | `rp-generate` | Exit 1, naming each element; outputs untouched |
| Generated output stale | `rp-generate --check` (manifest), at session start, in `check-quality`, pre-commit; CI regenerates and diffs | Exit 1 naming the stale files and `make generate` |
| Generated output edited by hand | Output hash differs from the manifest | Exit 1 naming the edited files |
| Generated classes and shapes disagree on a constraint | Conformance suite (PD-27) | Test fails naming the constraint case |
| A LinkML bump breaks an extension | Extension tests on the toy schema | Fix the extension, or hold the pin |

## Risks / Trade-offs

- [pySHACL on every write is slow] → Toy-sized aggregates; the parsed shapes graph is cached. If one
  write in the end-to-end test exceeds 200 ms, record it in `api.adoc` as a finding.
- [Framing nested owned parts grows complex] → One generated frame per type (PD-12), tested on
  `Book → Chapter → Note`.
- [Zitadel is heavy in CI] → Only the identity suite and the end-to-end suite need it (PD-16), in
  the container job.
- [Generator extensions break on LinkML releases] → Exact pins (PD-2) and extension tests.
- [The filter grammar grows] → Equality, `limit`, `offset` and one sort key (EPIC rabbit-hole).

## Open Questions

None. One choice is left to a task, and its outcome is recorded in the architecture: whether
linkml-openapi can replace the OpenAPI hook (spike 5.6).
