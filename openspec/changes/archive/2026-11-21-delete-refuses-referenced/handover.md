# Hand-over: delete-refuses-referenced, after stage 3

## Done

Stage 1, PR #224. Stage 2, PR #225 (merged with `--admin` on the owner's word, its last check
green after). Accepted by the owner on 2026-11-21 (`evidence/acceptance.md`). Stage 3 (docs,
`proposal.md` reconciled, the D-15 fix: the annotation value is read in any case), the PR from
`docs/delete-refuses-referenced-s3` (merged by the watch-and-merge command after this note). Every
task in `tasks.md` is ticked.

## Decided since the PLAN

D-1 to D-15 (design.md, Delivery decisions). Scenarios signed off (evidence/clarity-gate.md).

## Open

- #226: a commit that adds a comment on a root and removes that root loses the comment with a
  misleading `Conflict` (predates this change).
- #227: structural tidy-ups under the delivery floor (the judged root unnamed in `in_use`,
  `ReferrerRow` by position, the guard inside `Transaction`, two modules outside the import
  contract, test helpers, docstrings).
- Flaky under load, unrelated to this change: `test_sparql.py::test_a_pattern_too_long_for_the_parser_is_refused_with_the_advice_to_split`
  and `test_events_route.py::test_a_reader_whose_queue_filled_resumes_and_gets_every_missed_activity_once`
  (each failed once in a full run and passes alone).

## Next

Archive the change (`openspec archive delete-refuses-referenced --yes`) in its own PR, then show
the owner D-1 to D-15 for validation (R-0007).

## Prompt

Act as the team lead and follow the epic-delivery skill and
docs/modules/ROOT/pages/develop/agents.adoc. Archive openspec/changes/delete-refuses-referenced
from handover.md in its own PR off develop, then present its delivery decisions D-1 to D-15.
