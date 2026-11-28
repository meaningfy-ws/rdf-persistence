# Seeds and Q&A: openapi-refusal-problems

**Secondary.** The shaped truth is `proposal.md`; this record is kept, never groomed.

## Seeds (read 2026-11-28)

- The developer's brief: task 1.4 of `consumer-write-rules`, stopped by its D-5. Goal: each class
  registered through `refusal_problems` is a component; the 409 and 422 answers of the generic
  create and replace routes, and every `default` answer, accept those classes (`anyOf` with the
  existing problem schema). No `refusal_problems` → the same document, byte for byte. Recommended
  approach: leave `route_options` alone and do it in the `openapi()` closure of `install_openapi`.
- `archive/2026-11-28-consumer-write-rules/design.md`: PD-7, PD-8, D-5, D-20; `tasks.md` 1.4;
  `handover.md`; `evidence/clarity-gate.md` (PD-8's open "how are create/replace found");
  `evidence/docs-owed.md` (the docs go with 1.4).
- Code: `api/entrypoints/openapi.py` (`route_options` :260, `AggregateOpenApi` :450,
  `install_openapi` :589), `router.py` (`add_aggregate_routes`, the tenant routes), `kit.py`
  (`_checked_refusal_problems`), `service.py` (`install_openapi(app, kit)` :194), `problems.py`
  (`refusal_response`); the toy (`tests/toy_service.py`: `HeldKeyProblem`, `fixed_refusal`,
  `refusal_problems`); `tests/fixtures/library/golden/openapi/openapi.json`;
  `tests/unit/api/test_openapi.py`, `test_openapi_served.py`, `test_contract.py`,
  `tests/dump_openapi.py`; the Makefile's `typecheck-openapi-ts`.
- The docs that say the document does not list the classes: `architecture/api.adoc:210`,
  `user-manual/access.adoc:319`, `CHANGELOG.md` (Unreleased, "does not yet list the classes").

## What the reading found

- Operation ids do not separate the routes: the tenant create is `create_libraries_post`, an
  aggregate's `create_libraries__t__books_post`.
- Tags do: every aggregate route has one tag, its `rp_path` (a key of `kit.documents.aggregates`);
  the tenant routes have `tenants` (`TenantOpenApi.TAG`). Under an aggregate tag the only POST is
  the create and the only PUT is the replace. A service-written aggregate has neither.
- `HeldKeyProblem` is in no generated components file (`services/generated/` has none);
  `HeldKeyProblem.model_json_schema(ref_template="#/components/schemas/{model}")` is a flat object
  schema, no `$defs`.

## Round 1 (2026-11-28), the developer's answers

1. **Approach and recognition.** `route_options` and `router.py` untouched; `install_openapi` reads
   `kit.refusal_problems`, adds the components, and rewrites the paths after `build()`. Create and
   replace are recognised by **tag + method** (tag an aggregate `rp_path`, method POST or PUT).
   Rejected: operation id (the tenant create shares the prefix), a marker the router sets (touches
   the router). → DEC-1, DEC-2.
2. **`default` scope.** Every operation that has a `default` answer. → DEC-3.
3. **Scenarios (signed off).** S1 component + `anyOf` on create/replace 409 and 422, nothing else's
   409/422 changes; S2 `anyOf` on every `default`, and without `refusal_problems` the document equals
   the golden; S3 a name already a component fails start-up with `ValueError`; S4 the contract test
   passes with the toy's refusal registered, and `tests/dump_openapi` registers `HeldKeyProblem` so
   that `make typecheck-openapi-ts` compiles a document with the `anyOf`. → DEC-4.
4. **Risk.** Pydantic schema drift (an upgrade changes `model_json_schema`'s output): mitigated by
   S4's `tsc` lane. → RISK-1.
