EPIC: generator-e2e-fixtures (proposal.md, #331). Decisions: DEC-1, DEC-2; design.md PD-1, PD-2. Retrospective: the fix was made before this PLAN was written.

## 1. Stage 1: the tests run against the current toy

- [x] 1.1 PD-1 in `tests/generator/e2e/generated_toy.py`. Red first: the six e2e tests on `develop`.
  Accept: they pass.
- [x] 1.2 PD-2 in `tests/integration/api/test_router.py`. Red first: the restart test on `develop`.
  Accept: it passes.
- [x] 1.3 Lead: `make check-all`, `make test-containers`, PR, #331 closed by the merge.

## Roadmap

- [x] 1.1 · [x] 1.2 · [x] 1.3

## Verification

The seven tests pass; `make test-containers` exits 0.
