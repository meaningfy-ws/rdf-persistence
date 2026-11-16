<!-- Parents: the developer's gap analysis of 2026-11-16 against skillery 3.19.0's project-setup
     (archetype: library). -->

# EPIC: Align the repository with the Meaningfy project setup

**Golden-thread parent:** the developer's request of 2026-11-16, after a `project-setup` gap
analysis of the repository against skillery 3.19.0.

## Appetite

**SMALL.** Configuration, docs and agent files; no behaviour of the package changes.

## Why

The audit found the repository conformant on every non-negotiable, with six gaps: the adapters sat
outside the coverage floor, Ruff ran only the base selection, the Makefile kept Docker targets for
an `infra/` a library does not have, the docs lacked the standard buckets, the version had no
`VERSION` file, and `AGENTS.md` had grown into a second rule store and a lead's runbook.

## Solution outline

- Measure the adapters under the 80 % floor; only the modules that need a container stay out.
- Adopt the template's Ruff selection (`S113`, `DTZ`, `BLE001`, `TID251`, `PLR2004`, `PLR0912`,
  `PLR0913`, `PLR0915`, `PT018`); fix the findings, and list the production files that still break
  `PLR0913` as tracked debt.
- Drop the Docker block and the `run` target from the Makefile.
- Add placeholder pages for tutorials, user guide, reference, requirements and ADRs.
- Make `VERSION` the version's one source: release-please writes it and mirrors it into
  `pyproject.toml` and `uv.lock`; `make check-version` fails on drift.
- Cut `AGENTS.md` to what the project is, how it is developed and its principles; the lead's
  runbook moves to `develop/agents.adoc`.

## Key decisions

- **DEC-1**: No `infra/`: a library has no deploy. Source: developer, 2026-11-16.
- **DEC-2**: The feature lane keeps its 50 % floor. Source: developer, 2026-11-16.
- **DEC-3**: `VERSION` is the source and `pyproject.toml` mirrors it, because `uv_build` reads no
  dynamic version. Rejected: switching the build backend to read the file.
- **DEC-4**: `PLR0913` in production code is listed per file as debt, not refactored here.

## Rabbit-holes

- Refactoring signatures into parameter objects to satisfy `PLR0913`.
- Filling the placeholder pages.

## No-gos

- No `/src` lift and no `infra/` (DEC-1).
- No change to the package's behaviour or public API.
- The shared `quality/` checks (Semgrep, ls-lint, checkmake) are a later change.

## Capabilities

- `rp-release` (modified): the version's one source is `VERSION`.
- `rp-developer-checks` (modified): the adapters are under the unit floor; the lint selection.
