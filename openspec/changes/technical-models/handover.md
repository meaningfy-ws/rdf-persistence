# Hand-over: technical-models, after stage 2

## Done
Stage 2 (the templates' variables as models, tasks 2.1–2.3), PR #145 (merged as admin
on the developer's word after this note, before CI and the rebased head's local gates finished). The developer granted the lead push, PR and merge on
green CI for `technical-models` until the change ends (D-26).

## Decided since the PLAN
D-1 to D-26 and the floor lists for stages 1 and 2 (design.md, Delivery decisions). D-19 renames
PD-5's `StampGuardTerms.schema` to `schema_id`; D-17 corrects a Context row.

## Open
- **Generator bootstrap (stage 1 floor, L4+L5 W3).** Still undocumented. Task 3.1 adds
  `default_instance` to `GenerationAnnotation`, which the generator imports: stub the new import,
  `make generate`, restore, `make generate` again. A new target (task 4.1's `testkit`) may need it
  too; stage 2's new target did not. `make format` can change a generation input: re-run
  `make generate` after it.
- Owed to stage 4: the `CHANGELOG.md` line for the `python_import` annotation (stage 2 floor, L2
  W4), beside task 4.3's docs and the three pre-split docstrings (stage 1 floor, L3 S1).
- `make refresh-map` still exits 1 on 51 unmapped test ids older than this change; stage 2 mapped
  all its own.
- Builders in a worktree run `make`, `uv` and file writes with the sandbox disabled; a bare
  `uv run` prunes the `generate` extra, so narrow checks use `uv run --all-extras pytest …`.
  GitNexus indexes the main checkout only; the index errored once this stage and needed
  `gitnexus clean --force` and a forced rebuild (`develop/agents.adoc#reindex`).
- Review set: stage 2 ran P-0005's single L2+L3 pass, the tester after 2.2 and a checker. Stage 3
  carries RISK-3 and RISK-6 (task 3.2, `jwks.py`) and the PLAN puts the tester after 3.3; the full
  review runs after stage 4.

## Next
Stage 3, task 3.1, on `change/technical-models-s3` off the latest `develop`. Read first: tasks.md
§Stage 3, design.md PD-6, PD-7, PD-8, PD-12, DEC-5, DEC-8, RISK-3, RISK-6, RISK-8, D-4, D-14 to
D-26; `specs/rp-settings`.

## Prompt
Act as the team lead (epic-delivery); read docs/modules/ROOT/pages/develop/agents.adoc. Deliver
stage 3 of openspec/changes/technical-models from handover.md: one PR into develop from branch
change/technical-models-s3 off the latest develop. Rebase before the PR.
