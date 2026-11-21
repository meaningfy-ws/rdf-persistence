# Hand-over: uml-to-linkml, after stage 2

## Done
Stage 2 (tasks 2.2–2.7, 2.9, 2.10 and the build half of 2.8), PR #228, merged by the
watch-and-merge command after this note. Full review (L1, L2, L3, L4+L5), four accepted findings
fixed (D-29 C-1..C-4), the checker passed. Gates on `3c1fcb40`: `make check-all` exit 0 (unit
7592, feature 97, generator 1477), `make test-containers` exit 0 (334 passed). The acceptance demo
ran on the consumer's real `.qea`, read-only (`evidence/acceptance.md`).

## Decided since the PLAN
D-1..D-29 (design.md, Delivery decisions); stage 2 added D-23 (rule freeze with R-30), D-24 (W-1
scope), D-25 (reader skips connectors to ignored objects), D-26 (build order, R-30 enumerations
only), D-27 (2.6 as built), D-28 (develop merged in, not rebased), D-29 (the review's findings and
floor).

## Open
- To the developer: the acceptance verdict (`evidence/acceptance.md`), and D-1..D-29 with D-29's
  floor for validation (R-0007).
- After acceptance: the docs stage is done in this EPIC (how-to cold-read, conventions page
  checked against the code), so `evidence/docs-owed.md` says no docs owed; then archive the change
  per `spec-stewardship` (`openspec archive uml-to-linkml --yes`) in a docs PR.
- Upstream issues stay open: #208 (cyclic split modules), #209 (a language-string range).
- The floor of D-29 (the reader/converter double ownership, `Context` order, `Usage`/`Composed`,
  enum constants, `slots.py` split, disk-error staging, WAL side files) is a candidate follow-up
  EPIC for the developer to decide.
- Builder worktrees `.worktrees/uml-to-linkml-{1.6,2.5,2.6,2.7,2.9,2.10,w1,fix-c12,fix-c4}`, their
  `wip/uml-to-linkml-*` branches and `backup/uml-to-linkml-stage2-pre-rebase` can be removed once
  #228 is merged.

## Closed (2026-11-21)
Accepted with a follow-up (#229, the review's floor); D-1..D-29 validated; no docs owed
(`evidence/docs-owed.md`); archived in the same session. Nothing is left in this change.

## Next
None for this change. The hardening follow-up #229 is a shaping session's when the developer
schedules it; the 0.8.0 release (#210) may now go ahead.

## Prompt
Act as the planner. Shape issue #229 (uml-to-linkml hardening) into an EPIC with the
epic-planning skill, reading the archived change's design.md D-22 and D-29 first.
