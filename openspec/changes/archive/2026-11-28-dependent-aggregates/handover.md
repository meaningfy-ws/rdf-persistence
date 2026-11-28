# Hand-over: dependent-aggregates, after stage 3

## Done
Stage 1, PR #446; stage 2, PR #450 (both merged). Stage 3 (the converter emits a dependent root for
a generated «own graph» part), PR #452 (merged by the watch-and-merge command after this note), with
the end-of-epic full review (D-13) and its fix pass. Every build task is ticked.

## Decided since the PLAN
D-1 to D-13 (design.md, Delivery decisions).

## Open
- Acceptance is deferred to the developer (`evidence/acceptance.md`): the scenarios, D-1 to D-13,
  and two decisions the review left open (a session without `may_read` names parts; a part write
  discloses whether an unreadable whole exists). No release before that.
- Archive order: archive `aggregate-composition` first, then turn this change's `rp-uml-import`
  delta into a MODIFIED (task 3.1, D-12), then archive this change.
- Under the floor: issue #453 (both changes' review floor).

## Next
Acceptance by the developer, then the two archives in that order. Read first:
evidence/acceptance.md of both changes.

## Prompt
Act as the team lead. Run the acceptance of openspec/changes/aggregate-composition and
openspec/changes/dependent-aggregates with me from their evidence/acceptance.md, then archive both,
aggregate-composition first.
