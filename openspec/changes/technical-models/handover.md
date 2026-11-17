# Hand-over: technical-models, after stage 3

## Done
Stage 3 (central settings, tasks 3.1–3.5), PR #150 (merged by the watch-and-merge command after
this note). Stage 2 was #145, with the follow-up #146 (D-27). The developer's grant of push, PR
and merge on green CI holds until the change ends (D-26).

## Decided since the PLAN
D-1 to D-43 and the floor lists of stages 1 to 3 (design.md, Delivery decisions). Stage 3 adds
two external-library work-arounds (D-31 LinkML list defaults, D-34 pydantic-settings' private
`_load_env_vars`), the as-built divergences D-32, D-35, D-36, and the rebase onto
`otel-observability` stage 1 (D-37).

## Open
- **For the developer** (asked, not yet answered):
  - **D-33:** add an `rp-generation` requirement "A slot can default to an instance of its class"
    (type-range, required-slot, declaration-order and multivalued refusals as scenarios) in task
    4.2? It changes a signed spec, so it needs sign-off.
  - **D-31:** file a LinkML issue (a multivalued `ifabsent` is generated as a scalar default)?
- **For the full review after stage 4:** tester F-1 (an `inf` duration is accepted; an infinite
  JWKS TTL keeps a rotated-out key), and the other stage 3 floor items.
- Owed to task 4.3 beyond its list: the pre-split docstrings (stage 1 floor), `pydantic_split.py`'s
  module docstring (stage 3 L2 S6), `develop/index.adoc:194` (S8), the how-to's table of every
  removed keyword (the changelog now lists them, D-42).
- `make refresh-map` exits 1 on about 113 unmapped test ids, none from this change: older tests,
  and #149's.
- **Process:** after every rebase, run `make generate` and `make check-generated` and read the
  whole `git status`, not its head (D-27, D-37). Parallel builders each get their own worktree;
  briefs name absolute paths for Serena (D-36: a relative path resolved against the main checkout,
  which another session held). A builder's repo-wide `ruff --fix` touches other changes' files;
  briefs forbid it. GitNexus indexes the main checkout, which may be on another session's branch.
- Generator bootstrap: task 4.1 adds the `testkit` target and moves generator records; stub,
  `make generate`, restore, `make generate` again if the generator imports a moved record.

## Next
Stage 4, task 4.1, on `change/technical-models-s4` off the latest `develop`. Read first: tasks.md
§Stage 4, design.md PD-10, PD-11, D-4, D-33, RISK-7, and the floor lists; `specs/rp-generation`.
Tasks 4.1 and 4.3 can run in parallel (disjoint files); 4.2 (BDD) after 4.1. Stage 4 closes with
the full review (L1, L2, L3 separate; L4+L5 one pass, P-0005) and the reconciliation of
`proposal.md` (P-0004).

## Prompt
Act as the team lead (epic-delivery); read docs/modules/ROOT/pages/develop/agents.adoc. Deliver
stage 4 of openspec/changes/technical-models from handover.md: one PR into develop from branch
change/technical-models-s4 off the latest develop, with the full review and the reconciliation of
proposal.md. Run tasks in parallel where their files are disjoint. Rebase before the PR.
