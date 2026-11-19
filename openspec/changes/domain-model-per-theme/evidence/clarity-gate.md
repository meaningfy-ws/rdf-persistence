# Clarity gate: domain-model-per-theme

- run 1, 2026-11-19, 7.8/10, fail — 13 gaps: PD-4 contradicted its error row (theme targets with
  roots fail the migrations check), how the root's package reaches the import rule (PD-2) and the
  package check (PD-3) unspecified, the mode of a root with classes, the new `domain/` packages, the
  `PLACED` rows, test placement and the planted `files-to-provenance` test, three anti-patterns, a
  consumer case unstated, counts and wording, the doc anchors, `rp_collaboration.yaml` and the
  entries unspecified. Revised: PD-2 to PD-6, PD-9 (new), the error matrix with ids, the test-case
  table with locations, six anti-patterns, the doc anchors.
- run 2, 2026-11-19, 8.9/10, fail — 11 of 13 gaps closed; open: TC-03's method (no git call at
  test time), the EPIC's counts, and a new one, N1 (`turned_on_pairs` must yield the `MovedModule`
  rows for TC-02 and TC-07). Each fixed after run 2 as the gate stated it (PD-9, TC-03, the counts;
  `rp_collaboration.yaml`'s title, optional); the developer is asked to accept the PLAN with these
  fixes (the method's limit of two runs).
- accepted by the developer, 2026-11-19 ("yes accept both"): the PLAN proceeds at 8.9 with the
  post-run-2 fixes (design.md, Accepted gate).
