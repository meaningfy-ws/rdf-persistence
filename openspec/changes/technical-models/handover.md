# Hand-over: technical-models, after stage 1

## Done
Stage 1 (technical models in the layer that uses them, tasks 1.1–1.3), PR #144 (merged by the
developer after this note). Built on `develop` with `manual-revision-notes` stage 1 (PR #141)
merged; RISK-6 checked against `jwks.py` as landed (D-4), so task 3.2 can proceed as planned.

## Decided since the PLAN
D-1 to D-13 and the stage 1 findings under the floor (design.md, Delivery decisions). D-7 was
withdrawn (not a defect).

## Open
- **Generator bootstrap (L4+L5 W3, under the floor).** `rp-generate` imports its own generated
  output at start (`generation.generated.rp_generation`, and `services.generated.service` through
  `lock.py`/`lock_step.py`). A task that adds a type the generator uses (2.1's
  `GenerationAnnotation.python_import`, 3.1's `default_instance`) or adds or moves a target needs a
  bootstrap: stub the new import, `make generate`, restore, `make generate` again. Tell the builder
  in the brief; no page documents it yet.
- The review set: stage 1 ran L1, L2, L3 separately and L4+L5 as one (D-3). Stages 2 and 3 may take
  P-0005's single L2+L3 pass per stage, with the full review after stage 4, unless the stage
  carries a PLAN risk.
- Docs owed to task 4.3 beyond its list: the three pre-split docstrings (L3 S1) and the layer-map
  table's full rewrite (D-12 moved only the names).
- `make refresh-map` exits 1 with 51 unmapped test ids, all older than this change (jwks,
  negotiation, documents, mapper limits, `RpModel.replaced`, router `If-Match`, problems, receive,
  mostly from `manual-revision-notes` stage 1). Stage 1 mapped its own tests and remapped four rows
  of tests renamed earlier (D-11). The tool also re-quotes one `test_dependents_cost` evidence cell
  on every run; harmless.
- Builders in a worktree run `make`, `uv` and file writes with the sandbox disabled (the worktree's
  git dir and the uv cache are read-only inside it); GitNexus indexes the main checkout only, so
  impact on symbols a stage adds reads UNKNOWN until develop has them.

## Next
Stage 2, task 2.1, on `change/technical-models-s2` off the latest `develop`. Read first: tasks.md
§Stage 2, design.md PD-4, PD-5, DEC-7, the anti-patterns, D-1 to D-13; `specs/rp-generation`. The
tester runs after task 2.2 (the term models replace the bare dicts in four services).

## Prompt
Act as the team lead (epic-delivery); read docs/modules/ROOT/pages/develop/agents.adoc. Deliver
stage 2 of openspec/changes/technical-models from handover.md: one PR into develop from branch
change/technical-models-s2 off the latest develop. Rebase before the PR.
