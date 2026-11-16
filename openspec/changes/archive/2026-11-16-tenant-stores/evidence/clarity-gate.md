# Clarity gate: tenant-stores PLAN

- run 1, 2026-11-15, 9.0/10, pass. Gaps G1 to G8 (StoreNotWired's problem row, where
  `migrate_tenants` resolves the store, the log level for RISK-2, the container gate command, three
  stale EPIC lines for the reconciliation, TC-26's missing assertion, which TC covers which spec
  scenario, when `TenantBehind` is raised) were folded into the PLAN the same day.
- attack, 2026-11-15 (a fresh reviewer, against develop ae04865): 2 MAJOR findings and 9 MINOR.
  All were folded in: PD-3 (the kit checks for one store wired twice before wrapping), PD-5
  (`TenantBehind` raised at the call; `store` a required keyword), PD-6 (the sweep's order, and
  `misplaced-tenant`), PD-7 (the restore's sites), PD-8 (`delete` resolves the store first),
  PD-9 (the trap of naming a store directly), PD-10 (a consumer's own choice of store), RISK-5,
  five error-matrix rows, TC-38 to TC-43.
