# Acceptance: nested-collections

## Demo (2026-11-21, stage head e88913d2)

The design's worked example on the toy library, over the in-memory store, as one script outside the
repository (`demo_nesting.py`, kept in the lead's scratchpad). Run:

```
uv run pytest -s -p no:cacheprovider -p no:randomly --rootdir=. -c pyproject.toml demo_nesting.py
```

Exit 0. What it showed, step by step:

| Step | What was done | What happened |
|---|---|---|
| 1 | Books b1..b3; `poetry` (leaf) holds b1, b2; `library` (`nests`) holds b3 and `poetry` | stored |
| 2 | `members(library, deep=True)` and `members(library)` | deep: `[b1, b2, b3]`, no sub-collection; plain: `[b3, poetry]` |
| 3 | A reader without read on `poetry` reads `library` deep | `[b3]`, `hidden_count=1`; `poetry` never named |
| 4 | Save `poetry` naming `library` | `InvalidBody`: "saving poetry would make a cycle: poetry → library → (0 more) → poetry" (full IRIs); `poetry` unchanged |
| 5 | Two transactions collected: x adds y, y adds x; committed in turn | the second gets `Conflict` naming y ("was changed by someone else since it was read"); its retry gets the cycle refusal |
| 6 | `library` names a nested shelf of authors | `InvalidBody`: "not stored aggregates of Book" |
| 7 | `delete_cascade(library)` | `library`, `poetry` and b3 deleted; b1, b2 (poetry's books) kept |

The race and a three-level deep read also run against Fuseki in `make test-containers`
(`tests/integration/store/test_collaboration.py`).

## Known risk shown to the developer

D-5: across two transactions, a member-class change of a collection racing a save that makes a
nesting collection hold it can commit both when the holder commits first; a replace that restores
the member class repairs it.

## Verdict

Pending the developer.
