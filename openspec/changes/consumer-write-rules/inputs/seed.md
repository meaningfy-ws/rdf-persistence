# Seeds: consumer-write-rules (secondary; never groomed)

Captured 2026-11-27 by the planner. The EPIC (`proposal.md`) is the shaped truth.

## The owner's brief

The developer closed `typescript-client` as overtaken (2026-11-27) and asked to shape new work for
the live remainder, #402 and #415, "or two epics". A triage of the open issues against the
consumer (MWB2, develop and its open v2-06 branches) found #397, #387 and #386 on the same API as
#415, and ordered MWB2's needs #417, #397, #410, #419, #413. The developer accepted the split:
`narrowed-slot-override` (#417, TINY), this change (#415, #397, #387, #386, MEDIUM),
`typescript-toolkit-modules` (#402, SMALL).

## Issue #415: a consumer schema cannot extend `Problem`

Importing `rdf_persistence/model/technical/api/rp_api_entrypoints` from a consumer schema fails in
`rp-generate`: the path is resolved under the consumer's folder; the metamodel modules
`rdf_persistence/model/rp_*` resolve. Expected: the toolkit's problem shapes importable, so a
consumer's 4xx problem with extra fields is a generated model extending `Problem`, declared in its
OpenAPI. Acceptance: GIVEN a consumer schema importing the toolkit's problem module, WHEN it
declares a class with `is_a: Problem` and one extra slot, THEN `rp-generate` produces a Pydantic
class inheriting the toolkit's `Problem`. Context: MWB2 v2-06-cm-review D-11; its interim 422
carries the extra field as a key beside the toolkit's `Problem` fields.

## Issue #397: refuse with a consumer problem type; find a key's holder through the reader

A write rule (`(old, new, principal, reader)`) refuses only by raising `InvalidBody` (422
`invalid-body`); any other exception becomes a 500. `AggregateReader` offers `classes_of` and
`aggregate` only, so a rule cannot name what a write clashes with. Expected: (1) a write rule can
refuse with a problem type, status and detail of the consumer's choosing, answered as that problem
on the generic create and replace routes; (2) `reader.find(cls, **equals)`, scoped to the write's
tenant and to what the writer may read, returns the IRIs of the aggregates of `cls` with those slot
values. Acceptance: GIVEN a write rule raising the refusal with type `T` and 422, WHEN a create
breaks it, THEN the answer is 422 with problem type `T` and the rule's detail. GIVEN a write rule
calling `reader.find(C, key=v)`, WHEN another aggregate of `C` in the tenant holds `v`, THEN the
rule receives that aggregate's IRI; one in another tenant, or unreadable by the writer, is not
returned. Context: MWB2 v2-04 F-2 (task 5.3 left open), v2-07 D-2; the most-cited open toolkit
issue on MWB2's develop.

## Issue #387: typed validators per model class; a public state name

(1) `aggregate_validators` hands a rule the base model type, so a rule casts to its generated
model. Expected: registering a validator for class `C` types the callable as receiving `C`, so a
type checker catches a rule registered on the wrong class. (2) `state_iri` (name → IRI) is
exported, its inverse is not; a consumer cuts the IRI's last segment itself. Expected: a public
`state_name(iri)` that refuses an IRI that is not a state of that workflow. Acceptance: a validator
registered for `C` type-checks with a parameter of type `C` and no `cast`;
`state_name(state_iri(w, 'draft')) == 'draft'`, and an IRI not of a state raises.

## Issue #386: a fake `AggregateReader` in the testkit

`rdf_persistence.testkit.fakes` has no reader fake; each consumer stubs one. Expected: an in-memory
`AggregateReader`, seeded with aggregates, recording the calls a rule made, leaving out aggregates
the writer may not read; ideally a conformance test checks the fake and the real reader against
one contract. Acceptance: GIVEN a validator under unit test, WHEN it is called with the fake seeded
with two aggregates, one unreadable by the writer, THEN the rule sees only the readable one, and the
test asserts which reader calls were made.

## What the code does today (read 2026-11-27, `develop` at 801613ba)

- `metamodel_importmap()` (`rdf_persistence/schema/services/schema.py`) maps
  `rdf_persistence/model/<stem>` for `model/*.yaml` only; `model/technical/**` is not mapped.
  GitNexus impact on it: CRITICAL (81 dependants, 14 flows, index 280 commits behind).
- `Problem` (`model/technical/api/rp_api_entrypoints.yaml`, generated into
  `rdf_persistence.api.entrypoints.generated`) is exported by `rdf_persistence`. Its OpenAPI
  component is `additionalProperties: false`.
- `problems.problem_response(problem)` dumps `problem.model_dump(exclude_none=True)`, so a
  subclass instance's extra fields would be sent. But no raised error reaches it with a consumer
  instance: the handler builds a fresh `Problem` from the error's kind and text, and
  `run_aggregate_validators` turns any exception other than `InvalidBody`, `ValidationError`,
  store errors and `Conflict` into a `RuntimeError` (500).
- `Session.find(cls, **equals)` exists (listings; equality, `Contains`, `None`, dotted paths; no
  access check, prohibitions ignored). The reader's `_visible(iri)` applies the session's
  `may_read` and the tenant check.
- A stored root carries one `rdf:type`, its own class (`mapper._write`), so `classes_of` gives the
  root's own class name.
- The TypeScript template lists every slot of a class and never writes `extends` (module docstring
  of `extensions/typescript.py`); `InUseProblem` in `rp_service.ts` repeats `Problem`'s fields.
- A domain or value module may not import a technical module (`checks/boundary.py`,
  `_module_problems`), so a consumer's `Problem` subclass lives in a technical module.
