# Hand-over: target-kind-from-the-model, shaped

## Done
EPIC shaped (`proposal.md`, DEC-1 to DEC-5), PLAN derived and attacked (`design.md`, `tasks.md`),
gated 7.8 then 8.7 and accepted by the developer with the run-2 fixes (DEC-6). Shaped in one session
with `domain-model-per-theme`; seeds in that change's `inputs/seed.md`.

## Decided since the EPIC
DEC-6 (accepted gate). PD-2 (no mixed target) is the lead's choice.

## Open
None. Acceptance demo: SMALL appetite, the developer's call at the session's start.

## Next
Deliver tasks 1.1 to 3.1 in one stage, one PR into `develop`. Release 0.7.0 after
`domain-model-per-theme` is merged too (DEC-5), unless the developer releases this one alone.

## Prompt
Act as the team lead (epic-delivery). Read docs/modules/ROOT/pages/develop/agents.adoc, then deliver
openspec/changes/target-kind-from-the-model from its handover.md in .worktrees/lead (detached at
origin/develop): one stage, one PR, builder worktrees under .worktrees/, gates make check-all,
make test-containers, make check-spec and make refresh-map on the PR's commit, one L2+L3 review pass,
the checker, reconcile proposal.md (P-0004), archive the change, merge on green CI. Detach the lead
worktree before watch-and-merge. Commit, push, open and merge the PR without asking.
