> Derives from: EPIC `refresh-map-collect` (proposal.md, #290). Decisions: DEC-1, DEC-2, design.md PD-1, PD-2. Retrospective: every task was done in PR #294 before this PLAN was written.

## 1. Stage 1: collect at a fixed verbosity

- [x] 1.1 TC-1 (unit) and PD-1 in `tests/audit/refresh_map.py`, in one commit (cf6757e). Whether
  TC-1 was seen failing first is not recorded. Accept: TC-1 passes; `make refresh-map` lists node
  ids.
- [x] 1.2 Lead: a scenario-map row for TC-1; PR #294 merged; #290 closed with the merge commit.

## Roadmap

- [x] 1.1 · [x] 1.2

## Verification

TC-1 passes; `make refresh-map` exits 0 on develop with no unmapped ids.
