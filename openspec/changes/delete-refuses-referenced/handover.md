# Hand-over: delete-refuses-referenced, after stage 2

## Done

Stage 1, PR #224 (merged). Stage 2 (tasks 2.1–2.5, the fix pass, the full review), PR #225
(merged by the watch-and-merge command after this note). Accepted by the owner on 2026-11-21
(`evidence/acceptance.md`). The docs stage is written on `docs/delete-refuses-referenced-s3`
(worktree `.worktrees/delete-refuses-referenced-s3`; `evidence/docs-owed.md`).

## Decided since the PLAN

D-1 to D-14 (design.md, Delivery decisions). Scenarios signed off (evidence/clarity-gate.md).

## Open

- #226: a commit that adds a comment on a root and removes that root loses the comment with a
  misleading `Conflict` (predates this change).
- #227: structural tidy-ups under the delivery floor (the judged root unnamed in `in_use`,
  `ReferrerRow` by position, the guard inside `Transaction`, test helpers, docstrings).
- Stage 1 review S2 (the annotation on a non-root class is inert) is under the floor (D-6); not
  raised further.

## Next

Stage 3 (docs): rebase `docs/delete-refuses-referenced-s3` on develop, `make docs-reference`,
reconcile `proposal.md` with what was built (P-0004), tick 3.1 and 3.2, the full gates, the PR
with one review pass, merge; then archive the change (`openspec archive delete-refuses-referenced
--yes`) in its own PR.

## Prompt

Act as the team lead and follow the epic-delivery skill and
docs/modules/ROOT/pages/develop/agents.adoc. Finish openspec/changes/delete-refuses-referenced
from handover.md: deliver stage 3 (docs) from the worktree .worktrees/delete-refuses-referenced-s3
after rebasing it on develop, then archive the change.
