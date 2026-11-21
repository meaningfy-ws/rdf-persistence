EPIC: test-debt-paydown (proposal.md). Decisions: design.md PD-1 to PD-17, DEC-1 to DEC-4.

Every task: test-first where it adds a test; task gate `make test-changed check-quality`
(`make test-fast check-quality` after a `domain` module or a port); commit body
`Refs: test-debt-paydown <task> <PD>`. Builders never commit; the lead does, and ticks this file.
Branch `change/test-debt-paydown-build` off `develop`; one PR after stage 3 (PD-14). Builders
never edit `tests/audit/scenario-map.csv`: the lead adds the new tests' rows after each task or
parallel group, then runs `make refresh-map`.

## 1. Stage 1: test structure (tests only)

- [x] 1.1 PD-11 moves: the 13 tooling tests to `tests/unit/tooling/`, the 17 package tests and
  `sparql_threads.py` to `tests/unit/package/` (refresh-b §2), `git mv` committed first;
  `parents[3]` in the 21 files; `Makefile:55, :121`; `testing.adoc:27`; `tests/changed.py` as PD-11
  says (rule 11 → `tests/unit/package/`, rule 2 → `tests/unit/tooling/test_check_docs.py`,
  `root_unit_tests()` and `root_tests` removed, the root-file branch kept);
  `tests/unit/tooling/test_changed.py` follows; the importers of moved modules rewritten
  (`test_public_surface.py:22`, `test_theme_contracts.py:20`, `test_no_old_module_paths.py:17-18`,
  `access/test_wire_models.py:12`, `testkit/test_model_guard.py:9`,
  `tests/feature/test_technical_models.py:35`), `test_sparql_parser_threads.py:22`'s
  `-m tests.unit.package.sparql_threads`, `test_no_old_module_paths.py:36, :47, :51, :53`
  (`THIS_FILE`, the exempt paths); the `rp-developer-checks` delta's scenarios pass; then
  `make refresh-map` and `make test-durations`. Accept: no `tests/unit/test_*.py` left;
  `make test-fast` collects the count before minus 1
  (`test_the_root_level_unit_test_files_are_the_real_ones` goes) plus the new scenario tests;
  `make refresh-map` exit 0 with "Removed rows (1)", that test's row.
- [x] 1.2 PD-8, after 1.1: every source module of the table to its home (one module per step,
  `make test-fast` after each); then `tests/unit/tooling/test_no_cross_test_imports.py`. Accept:
  the guard passes on `tests/`, and its own test fails on each of the five planted forms.
- [x] 1.3 PD-1 (except TC-37a, TC-38) and PD-17: the replacements, the `Mapper` limit, the five
  classes in `testing.adoc` rule 3, a `# X<n>` comment on each kept line (in `test_relay.py`,
  1.4 adds them). Accept:
  `grep -rnE "monkeypatch\.(setattr|delattr)" tests/unit tests/generator/unit` lists only lines
  (or the statements those lines open) with a trailing
  `# X1` to `# X5`, TC-37a/TC-38 (stage 2), or non-toolkit targets; the builder reports
  SparqlError's outcome to the lead in its hand-off.
- [x] 1.4 PD-4 and PD-16 in `tests/unit/events/test_relay.py`, `tests/unit/api/test_events_route.py`,
  `tests/unit/api/test_open_event_stream.py`, plus PD-17's `# X3` comments in `test_relay.py`.
  Accept: S1-S3 as PD-16 states; with
  `PYTEST_ADDOPTS="--durations=0" make test-changed`, the call phase of d18
  (`test_relay.py:307-321`, 0.192 s today) and of the grant-removed keep-alive test
  (`test_events_route.py:236-243`, 0.881 s today) are each under 0.1 s.
- [x] 1.5 PD-9 and PD-10. Accept: 17 token cases, 1 email case; each hand mutation is caught (the
  builder lists them in its hand-off, the lead puts them in the commit body); `test_documents.py`
  has 2 tests on `each_policy_documents`.
- [x] 1.6 PD-11's rest, after 1.3 to 1.5: `test_tenant_move.py` literals and its `.importlinter`
  contract; class-comment form; plan numbers; marker completeness; Hypothesis `-n 2`;
  `utc_now`; `listing_shelf` and personas; conftest constants; `TEST_DATA_DIR` and
  `load_text_file` deleted. Accept:
  `grep -rniE "equivalence class|\bstage [0-9]|\btask [0-9]+\.[0-9]+" tests --include=*.py` is
  empty; `make check-architecture` passes with the new contract;
  `make refresh-map` exit 0 with "Removed rows (0)".
- [x] 1.7 Lead: stage-1 full gates, one L2+L3 pass (P-0005), fixes, gates again, rebase on
  `develop`, ticks.

## 2. Stage 2: production seams and clean-ups

- [x] 2.1 `Relay.paused()` (PD-2) with its three unit tests; then TC-37a and TC-38 use it.
  Accept: no `monkeypatch` in `test_events_route.py`; the `rp-events` scenarios pass.
- [x] 2.2 PD-5. Accept: `test_data_plane_statuses_map_to_errors` passes unchanged in its asserts.
- [x] 2.3 PD-6. Accept: each new test fails when its half of the guard is removed by hand.
- [x] 2.4 PD-7 (cache and warm once; probe imports updated). Accept: the median of 7 `ToyService()`
  timings drops by ≥ 25 % (before and after, one checkout); the revised `test_shacl` test passes;
  a new test in `tests/unit/api/test_shacl.py`: two same-size rewrites of a shapes file in
  `tmp_path`, each `Documents` gets its own.
- [x] 2.5 PD-15. Accept: both delta scenarios pass as the two tests PD-15 names; the Redis test
  passes `poll_seconds=0.05`.
- [x] 2.6 Lead: the `rp-messages` delta (DEC-1) checked against `Transaction`'s docstring and
  `test_an_empty_commit_does_not_spend_the_command_for_the_real_one_after_it`
  (`tests/unit/messaging/test_messagebus_adversarial.py:353`); stage-2 full gates; one L2+L3 pass;
  fixes; gates again; rebase on `develop`.

## 3. Stage 3: mutation

- [x] 3.1 Lead: `make mutation`; the survivor list in `inputs/survivors-before.md` (commit,
  selection).
  Each survivor is assigned there: to 3.3 if its killing test belongs in a `tests/unit/iris/` file
  other than `test_layout.py`, else to 3.2.
- [x] 3.2 Kill the survivors assigned to 3.2 in PD-12's 3.2 files, in parallel with 3.3. Accept:
  each is killed by a test in those files, or handed to 3.4 with its reason.
- [x] 3.3 Kill the survivors assigned to 3.3 in the other `tests/unit/iris/` files; L' timeboxed
  (PD-12). Accept: as 3.2, in its files.
- [x] 3.4 `tests/audit/equivalent-mutants.md`: every remaining survivor with its one-line reason.
  Accept: `make mutation`'s survivors = the file's list, exactly.
- [x] 3.5 Lead: full gates; the final review (L1, L2, L3 apart, L4+L5 one); fixes; `proposal.md`
  reconciled (P-0004); rebase on `develop` and full gates again; `make refresh-map`; the PR
  ("Closes #215 S1-S3" in the body); CI green (PD-14); merge; acceptance by the owner; no docs
  owed beyond `testing.adoc` (said in `evidence/docs-owed.md`); archive.

## Roadmap

1.1 → 1.2 → (1.3 ∥ 1.4 ∥ 1.5) → 1.6 → 1.7 → (2.1 ∥ 2.2 ∥ 2.3 ∥ 2.4 ∥ 2.5) → 2.6 → 3.1 →
(3.2 ∥ 3.3) → 3.4 → 3.5

## Verification

`make check-all`, `make test-containers` and `make mutation` pass, the mutation survivors match
`tests/audit/equivalent-mutants.md`, `openspec validate test-debt-paydown --strict` passes, and the
PR's CI is green before the merge.
