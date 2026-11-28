# Q&A: consumer-write-rules (secondary; never groomed)

One round, 2026-11-27. The developer answered "accept recommendations": every recommendation below
is accepted. The risk questions were asked and not answered beyond "none" being accepted for the
earlier `typescript-client` round; every risk below therefore gets a mitigation, as the leader's
choice the developer may overrule (R-0002).

| # | Question | Recommendation (accepted) | Becomes |
|---|---|---|---|
| 1 | Split and order | Three changes: `narrowed-slot-override` (#417, TINY, first: it holds a consumer merge), this one (#415, #397, #387, #386, MEDIUM), `typescript-toolkit-modules` (#402, SMALL) | appetite, scope |
| 2 | #415: which toolkit modules a consumer may import | Every module under `rdf_persistence/model/technical/**`, by the same path form as `rdf_persistence/model/rp_*`; the docs name only `Problem` as a supported extension point | DEC-1, DEC-2 |
| 3 | #415: how far a consumer `Problem` subclass goes | Generated Pydantic class inherits `Problem`; the generated TypeScript interface is a `Problem` (see PD-4 on `extends`); a raised one is answered with its extra fields; declaring it on the consumer's own routes stays the consumer's | DEC-3, DEC-4 |
| 4 | #397: the refusal | A write rule raises a refusal carrying an instance of a generated `Problem` subclass; the generic create and replace routes answer that problem, extra fields included; `reader.find` scoped to the write's tenant and to what the writer may read | DEC-4, DEC-5 |
| 5 | #387 `state_name()` | In, though not about validators: small, and needed in the same consumer rule | DEC-6 |
| 6 | Scenarios | The acceptance blocks of #415, #397, #387, #386 as written, plus one conformance test run against the fake and the real reader | design Test plan |
| 7 | Risks | Asked (what outside could change, who is hurt, what we do); none accepted | design Risks |

## Found while planning (recorded as PD, the developer may overrule)

- No route answers a consumer problem today (seed, "What the code does today"), so the answer path
  is in scope (PD-6).
- `Problem`'s OpenAPI component is closed (`additionalProperties: false`), so the generic routes'
  documents must list the consumer's problem classes, or the published contract rejects every
  such answer. That needs the service to know the classes: they are registered at install (PD-7).
- The TypeScript generator never writes `extends` (a narrowed slot breaks it); "the interface
  extends `Problem`" is met structurally: it holds every `Problem` field, and a `tsc` check
  assigns it to `Problem` (PD-4).
- `metamodel_importmap` is a CRITICAL blast radius in GitNexus: the change only adds keys (PD-1,
  RISK-1), and it goes to the developer with the PLAN.

## Put to the developer (2026-11-27), answered 2026-11-27

The lead put three points to the developer, each with the recommendation to accept. The developer
accepted all three on 2026-11-27, as recommended:

1. **Accepted.** The importmap change goes ahead despite the CRITICAL rating: keys are only added,
   the old ones are pinned by a test (TC-1). The epic session re-runs impact on a fresh index at
   stage start and brings any *new* HIGH or CRITICAL finding to the developer.
2. **Accepted.** "Extends `Problem`" is met in TypeScript by assignability, not the `extends`
   keyword (PD-4).
3. **Accepted.** The consumer registers its problem classes at install (`refusal_problems`), and the
   generic create, replace and `default` answers list them in the OpenAPI document (PD-7, PD-8).

The points as put:

1. The CRITICAL GitNexus blast radius of `metamodel_importmap` (81 dependants, index 280 commits
   behind): keys added only, old keys pinned by TC-1, the toolkit's trees checked unchanged at
   `make generate`, a re-index and impact run at stage start (PD-1, RISK-1).
2. "The TypeScript interface extends `Problem`" met by assignability, not the `extends` keyword,
   which the template never writes (PD-4).
3. Registering the consumer's problem classes (`refusal_problems`) and listing them in the OpenAPI
   document, beyond the accepted answers, because `Problem`'s component is closed (PD-7, PD-8).

## Gate run 1 revisions (2026-11-27)

Decisions taken to close the gaps, each a PD with its rejected alternative: the refusal branch
before the internal-error log (PD-6); a stage-1 toy rule with no reader call (PD-9a); where the
document's `anyOf` is written (PD-8); `old` typed as the base model (PD-11); `find` leaves out roots
the transaction changed earlier and refuses `None` (PD-10); shadowed fields refused (PD-2a); one
schema under two import names probed and handled (PD-1a); a generic `Seeded` and the reader
contract's edge cases (PD-13, PD-14); a second worked example.
