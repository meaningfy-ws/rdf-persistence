<!-- SECONDARY INPUT: preserved, never groomed. The EPIC (../proposal.md) is the shaped truth. -->

# Seed: commit several aggregates of one tenant atomically

## Source

- GitHub issue [#83](https://github.com/meaningfy-ws/rdf-persistence/issues/83) (filed 2026-11-12),
  consumer MWB2, change `domain-model-v2`, requirement R-7 (`requirements/rdf-persistence.md`).
- Developer decision on the consumer side (2026-11-12): "we need a mechanism for these
  multi-aggregate saves".
- The consumer session's note (2026-11-12): MWB2's v2-02 waits on it. Its draft 5 imports a source
  version as one aggregate in one commit, so the bulk-import pressure drops, but the "Map element"
  dialog still saves up to five aggregates at once, so the atomic commit is still needed.
- The consumer session recommended its own small toolkit change, done before the collaboration EPIC.

## What the code does today (checked 2026-11-12 at `develop` `e70c889`)

- `UnitOfWork.commit` (`services/mapper.py`) loops over the dirty roots and calls
  `Session.replace_graph` or `Session.add_graph` for each: one SPARQL update request per root. Its
  docstring: "Each aggregate is committed atomically, the set of them is not".
- `Session.replace_graph` and `Session.remove` already send one update request of several
  operations (`REPLACE`, `REMOVE` in `services/session.py`), each operation repeating the version
  guard `GRAPH $graph { $graph $p_version $old }`; the comment there states that a store applies
  one request as one transaction (Fuseki/TDB2 does).
- `ADD` is one conditional insert, `FILTER NOT EXISTS { GRAPH $graph { ?s ?p ?o } }`.
- Each write is confirmed by an `ASK` for the new token (`ASK_TOKEN`), or for no triple (remove).
- `UnitOfWork` keeps the version tokens in the private `_versions`; there is no `remove`.

## Lead's decisions (2026-11-12, developer away, asked to decide)

- Its own change, done first: independent of the collaboration features, and the collaboration
  EPIC's cascade delete, transition and delete-with-comments all need it.
- The version token on the object-level read (`UnitOfWork.version`, DEC-8 of the collaboration
  EPIC as shaped in PR #82) moves here: this change reworks `UnitOfWork`'s versions anyway.
- Batch mode is kept (the issue asks for it; regeneration and deletion of many roots remain bulk
  use cases) but is its own stage, after the atomic commit.
