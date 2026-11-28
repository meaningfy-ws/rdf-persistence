# Hand-over: dependent-aggregates, after stage 1

## Done
Stage 1 (the annotation and its schema check), PR #446 (merged by the watch-and-merge command after
this note).

## Decided since the PLAN
D-1 to D-7 (design.md, Delivery decisions).

## Open
- The developer validates D-1 to D-7 and the scenarios (`evidence/scenario-signoff.md`).
- Under the floor in stage 1 (D-7): more refusal-branch fixtures, a shared concrete-descendants
  helper, `pattern_of` bound twice in `uml/tags.py`.
- The checker's minor findings: tests do not name their spec scenarios; noted, not fixed.
- Stage 2 must change the OpenAPI table rows of `audit-results` and `audit-findings` (404 on create
  and replace, PD-18); the refusing-classes lists in tests still name classes by hand.
- Stage 3 waits for `aggregate-composition` to merge its converter (stage 1 of that change).
- A rebase on `develop` before the merge regenerated the toy's services and moved the public
  surface count to 160 (develop added a name too).

## Next
Stage 2, task 2.1. Read first: tasks.md §2 (Roadmap order: 2.5a before 2.5, 2.7 before 2.6),
design.md PD-3 to PD-11, PD-18, D-1 to D-3, RISK-1, RISK-8; evidence/attack.md.

## Prompt
Act as the team lead. Deliver stage 2 of openspec/changes/dependent-aggregates from handover.md.
