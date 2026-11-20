# Hand-over: collection-has-part, after stage 1 (the only stage)

## Done
Stage 1, tasks 1.1 to 1.6, PR #207 into `develop`. The watch-and-merge command merges it after this
note.
- Reference collections state their members with `dct:hasPart`, and the mixin is
  `dcmitype:Collection`.
- The toolkit's schema is at version 3. `2__3.yaml` rewrites stored members at start-up and on
  restore.
- The toy library's lock is re-baselined, and the byte-identity test against 0.6.0 is dropped.
- Docs and the BREAKING release note are in `CHANGELOG.md`.
- Review: one L2+L3 pass, 8 findings, 4 accepted as Critical and fixed (D-4).
- Both full-gates runs passed. The demo was skipped; the developer accepted the change. No docs
  owed. The change is archived in this PR.

## Decided since the PLAN
D-1 to D-4 (design.md, Delivery decisions).

## Open
- Under the review floor (D-4):
  - W5: call a collection service after the start-up migration.
  - S1: share one `Collaboration` builder in the tests.
  - S2: TC-1's weak request check; integration tests importing unit-tier helpers.
- #206: the generator check for two slots sharing one IRI (RISK-2).
- The consumer (MWB2) must regenerate against `has_part` and raise its lock version where its lock
  names a collection class (PR #207 body, CHANGELOG). Its `v2-02` 2.1b can proceed once a release
  holds this change. Release-please should propose 0.8.0 (`feat!`).
- Environment, for builder briefs:
  - A fresh worktree needs `uv sync --all-extras`; without it, `make generate` lacks LinkML.
  - In the sandbox, `make` needs `UV_NO_SYNC=1 UV_CACHE_DIR=$TMPDIR/uv-cache`.
  - `check-quality`'s tsc step needs `registry.npmjs.org` and `npm_config_cache=$TMPDIR/npm-cache`.

## Next
Wave 2 waits for this merge. `nested-collections` (#198) rebases onto `has_part` (its DEC-3), and
`delete-refuses-referenced` (#201) follows.

## Prompt
Act as the team lead. Deliver openspec/changes/nested-collections from its gated PLAN, in a worktree
under .worktrees/, branched from develop after PR #207 merged.
