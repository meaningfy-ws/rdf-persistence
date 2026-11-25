# Acceptance: consumer-friction

SMALL appetite: the demo is offered to the developer and may be skipped. PR #391.

## Demo offered

Regenerate the toy library (`make generate`), then show:

1. `tests/fixtures/library/web/src/services/generated/` has no `loan_checks.ts`.
2. `loan_checks_response.ts` there imports from `../../domain/generated/values/loan_checks`.
3. `make typecheck-ts` is green (it compiles the toy's three TypeScript folders together).

## Result

TODO(lead): what was shown, or the reason for a skip.

Verdict: pending (developer)
