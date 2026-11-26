# Seed: the follow-ups of agent-test-control (secondary, never groomed)

Source: the developer, 2026-11-25 ("do a and b"; (a) = shape a new EPIC from the follow-ups),
after `agent-test-control` merged (#394) and was archived (#395).

From the archived change (`openspec/changes/archive/2026-11-25-agent-test-control/`):

1. **D-3, ours.** Each `ServiceKit` builds `Annotated[VerifiedCaller, Depends(<bound method>)]` in
   per-kit closures (`rdf_persistence/api/entrypoints/auth.py:87,97`,
   `rdf_persistence/api/entrypoints/sse.py:79-81`); `typing` caches such subscripted types by value,
   so its cache holds the last kit alive until `typing`'s caches are cleared (the testkit's
   `clear_caches` does that today, through a private CPython list).
2. **DEC-9 follow-up, ours.** Every `install_service` call parses the schema YAML and its imports
   again (`rdf_persistence/api/entrypoints/kit.py:165`, `load_schema`): about 70 MB of the growth
   from test 5 to 12 of one module was the YAML parsed again per test (`inputs/memory.md` of the
   archived change), and every API test pays the parse time.
3. **Under the floor.** `tests/unit/migrations/test_migration_files_adversarial.py::
   test_a_step_too_long_for_the_parser_is_refused_with_its_own_message` depends on test order: it
   expects rdflib to exhaust the recursion limit on a 120-pattern step, which fails when a
   Hypothesis run on the same worker has raised the limit meanwhile (seen in the seed run,
   `evidence/selection.md` of the archived change).
4. **Task 4.3 carried forward.** DEC-8 of agent-test-control: measure in Langfuse, over the first
   epic session with at least three sessions on the merged code, the builders' task-gate median
   (< 3 min), `make check-all` minus queue wait (< 15 min), and the builders' share of time waiting
   on gates (< 10 %).

Filed upstream the same day: linkml/linkml#4284 (the `SchemaView` method caches), and
meaningfy-ws/skillery#361 (the Langfuse trace tag).

Code facts read while shaping:
- `router.py:355` already uses the default-argument form `caller: VerifiedCaller = as_caller` with
  `as_caller = Depends(gate.caller)`; no lint rule forbids it (`ruff.toml` selects no `FAST` rule).
- `generation_view` (`schema_structure.py:481`) loads a schema and then modifies the view
  (`apply_defaults`, `view.set_modified()`), and the generator calls `load_schema` in
  `pipeline.py`, `config.py`, `jsonld_context.py`: a cache inside `load_schema` would share a view
  the generator modifies.

## Added 2026-11-25, after the PLAN was gated

Source: the developer, in a close-out session of `review-floors` (stages 2 and 3), after the lead
had run `make test-seed` on both worktrees and started `make test-unit` on s3: "is there anything
I could adjust in the whole repo instructions about this? or this inefficiency is a local
fluke?", then "add the spike to the parked epic change in tests followup ... and also record there
the wisdom on no overrunning tests if not needed from this session".

5. **The spike.** Let the full run also refresh the seed: record the selection data during
   `make check-all`'s unit and feature lanes, so the pre-PR run doubles as the next stage's seed.
   Open: testmon and pytest-cov each attach a coverage.py tracer, and it is not known whether they
   combine in one run.
6. **The wisdom: no test run whose result nobody reads.** What the session showed:
   - Not a fluke: the instructions seeded at every stage start, unconditionally, and `make
     check-all` (`check-quality test`, `test` = `test-unit test-feature test-generator`) ran the
     same unit and feature tests again before the PR: about 7 extra minutes a stage on this machine,
     more when the queue is held.
   - The seed exists only for builders' `make test-changed`; a session without builders (rebase,
     gates, a lead-only fix pass) got nothing from it. The s2 seed bought nothing: its session ran
     only `make check-quality` and `make test-generator`.
   - A seed that passed on a commit is that commit's pass/fail for the unit and feature tests
     (10,251 passed, 5 xfailed on s3). A later `make test-unit` / `make test-feature` on the same
     commit adds only the coverage floors (80 % unit, 50 % feature).
   - Already fixed outside this EPIC, ad hoc: #398 (the docs: the lead seeds only when builders
     follow) and #399 (rule P-0022).
7. **#416's design gap (added 2026-11-26, round 3).** `make test-changed` diffs against the
   merge base with `develop`; on a branch that changed `Makefile`, `pyproject.toml`, `uv.lock` (any
   of `tests/changed.py`'s `SHARED_FILES`, or another fallback path), every later task gate falls
   back to the queued `make test-fast`, whatever the task touched. MWB2's builders waited 57 % and
   76 % of their gate time on it (DEC-8 of `agent-test-control` targets 10 %). #416 suggests
   judging shared configuration against the last seed's commit, not the base: a seed taken after
   the configuration changed already covers it. The planner now lives in
   `rdf_persistence.testkit.changed_tests` (`test-control-testkit`, archived 2026-11-26), so the
   fix reaches MWB2 with its adoption.
