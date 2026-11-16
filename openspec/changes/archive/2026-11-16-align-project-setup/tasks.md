> Derives from: EPIC `align-project-setup` (proposal.md).

## 1. Checks

- [x] 1.1 Put the adapters under the coverage floor (PD-1).
- [x] 1.2 Adopt the wider Ruff selection and fix or list its findings (PD-3). Gate:
  `make lint format-check test-fast`.
- [x] 1.3 Drop the Makefile's Docker block and `run` target (DEC-1).

## 2. Version

- [x] 2.1 Add `VERSION`, switch release-please to it, add `make check-version` (PD-2).

## 3. Docs and agents

- [x] 3.1 Placeholder pages for tutorials, user guide, reference, requirements and ADRs, in the nav.
- [x] 3.2 Slim `AGENTS.md`; move the runbook to `develop/agents.adoc` (PD-4).

## 4. Close

- [x] 4.1 `make check-all` green (PR #131, merged); archive the change.
