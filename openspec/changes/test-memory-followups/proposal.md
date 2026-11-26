<!-- Parents: the follow-ups of the archived change 2026-11-25-agent-test-control (D-3, DEC-9's
     rejected alternative, the order-dependent test under its floor, its task 4.3), inputs/seed.md. -->

# EPIC: Free and reuse what the service kit builds in tests

**Golden-thread parents:** `2026-11-25-agent-test-control` (D-3, DEC-8, DEC-9, task 4.3);
capabilities `rp-service-api` (installing the service) and `rp-developer-checks` (the checks give
the same answer on every run), `rp-testkit` (a project selects its tests with the testkit);
issue #416 (its DEC-8 design gap); upstream linkml/linkml#4284.

## Appetite

**MEDIUM** (re-shaped 2026-11-26 from SMALL, `inputs/qa.md` round 3: the developer folded in
#416's fallback gap, DEC-7). Three local fixes in code that exists, one measurement, a
timeboxed spike, and one behaviour added to the testkit's public planner with its tests and docs.
The spike (DEC-5) stays timeboxed to half a day: if it passes, its change is a Makefile flag and
a docs paragraph.

## Why

`agent-test-control` stopped test workers from growing by clearing library caches after every
test, but two causes remain in our own code: a kit's dependency types keep the kit alive through
`typing`'s cache (cleared today only through a private CPython list), and every service built in a
test parses its schema YAML again, which is most of the remaining time and memory of the API
tests. One test also fails depending on what ran before it on its worker. And the change's own
success measure (DEC-8) is still to be taken. Finally, a stage that has builders still runs the unit and
feature tests twice: once for the seed at the start, and again in `make check-all` before the PR
(`inputs/seed.md` items 5 and 6). And on a branch that changed a shared file (`Makefile`,
`pyproject.toml`, `uv.lock`), every later task gate falls back to the queued `make test-fast`, even
after a seed that already ran with that file: MWB2's builders waited 57 % and 76 % of their gate
time on it, against DEC-8's 10 % (#416, `inputs/seed.md` item 7).

## Solution outline

1. A service no longer referenced is freed by ordinary garbage collection: no type cache keeps a
   kit alive.
2. A process that builds many services from one schema file parses that file once (in tests: once
   until the testkit's next `release_memory`, at each module boundary); services built
   from it behave exactly as before, and nothing else (the generator above all) shares the view.
3. The parser-depth test gives the same answer whatever ran before it.
4. DEC-8 of `agent-test-control` is measured on sessions running the merged code, and recorded.
5. A spike settles whether the pre-PR full run can also be the next stage's seed, and the answer
   lands in the Makefile or in the docs.
6. A file that forces the fallback forces it only when it changed since the selection data was
   recorded: a seed taken after the branch changed its `Makefile` already ran with that
   `Makefile`, so the next task gate selects its tests as usual.

## Key decisions

- **DEC-1**: The per-kit dependency parameters use FastAPI's default-argument form
  (`caller: VerifiedCaller = Depends(...)`), as `router.py` already does, instead of
  `Annotated[…, Depends(<per-kit callable>)]`, which `typing` caches by value — no type is built per
  kit, so nothing holds the kit. Rejected: a module-level dependency reading the kit from
  `request.app.state` (a larger refactor of every route).
- **DEC-2** (recommended to the developer, `inputs/qa.md` Q1): a service kit (`install_service`, or
  `ServiceKit` constructed directly) takes its view from a bounded process-wide cache keyed by the
  schema's resolved path and content, a new function beside `load_schema`, emptied by the
  testkit's `release_memory`; `load_schema` itself stays uncached, because `generation_view` modifies the
  views it loads. A guard test proves building and using a kit leaves its view unchanged.
  Rejected: caching inside `load_schema` (the generator would share and modify the view);
  `install_service` accepting a `SchemaView` (every caller would have to manage the cache).
- **DEC-3**: Every test of the parser-depth test's module runs at Python's default recursion limit
  (an autouse fixture that restores the previous limit), because the behaviour they guard is "past
  the default depth, the input is refused with its own message", and the deeply nested cases could
  exhaust the C stack under a raised limit. Rejected: quarantine (the test is right; only
  its environment varies).
- **DEC-4**: DEC-8's measurement is this EPIC's last task, taken from Langfuse after the paused
  sessions run on the merged code; a missed target goes to the developer, it does not block the
  merge of 1 to 3.
- **DEC-5** (added 2026-11-25, `inputs/qa.md` Q6): a timeboxed spike decides whether
  `make check-all`'s unit and feature lanes can also record the test selection data, so the
  pre-PR run doubles as the next stage's seed. It passes only if coverage and selection both come
  out as from separate runs (PD-6); then the Makefile and docs change in this EPIC. It fails on
  any doubt, and the finding is recorded in `develop/testing.adoc#test-control`. Rejected: letting
  `check-all` skip what a seed on the same commit passed (a "same commit" check that goes stale).
- **DEC-6** (added 2026-11-25, Q7): **no test run whose result nobody reads.** A run is started
  only when someone reads what it gives: a seed only where builders will run `make test-changed`
  (#398, P-0022); one `make check-all` per stage, never also its lanes by hand; on a commit whose
  seed passed, a separate unit or feature lane only for its coverage floor. This EPIC's own
  delivery follows it (PD-7).
- **DEC-7** (added 2026-11-26, `inputs/qa.md` round 3, #416): **a fallback path counts only if
  it changed since the seed.** The seed records the commit it ran on beside the selection data;
  when that data is sound, the planner keeps a path's fallback reasons only if the path differs
  between that commit and the worktree, and says in a hint which ones it set aside; a shared
  file reverted since the seed falls back, which today goes unnoticed. Without a
  recorded commit, or if git cannot read it, the planner works as today. It lives in the
  testkit's planner, so every project inherits it; it is additive to the public API (semver
  minor). Rejected: diffing every path against the seed's commit instead of the base (a folder
  rule's selection would shrink to what changed since the seed, while the seed's own failures
  are not recorded as such); a list of "configuration that never matters" (it would be wrong for
  the first project whose `Makefile` sets a pytest flag).

## Rabbit-holes

- Replacing `SchemaView`'s caches ourselves (that is linkml/linkml#4284's to fix upstream).
- Sharing one view across different schema files or across modifications of the file.
- Re-measuring the memory of `agent-test-control`'s release; only DEC-8 is measured.
- Teaching testmon to track non-Python files, or reclassifying which files force the fallback
  (each project's classifier decides that; DEC-7 only changes when its verdict applies).

## No-gos

- No change to `load_schema`, `generation_view` or the generator.
- No change to what a service does or answers.
- No removal of the testkit's `clear_caches` (other projects use it; it stays harmless).
- No work in other repositories (MWB2 gets DEC-7 when it adopts the testkit modules).
- No change to the planner's existing signature or exit codes: DEC-7 adds a keyword only.

---

## What Changes

- `rdf_persistence/api/entrypoints/auth.py`, `sse.py`: the dependency parameters in the default
  argument form (DEC-1).
- `rdf_persistence/schema/services/schema.py` (or beside it): the cached view for the service kit;
  `kit.py` uses it (DEC-2).
- `rdf_persistence/testkit/memory.py`: `clear_caches(typing=...)`, `release_memory` also empties the
  service views and reports `service_views` (DEC-1, DEC-2).
- `tests/unit/migrations/test_migration_files_adversarial.py`: the recursion limit pinned (DEC-3).
- The DEC-8 record in `evidence/measure.md` (DEC-4).
- The spike's record in `evidence/seed-spike.md`; if it passes, `Makefile` (`test-unit`,
  `test-feature`) and `develop/testing.adoc#test-control`, `develop/agents.adoc`, `AGENTS.md`; if
  it fails, one paragraph in `develop/testing.adoc#test-control` (DEC-5).
- `rdf_persistence/testkit/selection_data.py`: the seed records its commit in `.testmondata.commit`
  at the swap; `rdf_persistence/testkit/changed_tests.py`: `plan(..., since_seed=...)` and `main`
  reading it; the user manual's *Test control for your project*, `develop/testing.adoc#test-control`,
  CHANGELOG (DEC-7).

## Capabilities

### New Capabilities

### Modified Capabilities
- `rp-service-api`: a dropped service is freed; services from one schema file share one parse.
- `rp-developer-checks`, only if the spike passes (DEC-5): the full run also refreshes the test
  selection data; its delta is drafted, and task 2.2 deletes it on a fail.
- `rp-testkit`: a fallback path counts only if it changed since the seed (DEC-7).

## Impact

`rdf_persistence/api/entrypoints/{auth,sse,kit}.py`, `rdf_persistence/schema/services/schema.py`,
`rdf_persistence/testkit/memory.py`, their tests, one migrations test, docs only if a docstring names the behaviour. Consumers building
one service per process see no change; consumers building many (tests) get faster and lighter.
The spike touches only the developer tooling (`Makefile`, `rdf_persistence/testkit/selection_data.py`
if the swap needs it, the develop docs). DEC-7 changes the testkit's planner and seed: a project
using them gets fewer fallbacks after its next seed; one that never seeds sees no change.
