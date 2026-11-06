<!-- Parents: openspec/specs/rp-service-api ("The contract is published"); openspec/specs/rp-generation
     ("LinkML is the single source of every model artefact"); docs/modules/ROOT/pages/architecture/api.adoc
     (the path table: client code uses the generated TypeScript types). Seeds: inputs/seed.md. -->

# EPIC: A TypeScript client library

> Candidate EPIC, shaped 2026-11-06 from the v1 future list. Not planned: the PLAN (design.md, tasks.md) waits for the developer's answers in inputs/seed.md.

**Golden-thread parent:** capabilities `rp-service-api` (requirement "The contract is published")
and `rp-generation` (TypeScript types), and the path table of
`docs/modules/ROOT/pages/architecture/api.adoc` ("Client code | TypeScript types (generated)").

## Appetite

**LARGE.** Several related capabilities: a generated client, its runtime part, its packaging, and its
tests against the served API. The generation pipeline gains a target and a new toolchain (Node) joins
the build.

## Why

v1 generates TypeScript types, one file per schema module (`generation/extensions/typescript.py`;
the toy's output is `tests/fixtures/library/web/src/domain/generated/`), and checks them with
`make typecheck-ts`. The service publishes an OpenAPI 3.1 document built over the schema
(`entrypoints/openapi.py`, `install_openapi`). Nothing joins the two: each client writes its own
calls, `ETag`/`If-Match` handling, content negotiation and problem parsing, and the toolkit has no
package or `package.json` for clients.

## Solution outline

A client application can import a typed client for its schema and call every route the generic
router serves: tenants, grants, aggregates, listings, with the versioned-write rules and problem
responses handled the way the service defines them. The client is generated from the same sources
as the server, so it cannot drift from it, and a test runs it against the served toy library.

## Key decisions

- **DEC-1**: Everything in the client that restates the model (types, route paths per aggregate
  type, filter parameters) is generated from LinkML, by a stock or toolkit-extended generator; no
  hand-written restatement and no edits to generated code. Source: D-13; PD-24, PD-25; AGENTS.md.
- **DEC-2**: The OpenAPI document stays the toolkit's own hook over the schema (D-3); the client
  does not change what the server publishes.
- **DEC-3**: The wire is v1's: plain JSON by default, JSON-LD and Turtle by content negotiation,
  `ETag`/`If-Match`, problem responses (D-1, `rp-service-api`).
- **DEC-4**: Sign-in stays with the identity provider's flows; the client carries a token it is given
  and has no login of its own (D-10).

## Rabbit-holes

- **Two sources for one fact.** The TypeScript types come from LinkML and the OpenAPI bodies come
  from generated components; a client built from both must not get two different types for one class.
- **JSON-LD in the browser.** A client that compacts or frames JSON-LD pulls in a large library;
  plain JSON may be enough.
- **Generator choice.** Off-the-shelf OpenAPI client generators have their own runtime and style.

## No-gos

- A user interface, components or forms (v1 no-go: "no frontend is built here").
- A login flow, token storage or token refresh.
- A client for routes the consumer writes itself.
- GraphQL (see `graphql-read-api`) and server-sent events (see `aggregate-events`).
- Any consumer term, model or code.

---

## What Changes

- `rdf_persistence/generation/`: a client target, by extending a generator or a template.
- A client runtime part (HTTP calls, version headers, problems), where Q-1 decides.
- `tests/`: the toy library's client, type-checked and run against the served toy.
- `docs/modules/ROOT/pages/howto/adopt.adoc`: a step for the client.

## Capabilities

### New Capabilities

- `rp-typescript-client`: the generated client and its runtime, and how they are tested.

### Modified Capabilities

None.

## Impact

- Node and an npm toolchain become part of generation or of a package build, not only of a check.
- The `[tool.rp-generate]` table may gain an output place for the client (D-9).
