<!-- Parents: the follow-ups of the archived change 2026-11-25-agent-test-control (D-3, DEC-9's
     rejected alternative, the order-dependent test under its floor, its task 4.3), inputs/seed.md. -->

# EPIC: Free and reuse what the service kit builds in tests

**Golden-thread parents:** `2026-11-25-agent-test-control` (D-3, DEC-8, DEC-9, task 4.3);
capabilities `rp-service-api` (installing the service) and `rp-developer-checks` (the checks give
the same answer on every run); upstream linkml/linkml#4284.

## Appetite

**SMALL.** Three local fixes in code that exists, reused as is, plus one measurement: no new
concept, no new capability.

## Why

`agent-test-control` stopped test workers from growing by clearing library caches after every
test, but two causes remain in our own code: a kit's dependency types keep the kit alive through
`typing`'s cache (cleared today only through a private CPython list), and every service built in a
test parses its schema YAML again, which is most of the remaining time and memory of the API
tests. One test also fails depending on what ran before it on its worker. And the change's own
success measure (DEC-8) is still to be taken.

## Solution outline

1. A service no longer referenced is freed by ordinary garbage collection: no type cache keeps a
   kit alive.
2. A process that builds many services from one schema file parses that file once; services built
   from it behave exactly as before, and nothing else (the generator above all) shares the view.
3. The parser-depth test gives the same answer whatever ran before it.
4. DEC-8 of `agent-test-control` is measured on sessions running the merged code, and recorded.

## Key decisions

- **DEC-1**: The per-kit dependency parameters use FastAPI's default-argument form
  (`caller: VerifiedCaller = Depends(...)`), as `router.py` already does, instead of
  `Annotated[…, Depends(<per-kit callable>)]`, which `typing` caches by value — no type is built per
  kit, so nothing holds the kit. Rejected: a module-level dependency reading the kit from
  `request.app.state` (a larger refactor of every route).
- **DEC-2** (recommended to the developer, `inputs/qa.md` Q1): `install_service` takes its view from
  a process-wide cache keyed by the schema's resolved path and modification time, a new function
  beside `load_schema`; `load_schema` itself stays uncached, because `generation_view` modifies the
  views it loads. A guard test proves building and using a kit leaves its view unchanged.
  Rejected: caching inside `load_schema` (the generator would share and modify the view);
  `install_service` accepting a `SchemaView` (every caller would have to manage the cache).
- **DEC-3**: The parser-depth test pins the recursion limit to Python's default for its own
  duration (a fixture that restores it), because the behaviour it guards is "past the default
  depth, the step is refused with its own message". Rejected: quarantine (the test is right; only
  its environment varies).
- **DEC-4**: DEC-8's measurement is this EPIC's last task, taken from Langfuse after the paused
  sessions run on the merged code; a missed target goes to the developer, it does not block the
  merge of 1 to 3.

## Rabbit-holes

- Replacing `SchemaView`'s caches ourselves (that is linkml/linkml#4284's to fix upstream).
- Sharing one view across different schema files or across modifications of the file.
- Re-measuring the memory of `agent-test-control`'s release; only DEC-8 is measured.

## No-gos

- No change to `load_schema`, `generation_view` or the generator.
- No change to what a service does or answers.
- No removal of the testkit's `clear_caches` (other projects use it; it stays harmless).
- No work in other repositories.

---

## What Changes

- `rdf_persistence/api/entrypoints/auth.py`, `sse.py`: the dependency parameters in the default
  argument form (DEC-1).
- `rdf_persistence/schema/services/schema.py` (or beside it): the cached view for the service kit;
  `kit.py` uses it (DEC-2).
- `tests/unit/migrations/test_migration_files_adversarial.py`: the recursion limit pinned (DEC-3).
- The DEC-8 record in `evidence/measure.md` (DEC-4).

## Capabilities

### New Capabilities

### Modified Capabilities
- `rp-service-api`: a dropped service is freed; services from one schema file share one parse.

## Impact

`rdf_persistence/api/entrypoints/{auth,sse,kit}.py`, `rdf_persistence/schema/services/schema.py`,
their tests, one migrations test, docs only if a docstring names the behaviour. Consumers building
one service per process see no change; consumers building many (tests) get faster and lighter.
