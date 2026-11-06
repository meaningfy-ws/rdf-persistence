<!-- SECONDARY INPUT: preserved, never groomed. The EPIC (../proposal.md) is the shaped truth. -->

# Seed: a TypeScript client library

## Seed text

From `docs/modules/ROOT/pages/questions.adoc`, "What could strengthen it in the future":

> *A client library* over the generated TypeScript types and the OpenAPI document.

From the archived `toolkit-v1-foundation/proposal.md`, No-gos:

> A user interface. The TypeScript types are generated, but no frontend is built here.

## What the code does today (checked 2026-11-06)

- `rdf_persistence/generation/extensions/typescript.py`: a subclass of `gen-typescript` with the
  toolkit's template; enums as string-literal unions, dates as strings, owned parts nested, other
  classes as IRI strings; one file per module and an `index.ts`.
- `rdf_persistence/entrypoints/openapi.py`: the OpenAPI 3.1 document, built when the service is
  installed from component schemas `rp-generate` wrote (`openapi-components.json`).
- `make typecheck-ts` runs `tsc --noEmit --strict` (typescript 5.9.3). The only `package.json` in
  the repository is `docs/package.json` (Antora).

## Open questions for the developer

1. **Where does the client live, and how is it shipped?**
   - (a) Generated into each consumer's tree, beside the types (a `[tool.rp-generate]` output):
     no package to publish; every consumer carries a copy of the runtime part.
   - (b) A small runtime npm package (HTTP, versions, problems) published by this repository, plus
     generated per-schema calls in the consumer's tree: one runtime to fix; an npm release to run.
   - (c) Only a generic runtime, no generated calls: least generated code; calls are typed only by
     generics, and route paths are restated by hand (conflicts with D-13 if they restate the model).
2. **What generates the calls?**
   - (a) A toolkit template over the schema, as the types are: one source, full control.
   - (b) An OpenAPI client generator (`openapi-typescript` + `openapi-fetch`, `orval`, …) over the
     served document: little code of ours; its types duplicate ours (see the rabbit-hole) and the
     document exists only at run time today.
   - (c) (b) over a document written at generation time: needs the OpenAPI document generated, not
     only built at install.
3. **Which HTTP layer?** `fetch` only (no dependency, works in browsers and Node 18+) or a library
   (`ky`, `axios`)?
4. **Which representations does the client read?** (a) plain JSON only; (b) also JSON-LD, with the
   context; (c) also Turtle as text. (a) is smallest.
5. **Is the client a public, versioned artefact?** If so, its version follows the toolkit's
   (`release-pipeline`) or its own SemVer line.
6. **Which runtime targets?** Browser only, Node only, or both (ESM only, or ESM and CommonJS)?
7. **Listings.** A paging helper (async iterator over pages) or one call per page?

## Developer answers (2026-11-06)

Developer: "yes generate from openapi doc please". Answers Q-2: the client's calls are
generated from the OpenAPI document; together with the generated types, nothing is hand-written.
- Still open: Q-1, Q-3 to Q-7. Recommendations to propose: `fetch` only; plain JSON first; ESM;
  an async iterator over pages.

## Test scenarios the EPIC must prove

- The toy library's generated client type-checks with `tsc --strict`.
- Each route the router serves for the toy has a client call (compared against the OpenAPI document).
- Against the served toy (containers): create a tenant, create, read, list with a filter, replace
  and delete a book through the client.
- A replace with a stale version fails with a typed conflict error.
- A 404, 403 and 422 surface as typed errors with the problem's type.
- Regenerating with an unchanged schema leaves the client unchanged (reproducible, PD-19).
- A hand edit to the generated client is detected by the freshness check (PD-26).
