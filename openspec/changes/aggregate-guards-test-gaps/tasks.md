EPIC: aggregate-guards-test-gaps (proposal.md, follows #305, #309). Decisions: DEC-1, DEC-2; design.md TC-1 to TC-10.

## 1. Stage 1: the tests the floor left out

- [x] 1.1 TC-1 to TC-10 (`design.md#tests`), each failing first per DEC-1, in the module of the
  layer it tests; scenario-map rows. Accept: all pass; `make test-fast check-quality`.
- [x] 1.2 R1-S7 in `user-manual/access.adoc`. Accept: `make check-docs`.
- [x] 1.3 Lead: `make check-all`, `make test-containers`, PR, archive with `--skip-specs`; the
  skipped demo recorded in `archive/2026-11-24-aggregate-guards/evidence/acceptance.md`.

## Roadmap

- [x] 1.1 · [x] 1.2 · [x] 1.3

## Verification

TC-1 to TC-10 green; the full gates green.
