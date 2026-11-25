# Hand-over: review-floors, parked after building all three stages (2026-11-25)

## Done
- Plan PR #384 merged (EPIC, PLAN gated 9.4, scenarios signed off).
- Stage 1 merged as PR #393 (`change/review-floors-s1`). Its gate ran only the unit tier: the
  feature and generator tiers did not run (see the correction comment on #393); they run on the
  stage 3 tip below, which carries stage 1's code.
- Stages 2 and 3 are built, reviewed and fixed, committed and pushed, **not merged, no PR yet**:
  `change/review-floors-s2` (generator: tasks 2.0-2.7) and `change/review-floors-s3` (events,
  testkit, docs, `load_warm_shapes`, the patch-marker guard: tasks 3.0-3.10), stacked: s3 is s2
  plus stage 3. Worktrees `.worktrees/review-floors-s2`, `.worktrees/review-floors-s3`.
- The full end-of-epic review (L1, L2, L3, L4+L5 over the three stages) ran; its accepted findings
  are fixed (D-10). `proposal.md` is reconciled (P-0004). Task boxes ticked to 3.10.

## Decided since the PLAN
D-1 to D-11 (`design.md`, Delivery decisions). The ones that changed the PLAN: D-5 (the theme map
stays on the generator side), D-7 (the `rp-testkit` scenario names the start-up only), D-11
(`_CollectionCheck` in the model guard's allow list).

## Open
- **No complete test run on stages 2 and 3.** Quality checks pass on both tips; on stage 3's code
  `make test-containers` (368), `make test-e2e` (19) and `make check-generated` passed. Every full
  unit run was killed by SIGTERM from outside this session (host load, other sessions' `pkill`).
- **The owner pulls new changes to the testing system into `develop`.** Rebasing s2 and s3 onto
  them may conflict in what this change touched: `tests/toy.py`, `tests/conftest.py` and
  `tests/generator/unit/conftest.py`, `tests/audit/scenario-map.csv`, the `# X1`-`# X5` markers
  (`tests/unit/tooling/test_patch_markers.py` will flag any new unmarked patch of toolkit code),
  `docs/modules/ROOT/pages/develop/testing.adoc` rule 3, and the Makefile targets the gates use.
  Resolve toward `develop`'s new testing system; keep this change's intent (P-0003 for any
  generated file: take develop's, then `make generate`).
- **D-9 is the owner's call:** one patch (`tests/unit/collaboration/test_aggregate_validators.py`,
  a tripwire) is marked `# X2`, although rule 3's X2 says "pass-through spy". Reword X2 or give
  the test a seam.
- GitNexus could not re-index (another session held its database, D-1); re-try `make reindex`.

## Next
1. In each worktree: `git fetch origin`, then rebase **s2 onto `origin/develop`**, then **s3 onto
   s2** with `git rebase --onto change/review-floors-s2 <old s2 tip> change/review-floors-s3`
   (old tip from `git rev-parse change/review-floors-s2@{1}` right after the s2 rebase). Conflicts
   in `design.md` Delivery decisions: keep both sides. `make install` in each worktree.
2. On the s3 tip, one at a time: `make check-quality`, `make test-unit`, `make test-feature`,
   `make test-generator`, `make test-containers`, `make test-e2e`, `make check-generated`,
   `make refresh-map` (exit 1 only for tests other changes left unmapped). Fix what fails (a
   fixer brief per `epic-delivery`; record in `design.md` as D-12 and on).
3. On the s2 tip, the same `make test-*` tiers (or accept the s3 run as covering s2, recorded).
4. Open the stage 2 PR, merge (P-0021: local gate, results in the PR body); rebase s3 onto
   `develop`, open the stage 3 PR, merge. Link the full test result from #393.
5. Task 4.1: post `close-comments.md` (this folder; replace PRLIST, PRS1 = #393, NEWISSUE), close
   #215, #272, #273, #275, narrow the rest, open the 189-v issue. Task 4.2 and the archive
   (`spec-stewardship`); update `openspec/changes/README.md`.

Read first: `tasks.md` §2-§4, `design.md` Delivery decisions D-1 to D-11, this note.

## Prompt
Act as the team lead. Finish openspec/changes/review-floors from handover.md: rebase stages 2 and
3 onto the latest develop (it carries new testing-system changes), run the gates, merge both stage
PRs, then close the issues and archive the change.
