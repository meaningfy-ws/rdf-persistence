EPIC: ci-minimal-gate (proposal.md). Decisions: proposal.md DEC-1 to DEC-5; design.md PD-1 to PD-3.

> Derives from: the EPIC `ci-minimal-gate`.

One stage, branch `change/ci-minimal-gate` off `develop`, one PR. Red test first for 1.1. Commit
body `Refs: ci-minimal-gate <task> <PD>`.

## 1. Split the workflows

- [x] 1.1 PD-2, unit. Red, in `tests/unit/tooling/test_lanes.py`: `ci.yaml` runs on pull requests
  only and has exactly the jobs `style`, `types`, `architecture`, `spec-docs-generation`,
  `feature`; `nightly.yaml` runs on a schedule and by hand; the shard, combine, generator and Sonar
  tests read `nightly.yaml`.
- [x] 1.2 PD-1. Green: move the four jobs to `.github/workflows/nightly.yaml`, drop the push
  trigger from `ci.yaml`, rewrite both headers.

## 2. Docs

- [x] 2.1 PD-3. `develop/testing.adoc#slow`, `develop/index.adoc`, Makefile comments,
  `sonar-project.properties`, README badge. `make check-docs`.

## 3. Close

- [ ] 3.1 `make check-spec check-quality`; the developer runs `nightly.yaml` once by hand after
  merge.
