<!-- SECONDARY INPUT: preserved, never groomed. The EPIC (../proposal.md) is the shaped truth. -->

# Seed: export wait_until from the testkit

## Seed text

GitHub issue #24, copied in `issue.md`. A consumer (MWB2) follows rule 11 of
`docs/modules/ROOT/pages/develop/testing.adoc` ("wait for eventual consistency with
`testkit.wait_until`") and finds the name is not exported; only the internal module
`rdf_persistence/testkit/bootstrap.py` has it.

## What was read

- `rdf_persistence/testkit/__init__.py` (`__all__`, lazy names), `rdf_persistence/testkit/bootstrap.py`
  (`wait_until`, `POLL_SECONDS`, `DEFAULT_TIMEOUT_SECONDS`).
- Callers: `rdf_persistence/testkit/containers/fixtures.py`, `tests/unit/test_testkit_bootstrap.py`.
- `openspec/specs/rp-testkit/spec.md`, `openspec/specs/rp-package-boundaries/spec.md`.
- `docs/modules/ROOT/pages/develop/testing.adoc` rule 11, the public API table in
  `docs/modules/ROOT/pages/architecture/index.adoc`.

## Questions and answers (developer, 2026-11-08)

1. **Include an async twin (`wait_until_async`)?** Options: export only (recommended by the leader:
   nobody is blocked on it), or export plus an async twin. **Answer: export plus the async twin.**
