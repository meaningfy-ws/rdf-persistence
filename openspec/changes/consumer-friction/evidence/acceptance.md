# Acceptance: consumer-friction

SMALL appetite: the demo is offered to the developer and may be skipped. PR #391.

## Demo offered

Regenerate the toy library (`make generate`), then show:

1. `tests/fixtures/library/web/src/services/generated/` has no `loan_checks.ts`.
2. `loan_checks_response.ts` there imports from `../../domain/generated/values/loan_checks`.
3. `make typecheck-ts` is green (it compiles the toy's three TypeScript folders together).

## Result

Skipped by the developer (2026-11-25), on the lead's recommendation: CI's "Types" job compiles the
toy's cross-folder import with `make typecheck-ts`, and TC-1/TC-2 pin the files the demo would show
(no `loan_checks.ts` in the technical folder, the relative import in `loan_checks_response.ts`).

Verdict: accepted without a demo (developer)
