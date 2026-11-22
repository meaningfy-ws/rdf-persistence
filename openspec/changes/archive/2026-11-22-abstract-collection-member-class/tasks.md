> Derives from: EPIC `abstract-collection-member-class` (proposal.md, #274). Decisions: DEC-1 to DEC-4, design.md PD-1 to PD-4. Retrospective: every task was done in PR #287 before this PLAN was written.

## 1. Stage 1: the abstract parent leaves its member class to its subclasses

- [x] 1.1 Tests first: TC-1 to TC-3 (unit) and IT-1 (integration), failing for the reason #274
  states. Then PD-1 to PD-3 in `uml/slots.py`, `make generate` (freshness hashes). Accept: the
  four tests pass; IT-1 fails on the parent commit.
- [x] 1.2 Docs (PD-4). Accept: `make check-docs` passes.
- [x] 1.3 Lead: `make check-all`, `make test-containers`, `make refresh-map` (row for IT-1); the
  MWB2 phase-B `.qea` converted and checked with `rp-generate --check` (5 errors → 0); PR #287
  merged on green CI; #274 closed; MWB2 PR #101 told (D-12).

## Roadmap

- [x] 1.1 · [x] 1.2 · [x] 1.3

## Verification

The spec delta's scenario passes as TC-1 to TC-3 and IT-1; `make check-all`, `make test-containers`
green; `openspec validate abstract-collection-member-class --strict`.
