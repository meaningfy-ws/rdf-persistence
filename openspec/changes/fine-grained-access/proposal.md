<!-- Parents: openspec/specs/rp-access; docs/modules/ROOT/pages/architecture/access-control.adoc
     ("How OpenFGA and ODRL would fit together"); D-4 and D-5 in
     docs/modules/ROOT/pages/architecture/open-decisions.adoc. Seeds: inputs/seed.md. -->

# EPIC: Fine-grained access: OpenFGA and property- or triple-level access

> Candidate EPIC, shaped 2026-11-06 from the v1 future list. Not planned: the PLAN (design.md, tasks.md) waits for the developer's answers in inputs/seed.md.

**Golden-thread parent:** capability `rp-access` and
`docs/modules/ROOT/pages/architecture/access-control.adoc` (decisions D-4, D-5; the section "How
OpenFGA and ODRL would fit together").

## Appetite

**VERY LARGE**, delivered in stages. It cuts across the metamodel (`rp_access`), the access check,
every read and write path (router, listings, sessions, and GraphQL and events if they exist), the
OpenAPI document and the testkit. Each stage ends with tests green and merged to `develop`. The
stages and their order are an open question (inputs/seed.md, Q-1).

## Why

v1 decides access per tenant and per aggregate only, in process: `AccessRules.require` in
`rdf_persistence/services/access.py` evaluates the ODRL subset of `model/rp_access.yaml` (grants,
prohibitions, role definitions), loaded per request by `load_caller_access`. A caller who may read a
book reads all of it; there is no way to hide a slot or a statement. D-4 deferred OpenFGA "unless a
cheap opportunity to reuse it appears", for example access that flows through relationships, which
v1's check cannot express.

## Solution outline

An application can say, in its access module, that some properties (or statements) of an aggregate
are readable or writable only by some roles, and every representation the service returns (plain
JSON, JSON-LD, Turtle, listings and their filters) respects that, while writes that touch a
protected property are refused. If the developer confirms OpenFGA, the same ODRL records also drive
OpenFGA as an alternative decision engine, and both engines give the same answers on the toy
library's permission matrix.

## Key decisions

- **DEC-1**: ODRL in RDF stays the record of what is allowed; a grant is an `odrl:Permission`
  (D-4, D-5). An engine such as OpenFGA is fed from that record, one way, never the other way
  (access-control.adoc).
- **DEC-2**: The access model stays its own module; applications keep their rules in an access
  module apart from the domain (open-decisions.adoc, decided with the request).
- **DEC-3**: Every new access construct is declared in LinkML (`rp_access` or a new module) and
  generated; data goes through generated models, not dicts (D-13; PD-24; AGENTS.md).
- **DEC-4**: The refusal order of v1 stands: inactive tenant 404, Prohibition 403, nothing visible
  404, permitted allowed, otherwise 403; 401, 403 and 404 carry no detail (`services/access.py`,
  PD-13a).
- **DEC-5**: Delivered in stages, each merged to `develop` with tests green (as archived DEC-3).

## Rabbit-holes

- **Filters leak.** A listing filter on a hidden property tells the caller its value.
- **Shapes and hidden slots.** A replace without a hidden required slot fails validation; the
  service must merge or refuse.
- **Versions.** An `ETag` changes when a hidden property changes; the caller learns that it changed.
- **Prohibitions in OpenFGA.** They have no direct counterpart (only `but not`); constraints map only
  partly (access-control.adoc).
- **Triple level.** Per-statement rules need a way to name statements; RDF-star or reification are
  each a project of their own.

## No-gos

- Changing D-5: grants and ODRL stay one model.
- A policy language other than the ODRL subset (Rego, Cedar).
- Access decided inside the triple store.
- A user interface for policies.
- Any consumer term, model or code.

---

## What Changes

- `rdf_persistence/model/rp_access.yaml`: property-level (and maybe statement-level) rules.
- `rdf_persistence/services/access.py`: the check decides per property; a decision-engine port if
  OpenFGA is confirmed, with an OpenFGA adapter in `adapters/`.
- `rdf_persistence/entrypoints/router.py`, `services/listing.py`, `services/documents.py`: reads
  filtered and writes checked per property.
- `rdf_persistence/testkit/`: an OpenFGA container fixture, if confirmed.
- `docs/modules/ROOT/pages/architecture/access-control.adoc`: OpenFGA and property access move from
  deferred to implemented.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `rp-access`: adds property-level access and the alternative decision engine (ADDED requirements;
  v1's per-tenant and per-aggregate requirements are unchanged).

## Impact

- Every read path may become more expensive; the cost is measured.
- OpenFGA, if confirmed, becomes a deployment dependency with its own store.
