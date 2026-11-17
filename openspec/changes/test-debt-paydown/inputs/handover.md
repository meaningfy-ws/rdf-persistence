# Hand-over: test-debt-paydown (2026-11-17)

**State:** shaped, not planned. `proposal.md` (the EPIC) and the `rp-messages` spec delta are
written; `design.md` and `tasks.md` (the PLAN) are not. Nothing is built.

**Start here (next session, as lead, `epic-delivery`):**
1. Work in your own worktree on branch `change/test-debt-paydown` (another session has used the
   main checkout; create the worktree with `git worktree add <path> change/test-debt-paydown`
   outside the sandbox, under `temp/`).
2. Read `proposal.md`, then `inputs/facts.md` (one recommended decision per debt item, with
   file:line) and `inputs/domain-survivors.md`. The probes behind facts 6 and 8 are in
   `inputs/probes/`.
3. Write `design.md` + `tasks.md` from the facts: decide every choice in the PLAN (the grooming's
   first clarity gate scored 7.0 for inherited "or"s). Gate it with a fresh scorer (≥ 9/10).
4. Deliver in three stages with builders in worktrees the lead creates (not the Agent tool's
   isolation: it bases worktrees on the remote default). One pull request; **CI green on the PR
   before the merge** (the grooming merged before CI and broke it).

**Lessons to carry (from the grooming, `archive/2026-11-16-test-suite-grooming/inputs/`):**
- Measure a set-up change before landing it; two of four estimates were 0 %.
- A class 2 survivor is the case that fails under its branch's mutation; prove domain merges with
  an unchanged `make mutation` set.
- A test moved to a lane CI does not run loses its guard; name the CI lane of every moved test.
- pytest-timeout runs with `signal`; a CI limit or dist-mode change needs a hosted-runner run.
- Builders: no `sed -i`/heredoc rewrites, no `pkill`, no `git stash`; the lead ticks `tasks.md`.

**State of the repository at hand-over:**
- `develop` = `be129a0` (#136 merged); its CI is green. A cancelled develop run from 06:34 UTC
  (unit job cancelled at 60 min) is the pre-#136 hang, already fixed.
- Release PR #134 (0.5.0) is open, for the owner. The main checkout is on another session's branch
  (`docs/manual-revision-notes`); do not touch it.

**Skillery feedback filed from the grooming** (the owner works on these in parallel; if a fix
ships before this change is delivered, follow the fixed skill, not this note):
#307-#315 test-suite-care (#315 also epic-planning), #316 and #317 epic-delivery, #318
project-setup, #319 implementer, plus a comment on #195. The owner declined the comment on #283
(merge before CI is green).

**Open for the owner (ask once, at the PLAN gate):** whether this change merges only after the
PR's CI is green. The lead's lesson says yes; the owner has said "ignore PR GH runs" and declined
the #283 comment. Recommended: wait for CI only when the change touches CI, timeouts or lanes
(this one does, in stage 1).

**Owner's words for this change:** decisions 15-17 of the grooming: "not sure; do what makes
sense", "fix the debt, do what is right", "do what is right; what was done was done, now build on
top of this knowledge".
