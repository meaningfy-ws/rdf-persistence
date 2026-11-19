# Hand-over: domain-model-per-theme, shaped

## Done
EPIC shaped (`proposal.md`, DEC-1 to DEC-8), PLAN derived, attacked (seven counterexamples, all
answered in the PLAN) and gated 7.8 then 8.9; accepted by the developer with the run-2 fixes (DEC-9).
Seeds, the attack and the developer's answers: `inputs/seed.md`.

## Decided since the EPIC
DEC-9 (accepted gate). PD-4 (migrations checked on `rp.yaml` only), PD-5 (a theme root with classes
in `AUTO` mode), TC-03's committed `v0.6.0` fixtures are the lead's choices.

## Open
None. Acceptance demo: MEDIUM appetite, the developer's call at the session's start.

## Next
Precondition: `target-kind-from-the-model` merged into `develop`. Deliver tasks 1.1 to 3.1 in one
stage, one PR (task 2.1 is one atomic commit, PD-7). Then release 0.7.0 with both changes (DEC-8):
the changelog PR, release-please's PR, `main` fast-forwarded to the tag; move the getting-started
example's pin to `v0.7.0` after the tag exists.

## Prompt
Act as the team lead (epic-delivery). Read docs/modules/ROOT/pages/develop/agents.adoc, then deliver
openspec/changes/domain-model-per-theme from its handover.md in .worktrees/lead (detached at
origin/develop), once target-kind-from-the-model is merged: one stage, one PR, task 2.1 as one atomic
commit, builder worktrees under .worktrees/, re-index GitNexus before task 2.1, gates make check-all,
make test-containers, make check-spec and make refresh-map on the PR's commit, one L2+L3 review pass
plus the full review (L1, L2, L3 apart, L4+L5) as the epic's end, the tester after task 1.2, the
checker, reconcile proposal.md (P-0004), archive the change, merge on green CI, then cut 0.7.0 per
develop/index.adoc#release. Detach the lead worktree before watch-and-merge. Commit, push, open and
merge PRs without asking.
