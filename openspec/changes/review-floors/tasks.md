EPIC: review-floors (proposal.md). Decisions: proposal.md DEC-1 to DEC-6; design.md PD-1 to PD-22.

> Derives from: the EPIC `review-floors`; item ids (252-e, 235-m, …) are the rows of
> `inputs/triage.md`.

Every task: the test named **Red** is written first and seen failing; where it is a
characterisation test (it passes on today's code, DEC-3), it is seen failing under the named
planted mutation, which is then reverted and recorded in the hand-off. A task marked "Red: none
(DEC-3)" is a refactor, a move or docs: its proof is the named **Guard** tests staying green with
no edit to their assertions. Task gate `make test-changed check-quality` (`make test-fast
check-quality` after a change to a port or a `domain` module). Commit body
`Refs: review-floors <task> <PD>` plus `Refs: #<issue>`. Builders never commit, never edit
`tests/audit/scenario-map.csv` (the lead adds rows, then `make refresh-map`), and stop and report
instead of editing an assertion (P-0019). One branch per stage off `develop`
(`change/review-floors-s1`, `-s2`, `-s3`), one PR each, merged per DEC-5.

## 1. Stage 1: persistence, collaboration and the test helpers (#252, #235, #272 b/d/e/f, #275)

- [ ] 1.0 Lead: re-check the #252, #235, #272 and #275 rows of `inputs/triage.md` on the current `develop`
  (RISK-6); re-index GitNexus; a row no longer present is struck with a note.
- [ ] 1.1 252-j1, unit. Red: `tests/unit/persistence/test_session_referenced_removal.py::test_a_key_held_elsewhere_wins_over_a_removed_root_still_referenced`
  asserts the commit raises `KeyConflict` (not `InUse`) when the store reports both a held key and
  a referenced removed root (PD-4 of `delete-refuses-referenced`). Mutation: swap the two `if`
  blocks of `Transaction._refused_by_store`.
- [ ] 1.2 252-j2, unit. Red: `tests/unit/persistence/test_session_referenced_removal.py::test_no_type_is_read_when_no_link_names_a_removed_root`
  asserts `FakeStore.sent(...)` holds no heads read naming the removed author for a commit that
  removes one author and adds a book linking another (design.md, *Worked examples*). Mutation:
  `named = sorted(removed)` in `_refuse_links_to_removed`.
- [ ] 1.3 235-o2, unit. Red: `tests/unit/collaboration/test_collaboration_nesting.py::test_a_shelf_held_by_two_nesting_shelves_is_allowed`
  saves nesting shelves P1 and P2 that both hold shelf S, then a replace of S with its member
  class unchanged; asserts the three commits succeed and a deep read of each parent holds S.
  Mutation: make `_check_held_member_class` refuse when `_holders` returns more than one holder
  (it runs on the replace of S, whose holders are P1 and P2).
- [ ] 1.4 252-i (PD-4), after 1.1-1.2, unit. Red: none (DEC-3, a move). Guard: the three files'
  tests pass, and `make refresh-map` (run by the lead) exits 0 and removes no row: every test id
  is unchanged.
- [ ] 1.5 252-g1, g2, g4 (PD-3) and 252-h1, h2 (the docstring texts of PD-16), unit. Red: none (DEC-3). Guard:
  `tests/unit/collaboration/test_referenced_removals.py` (whole file),
  `tests/unit/api/test_openapi.py`, `tests/unit/api/test_contract.py`,
  `tests/unit/api/test_delete_in_use.py`. The `InUse` text is unchanged byte for byte.
- [ ] 1.6 235-m1, m2 (PD-5), unit. Red: none (DEC-3). Guard: `test_collaboration_nesting.py`
  (with 1.3's test), `test_collaboration_nesting_cycles.py`,
  `test_collaboration_nesting_adversarial.py` (its three `xfail(strict=True)` stay xfail),
  `test_collaboration_nested_reads.py`; the three `# noqa: PLR0913` are gone. Then the
  adversarial tester on the write guard (RISK-1).
- [ ] 1.7 252-f (PD-2). Red: `make check-architecture` with the two modules added to
  `collaboration-layers` in `.importlinter`; it must pass on today's imports (a refusal is
  reported, PD-2). Mutation: an import of `collaboration.services.collaboration` planted in
  `referrer_naming.py` makes it fail.
- [ ] 1.8 252-e (PD-1) and 252-h3 (PD-16), unit. Red: none (DEC-3). Edit the two YAML files and
  the slug text, then `make generate`, `make refresh-golden`, `make refresh-served-golden`.
  Guard: `tests/unit/testkit/test_shape_snapshot.py`,
  `tests/unit/package/test_public_surface.py`, `tests/unit/api/test_problems.py`,
  `make check-generated`; `git diff --stat` lists only the files PD-1 and PD-16 name.
- [ ] 1.9 #275 (PD-22), unit. Red: `tests/unit/api/test_tenancy_double.py::test_the_tenancy_double_takes_what_tenant_session_takes`
  fails while `TenancyDouble` does not exist. Mutation once it passes: a new keyword on
  `Tenancy.tenant_session` (reverted). Then the four doubles go. Guard:
  `test_iri_policy_minting.py`, `test_replace_internal_values.py` and the users of
  `iri_policy_helpers.py` pass unedited in what they assert.
- [ ] 1.10 272-b (PD-18), unit. Red: none (DEC-3, a move). Guard: `test_library_app.py` and
  `tests/unit/tooling/test_no_cross_test_imports.py` and `tests/unit/tooling/test_changed.py`
  pass; `make check-docs` (the `user-manual/index.adoc` path); the lead runs `make test-e2e` once
  in 1.12 (`test_library.py`'s public-imports check reads the moved file).
- [ ] 1.11 272-d, 272-e, 272-f (PD-17), last of stage 1 (after 1.4, 1.9 and 1.10), unit and generator unit. Red:
  `tests/unit/tooling/test_toy_vocabulary.py::test_book_json_is_new_on_each_call` asserts
  `book_json()["chapters"] is not book_json()["chapters"]` and that appending to one leaves the
  next call's list empty of it (fails today: `book_json` absent). Then PD-17's constants and
  imports. Guard: `make test-fast` green with no assertion edited; `uv run pytest --collect-only -q
  tests/integration tests/perf` collects with no import error (those lanes are local and the
  stage gate runs `make test-containers`); `rg -n "^(BIBO|TITLE|BOOK_CLASS|TIMEOUT)\b.*=" tests`
  lists `tests/toy.py`, `tests/events_follow.py` and exactly PD-17's four exceptions;
  `rg -n "poll_seconds=0\.01" tests` is empty.
- [ ] 1.12 Lead: `make check-all`, `make check-generated`, `make refresh-map`; one L2+L3 pass
  (P-0005) that also checks the diff against the **P** rows; the PR; merge per DEC-5.

## 2. Stage 2: the generator (#192, #189)

- [ ] 2.0 Lead: re-check the #192 and #189 rows on the current `develop` (RISK-6); re-index.
- [ ] 2.1 192-k, unit. Red: `tests/unit/package/test_theme_layout.py::test_each_theme_domain_generated_folder_holds_exactly_its_modules`
  asserts the set of `*.py` modules (bar `__init__.py`) of every `rdf_persistence/<theme>/domain/generated/`
  equals the stems of the schemas its target generates that declare at least one class
  (`generated_schemas` on the target's root schema, from `read_targets`, minus class-less
  modules such as `rp.yaml` and `rp_collaboration.yaml`, which write no `.py`), e.g.
  `{rp_access, rp_tenancy}` for `access`. Probed on 2026-11-22: the five theme folders match
  with that exclusion. Mutation: a stray empty module added to one folder.
- [ ] 2.2 192-j2 (PD-10), unit. Red: `tests/unit/tooling/test_theme_map.py::test_the_theme_map_is_read_from_the_targets`
  imports `tests/theme_map.py` (absent today) and asserts its map equals the one `read_targets`
  gives on the repository's `pyproject.toml`. Then the six places use it; their tests pass
  unedited in what they assert.
- [ ] 2.3 192-i (with PD-9) and 192-m (PD-11), unit and generator unit. Red: none (DEC-3, tests
  only). The assertion sites are the 192-i row of `inputs/triage.md`. Guard: the same test ids
  pass (minus the three dropped: PD-9's duplicate and PD-11's two tests); for one split assertion per file, flipping its expected value
  makes that assertion fail with its own message (shown in the hand-off, then reverted);
  `noqa: PT018` gone from `test_hard_check.py:1131` and `test_python_package_rule.py:57`.
- [ ] 2.4 189-r, 189-s (PD-12), 189-q, feature and generator unit. Red: none (DEC-3). Guard: the
  feature scenario "A technical layer refuses a domain module" passes with three `Then`/`And`
  steps; the six config tests pass unedited in what they assert; `openspec validate
  review-floors --strict` passes with the `rp-generation` delta.
- [ ] 2.5 192-e (PD-7), generator unit. Red: `tests/generator/unit/test_toolkit_roots_readers.py::test_only_the_accessor_reads_toolkit_roots`
  asserts no module of `rdf_persistence_generation/` but `config.py` names `TOOLKIT_ROOTS` (it
  fails today: ten do), plus its own case on a planted alias import. Then the accessor, the
  ten readers, one `# X1` patch in `tests/generator/unit/conftest.py`, `ROOTS_USERS` gone.
  Guard: "Generator tests" lane green.
- [ ] 2.6 192-f, g, h (PD-8), unit and generator unit. Red: none (DEC-3). Guard:
  `test_ext_pydantic_split.py` (the whole file, with the two `METAMODEL_DIR` tests at `:147` and
  `:625`), `tests/unit/schema/test_vocabulary.py`,
  `tests/unit/access/test_access_loading.py`, `test_schema_imports_no_upper_module.py`,
  `make check-generated` (no diff), `make check-freshness`.
- [ ] 2.7 192-b (PD-6) and 189-p, unit and generator unit. Red: none (DEC-3). Guard:
  `tests/unit/schema/test_schema_structure.py`, `tests/unit/api/test_service_written.py`, the
  application rows of `test_hard_check.py`, `tests/generator/unit/test_boundary_check.py`.
- [ ] 2.8 Lead: as 1.12 for stage 2.

## 3. Stage 3: events, testkit and docs (#215, #214, #125, #189, #272 a/c, #273)

- [ ] 3.0 Lead: re-check the #215, #214, #125, #189 t, u, 272-a, 272-c and #273 rows (RISK-6); re-index.
- [ ] 3.1 215-W2b, unit. Red: `tests/unit/testkit/test_streams.py::test_a_lifespan_start_up_longer_than_the_timeout_does_not_raise`
  asserts the helper returns the head when the app's start-up takes 0.2 s and `timeout=0.05`
  (the `Lifespan` helper of that file with a start-up delay). Mutation: enter the lifespan inside
  the `asyncio.timeout` block of `testkit/streams.py`. The real 0.2 s delay is PD-13's recorded
  exception to `testing.adoc` rule 11, cited in the test's docstring. The `rp-testkit` delta's
  scenario names it; the lead adds its row.
- [ ] 3.2 215-W5, unit. Red: `tests/unit/testkit/test_testkit_lazy_import.py::test_testkit_root_does_not_load_the_stream_or_service_module`,
  parametrized on `rdf_persistence.testkit.streams` and `rdf_persistence.api.entrypoints.service`,
  asserts a fresh `-I` interpreter that imports `rdf_persistence.testkit` has neither in
  `sys.modules`. Mutation: an eager `from . import streams` in `testkit/__init__.py`.
- [ ] 3.3 215-S5, unit. Red: none (DEC-3). `re.escape` in `test_open_event_stream.py:102` and
  `test_streams.py:154, 165`; the three tests pass.
- [ ] 3.4 125-i1 (PD-13), unit. Red: `tests/unit/api/test_event_wiring.py::test_a_commit_wakes_the_relay_before_its_interval`
  asserts, with `relay_interval_seconds=60`, that a second commit's activity reaches the hub
  within 2 s once the first one has (design.md, error matrix: the relay is then in its wait).
  Mutation: delete `self.relay.wake()` in `kit.py:_publish`.
- [ ] 3.5 125-i2 (PD-14), integration (`make test-containers`, local only). Red:
  `tests/integration/adapters/test_redis_events.py::test_a_receiver_that_raised_gets_the_message_again_without_a_restart`
  asserts a receiver that raised once receives the same message again within 5 s, with no
  close or restart of the bus. Mutation: `claim_idle_seconds=600`. The lead records the run in
  `evidence/`.
- [ ] 3.6 214-g and 215-S4a, docs. Red: none (DEC-3). `user-manual/test.adoc#event-stream` states
  the five outcomes and the several-streams note (design.md, *Worked examples*); each sentence
  cites its docstring line or test in the hand-off. Guard: `make check-docs`.
- [ ] 3.7 189-t and 189-u (PD-15), docs. Red: none (DEC-3). `tutorials/getting-started.adoc`:
  `domain/__init__.py`, `cd library`, the terms `ServiceKit`, `UnitOfWork`, `generated_models`
  defined where first used (one sentence each, naming the module that exports it), and the
  printed read-back of the book at line 145, copied from a run of
  `docs/modules/ROOT/examples/getting-started/` (no invented output); `user-manual/model.adoc:179-183` and
  `user-manual/generate.adoc:264-267` state the route-shapes rule and the OpenAPI source. Guard:
  `make check-docs`; `tests/generator/integration/test_getting_started_example.py`.
- [ ] 3.8 272-c (PD-19), unit. Red: `tests/unit/api/test_shacl.py::test_load_warm_shapes_warms_once_per_content`
  writes the same Turtle to two paths and other Turtle to a third (each Turtle carries a triple
  with a fresh `uuid4` IRI, so no other test in the process has warmed its digest:
  `_WARMED_SHAPES` lives as long as the process), loads all three, and asserts
  the warm-up ran twice (a pass-through spy on `shacl.warm_up`, marked `# X2`: no public result
  shows a warm-up) and that each returned graph is a graph of its own (adding to one leaves
  another unchanged). Mutation: digest `str(path).encode()` instead of the bytes (warms three
  times). Guard: the rest of `test_shacl.py`, `tests/unit/api/test_documents.py`,
  `tests/unit/package/sparql_threads.py`'s users.
- [ ] 3.9 #273 (PD-21), docs. Red: none (DEC-3). The sentence in `develop/testing.adoc` after the
  `# X1`-`# X5` list. Guard: `make check-docs`.
- [ ] 3.10 272-a (PD-20), last of stage 3, unit. Red:
  `tests/unit/tooling/test_patch_markers.py::test_every_patch_of_toolkit_code_names_its_kind`
  fails today, listing the unmarked calls (e.g. `tests/unit/collaboration/test_aggregate_validators.py:613`);
  plus `test_the_marker_check_sees_an_aliased_import`, on a planted source string with
  `import rdf_persistence.x as m` and an unmarked `monkeypatch.setattr(m, ...)`. Then each listed
  call gets its kind's marker (the hand-off lists call, kind and why). Guard: the new test green;
  no test other than those calls' lines edited.
- [ ] 3.11 Lead: as 1.12 for stage 3, then the full review once (L1, L2, L3 apart; L4+L5 as one;
  P-0005) over the three stages' diff; accepted findings recorded in `design.md` before the fix.

## 4. Close

- [ ] 4.1 Lead, after stage 3 merges: one comment per issue listing each item with its class and
  where it went (DEC-4): close #215 (OPEN-7), #272, #273 and #275 (each item delivered, the
  commit or PR named); narrow #252, #235, #214, #192, #189 to their **B**/**Q**/**R** items;
  split 189-v into a new issue (OPEN-5); #125 stays as triaged, with 125-i3 added (OPEN-8).
- [ ] 4.2 Lead: reconcile `proposal.md` with what was delivered (P-0004); archiving follows
  `spec-stewardship`.

## Roadmap

- [ ] 1.0 · [ ] 1.1 · [ ] 1.2 · [ ] 1.3 · [ ] 1.4 · [ ] 1.5 · [ ] 1.6 · [ ] 1.7 · [ ] 1.8 · [ ] 1.9 · [ ] 1.10 · [ ] 1.11 · [ ] 1.12
- [ ] 2.0 · [ ] 2.1 · [ ] 2.2 · [ ] 2.3 · [ ] 2.4 · [ ] 2.5 · [ ] 2.6 · [ ] 2.7 · [ ] 2.8
- [ ] 3.0 · [ ] 3.1 · [ ] 3.2 · [ ] 3.3 · [ ] 3.4 · [ ] 3.5 · [ ] 3.6 · [ ] 3.7 · [ ] 3.8 · [ ] 3.9 · [ ] 3.10 · [ ] 3.11
- [ ] 4.1 · [ ] 4.2

Within a stage: 1.1 then 1.2 (same file), beside 1.3; then 1.4-1.8 in order, 1.9 and 1.10
beside them; 1.11 last (it edits the files of 1.1-1.4 and 1.9, RISK-7). 2.1, 2.2, 2.3 in order
(shared test files), beside 2.4; then 2.5-2.7. 3.1 then 3.3 (same file), beside 3.2, 3.4, 3.5;
then 3.6-3.9; 3.10 last (it marks the patches every other task left).

## Verification

Each stage: the task gates, then the lead's `make check-all`, `make check-generated` and (stage 1
and 3) `make test-containers`; every existing test green with no edited assertion (DEC-3);
`openspec validate review-floors --strict`; the PLAN gated ≥ 9/10 (`evidence/clarity-gate.md`).
