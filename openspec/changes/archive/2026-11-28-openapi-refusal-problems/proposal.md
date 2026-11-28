# EPIC: The OpenAPI document lists the registered refusal problems

Parents: `consumer-write-rules` (archived 2026-11-28) task 1.4, stopped by its D-5; its PD-8 and
RISK-3; requirement "A consumer rule refuses a write with its own problem" (`rp-service-api`).
Issue: #457.

## Appetite

SMALL. One capability (the published document) touched in one function, `install_openapi`.

## Why

A rule may refuse a write with a registered subclass of `Problem`, and the service sends its extra
fields. The published document still names only the closed `Problem` component, so a client
generated from it does not see those fields (RISK-3 of `consumer-write-rules`). The first attempt
was stopped because it changed `route_options`, which GitNexus rates CRITICAL (14 callers).

## Solution outline

`install_openapi` already post-processes the document FastAPI builds. With `kit.refusal_problems`
non-empty, it also adds each class's schema as a component, widens the 409 and 422 answers of the
generic create and replace operations to `anyOf` the current problem schema and the classes, and
does the same to every operation's `default` answer. With none registered it does nothing new, and
the document stays byte-identical. A client generated from the document then types the extra
fields.

## Key decisions

- **DEC-1 Post-process, do not touch the routes.** The change lives in `install_openapi` and its
  `openapi()` closure; `route_options`, `AggregateOpenApi` and `router.py` stay as they are. Reason:
  `route_options` is CRITICAL (D-5 of `consumer-write-rules`), the closure already post-processes
  the document. Rejected: PD-8's per-route `refusals` parameter.
- **DEC-2 Create and replace are recognised by tag and method.** An operation whose tag is an
  aggregate's `rp_path` (a key of `kit.documents.aggregates`) and whose method is POST (create) or
  PUT (replace). Reason: under an aggregate tag these are the only POST and PUT; the tenant routes
  carry the `tenants` tag. Rejected: the operation id (the tenant create shares the `create_`
  prefix); a marker set by the router (touches the router).
- **DEC-3 Every `default` answer.** Every operation that has a `default` answer accepts the classes:
  a refusal reaches any route that runs rules. Rejected: aggregate routes only.
- **DEC-4 The scenarios S1 to S4** (`inputs/qa.md`, round 1), signed off by the developer; the
  `tsc` lane runs on a toy document with `HeldKeyProblem` registered, the golden stays the
  no-refusal document.

## Rabbit-holes

- Rewriting `route_options` or threading the classes through the router: that is the stopped
  approach (DEC-1).
- Generating a components file for consumer problem modules from LinkML: the pydantic class is
  already the generated artefact, and its schema is enough here.

## No-gos

- No change to `route_options`, `AggregateOpenApi`, `RouteDocs` or `router.py`.
- No change to how a refusal is answered (`problems.py`), only to how it is documented.
- No widening of any 409/422 other than the generic create and replace (tenant routes, delete,
  grants and label keep theirs).
- No change to the document of a service without `refusal_problems`.

---

## What Changes

- `install_openapi` adds each registered refusal class as a component, refuses at start-up a class
  whose name is already a component (`ValueError`), and widens the create/replace 409 and 422 and
  every `default` answer to `anyOf`.
- The toy's TypeScript check runs on a document with `HeldKeyProblem` registered.
- The docs drop "the document does not list your problem classes".

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `rp-service-api`: the requirement "A consumer rule refuses a write with its own problem" gains
  the document's listing and its scenario.

## Impact

`rdf_persistence/api/entrypoints/openapi.py` (`install_openapi` and new private helpers);
`tests/unit/api/test_openapi.py`; `tests/dump_openapi.py`; `docs/` (`architecture/api.adoc`,
`user-manual/access.adoc`); `CHANGELOG.md`. Published document unchanged for a service with no
`refusal_problems`.

## Reconciliation (as delivered, P-0004)

| Shaped | Delivered | PR | Difference |
|---|---|---|---|
| DEC-1 post-process in `install_openapi` | `_listed`, `_refusal_components`, `_accepting_refusals`; `route_options`, `AggregateOpenApi`, `RouteDocs`, `router.py` untouched | this PR | none |
| DEC-2 tag + method | as shaped | this PR | none |
| DEC-3 every `default` | as shaped, only where the answer has a problem schema (PD-5) | this PR | none |
| DEC-4 S1–S4 | TC-1 to TC-4 in `test_openapi.py` and `test_contract.py`; `typecheck-openapi-ts` on the refusing toy | this PR | TC-4's red shown by an unregistered run, not against the parent commit (D-5, #459 W-3) |
| Docs | `architecture/api.adoc`, `user-manual/access.adoc`, `CHANGELOG.md`, `install_service` docstring | this PR | none |

What Changes, Capabilities and Impact hold as written. Not delivered, under the review floor:
#459 (a `$defs` name shared by two listed classes is refused, W-1; tests and tidy-ups).
`consumer-write-rules`' RISK-3 is closed by this change.
