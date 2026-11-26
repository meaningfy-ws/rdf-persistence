# Clarity gate: test-control-testkit

Fresh reviewer (general-purpose subagent), attack and gate in one pass.

- run 1, 2026-11-26, 7.5/10, fail: twelve counterexamples. The two blocking ones were the seed
  race surviving `--before` and the fallback still syncing. All twelve were folded in (PD-6,
  PD-7, PD-12, PD-13, PD-2, PD-3, PD-4, RISK-5, RISK-6, the error matrix, the anti-patterns and
  the worked examples).
- run 2, 2026-11-26, 8.7/10, fail: five wording gaps where older passages contradicted the new
  decisions (the seed spec requirement, three places saying "only imports change", TC-12,
  RISK-3, the quoted reference in task 1.2). All five were fixed after the run. The reviewer
  estimated about 9.0 with gaps 1 to 3 fixed, and a clear pass with all five.

**DEC-11** (lead, 2026-11-26, under R-0005 and R-0007): the PLAN proceeds without a third gate
run. The skill caps the gate at two runs, the remaining gaps were wording only, and all of them
are fixed. The developer may overrule this. PD-12 (b), the wheel listing, stays a step in the
lead's checklist (tasks 2.6 and 3.5) rather than an `@manual` feature: it is a build check, not a
behaviour a user sees.

Scenarios: the spec deltas in `specs/`. The developer asked on 2026-11-26 to "continue to
planning and then implement complete epic", which the lead takes as sign-off of the scenarios as
gated. The developer may overrule this at the acceptance check.
