EPIC: tenant-root-owned-parts (proposal.md, issue #276). Decisions: design.md PD-1 to PD-4, DEC-1 to DEC-4.

> Derives from: EPIC `tenant-root-owned-parts`. One stage (TINY). Retrospective: every task was
> done in PR #288 before this change was written.

## 1. Stage 1: mint the parts of a new tenant's root

- [x] 1.1 Toy fixture (PD-4): `Library.charter` → `Charter` in `library_tenant.yaml`,
  `make generate`. The goldens, the shape snapshot and `test_hard_check.py`'s planted text are
  refreshed.
- [x] 1.2 Unit, failing first: `tests/unit/api/test_tenant_root_parts.py`. Create with a part
  answered the issue's 422.
- [x] 1.3 `Tenancy.create` mints part IRIs and refuses a part `id` (PD-1, PD-2, PD-3). The tests
  pass.
- [x] 1.4 Docs: `user-manual/generated-classes.adoc` names the tenant-create `root`.
- [x] 1.5 Full gates: `make check-all`, `make test-containers`, `make check-docs`, and the
  scenario map (with `--collect`, issue #290). CI green, merged on green (P-0013).
