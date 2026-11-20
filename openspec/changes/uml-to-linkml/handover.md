# Hand-over: uml-to-linkml, after stage 1

## Done
Stage 1 (tasks 1.1–1.9), PR #212 (merged by the watch-and-merge command after this note). Task
2.1 is done too: the rule table is frozen (D-20).

## Decided since the PLAN
D-1 to D-22 (design.md, Delivery decisions). For stage 2 mind especially D-5 (cycles merge into
one module), D-7 (SPIKE-1 passed: `activity_root` stays inactive), D-9..D-14 (model2owl
alignment), D-16 (merge authority, admin included, on green CI), D-17, D-18, D-21 and D-22
(review floor; carry-over in task 2.9).

## Open
- To the developer at the end: W-1 of D-22 (D-18's `__slots__` working classes pass the model guard
  unseen: generate them, use `SlotDefinition`, or list them in `HAND_WRITTEN`), and the delivery
  decisions D-1..D-22 for validation (R-0007).
- Upstream issues: #208 (split pydantic modules fail on import cycles), #209 (language strings).
- IT-2's generate-and-import step is a strict xfail until task 2.3 writes `Described`.
- The UML conventions page is drafted and committed off-branch as `88066c6f` (worktree
  `.worktrees/uml-to-linkml-1.6`); cherry-pick it in task 2.7 and check it against the stage-2 code.
- Builder worktrees `.worktrees/uml-to-linkml-1.1`, `-1.5`, `-1.6` and the ref
  `backup/uml-to-linkml-pre-rebase` can be removed once #212 is merged (keep `-1.6` until
  `88066c6f` is picked).
- Builders: run `make test-fast check-quality` with `PYTEST_N=8`, and `make generate` after the last
  edit of any file under `rdf_persistence_generation/` (D-8).

## Next
Stage 2, task 2.2 (toolkit index), then 2.3 ∥ 2.4 ∥ 2.5, then 2.6 ∥ 2.7 with 2.9, then 2.8 (full
five-lens review, acceptance demo on the real `.qea` read-only, archive). Read first: tasks.md §2,
design.md PD-17..PD-21, D-1..D-22, specs/rp-uml-import/spec.md.

## Prompt
Act as the team lead. Deliver stage 2 of openspec/changes/uml-to-linkml from handover.md,
following the epic-delivery skill and docs/modules/ROOT/pages/develop/agents.adoc; work in the
worktree .worktrees/uml-to-linkml after rebasing it on develop; run builders in parallel where the
files are disjoint.
