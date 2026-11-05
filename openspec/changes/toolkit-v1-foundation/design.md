> Derives from: EPIC `toolkit-v1-foundation` ([proposal.md](proposal.md)) · Type: implementation

## Context

The package `rdf_persistence` is the uv scaffold. It has empty `domain/`, `services/`,
`adapters/` and `commons/` packages, a smoke test, an import-linter contract, CI (Ruff, mypy,
import-linter, OpenSpec, pytest, Xenon) and `testcontainers` in the test group. The architecture
it implements is in `docs/modules/ROOT/pages/architecture/`:

- `index.adoc`: needs N-1..N-11, the building blocks and the public API with its layer map.
- `generation.adoc`: the metamodel and `rp-generate`.
- `api.adoc`: the generic router.
- `access-control.adoc`: the ODRL check and identity.
- `open-decisions.adoc`: D-1..D-12.

The generation steps 1–4 and Fuseki's behaviour were proven in a spike (LinkML 1.12.1, Fuseki
5.1.0). The spike's evidence lives in the first consumer's repository and is summarised in
`generation.adoc` (_(spike)_ marks).

## Goals / Non-Goals

**Goals:** the nine capabilities of the EPIC, plus `rp-package-boundaries`. Each lands in its stage
with its tests (DEC-3, DEC-4), ending in the end-to-end proof on the toy library (DEC-2).

**Non-Goals:** the EPIC's no-gos. Also excluded: performance tuning beyond the toy library, a
command-line tool other than `rp-generate`, and any documentation site change except what a task
names.

## Decisions

New choices made while planning. Settled decisions are cited, not restated: EPIC DEC-1..DEC-6 and
architecture D-1..D-12, O-1, O-2.

- **PD-1 Layer contract.** The scaffold's import-linter contract orders the layers
  `entrypoints > services > adapters > domain`, so services could import adapters. The architecture
  says otherwise: ports live in services, and adapters implement them. The contract is rewritten to
  `entrypoints | adapters > services > domain`, with `entrypoints` and `adapters` as independent
  siblings. `generation` and `testkit` sit outside the contract and may import any layer; the
  top-level `__init__.py` re-exports the public names. A second contract forbids `domain` from
  importing `rdflib.plugins.stores`, `httpx`, `boto3`, `fastapi` and `jwt`.
- **PD-2 Dependencies (DEC-5).**
  - Runtime: `linkml-runtime`, `rdflib`, `pyld`, `pyshacl`, `pydantic`, `httpx`, `fastapi`,
    `pyjwt[crypto]` and `boto3`.
  - Build-time: an optional extra `rdf-persistence[generate]` with `linkml`, so consumers' running
    services do not install the generators.
  - `linkml` and `linkml-runtime` are both pinned to 1.12.x, with exact `==` pins as the scaffold
    requires. `linkml==1.10.0` leaves the dev group.
  - Rejected: `aioboto3` (a second S3 stack to track); the async service runs `boto3` calls in a
    worker thread (`anyio.to_thread`).
- **PD-3 One SPARQL value function.** `domain/sparql.py` holds `term(value) -> str` for IRIs,
  literals with datatype or language, and blank nodes. Every query template in `adapters` is a
  constant with `$name` placeholders, filled by `fill(template, **terms)`. Nothing else may
  produce SPARQL text (rp-aggregate-store, "SPARQL is never built…").
- **PD-4 Graph IRI function.** `graph_iri(root_iri) = root_iri + "/graph"`. It is the only place the
  rule lives; the session, the registry, the access check and the shapes use it. Changing the rule
  after data exists is a migration (DEC-29).
- **PD-5 Body handling in the router.** The incoming body is processed in four steps:
  1. A JSON body is expanded with the generated context, a JSON-LD body as is, to triples, with the
     IRI from the path as the root.
  2. The triples are validated against the type's shape.
  3. The session replaces the graph.
  4. The response is built from the stored graph: compacted with the context for JSON, compacted
     as is for JSON-LD, serialised for Turtle.

  The generated Python classes are not used on this path (D-2).
- **PD-6 Frames.** One JSON-LD frame per aggregate type nests owned parts (blank nodes) under
  their root. It is generated in step 5 (`gen-jsonld-context --emit-frame` plus the toolkit's
  extension) and placed beside the context.
- **PD-7 Test containers.** A compose file `tests/containers/compose.yaml` defines Fuseki 5.x (the
  Apache image, pinned by digest), Garage (pinned, single node) and Zitadel with Postgres (pinned).
  Fixtures in `testkit/containers.py` start only what a test marks (`@pytest.mark.store`, `files`,
  `identity`). CI runs the integration and end-to-end suites in a separate job.
- **PD-8 Toy library.** It lives in `tests/fixtures/library/`: `library.yaml` (root), three domain
  modules (`library_tenant`, `books`, `scans`), `library_access.yaml`, and a `pyproject.toml`
  fragment with the `[tool.rp-generate]` table. Its generated output is committed under
  `tests/fixtures/library/generated/`, and CI checks it is fresh.
- **PD-9 Zitadel in tests.** The identity port's integration test provisions a project, a machine
  user and two human users through Zitadel's API at fixture start. The service kit's own tests use
  the testkit's token signer and a JWKS served from memory, so only the identity-port suite needs
  Zitadel.

## Algorithm / approach

### Stage order and what each stage proves

| Stage | Builds | Proven by |
|---|---|---|
| 1 Metamodel and generation | six metamodel modules; `rp-generate` (lint, hard check, boundary check, seven steps, placement) | the toy library generates; planted faults fail with named elements |
| 2 Store, session, tenancy | store port, Fuseki adapter, session, registry, graph loading, mapper, tenancy and sweep | integration tests against Fuseki: commit, conflict, load, create/delete tenant, sweep |
| 3 Files and identity | file store port and S3 adapter, token validation, identity port and Zitadel adapter | integration tests against Garage and Zitadel |
| 4 Access | ODRL evaluation and the check | unit tests over the role matrix of the toy library |
| 5 Service kit and router | router, content negotiation, ETags, problems, listing, OpenAPI hook | the end-to-end test |

### Worked example: a guarded commit

The session holds the graph IRI `<g>` = `graph_iri(<b>)` and the version `v7` it read. The commit
sends one update:

```sparql
DELETE { GRAPH <g> { ?s ?p ?o } }
INSERT { GRAPH <g> { …new triples… <g> rp:version "v8" ; dcterms:modified "…"^^xsd:dateTime ; dcterms:creator <principal> } }
WHERE  { GRAPH <g> { <g> rp:version "v7" . ?s ?p ?o } }
```

It then sends `ASK { GRAPH <g> { <g> rp:version "v8" } }`. True means the commit happened. False
means a conflict: Fuseki answers 204 even when `WHERE` matched nothing. A new aggregate uses
`INSERT DATA`, guarded by `ASK` that `<g>` does not exist first. A race on the same new IRI cannot
occur, because IRIs are random UUIDs.

### Worked example: the access check for `PUT /books/{id}`

1. The route declares `modify`. The token gives principal `<p>` and global roles `[]`.
2. A `Prohibition` with assignee `<p>`, action `modify` and a target matching the book's scope
   means 403.
3. No `Permission` of `<p>` on the tenant scope and none on `graph_iri(<book>)` means 404.
4. Otherwise, collect the roles from those permissions and look up `RoleDefinition`s: if any role
   permits `modify` at the matching level, allow; else 403.

The permissions of one caller in one tenant are read in one query against the system database and
cached for the request only.

### Idempotency and retries

- **Commits** are not blindly retryable. A replay after a lost response gets 409, because the
  version has moved; the client re-reads the aggregate.
- **Tenant creation** writes the access record last. A retry after a failure creates a new tenant,
  and the sweep removes the orphan.
- **Tenant deletion** is idempotent: `deleting` records are finished by any later attempt or by
  the sweep.
- **Blob puts** use a fresh random key each time, so a retry leaves at most an orphan blob, erased
  with its tenant.
- **`rp-generate`** writes to temporary files and moves them into place only on success, so it is
  safe to re-run.

### Anti-patterns

| Don't | Do instead | Why |
|---|---|---|
| Format SPARQL with f-strings | `fill(template, …)` with `term()` (PD-3) | Injection; one place to audit |
| Use the root IRI as a graph name | `graph_iri()` (PD-4) | DEC-29 |
| Generate routes or repositories | The generic router reads `SchemaView` at run time | O-1, D-1 |
| Use generated classes in the router | Context + shapes (PD-5) | D-2 |
| Import an adapter in `services` or `domain` | Depend on the port; the consumer wires the adapter | PD-1 |
| Mock Fuseki, Garage or Zitadel in integration tests | Containers (PD-7) | DEC-4 |
| Edit generated files | Change the schema or the template; regenerate | Freshness check |
| Put a consumer term in code, tests or architecture docs | Toy library terms | `rp-package-boundaries` |
| Add a login endpoint | The provider's flows | D-10 |

## Error matrix

| Failure mode | How it is detected | Expected handling |
|---|---|---|
| Stale `If-Match` / guard matched nothing | `ASK` for the new version is false | `Conflict` → 409 problem; nothing changed |
| `If-Match` missing on update or delete | Service kit dependency | 428 problem |
| Body fails the shape | pySHACL report | 422 problem, with the report's messages |
| RDF file does not parse | rdflib parser error | 422 problem, with the parser's message; no graph created |
| Token missing, expired, wrong issuer or audience, bad signature | PyJWT validation against cached JWKS | 401 problem; the JWKS is refreshed once on an unknown `kid` |
| Provider's JWKS unreachable | httpx error on refresh | 503 problem; cached keys are used while still valid |
| Caller not permitted | Access check | 403, or 404 when there is no grant or the tenant is not active |
| Store unreachable or 5xx | httpx error | 503 problem; no retry inside the request |
| Tenant database gone mid-request (405 from Fuseki) | Store adapter maps 405 on a dataset path | `DatabaseGone` → 404 |
| Object store unreachable | botocore error | 503 problem; metadata not committed (blob first, ADR invariant) |
| Put into a missing bucket | `NoSuchBucket` | `TenantGone` → 404; no bucket created |
| Crash between tenant steps | Start-up sweep | Finish `deleting`; drop unnamed databases and buckets |
| Schema fails the hard or boundary check | `rp-generate` | Exit 1, naming each element; outputs untouched |
| Generated output stale in CI | Regenerate and diff | CI fails |
| LinkML bump changes generator internals | Extension tests on the toy schema | Fix the extension or hold the pin |

## Risks / Trade-offs

- [pySHACL on every write is slow for large aggregates] → Toy-sized aggregates in v1. Measure in
  the end-to-end test; if one write exceeds 200 ms, validate only the changed aggregate's shape
  (already the case) and cache the parsed shapes graph.
- [JSON-LD framing of owned parts grows complex] → One generated frame per type (PD-6); nested
  owned parts deeper than one level are covered by a toy-library test (`Book → Chapter → Note`).
- [Zitadel's container is heavy for CI] → Only the identity-port suite needs it (PD-9). It runs in
  the integration job, not on every unit run.
- [Generator extensions break on LinkML minor releases] → Exact pins (PD-2) and extension tests.
- [The filter grammar grows] → Equality, `limit`, `offset` and one sort key only (EPIC
  rabbit-hole).

## Open Questions

None blocking. Two choices are made in a task, with the outcome recorded in that task's PR and in
the architecture page it touches:

- the exact container images (pinned by digest in 3.1 and 2.1);
- whether linkml-openapi can replace the OpenAPI hook (spike 5.6).
