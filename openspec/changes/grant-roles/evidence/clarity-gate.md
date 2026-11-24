# Clarity gate: grant-roles

Run by a fresh reviewer who did not write the PLAN, after an attack against the code.

- **Run 1, 2026-11-24: 8.4/10, fail.** The reviewer attacked and gated the PLAN and found 11
  counterexamples:
  - the report could not survive a record that does not decode;
  - the order of the operations for a merge rename was not stated;
  - whether a dropped name could be a rename target was not stated;
  - a rename ignored the role's level;
  - `validate_grants` was wrongly claimed unchanged;
  - `access_records()` already existed;
  - how the flag reaches `_apply` was not stated;
  - the grant operations left out the step guard;
  - it was unclear whether the discussion module is required;
  - the lock-out warning was too narrow;
  - line references were wrong.

  The reviewer confirmed that the consumer's chain does reach the system database.
- **Run 2, 2026-11-24: 9.2/10, pass.** The same reviewer re-gated only the listed gaps; all 11 are
  closed. Of its two nits, RISK-1's test references was fixed after the run. The order of rows
  E13 to E15 in the error matrix is left as it is.

No gaps were accepted. The scenarios are #307's two answers, #310's acceptance, and one test per
risk, in `specs/*/spec.md`. The owner signs them off with the PR.
