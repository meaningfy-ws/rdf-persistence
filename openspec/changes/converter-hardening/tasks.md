EPIC: converter-hardening (proposal.md). Decisions: DEC-1 to DEC-5 (proposal.md), PD-1 to PD-8 (design.md).

> Derives from: the EPIC `converter-hardening`; the PLAN is this file and [design.md](design.md).

One stage, one pull request (appetite SMALL). Branch `change/converter-hardening` off `develop`.
Every task is test-first: its first failing test is written and seen failing before the code.
Task gate: `make test-changed check-quality`; `make test-fast check-quality` for 1.1 (a service of
the library). Commit body trace: `Refs: converter-hardening <task> <PD/DEC>` (and `Closes #<n>` in
the PR body for #229, #258, #259, #260, #261). Builders never commit; the lead does and ticks this
file. Tests of the converter run in CI lane `test-generator`; those of the library in `test-unit`.

## 1. Stage 1: harden the converter

- [ ] 1.1 #258, PD-6, DEC-5 (library). Tier unit. First failing test:
  `tests/unit/access/test_access_roles.py::test_a_non_ascii_role_is_read_as_utf8_whatever_the_locale`
  (subprocess with `-X warn_default_encoding`, `EncodingWarning` an error around the load only,
  PD-6; loads a UTF-8 file with `rédacteur`; asserts exit 0 and the role read back; fails today on the `EncodingWarning`). Then
  `test_bytes_that_are_not_utf8_are_an_invalid_role_definition` and
  `test_a_key_given_twice_is_an_invalid_role_definition`. Code: `read_yaml` in `yaml_files.py`,
  `read_mapping` on top of it, `load_role_definitions` through it. Accept: the three `rp-access`
  scenarios pass; every existing test in `tests/unit/access/` and `tests/unit/collaboration/`
  (workflow loading uses `read_mapping`) passes unchanged.
- [ ] 1.2 PD-1, PD-2 (reader). Tier unit. First failing test:
  `tests/generator/unit/test_uml_qea.py::test_a_missing_path_is_named_as_missing` (rewrites
  `test_a_missing_file_is_not_an_ea_file`; asserts the `QeaUsageError` message `<path>: no such file`).
  Then `test_an_unreadable_file_is_a_read_error` (chmod 000; skipped when run as root),
  `test_a_corrupt_page_is_a_read_error_not_a_traceback` (a fixture `.qea` with a page overwritten),
  `test_reading_a_wal_model_leaves_no_side_files` (fixture switched to `journal_mode=wal`, closed;
  asserts the folder's file list before equals after),
  `test_a_wal_model_with_a_wal_file_is_read` (a second connection holds it open),
  `test_a_view_named_like_a_table_is_refused`. Accept: the `rp-uml-import` scenarios "a missing
  model file", "a read error", "no side files", "a view in place of a table" pass; the existing
  "not a .qea" tests pass unchanged.
- [ ] 1.3 PD-3, DEC-4 (writer). Tier unit. First failing test:
  `tests/generator/unit/test_uml_write.py::test_a_failed_move_leaves_no_report_and_names_the_file`
  (an `--out` with a previous report; `os.replace` made to raise `OSError(ENOSPC)` on the second
  move through an injected `move` callable that `write` takes, default `os.replace`; asserts
  `OutputError` naming that target, no report in `--out`, and a second `write` producing the same
  bytes as a clean run). Then `test_staging_happens_inside_out` (the injected move sees source and
  target under `out`), `test_a_left_staging_folder_is_reported_not_deleted`, and
  `tests/generator/unit/test_uml_cli.py::test_an_unwritable_out_is_a_usage_error` (`--out` is a
  file; exit 2, the matrix line). Accept: "an interrupted write", "an output folder that cannot be
  written" pass; `test_uml_write.py` existing tests pass.
- [ ] 1.4 #259, PD-4, DEC-3 (after 1.3: same file). Tier unit. First failing test:
  `tests/generator/unit/test_uml_write.py::test_the_start_up_check_refuses_a_staged_workflow`
  (`write` given hand-built schemas, a workflow file and a roles file that each load alone, the
  schema holding two classes with one class IRI that name different workflows, a refusal of
  `Workflows._by_iri` that no per-file loader makes; asserts `StagedFileRefused` whose message
  starts `the written files would stop the service:`, names the one class `_by_iri` reports (the second of the two), the shared class IRI and
  both workflows, and
  holds no `.uml-write-`; and `--out` unchanged). Then
  `test_a_refusal_naming_a_file_names_it_under_out` (a class naming a workflow no staged file
  defines, the `_by_class` refusal listing the files given; asserts each listed file reads as
  `<out>/workflows/…` and no `.uml-write-` appears). Then
  `test_a_run_without_workflows_loads_no_schema` (no `SchemaView` load when no workflow is staged:
  an injected loader is not called). Accept: "a workflow the service would refuse" passes; the
  workflow rows in `uml_workflow_rows.py` and the feature scenario "A drawn workflow" (which now
  loads the real converted root and its `app_*` modules from staging through `load_schema`) pass
  unchanged.
- [ ] 1.5 #260, PD-5, DEC-2. Tier unit, then feature. First failing test: a `Row` in
  `tests/generator/unit/test_uml_rules.py`, "a lone role to its own class fixes member_class"
  (`UmlRule.TOOLKIT_SLOT`; asserts `slot_usage.member_class.equals_string == "Shelf"` and no
  `toolkit-slot-kept` line for the role). Then the row "a role to its own class beside one to Book
  stays nesting" (today's behaviour, pinned). Feature: the scenario "a collection of collections"
  in `uml_import.feature` / `test_uml_import.py`. Accept: both rows and the scenario pass.
- [ ] 1.6 PD-7. Tier unit. First failing test:
  `tests/generator/unit/test_uml_toolkit.py::test_convert_uses_the_toolkit_it_is_given` (builds a
  `Toolkit` from the metamodel view, then `load_toolkit.cache_clear()` and a pass-through spy on
  `load_schema` in `toolkit.py`'s namespace, tagged `# X2` per `testing.adoc` rule 3; calls
  `convert` on the stage-1 fixture model with that toolkit; asserts the spy saw no call. It fails
  today, deterministically: `Context.__init__` calls `load_toolkit()`, which after the cache clear
  loads the metamodel once). The test touches no cache of `metamodel_prefixes`, which PD-7
  deletes. Then: the exceptions moved (imports in tests follow), the enum
  constants, `LeftOutReason` in `rp_generation.yaml` + `make generate` (the lead runs
  `make check-generated` after committing it), the typed lookups replacing the `assert`s and the
  `type: ignore`. Accept: `grep -nE "^\s*assert |type: ignore" rdf_persistence_generation/uml/*.py`
  is empty; `grep -nE "= \"(rp_path|owned|graph|module_kind|workflow|meta|domain)\"" rdf_persistence_generation/uml/*.py`
  is empty; `grep -n "^class .*Error\|^class StagedFileRefused" rdf_persistence_generation/uml/*.py`
  is empty; the golden tests (`test_uml_golden.py`) pass byte for byte.
- [ ] 1.7 PD-8 (tests only; after 1.5: same files). Tier unit and feature. First failing test:
  `tests/generator/unit/test_uml_rules.py::test_every_cited_rule_has_a_row` (rewrites
  `test_every_uml_rule_has_a_row`; fails for R-22 and R-26..R-28 until their rows are added). Then
  `test_uml_naming.py::test_the_name_patterns_are_the_linters`; the feature's first scenario
  extended; one assert per Then step; messages on the asserts the review named; the scenarios "a
  tenant root" and "an abstract root" in `uml_import.feature`. Accept: those pass; no `@then` step function in
  `tests/generator/feature/test_uml_import.py` holds more than one `assert` statement (the lead
  checks with `ast-grep`). RISK-7: the lead may cut
  the feature additions to an issue.
- [ ] 1.8 #261 and the converter's docs (after 1.2-1.5). Docs, tier: `make check-docs`.
  `user-manual/serve.adoc`: what the relative paths of `install_service` are relative to (expected:
  the process's working directory, the `Path`s being opened as given; the builder checks
  `rdf_persistence/api/entrypoints/service.py` and writes what the code does); that `workflows=` lists each file
  (no folder or glob); a class naming a workflow left out stops the start (`InvalidWorkflow`); a
  workflow no class names is loaded; what a wrong, stale or missing roles or workflow file does at
  start; the smallest composition root. `howto/uml-to-linkml.adoc`: the new usage lines, the
  report-last rule, "save and close EA first" (RISK-1), one run per `--out`, add `.uml-write-*` to the
  consumer's `.gitignore` (OPEN-5), the whole-model check,
  that `no-note` covers neither role objects nor states and transitions (verified in
  `uml/roles.py`, `uml/workflows.py`), that `rp-generate --check` reads neither file.
  `reference/uml-conventions.adoc#member-class`: DEC-2. Every behaviour stated is backed by a
  named existing test; where none exists, the task adds one in `tests/unit/collaboration/` or
  `tests/unit/api/` first (failing test, e.g.
  `test_a_workflow_no_class_names_is_still_loaded`). Accept: `make check-docs` passes; a fresh
  cold reader follows the how-to to a started toy service and reports no open question (the lead
  records the read in `evidence/cold-read.md`).
- [ ] 1.9 Lead, release notes (RISK-3, RISK-6), in the PR before the gates: under `## [Unreleased]`
  in `CHANGELOG.md` (hand-written; release-please carries it into the release PR, as
  `develop/index.adoc#release` says), a `### Changed` entry each for DEC-2 (a lone self-role now
  writes `member_class`; what a model that meant nesting must draw) and DEC-5 (a roles file with a
  key given twice in an entry now stops the service at start), and a `### Fixed` entry for #258,
  #259, and the reader and writer errors (DEC-4's exit 2); the commits of 1.1 and 1.5 say the
  change in their body. Accept: the entries name #258 and #260 and are in the PR's diff.
- [ ] 1.10 Lead: full gates (`make check-all`, `make test-containers`), the review set `epic-delivery` sets
  for SMALL, with `develop/agents.adoc#challenge`'s adjustments (L1, L2, L3 never combined in a
  full review; L4+L5 one pass); the adversarial tester right after 1.3 (a write order); fixes,
  gates again, `make refresh-map`, `proposal.md` reconciled (P-0004), the PR with
  `Closes #229, #258, #259, #260, #261`, CI green, merge, the owner's acceptance; before the PR, a new
  issue holds DEC-1's deferred restructure (each #229 "Structure" bullet not done here, and S-3's
  indexes), so `Closes #229` loses nothing; the hand-over names RISK-4 for generator-module-cycles; `evidence/docs-owed.md`; archive.

## Roadmap

(1.1 ∥ 1.6) → (1.2 ∥ 1.3 ∥ 1.5) → 1.4 (after 1.3) → 1.7 (after 1.5) → 1.8 (after 1.2-1.5) → 1.9 → 1.10

1.6 goes first among the converter tasks because it moves the exceptions and constants that 1.2,
1.3 and 1.5 then use; 1.2 (`qea.py`), 1.3 (`write.py`, `cli.py`) and 1.5 (`slots.py`) touch
disjoint files.

- [ ] 1.1 · [ ] 1.6 · [ ] 1.2 · [ ] 1.3 · [ ] 1.5 · [ ] 1.4 · [ ] 1.7 · [ ] 1.8 · [ ] 1.9 · [ ] 1.10

## Verification

`make check-all` and `make test-containers` pass, every scenario of the two spec deltas maps to a
passing test (design.md, *Test coverage*), `openspec validate converter-hardening --strict` passes,
and the PR's CI is green before the merge.
