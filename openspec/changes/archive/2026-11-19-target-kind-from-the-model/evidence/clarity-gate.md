# Clarity gate: target-kind-from-the-model

- run 1, 2026-11-19, 7.8/10, fail — 14 gaps: a check lost without a decision (a mixed target), the
  feature test and the breaking tests not named, TC-02 contradicting itself, the cross-target and
  inline-config mapping incomplete, the toy library's paths, the getting-started example, the docs
  under-listed, stale generated descriptions, the requirement title, missing error rows, two
  anti-patterns. Revised: PD-2 (no mixed target, lead's choice), PD-3 to PD-5, the error matrix,
  TC-01 to TC-05, task 1.1's list of tests, task 3.1's list of pages, a RENAMED requirement.
- run 2, 2026-11-19, 8.7/10, fail — 7 of 14 gaps closed, 7 partly: the scenario-map rows (30, not
  8), four more breaking tests, the example's lines and `__init__.py`, the generate page's
  both-kinds paragraph, two more references in `rp_generation.yaml`, the exact messages, the mixed
  target's wiring. Each fixed as the gate stated it, after run 2; the developer is asked to accept the
  PLAN with these fixes (the method's limit of two runs).
- accepted by the developer, 2026-11-19 ("yes accept both"): the PLAN proceeds at 8.7 with the
  post-run-2 fixes (design.md, Accepted gate).
