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
- documentation changes beyond those that tasks 6.1 and 6.2 name.

## Decisions

New choices made while planning. Settled decisions are cited, not restated: EPIC DEC-1..DEC-6 and
architecture D-1..D-12, O-1 and O-2.

### Layers and dependencies

- **PD-1 The layer contract.**
  - The scaffold orders the layers `entrypoints > services > adapters > domain`. The architecture puts
    ports in `services` and their implementations in `adapters`.
  - The contract becomes `entrypoints | adapters > services > domain`. `entrypoints` and `adapters`
    are independent siblings: neither imports the other.
  - The service kit needs token verification. It depends on the `TokenVerifier` port, which lives in
    `services`. The JWKS-based implementation, `JwksTokenVerifier`, is an adapter, and the consumer's
    composition root wires it in. The public API table in `index.adoc` is updated to match.
  - `generation` and `testkit` sit outside the contract. The top-level `__init__.py` re-exports the
    public names.
  - A second contract forbids `domain` from importing `httpx`, `boto3`, `fastapi`, `jwt` and
    `pyshacl`. It sets `include_external_packages = True`.
- **PD-2 Dependencies (DEC-5).**
  - Runtime pins (`==`): `linkml-runtime`, `rdflib`, `pyld`, `pyshacl`, `pydantic`, `httpx`,
    `fastapi`, `pyjwt[crypto]`, `boto3`, `anyio`.
  - An optional extra, `rdf-persistence[generate]`, brings `linkml==1.12.1`, so consumers' running
    services do not install the generators. `linkml-runtime` is pinned to the version that `linkml`
    1.12.1 resolves to in `uv.lock`.
  - `linkml==1.10.0` leaves the dev group.
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
- **PD-7 Tracking on update.** `dcterms:created` and `dcterms:creator` are written by the first
  commit and kept. Every later commit replaces `dcterms:modified` and adds the committer to
  `dcterms:contributor`. All of these are statements about the graph IRI (D-7).
- **PD-8 The registry in the commit.** The commit's update also deletes and inserts the aggregate's
  registry entries: its own graph and its loaded graphs. A tenant's root object lives in the
  designated `meta` graph and has no registry entry.

### Access

- **PD-9 Where access data lives.**
  - **Grants, per-aggregate Permissions and Prohibitions** are owned parts of the tenant's access
    record, in its graph in the system database. They are therefore read in one query per request
    and changed by one guarded commit.
  - **Role definitions** are the consumer's data, not stored data. They are instances of
    `RoleDefinition` in a YAML file beside the consumer's access module, validated against
    `rp_access` at start-up and held in memory.
  - **Global roles** come from a configurable token claim. The default is Zitadel's
    `urn:zitadel:iam:org:project:roles`, an object keyed by role name.
  - The toy library's roles are `librarian` and `reader` per library, plus the global role `admin`.
- **PD-10 Grant slots.** A `Grant` is an `odrl:Permission` with:
  - `assignee` (`odrl:assignee`): a `Principal`;
  - `target` (`odrl:target`): the tenant IRI, or an aggregate's graph IRI;
  - `role` (`rp:role`) for a role grant, or `action` (`odrl:action`) for a direct permission;
    exactly one of the two.

  `generation.adoc`'s slot table is updated: `rp:principal` becomes `odrl:assignee`.

### Generation

- **PD-11 Unlabelled classes.** Before running the generators, `rp-generate` gives every class
  annotated `rp_unlabelled: true` a `slot_usage` of `{label: {required: false}}`. The generated
  classes and shapes then agree, with no separate change to the shapes generator.
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
- **PD-14 Body handling.**
  1. A JSON body is expanded with the generated context; a JSON-LD body is used as is. Either way it
     becomes triples whose root is the IRI from the path (on create, the minted IRI).
  2. The triples are validated against the type's shape.
  3. The session replaces the graph.
  4. The response is built from the stored graph: framed and compacted with the context for JSON
     and JSON-LD, serialised for Turtle.

  The generated classes are not used on this path (D-2).
- **PD-15 Problems and sorting.**
  - Problem `type` IRIs are `{base}problems/{slug}`, with these slugs: `invalid-token`, `forbidden`,
    `not-found`, `conflict`, `precondition-required`, `invalid-body`, `not-acceptable`,
    `unsupported-media-type`, `bad-query`, `unavailable`.
  - Listings sort by IRI ascending unless `sort=<slot>` or `sort=-<slot>` is given.

### Tests

- **PD-16 Test containers.** `tests/containers/compose.yaml` defines three containers:
  - **Fuseki**: built from Apache Jena's `jena-fuseki-docker` Dockerfile at the latest Jena 5.x
    release, pinned in task 0.4. Apache publishes the Dockerfile, not an image, so it is vendored in `tests/containers/fuseki/`. A
    `shiro.ini` admits one test user, on every endpoint.
  - **Garage**, pinned by digest. The fixture bootstraps it with `garage layout assign`,
    `garage layout apply` and `garage key create`, through `docker exec`.
  - **Zitadel with Postgres**, pinned by digest. It starts with `ZITADEL_FIRSTINSTANCE_*`
    variables that create an admin machine user and write its personal access token to a mounted
    file. The fixture provisions a project, roles, one service account and two human users through
    the API.

  The fixtures in `testkit/containers.py` start only the containers a test's marker needs (`store`,
  `files`, `identity`, `e2e`). The markers are registered in `pytest.ini`. `make test` excludes
  them; `make test-containers` runs them, in a separate CI job.
- **PD-17 The toy library.** `tests/fixtures/library/` holds:
  - `library.yaml`, the root schema;
  - three domain modules: `library_tenant` (`Library`, the tenant root), `books` (`Book` with owned
    `Chapter`, which owns `Note` and is marked `rp_unlabelled`) and `scans` (`Scan`, with
    `StoredFile`);
  - `library_access.yaml` (`module_kind: access`), with `library_roles.yaml` holding the role
    definitions;
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

The session holds `<g>` = `graph_iri(<b>)` and the version `"7f3a…"` it read. The new token is
`"c91e…"`, a fresh UUID. It sends one update:

```sparql
DELETE { GRAPH <g> { ?s ?p ?o } . GRAPH <registry> { ?e ?ep ?eo } }
INSERT { GRAPH <g> { …new triples…
                     <g> rp:version "c91e…" ; dcterms:modified "…"^^xsd:dateTime ;
                         dcterms:created "…" ; dcterms:creator <p0> ; dcterms:contributor <p> }
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
2. The access check loads, in one query, the permissions and prohibitions of `<p>` in tenant `<t>`'s
   access record:
   - a Prohibition on `modify` for the tenant or for `graph_iri(<book>)` means 403;
   - no grant in the tenant, and no permission on the book, means 404;
   - otherwise, if a role definition of one of `<p>`'s roles permits `modify` at the matching
     level, or a direct permission does, the request is allowed; if not, 403.
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
| Edit generated files | Change the schema or template; regenerate | Freshness check |
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
| Schema fails the hard or boundary check | `rp-generate` | Exit 1, naming each element; outputs untouched |
| Generated output stale | CI regenerates and diffs | CI fails |
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
