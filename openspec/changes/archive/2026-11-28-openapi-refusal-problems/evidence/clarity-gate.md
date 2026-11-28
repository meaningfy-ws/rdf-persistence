Accepted at 8.9 (R-0005, the lead, 2026-11-28): run 2's gap 1 folded into design.md §Algorithm
and PD-4; recorded as PD-8 in design.md §Gate.

run 1, 2026-11-28, 8.2/10, fail

- PD-2 breaks existing tests the PLAN says stay untouched: `tests/unit/api/test_rule_refusal.py:249`
  registers `(HeldKeyProblem, HeldKeyProblem)` (same name twice) and `:252` registers `(Problem,)`
  (`Problem` is already a component, `TOOLKIT_BODIES` in `openapi.py:97-100`); both would raise the
  new `ValueError` at `ToyService(...)`. Decide: the same class twice is deduplicated, and `Problem`
  itself adds no component or `$ref` (or the developer accepts the new refusal and those tests change);
  add both rows to the error matrix and drop "No test is moved or rewritten".
- PD-4/PD-5 assume every widened answer has `content["application/problem+json"]["schema"]`; a
  consumer's own route (added to the app after `install_service`, documented lazily) may have a
  `default` without it. Add an error-matrix row: skip an answer with no `application/problem+json`.
- TC-4 says "two explicit cases" but lists four (held/malformed x create/replace) and does not say
  how the replace case gets its `If-Match` and body, nor which fixture builds the toy (the module's
  `toy` fixture is `ToyService()`). Name the four cases, the `aggregate_validators={"Book": [fixed_refusal]}`
  toy, and the check list (`[response_schema_conformance]`).
- Task 1.3 misses the docstring of `install_service` (`api/entrypoints/service.py:132-133`, "They are not
  yet listed in the OpenAPI document") and its `Raises:` list lacks the new `ValueError`.
- PD-2 checks clashes only against `raw`; components FastAPI builds from a consumer's own routes are not
  checked and the merge (`openapi.py:606`) silently lets one overwrite the other. Record it as a risk.
- `tasks.md` cites PD-n/TC-n but no `design.md#anchor` deep links.

run 2, 2026-11-28, 8.9/10, fail

- Closed: gaps 1 to 5 of run 1 (PD-2 listed classes, PD-5 skip, error-matrix rows, RISK-4, TC-3b,
  TC-4's four cases, the task 1.1 docstring).
- Open: design.md §Algorithm still builds `refs` from `kit.refusal_problems`, not the listed classes,
  and PD-4 says "a $ref per registered class". Followed as written, `[Problem]` gives
  `anyOf [Problem, Problem]` and widens (breaks PD-6 and TC-3b), and a class registered twice gives
  two `$ref`s. Fix: build `refs` from the listed classes PD-2 keeps, PD-4 "per listed class"; the
  guard `if refs` then matches PD-6.
- Open (minor): tasks.md cites `design.md §Decisions PD-n` by section name, not `design.md#anchor`.
