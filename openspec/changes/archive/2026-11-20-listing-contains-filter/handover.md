# Hand-over: listing-contains-filter, after stage 1

## Done
Stage 1, the only stage (SMALL), PR #216, merged by the developer's admin merge. Accepted on
2026-11-20 (`evidence/acceptance.md`); docs shipped in the PR (`evidence/docs-owed.md`); specs
synced and the change archived in the same PR.

## Decided since the PLAN
D-1 to D-13 (design.md, Delivery decisions).

## Open
- Upstream: https://github.com/RDFLib/rdflib/issues/3739 (rdflib's `OFFSET` overflow); D-9's
  bound makes it unreachable here, so nothing waits on it.
- `holds_iri` ignores the schema's default range (D-12): harmless for every caller today; left
  because its impact is CRITICAL.

## Next
None for this change. The next consumer-need change from `openspec/changes/README.md`.

## Prompt
None: the change is closed.
