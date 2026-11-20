# Hand-over: listing-contains-filter, after stage 1

## Done
Stage 1, the only stage (SMALL), PR #216; the developer merges it.

## Decided since the PLAN
D-1 to D-11 (design.md, Delivery decisions), and the review findings under the floor.

## Open
- For the developer to validate (R-0007): the delivery decisions D-1 to D-11, in particular D-9
  (a listing's `offset` above 2^53 − 1 is now 400 `bad-query`, a small API contract change beside
  the shape) and D-8 (the public-surface snapshot refreshed whole, 79 stale module paths fixed).
- Upstream, not filed: rdflib lets a huge SPARQL `OFFSET` overflow `itertools.islice`
  (`ValueError … <= sys.maxsize`); D-9's bound makes it unreachable here. Filing it is the
  developer's call.
- On `develop`, outside this change: 38 tests of earlier changes have no row in
  `tests/audit/scenario-map.csv` (`make refresh-map BASE=origin/develop`; D-11).
- Under the floor, possible follow-ups: `holds_text` on an owned-part slot (S-1), a commit-guard
  test with a contains condition (S-2).

## Next
After the merge: the acceptance demo or its recorded skip (`evidence/acceptance.md`), the docs
decision (`evidence/docs-owed.md`: the docs pages shipped in this PR), then archive the change
per `spec-stewardship` with `openspec archive listing-contains-filter --skip-specs --yes`: the
deltas are already synced into `openspec/specs/` (D-13). Read first: tasks.md §2.2, design.md D-1 to D-11, proposal.md As built.

## Prompt
Act as the team lead. Close openspec/changes/listing-contains-filter from handover.md: the
acceptance decision, the docs decision and the archive.
