# Hand-over: unique-key-nulls-equal, after stage 1 (the only stage)

## Done
Stage 1, tasks 1.1 to 1.8, PR #211 into `develop`. The developer merges it after this note.
- A tenant-scoped unique key may set `consider_nulls_inequal: false`: an absent slot counts as one
  value, equal only to another absence, in the same guarded update; `key_duplicates()` shows it as
  `rp:absentKeyValue`. Keys without the option send byte-identical queries (G-4).
- Review: one L2+L3 pass, 5 findings, none Critical; W1 and W2 fixed as D-7 at the developer's
  word, S1 to S3 under the floor (PR body).
- Both full-gates runs passed (PR body). The demo was skipped by the developer
  (`evidence/acceptance.md`). No docs owed. The change is archived in this PR.

## Decided since the PLAN
D-1 to D-7 (design.md, Delivery decisions); D-4 superseded by `collection-has-part` PD-10.

## Open
- Under the review floor: S1 test assert messages, S2 fold ex1–ex3 into one table, S3 the
  `KEY_HELD` comment and RISK-2.
- RISK-2 stands: a key of only optional slots, all absent, makes the guard scan the type.
- The consumer (MWB2) `v2-04` stage C and `v2-05` 6.1 can proceed once a release holds this change.
- Environment, for builder briefs:
  - Parallel builders in one worktree stall on the freshness plugin whenever one edits a model or
    generator input (D-3): run such tasks first or in their own worktree.
  - In the sandbox: `UV_CACHE_DIR=$TMPDIR/uv-cache`; `typecheck-ts` needs
    `npm_config_cache=$TMPDIR/npm-cache` and `registry.npmjs.org` allowed; Docker (container
    tests) is reachable only outside the sandbox.
  - A rebase conflict in generated files: the generator refuses a conflicted manifest; delete the
    conflicted outputs and `make generate` from the merged sources (D-6, P-0003).

## Next
None: the EPIC is delivered and archived. The next consumer-need EPIC is in
`openspec/changes/README.md`.

## Prompt
None for this change. For a release: act as the release manager and cut the next release from
`develop` once #211 is merged.
