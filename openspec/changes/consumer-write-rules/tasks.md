EPIC: consumer-write-rules (proposal.md). Decisions: DEC-1 to DEC-8 (proposal), PD-1 to PD-15 (design.md).

> Derives from: EPIC `consumer-write-rules`. Issues #415, #397, #387, #386.

Every task: test-first; task gate `make test-changed check-quality`; commit body
`Refs: consumer-write-rules <task> <PD>` (`Refs: #<issue>` on the task that closes it).
Builders never commit; the lead does and ticks this file. Only the lead runs `make generate`.

## 1. Stage 1: a consumer problem, raised by a rule (#415, #397 part 1) — branch `change/consumer-write-rules-1`, one PR

- [x] 1.1 **unit + code (#415 import)** — PD-1, TC-1. Failing test first in `tests/unit/schema/`:
  the technical key exists; every `model/*.yaml` key and value is unchanged. Then
  `metamodel_importmap`. Accept: TC-1 passes; existing importmap and schema tests pass unchanged.
- [x] 1.2 **generator (#415 extend)** — after 1.1; PD-1a, PD-2, PD-2a, PD-4, PD-9, TC-1b, TC-2 to
  TC-4, TC-3b. Failing tests first in `tests/generator/unit/test_consumer_problem.py`. Then the toy
  module `services/library_problems.yaml` and its import from `loan_checks_response.yaml`;
  `generate_module_import`'s technical branch, the export and shadow checks in `pydantic_split.py`,
  the first-of-each-name rule in `ToolkitTypescriptGenerator.modules()`. The
  lead runs `make generate` and commits the toy trees and manifests. Accept: TC-2 to TC-4 pass;
  `make generate` changes nothing in the toolkit's trees beyond the manifests' input hashes (RISK-1:
  any other diff is reported, not fixed); `make typecheck-ts` green; task gate green. Closes #415.
- [x] 1.3 **unit + code (refusal)** — after 1.2 (the toy class); PD-5 to PD-7, PD-9a, TC-5, TC-6,
  TC-8. Failing tests first in `tests/unit/api/test_rule_refusal.py` and
  `tests/unit/collaboration/test_aggregate_validators.py`, over the toy rule `fixed_refusal`
  (PD-9a, no reader call). Then `RuleRefusal`, the pass-through in `run_aggregate_validators`, the
  refusal branch first in `toolkit_error`, and `refusal_problems` on `install_service`,
  `ServiceKit`, `ToyService`; `fixed_refusal` in `tests/toy_service.py`; the public export. Accept:
  TC-5, TC-6 (log records included), TC-8 pass; the error-matrix gap test passes; task gate green.
- [ ] 1.4 **stopped (D-5, the developer, 2026-11-27): back to shaping.** **unit + code (document)** — after 1.3; PD-8, TC-7. Failing tests first in
  `tests/unit/api/test_openapi.py`. Then `refusals` on `AggregateOpenApi` and `route_options`, the
  router passing `kit.refusal_problems`, and the components and `default` loop in
  `install_openapi`. Accept: TC-7 passes; the document golden without
  `refusal_problems` unchanged; `make typecheck-openapi-ts` green; task gate green.
- [x] 1.5 **docs** — after 1.4; PD-15's stage-1 half (generation page, how-to's problem section,
  `api.adoc` row, CHANGELOG added names). Accept: `make check-docs` green.
- [ ] 1.6 **lead** — scenario-map rows (done); `make check-all`, `make test-containers` not needed (no
  adapter); one review pass (L1+L2, L3+L4+L5: MEDIUM); PR into `develop` naming the consumer need
  (D-12); merged on green CI.

## 2. Stage 2: find, typed rules, the fake reader, state names (#397 part 2, #387, #386) — branch `change/consumer-write-rules-2`, one PR

- [ ] 2.1 **unit + code (find)** — PD-10, TC-9. Failing tests first in
  `tests/unit/collaboration/test_aggregate_validators.py` (the scopes of TC-9, worked example 2's
  two variants, `None`) and one through the toy service's generic create with `held_isbn` (worked
  example 1, added to `tests/toy_service.py`). Then `find` on the protocol and `_Reader`. The
  existing hand-written reader stubs that type as `AggregateReader` gain `find` (DEC-8): the stub in
  `tests/unit/collaboration/test_aggregate_validators.py`; `ast-grep` for any other class with `classes_of` and
  `aggregate` under `tests/`. Accept: TC-9 passes; `make typecheck` green; task gate green.
- [ ] 2.2 **unit + code (typed rules, state_name)** — independent of 2.1; PD-11, PD-12, TC-10,
  TC-11. Failing tests first. Then `aggregate_rules`, `delete_rules`, `state_name`, the exports.
  Accept: TC-10, TC-11 pass; `make typecheck` green; task gate green. Closes #387.
- [ ] 2.3 **testkit (fake + kit)** — after 2.1; PD-13, PD-14, TC-12, TC-13. Failing tests first in
  `tests/unit/testkit/test_fake_reader.py` and `test_reader_conformance.py`. Then
  `FakeAggregateReader`, `reader_conformance.py`, the export. Accept: TC-12, TC-13 pass for both
  readers; task gate green. Closes #386.
- [ ] 2.4 **feature** — after 2.1 to 2.3; `features/consumer_write_rules.feature` appended to
  `tests/feature/consumer_write_rules.feature` with its steps (the toy `held_isbn` rule of worked
  example 1, added in 2.1). Accept: the feature lane passes the scenarios. Closes #397.
- [ ] 2.5 **docs** — after 2.4; PD-15's stage-2 half and the CHANGELOG *BREAKING* line (DEC-8).
  Accept: `make check-docs` green.
- [ ] 2.6 **lead** — scenario-map rows; `make check-all`; one review pass (two grouped runs);
  PR into `develop`; merged on green CI; archive.

## Roadmap

- [ ] 1.1 → 1.2 → 1.3 → 1.4 → 1.5 → 1.6 · [ ] 2.1 ∥ 2.2 → 2.3 → 2.4 → 2.5 → 2.6

## Verification

`make check-all` green at each stage end; the toolkit's generated trees unchanged but for manifests
and the toy; the document golden unchanged without registered problems; the clarity gate on this
PLAN ≥ 9/10 (or 8.8 by R-0005) before 1.1.
