> Derives from: EPIC `testkit-wait-until` (proposal.md), GitHub issue #24.

## 1. Public helpers

- [ ] 1.1 Test first (`tests/unit/test_testkit_bootstrap.py`, `tests/unit/testkit/test_public_imports.py`):
  the scenarios of `specs/rp-testkit/spec.md` (public import, timeout naming `what`, async success
  on the third call, a non-retry error propagates). Then add `wait_until_async` and the shared
  timeout message to `rdf_persistence/testkit/bootstrap.py` (design PD-1, PD-2, PD-4) and export
  both names from `rdf_persistence/testkit/__init__.py` and its `__all__` (PD-3). Gates:
  `make test`, `make check-all`.

## 2. Docs

- [ ] 2.1 `docs/modules/ROOT/pages/develop/testing.adoc` rule 11 names `testkit.wait_until` and
  `testkit.wait_until_async`; the `rdf_persistence.testkit` row of the public API table in
  `docs/modules/ROOT/pages/architecture/index.adoc` (line 214) lists the waiting helpers. The prose
  mention at line 138 lists no helpers and stays as it is. Gate: `make check-docs`.

## Roadmap

- [ ] 1.1 · [ ] 2.1

## Verification

`make check-all` and `make check-docs` green; `openspec validate testkit-wait-until --strict` passes;
issue #24 closed by the PR.
