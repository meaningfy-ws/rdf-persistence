# Clarity gate: delete-refuses-referenced PLAN

run 1, 2026-11-20, 9.1/10, self-score (planner), pass
run 1, 2026-11-20, 8.4/10, fresh reviewer, fail (7 gaps, all fixed 2026-11-20; owner re-shaped
SMALL → MEDIUM and decided OPEN-1 to OPEN-4, `inputs/qa.md`)

| Criterion | Weight | Score | Note |
|---|---|---|---|
| Actionability | 25 % | 9.5 | Every task names files, its failing test and its acceptance |
| Specificity | 20 % | 9 | Cap 20, minimum 0, guard text given; docs task 3.1 is the loosest |
| Consistency | 15 % | 9 | Decisions only in design.md; tasks cite PD ids |
| Structure | 15 % | 9.5 | Decisions, examples, matrix and tests are tables |
| Disambiguation | 15 % | 8.5 | 8 anti-patterns, 15 matrix rows; four OPEN questions still open, OPEN-4 gates task 2.3 |
| Reference clarity | 10 % | 9 | File paths and line numbers at develop 4e8d1fe2 |

Attack (step 7) folded in: same-commit add of a referrer (PD-5, matrix 5), drop-link-and-delete
in one commit (matrix 6), batched unit of work (matrix 13), self-referring part (matrix 14), retry
loops on `Conflict` (matrix 15), comment referrers leaking past `may` (PD-9, matrix 9), referrer
committed after the delete (RISK-1, narrows DEC-2), cap applied before the readability filter
(PD-9). `openspec validate delete-refuses-referenced --strict`: valid.

Scenarios: not yet signed off by the owner.
run 2, 2026-11-20, 8.4/10, fresh reviewer, fail
run 3, 2026-11-20, 9.2/10, fresh reviewer (gaps only), pass

Scenarios: signed off as written by the owner, 2026-11-20 (epic session, before stage 1).
