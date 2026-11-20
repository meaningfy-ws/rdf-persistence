# Hand-over: delete-refuses-referenced, after stage 1

## Done

Stage 1 (tasks 1.1, 1.2: the model), PR #224 (merged by the watch-and-merge command after this
note). Already built ahead on stacked branches (D-1): task 2.1 on `feat/delete-refuses-referenced-s2`
(046bb5ef, worktree `.worktrees/delete-refuses-referenced-s2`), task 2.2 in progress there; the
stage-3 docs draft on `docs/delete-refuses-referenced-s3` (068494a3, worktree
`.worktrees/delete-refuses-referenced-s3`).

## Decided since the PLAN

D-1 to D-7 (design.md, Delivery decisions). Scenarios signed off (evidence/clarity-gate.md).

## Open

- S2 of the stage-1 review: the annotation on a non-root class is accepted and does nothing. Owner
  question at the full review (D-6).
- The stage-3 docs draft assumed ten details the PLAN leaves to the code (the `Referrer` JSON
  member names, `session.remove` argument order, `open_session(..., removals=)`, `had_member`, …):
  check them against the built code before the stage-3 PR.
- The stage-2 branch must be rebased on develop once #224 merges.

## Next

Stage 2, task 2.2 (in progress), then the adversarial tester on 2.2 (D-7), then 2.3 ∥ 2.4, 2.5.
Read first: tasks.md §2, design.md PD-3 to PD-12 and D-7, specs/rp-service-api/spec.md.

## Prompt

Act as the team lead and follow the epic-delivery skill and
docs/modules/ROOT/pages/develop/agents.adoc. Deliver stage 2 of
openspec/changes/delete-refuses-referenced from handover.md, in the worktree
.worktrees/delete-refuses-referenced-s2 (branch feat/delete-refuses-referenced-s2): rebase it on
develop first, then continue from task 2.2.
