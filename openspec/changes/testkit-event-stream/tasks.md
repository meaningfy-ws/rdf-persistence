EPIC: testkit-event-stream (proposal.md, DEC-1, DEC-2; issue #204). Decisions: design.md PD-1 to PD-8.

> Derives from: EPIC `testkit-event-stream`. One stage, one PR into `develop` (SMALL).

Every task: the failing test named in it is written and seen failing first; task gate
`make test-changed check-quality`; commit body `Refs: testkit-event-stream <task> <PD>`. Builders
never commit; the lead does.

## 1. The helper (testkit)

- [x] 1.1 Records (PD-1). Tier: unit. Failing test first: in `tests/unit/testkit/test_streams.py`,
  `test_the_result_records_are_public_and_generated` (imports `OpenedStream`, `StreamEvent` from
  `rdf_persistence.testkit`; `StreamEvent(id="x").id == "x"`; `OpenedStream.__module__` is
  `rdf_persistence.testkit.generated.rp_testkit`). Then add `Any`, `StreamEvent`, `OpenedStream` and
  their slots to `rdf_persistence/model/technical/testkit/rp_testkit.yaml`, `make generate`, export
  both. Accept: that test, `test_generated_classes_match_the_induced_slots[testkit]` and
  `tests/unit/testkit/test_model_guard.py` pass.
- [x] 1.2 Lifespan flag (PD-3). Tier: unit. Failing test first: in
  `tests/unit/api/test_event_wiring.py`, `test_the_lifespan_flag_is_set_while_the_lifespan_runs`
  (true inside `service.app.router.lifespan_context`, false after it). Then `LIFESPAN_STARTED` and
  its set/clear in `_run_at_startup`. Accept: that test; `make check-architecture`.
- [ ] 1.3 `open_event_stream` (PD-2, PD-4, PD-5, PD-8; algorithm steps 1-7) in
  `rdf_persistence/testkit/streams.py`, a lazy name of the testkit. Tier: unit. Failing tests first,
  in `tests/unit/testkit/test_streams.py`, one per error-matrix row: raw ASGI apps (split chunks and
  a split UTF-8 character, `\r\n`, multi-line `data`, `: keep-alive` and `: ping` skipped, a reset
  with `data == ""` and `id is None`, early end, no head, raising app, app ignoring the disconnect
  is done on return, a call cancelled while waiting leaves its app task done, bad arguments) and a
  plain FastAPI app (lifespan entered and left once when the flag is absent, not entered when set);
  then `tests/unit/api/test_open_event_stream.py` with the four scenarios of
  `specs/rp-testkit/spec.md` (refusal: `events=1, timeout=0.5` returns 404 instead of raising;
  timeout: the message contains the URL) and `assert_public_imports(__file__)`. Rows in
  `tests/audit/scenario-map.csv` for every new test (Edit). Accept: both files pass; `make
  refresh-map` lists no unmapped id.

## 2. The toolkit's tests switch (DEC-1)

- [ ] 2.1 `tests/unit/api/test_events_route.py`. Tier: unit. Failing test first: rewrite
  `test_a_reader_hears_the_replace_of_a_book_with_its_id_class_and_json` (TC-32) on `opening` and
  the `streams` fixture (PD-8) before they exist, and see it fail; then add `streams`, `opening`,
  `drained`, rewrite every other `follow` test per design.md "Tests rewritten" (PD-5, PD-6), and
  delete `Follow`, `follow`, `Block`, `parsed`. Accept: the same test names, all pass;
  `grep -rn "class Follow\|def parsed\|class Block" tests/` is empty; no `pytest.raises(TimeoutError)`
  left in the file.
- [ ] 2.2 `tests/unit/api/test_service_kit.py`. Tier: unit. Failing test first: rewrite
  `test_a_keep_alive_of_the_toolkit_settings_reaches_the_events_route` (TC-36) per its design row,
  failing until 1.3 is in; drop the `follow, parsed` import. Accept: the test passes.
- [ ] 2.3 `tests/feature/test_events.py`. Tier: feature. Failing test first: the step
  `_barred_reader` rewritten on `following.pending` (PD-7), so the scenario "a hidden aggregate"
  fails until `Following` holds `pending`; then `Following` per PD-7, the "resuming a stream" steps,
  and the imports of `Block`, `Follow`, `follow` removed. Accept: `make test-feature` passes both
  SSE scenarios.

## 3. Docs and gates

- [x] 3.1 `docs/modules/ROOT/pages/user-manual/test.adoc`: a section `[#event-stream]` "Follow a
  tenant's event stream" (the issue's example, PD-5's return rules, PD-3's lifespan rule, "start
  it as a task, then commit"); `questions.adoc`'s testkit answer links it. Accept: `make check-docs`.
- [ ] 3.2 Lead: `make check-all`, the SMALL review set, `openspec validate --all --strict`.

## Roadmap

- [x] 1.1 · [x] 1.2 · [ ] 1.3 · [ ] 2.1 · [ ] 2.2 · [ ] 2.3 · [x] 3.1 · [ ] 3.2

## Verification

`make check-all`; the four `rp-testkit` scenarios in `test_open_event_stream.py`; no `Follow` left
in `tests/`; the clarity gate in `evidence/clarity-gate.md`.
