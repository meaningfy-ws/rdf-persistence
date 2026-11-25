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
