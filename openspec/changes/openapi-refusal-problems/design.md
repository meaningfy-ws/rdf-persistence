> Derives from: EPIC `openapi-refusal-problems` (proposal.md), DEC-1 to DEC-4.

## Context

`install_openapi(app, kit)` (`api/entrypoints/openapi.py:589`) wraps `app.openapi`: its `openapi()`
closure builds FastAPI's document once, adds the component schemas and the bearer scheme, inlines
property pointers and caches the dumped dict in `app.openapi_schema`. `service.py:194` calls it after
`kit` holds `refusal_problems` (a tuple of `Problem` subclasses, checked by
`kit._checked_refusal_problems`). Each route's answers come from `route_options` (`openapi.py:260`):
every status of the route's problem kinds as a `Response` whose `application/problem+json` schema is
`{"$ref": "#/components/schemas/Problem"}` (or `InUseProblem` for a status shared with in-use), plus
a `default` with the `Problem` ref. Every aggregate route carries one tag, its `rp_path`; the tenant
routes carry `TenantOpenApi.TAG` (`tenants`); the context route has no tag and no `default`.

## Goals / Non-Goals

**Goals:** the components and the widened answers of DEC-1 to DEC-3; the start-up `ValueError` on a
name clash; scenarios S1 to S4 (DEC-4); the docs that say otherwise corrected.

**Non-Goals:** the no-gos of the EPIC.

## Decisions

- **PD-1 Where the schema comes from.** `cls.model_json_schema(ref_template=f"{COMPONENT_REFERENCES}{{model}}")`,
  its `$defs` (if any) hoisted beside it as components. The pydantic class is the generated artefact
  of the consumer's LinkML problem module; no components file exists for such a module (the toy's
  `services/generated/` has none). Rejected: generating one (EPIC rabbit-hole).
- **PD-2 When the clash is detected.** At `install_openapi` call time, that is at start-up. First the
  registered classes are reduced to the *listed* ones: a class registered twice counts once (first
  place kept), and `Problem` itself is dropped (it is already a component and already the schema of
  every widened answer; `test_rule_refusal.py:249,252` register both and stay green). A listed
  class whose name, or a `$defs` name it brings, is a key of `raw` (the components the routes
  mention) or the name of another listed class raises
  `ValueError(f"refusal problem {name} is already a component schema")`. Not lazily in the closure,
  so a bad registration never starts a service. With no listed class, PD-6 applies.
- **PD-3 Where the rewrite runs.** On the dumped dict, after `document.model_dump(...)`, in a private
  function `_accepting_refusals(document: dict, tags: set[str], refs: list[dict]) -> None`. The
  dumped dict is plain JSON, so no pydantic `PathItem | Any` typing question arises. The components
  are merged with the others (one sorted `components.schemas` mapping, as today).
- **PD-4 The widened schema.** For each widened answer, its `application/problem+json` `schema`
  becomes `{"anyOf": [<the former schema>, <a $ref per listed class (PD-2), in registration order>]}`.
  The former schema stays first and unchanged (`Problem` or `InUseProblem`).
- **PD-5 Recognition (DEC-2).** `tags = set(kit.documents.aggregates)`; an operation is a generic
  create or replace when its method key is `post` or `put` and its first tag is in `tags`. Its
  `"409"` and `"422"` answers are widened when present. Every operation's `"default"` is widened when
  present (DEC-3). An answer is widened only when it has `content["application/problem+json"]["schema"]`;
  any other (a consumer's own route added after `install_service`, whose `default` FastAPI wrote) is
  left as it is, never a `KeyError`.
- **PD-6 Nothing listed.** When PD-2 leaves no listed class (none registered, or only `Problem`), `install_openapi` adds no
  component and the closure does not call `_accepting_refusals`: the dumped dict is the one built
  today (S2, `test_openapi_served`, unchanged).
- **PD-7 The toy's TypeScript check.** `tests/dump_openapi.py` builds
  `ToyService(refusal_problems=[HeldKeyProblem])`, so `make typecheck-openapi-ts` compiles a
  document carrying the `anyOf` (S4, RISK-1). The golden (`tests/fixtures/library/golden/openapi/`)
  stays the no-refusal document; no generated artefact changes, so `make generate` is not run.

## Algorithm / approach

```python
# install_openapi, at call time
listed = _listed(kit.refusal_problems)   # PD-2: duplicates once, Problem dropped, order kept
refusals = _refusal_components(listed, taken=raw)   # PD-1, PD-2: name -> JsonSchema
refs = [{REF: f"{COMPONENT_REFERENCES}{c.__name__}"} for c in listed]
schemas = {name: Schema.model_validate(s) for name, s in {**raw, **refusals}.items()}
# in openapi(), after the dump
if refs:
    _accepting_refusals(app.openapi_schema, set(kit.documents.aggregates), refs)  # PD-3 to PD-5
```

Worked example (the toy, `HeldKeyProblem` registered): `POST /libraries/{t}/books` (tag `books`)
has `409` and `422`, each becoming
`{"anyOf": [{"$ref": "#/components/schemas/Problem"}, {"$ref": "#/components/schemas/HeldKeyProblem"}]}`;
its `default` the same. `DELETE /libraries/{t}/books/{aggregate_id}`: only `default` changes.
`POST /libraries` (tag `tenants`): only `default` changes. `GET /context.jsonld`: nothing.
`components.schemas.HeldKeyProblem` has `holder` in `properties` and in `required`.

Idempotency: the closure runs the rewrite once, guarded by `app.openapi_schema is None` as today;
`test_the_document_is_the_same_each_time_it_is_built` keeps it so.

### Anti-patterns

| Don't | Do instead | Why |
|---|---|---|
| Add a parameter to `route_options` or `AggregateOpenApi` | Post-process in `install_openapi` | DEC-1, D-5 of `consumer-write-rules` |
| Match on `operationId` or `summary` text | Tag + method (PD-5) | The tenant create shares the id prefix; summaries are prose |
| Widen every 409/422 | Only create/replace under an aggregate tag | EPIC no-go |
| Regenerate the golden with refusals | Keep it the no-refusal document; test refusals in `test_openapi.py` | S2: no-refusal document unchanged byte for byte |

## Error matrix

| Failure mode | How it is detected | Expected handling |
|---|---|---|
| A registered class's name, or a `$defs` name it brings, is already a component (`Book`) | PD-2 at `install_openapi` | `ValueError` naming the class at start-up; TC-3 |
| Two different listed classes share a name | PD-2 | Same `ValueError` |
| One class registered twice | PD-2 | Listed once; no error (`test_rule_refusal.py:249`) |
| `Problem` itself registered | PD-2 | Not listed, no component or `$ref` added; no error (`test_rule_refusal.py:252`) |
| A widened candidate answer has no `application/problem+json` schema (a consumer's own route) | PD-5 check | Left as it is |
| A consumer's own route makes FastAPI add a component named like a listed class | Not detected (FastAPI builds it lazily) | The listed class's schema wins the merge (`{**fastapi, **ours}`); accepted (RISK-4) |
| A create/replace answer lacks a 409 or 422 | `status in responses` check | That status is skipped; no error |
| An operation has no `default` (the context route) | `"default" in responses` check | Skipped |
| An aggregate's `rp_path` is `tenants` | Not detected | The tenant POST/PUT would be widened too; accepted (RISK-2) |
| A pydantic upgrade changes `model_json_schema`'s output | `make typecheck-openapi-ts` (PD-7), TC-1's component assertions | Fix the helper; RISK-1 |
| A widened answer no longer matches what the service sends | The contract test with the refusal registered (TC-4) | Fails the task gate |

## Risks / Trade-offs

- **RISK-1 Pydantic schema drift** (the developer's risk, round 1). Likelihood low, impact: the
  document's refusal component changes shape, or stops compiling to TypeScript. Mitigation: PD-7
  runs `tsc` on a document with the class registered; TC-1 asserts the component's `holder`.
- **RISK-2 An aggregate tagged `tenants`.** Likelihood very low, impact: two tenant answers widened
  that should not be. Accepted: the document stays a superset of what the routes send.
- **RISK-3 A later route kind that runs rules** gets only its `default` widened, not its own
  409/422. Accepted: DEC-2 scopes the widening to create and replace; such a route kind adds its own.
- **RISK-4 A consumer route's component named like a listed class.** Likelihood very low (the
  consumer chose both names), impact: one schema hides the other. Accepted: the same merge rule as
  today's toolkit components.

## Test cases

| Id | Scenario (spec / DEC-4) | Assertion | Tier, file |
|---|---|---|---|
| TC-1 | "the document lists the problem", S1 | With `HeldKeyProblem` registered: it is a component with `holder` (in `properties` and `required`); each aggregate create/replace 409 and 422 is PD-4's `anyOf`; every other response of every operation, `default` aside, equals the no-refusal document's | unit, `tests/unit/api/test_openapi.py` |
| TC-2 | "the document lists the problem", S2 | Every operation with a `default` has PD-4's `anyOf` there; the context route is unchanged; without refusals the document equals the golden (existing `test_openapi_served`, not edited) | unit, same file |
| TC-3 | "a registered name that is already a component", S3 | A `Problem` subclass named `Book` registered → `ValueError` naming `Book` at `ToyService(...)` | unit, same file |
| TC-3b | PD-2 | `ToyService(refusal_problems=[HeldKeyProblem, HeldKeyProblem])` lists `HeldKeyProblem` once in each `anyOf`; `ToyService(refusal_problems=[Problem])` builds the golden document | unit, `tests/unit/api/test_openapi.py` |
| TC-4 | S4 | A toy of its own, `ToyService(aggregate_validators={"Book": [fixed_refusal]}, refusal_problems=[HeldKeyProblem])` (the module's `toy` fixture is a plain `ToyService()`). `run_contract(toy, path="/libraries/{t}/books", method="POST")` passes. Four explicit cases, each validated with `[response_schema_conformance]`: create with isbn `held` (409) and `malformed` (422) through `schema["/libraries/{t}/books"]["POST"].Case(...)`; replace of the book `make_ids` made, with `If-Match` its current ETag (read first) and the same two isbns, through `schema["/libraries/{t}/books/{aggregate_id}"]["PUT"].Case(...)`. Each fails before 1.1 (`Problem`'s component is closed, `additionalProperties: false`). `make typecheck-openapi-ts` green with PD-7 | unit, `tests/unit/api/test_contract.py`; CI "types" |

No test is moved or rewritten; `test_openapi_served` stays as it is and keeps proving S2's
byte-for-byte half in the unit lane.

## Open Questions

None.

## Gate

Run 1 8.2, run 2 8.9 (`evidence/clarity-gate.md`). **PD-8 Accepted at 8.9 (R-0005, the lead,
2026-11-28):** run 2's one gap (the algorithm built `refs` from every registered class) is folded
in above (`_listed`, PD-4 "per listed class"); the section-name citations in `tasks.md` stay, the
sections are unique headings.

## Delivery decisions

(Recorded by the lead during delivery, R-0007.)
