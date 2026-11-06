<!-- Parents: rdf-persistence architecture v1 with its decisions of 2026-11-05
     (docs/modules/ROOT/pages/architecture/: index, generation, api, access-control,
     open-decisions D-1..D-12); background decisions DEC-1..DEC-39 (archived change
     2026-11-05-soa-python-rdf-orm). Consumer need: the first consumer's architecture v1 maps its
     decisions and use cases to needs N-1..N-11. Seeds: inputs/seed-brief.md. -->

# EPIC: Toolkit v1 foundation

## Appetite

**VERY LARGE.** The whole of architecture v1, from the metamodel to a served API, built in an empty
package. It is delivered in five stages, and each stage leaves `develop` usable by a consumer. If it
outgrows this, stages 4 and 5 become their own EPIC (see Rabbit-holes).

## Why

Architecture v1 of rdf-persistence was decided on 2026-11-05, but the package is an empty scaffold.
The first consumer cannot start its own first iteration until the toolkit can turn a LinkML model
into code, store aggregates in Fuseki, keep files, check tokens and access, and serve the model over
an API.

## Solution outline

When this EPIC is done, an application can do four things:
- write a LinkML model and run `rp-generate`;
- get Python classes, TypeScript types, shapes, a JSON-LD context and diagrams, each in the package
  that uses it;
- wire the toolkit's adapters in a composition root;
- serve its aggregates over one generic API, with versioned writes and per-aggregate access control.

Signed-in users and programs reach the API through the identity provider's own flows.

Five stages, in order. Each ends with tests green and the stage merged to `develop`.

1. **Metamodel and generation.**
   - The metamodel as six LinkML modules: core, annotations, provenance, access, tenancy and files.
   - `rp-generate`:
     - lint, the hard check (IRIs, labels, definitions), and the boundary check (aggregates and
       module kinds);
     - the generators, extended where needed: Python classes, shapes, JSON-LD context, TypeScript
       types and Mermaid diagrams;
     - output placed by a `[tool.rp-generate]` table.
   - Proven on a toy library domain.
2. **Store, session and tenancy.**
   - The Fuseki store adapter.
   - The aggregate session: one named graph per aggregate at `graph_iri(root)`, a guarded commit
     with an `ASK`, and the version and tracking statements about the graph IRI.
   - The registry, graph loading, and the mapper for domain services.
   - Tenancy: the system database, access records, lifecycle and the start-up sweep.
3. **Files and identity.**
   - The S3 file store adapter, tested against Garage.
   - Token validation against the provider's published keys.
   - The identity port and its Zitadel adapter.
4. **Access.**
   - The ODRL subset evaluated in process: permissions, prohibitions and role definitions.
   - Checks per tenant and per aggregate.
5. **Service kit and generic router.**
   - Routes driven by the schema at run time.
   - Plain JSON by default, JSON-LD and Turtle by content negotiation.
   - `ETag`/`If-Match`, problem responses, listings with equality filters and paging.
   - Body validation with the shapes, and the OpenAPI document from a hook over the schema.

The **test kit** grows with each stage: fakes of every port, a token signer, and container fixtures.
The EPIC is proven when the toy library is served end to end, against real containers, through the
permission matrix of its roles.

## Key decisions

Decisions of the architecture, D-1 to D-12 and O-1, O-2, are binding here and not restated. See
`docs/modules/ROOT/pages/architecture/open-decisions.adoc`. This EPIC adds:

- **DEC-1**: The scope is architecture v1 as revised on 2026-11-05. Nothing in this EPIC changes it.
  A finding that contradicts the architecture changes the architecture page first (Rule of
  Divergence). Rejected: adjusting the design inside the code.
- **DEC-2**: The toy library domain (library tenants, books with owned chapters, scans as files,
  `librarian` and `reader` roles) is the only domain in this repository. It is the fixture for every
  stage, from unit tests to the end-to-end test. Rejected: testing against the first consumer's
  model, which would break the boundary.
- **DEC-3**: Stages are delivered in order, each one merged to `develop` with its tests green, so the
  consumer can start on stage 1 while stage 2 is built. Rejected: one large merge at the end.
- **DEC-4**: Tests come in three kinds:
  - unit tests run on the test kit, with no servers;
  - integration tests run each adapter against its real container: Fuseki, Garage, and Zitadel
    where its API is used;
  - one end-to-end test runs the toy library over the API.

  Rejected: mocking a store or a provider in the integration tests.
- **DEC-5**: The toolkit's own dependencies are chosen in the PLAN. One rule is fixed now: `linkml`
  and `linkml-runtime` are pinned together, and any bump regenerates the toy library and reviews the
  diff. Rejected: unpinned generator versions.
- **DEC-6**: Each public name lands with its stage. A consumer imports only the top-level
  `rdf_persistence` names (and `rdf_persistence.testkit` for tests), as listed in the architecture's
  public API.

## Rabbit-holes

- **The filter grammar.** Equality filters, paging and a sort key only. No query language.
- **Nested owned parts in JSON-LD.** Compacting and framing a graph with blank nodes into nested JSON
  can grow. Keep one frame per aggregate type, generated from the schema, and nothing else.
- **LinkML internals.** The TypeScript and SHACL extensions subclass generator internals. Keep each
  extension small, tested on the toy schema, and behind the version pin.
- **SPARQL built from input.** Values are always bound or escaped by one function, never
  concatenated. One test per query template tries an injection.
- **The provider's administration API.** Implement only what need N-7 lists: find by exact email,
  list, disable, re-enable, and grant or remove a global role.
- **Stage growth.** If stage 4 or 5 does not fit, split them into their own EPIC, as a logged
  re-shape. Do not cut the end-to-end proof.

## No-gos

- GraphQL (the API's backup option C), OpenFGA, and property- or triple-level access: all deferred by
  the architecture.
- A second store (Oxigraph, Virtuoso), the outbox, events and server-sent events, schema migrations,
  and forms from shapes.
- A login endpoint of our own, and token exchange.
- Any consumer term, model or code in this repository.
- Publishing to a package index or versioned releases: consumers install `develop`.
- A user interface. The TypeScript types are generated, but no frontend is built here.

---

## What Changes

- `rdf_persistence/model/`: the metamodel modules `rp_core`, `rp_annotations`, `rp_provenance`,
  `rp_access`, `rp_tenancy`, `rp_files`, and `rp.yaml`.
- `rdf_persistence/generation/`: the `rp-generate` command, the hard check, the boundary check, the
  generator extensions and output placement.
- `rdf_persistence/domain/`, `services/`, `adapters/`, `entrypoints/`: the session, mapper, registry,
  graph loading, tenancy, access check, ports, adapters (Fuseki, S3, Zitadel, token validation), the
  service kit and the generic router.
- `rdf_persistence/testkit/`: fakes, a token signer and container fixtures.
- `tests/`: the toy library model and the unit, integration and end-to-end suites.
- `pyproject.toml`, the compose file for test containers, CI jobs for the container suites.
- `docs/`: the architecture pages updated where implementation teaches something, and a how-to for
  adopting the toolkit.

## Capabilities

### New Capabilities

- `rp-metamodel`: the metamodel modules and the rules an application model must follow.
- `rp-generation`: `rp-generate`, covering checks, generators, extensions and output placement.
- `rp-aggregate-store`: the store port and its Fuseki adapter, the aggregate session with guarded
  commits, the registry, graph loading, and the mapper.
- `rp-tenancy`: the system database, access records, lifecycle and the sweep.
- `rp-file-store`: the file store port and its S3 adapter.
- `rp-identity`: token validation, the identity port and its Zitadel adapter.
- `rp-access`: the ODRL subset and the access check.
- `rp-service-api`: the service kit, the generic router, content negotiation and the OpenAPI hook.
- `rp-testkit`: fakes, the token signer and container fixtures for consumers' tests.
- `rp-package-boundaries`: no consumer dependency or terms, layers import downward, consumers use the public API only. Added while deriving the PLAN: it was drafted in the first consumer's architecture change and moves here by D-12.

### Modified Capabilities

None; `openspec/specs/` holds no toolkit capability yet.

## Impact

- The package gains its runtime dependencies (chosen in the PLAN; `linkml` pinned).
- CI gains jobs that start containers (Fuseki, Garage, Zitadel).
- The first consumer can start building after stage 1, and serve its API after stage 5.
