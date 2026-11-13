# Acceptance: atomic-commit

> Derives from: EPIC `atomic-commit` (proposal.md, issue #83).

**Verdict: accepted by the developer, 2026-11-13**, with the conflict message to read for a person
(PD-20a) and the stage 2 review fixes (PD-20b to j) to land before the merge of #93.

## What was shown (2026-11-13, real Fuseki, the toy library)

Run through the Python API (`UnitOfWork` on a `Session`), output pasted to the developer:

1. One unit of work changes books A and B, adds C and removes D, commits once: all four applied,
   new version tokens held, no commit marker left in the registry.
2. Two sessions: mine reads A and B, the other changes B and commits, mine edits both and
   commits: `Conflict` with `iris` naming only B; A not written (all or nothing).
3. 600 new books with the default limit of 500: `commit()` raises `CommitTooLarge` naming 600 and
   500; `commit(batches=True)` stores all 600 in 2 update requests.
4. The same import re-run in a new unit of work, as after a crash: 0 update requests, 600 stored,
   none duplicated.

## The developer's first answer: "not yet"

- The `Conflict` message named a graph IRI and a raw version token. Decided: it names root IRIs
  in words, no tokens (PD-20a).
- The stage 2 review bugs were fixed first (PD-20b, c).
- The developer asked for the intended behaviour in depth; the lead explained it (guards per
  change, one request, the marker, `Conflict.iris`, retry by the caller, the limit, both batch
  retry paths). The developer: "I understand now the feature, looks fine … generally I have a
  positive verdict", and asked for that explanation in the docs (evidence/docs-owed.md).
