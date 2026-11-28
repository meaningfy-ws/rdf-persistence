# Hand-over: workflow-assignees, after stage 1

## Done
Stage 1 (tasks 1.1 to 1.8, and the stage-1 part of 3.1), PR #443, merged with `--admin` after
this note on the developer's grant (D-14).

## Decided since the PLAN
D-9 to D-21 (design.md, Delivery decisions). D-21: `develop` (aggregate composition, dependent
aggregates) was merged into the branch once instead of a rebase; the full gates ran again on the
merge, `make test-containers` included.

## Open
- The developer saw the CRITICAL GitNexus rating of stage 1 (the blast radius of the write path,
  53 flows) and said proceed (D-18). Stage 2 touches the grants route: run impact on
  `TenantApi.set_grants` and report a HIGH or CRITICAL first.
- Follow-up, ours: `persistence/services/listing.py` (l.71, l.194) and `persistence/services/jsonld.py`
  (l.27, l.151) keep their own absolute-IRI checks; `core/domain/sparql.is_absolute_iri` (D-18)
  could serve them. Not in this EPIC's scope.
- `make refresh-map` lists 242 tests from `develop` with no scenario-map row (none from this
  change); it exits non-zero until someone maps them.
- `make reindex` took 650 s in this worktree, against about 20 s in the durations table; the
  first one failed and needed the clean rebuild (D-12).
- Under the floor at stage 1 (PR #443, Delivery decisions): test gaps the review named (a principal
  that reads only through a global role; a kept principal not re-checked; a `command` passed to
  `assign`; the kit's `access_of` wiring; two agents in the history), and the duplicated
  `_workflow_of` in `assignments.py` and `transitions.py`. The full review after stage 2 (D-17)
  sees them again.
- The checker passed stage 1 with two map-label findings under the floor: the scenarios "a
  reviewer takes the work" and "a reader without a role on the edges" have no scenario row of
  their own in `tests/audit/scenario-map.csv`; fix them with task 3.1 of stage 2.
- Stage 2 already runs in parallel (D-20, in stage 2's `design.md`): `feat/assignee-release` in
  `.worktrees/assignee-release`, stacked on `378ca201`, with task 2.4 written; rebase it onto
  `develop` now that this merges.

## Next
Stage 2, task 2.1. Read first: tasks.md §2, design.md D-6, D-7, D-19, specs/rp-workflow/spec.md
("Losing read access releases an assignment", "A person's queue is one listing"). The lead runs
`make install` (never a bare `uv sync`, D-16), then `make reindex`, then `make test-seed`, and
briefs builders only after the seed's notice (D-15).

## Prompt
Act as the team lead. Deliver stage 2 of openspec/changes/workflow-assignees from handover.md,
in the worktree .worktrees/workflow-assignees on a new branch from develop.
