EPIC: grant-roles (proposal.md, #307, #310). Decisions: DEC-1 to DEC-7; design.md D-1 to D-7.

> Derives from: `proposal.md`. Stage 1 starts after `consumer-gap-fixes` stage 2 (#306) has merged.
> Review per stage: one pass (SMALL; P-0005 applies from MEDIUM).

## 1. Grants in a migration, and the start-up report (#307), PR 1, branch `feat/grant-roles-migration`

- [x] 1.1 `GrantRoles`, `RoleRename` and `Migration.grant_roles` in `rp_migrations_services.yaml`, then
  `make generate` ([D-1](design.md#d-1), DEC-1).
- [x] 1.2 Tests first: T1 to T9 (`design.md#stage-1-307-grants-in-a-migration-the-start-up-report`), in
  the files named there. RED: `grant_roles` unknown, no report.
- [x] 1.3 The load map and checks ([D-1](design.md#d-1), [D-2](design.md#d-2)). The `grants` flag
  through `migration_request`, `migrate_database` and `migrate_shared` ([D-3](design.md#d-3)). The
  operations, sent through `_step_operation` in their order ([D-4](design.md#d-4)). Covers DEC-2
  to DEC-4. Accept: T1 to T7 (T3b and T3c included), E1 to E6 and E13 to E15;
  `make test-fast check-quality`.
- [x] 1.4 `AccessRules.undefined_roles` and `AccessRules.administered`, `report_grants` (on the
  existing `Tenancy.access_records()`), and the call in `_run_at_startup` ([D-5](design.md#d-5),
  DEC-5). Accept: T8, T8b, T9, E7 to E9.
- [x] 1.5 `howto/migrate.adoc`: "A model round renames or drops a role", with the worked example,
  the order (RISK-3) and the replacement grant (RISK-2). Accept: `make check-docs`.
- [x] 1.6 Lead: `make check-all`, `make test-containers` (migrations run on Fuseki), one review
  pass, PR. Answer #307 on the issue, with a link to the how-to. This EPIC lands with it.

## 2. Roles held (#310), PR 2, branch `feat/held-roles`

- [x] 2.1 Tests first: T10 to T13 (`design.md#stage-2-310-roles-held`). RED: no `roles_held`, no
  header.
- [x] 2.2 `Collaboration.roles_held` ([D-6](design.md#d-6)); `HELD_ROLES`, `held_roles_value`, the
  read route and the OpenAPI helper ([D-7](design.md#d-7), DEC-6). Accept: T10 to T13, E10 to E12;
  `make test-changed check-quality`.
- [x] 2.3 `user-manual/access.adoc`: roles held, the header and RISK-4. Run `make refresh-surface`.
  Accept: `make check-docs`.
- [x] 2.4 Lead: `make check-all`, one review pass, PR.

## 3. Close

- [x] 3.1 Scenario-map rows for the new tests (each stage adds its own).
- [ ] 3.2 After the last merge: reconcile the proposal, archive, and comment on #307 and #310.

## Roadmap

- [x] 1.1 · [x] 1.2 · [x] 1.3 · [x] 1.4 · [x] 1.5 · [x] 1.6 · [x] 2.1 · [x] 2.2 · [x] 2.3 · [x] 2.4 ·
  [x] 3.1 · [ ] 3.2

## Verification

Each stage: its T-rows go red, then green; `make check-all` before each PR; `make test-containers`
for stage 1; `openspec validate grant-roles --strict`; the PLAN gated (`evidence/clarity-gate.md`).
