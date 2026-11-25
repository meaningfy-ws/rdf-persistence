> Derives from: the EPIC `test-memory-followups` (proposal.md, DEC-1 to DEC-4)

## Context

`inputs/seed.md` holds the four follow-ups and the code facts. The testkit's memory plugin
(`agent-test-control` PD-9) already clears `SchemaView`, FastAPI and `typing` caches after each
test; this EPIC removes the two causes in our own code and the test's order dependence.

## Goals / Non-Goals

**Goals:** a dropped kit is freed without clearing `typing`'s caches (DEC-1); one parse per schema
file per process for service kits (DEC-2); an order-independent parser-depth test (DEC-3); DEC-8
measured (DEC-4).

**Non-Goals:** the No-gos of the proposal.

## Decisions

- **PD-1 The dependency parameters** (DEC-1). In `Gate.tenant` and `Gate.aggregate`
  (`auth.py:86-101`) the inner `permitted` functions take `caller: VerifiedCaller =
  Depends(self.caller)`; in `sse.py:77-81` the three parameters take `= Depends(gate.caller)`,
  `= Depends(gate.tenant(Action.READ))` and `= Depends(link_to_context)`. FastAPI resolves the
  default-argument form exactly as the `Annotated` form; the OpenAPI document does not change
  (guarded by `tests/unit/api/test_openapi.py` and `tests/unit/api/test_openapi_served.py`).
  The testkit's `clear_caches()` gains a keyword `typing: bool = True` (default unchanged, so
  callers see no difference) so a test can clear only the `SchemaView` and FastAPI caches; the
  docstring of `memory.py:_clear_typing` drops the claim that a kit's own dependency is the
  reason, and keeps clearing `typing` for other projects' code.
- **PD-2 The service view** (DEC-2). `service_view(path) -> SchemaView` in
  `rdf_persistence/schema/services/schema.py`:
  - **Key:** `(resolved path, st_size, sha256 of the root file's bytes)`. The content hash, not
    the modification time, decides: a rewrite within the clock's 1–10 ms step still gives a new
    key. Imported modules are not hashed (RISK-2).
  - **Store:** an `OrderedDict` used as an LRU of at most `SERVICE_VIEWS = 8` entries (a module
    constant), guarded by one `threading.Lock`. A hit moves the entry to the end; a miss calls
    `load_schema(path)` and evicts the oldest entry past the bound. At most one entry per resolved
    path: a new hash replaces the old entry.
  - **Release:** `clear_service_views()` empties the store. The testkit's `release_memory()` (the
    module-boundary step, not the per-test `clear_caches()`) calls it, so a test process holds at
    most the views of one module's schemas; its count joins the returned index as
    `service_views`.
  - **Errors:** the file is read before the lookup; on an `OSError` from that read,
    `service_view` calls `load_schema(path)` and lets it raise, so a missing or unreadable file
    raises exactly what `load_schema` raises today (type and message), tested against
    `load_schema`'s own error.
  - **Seam:** `service_view(path, *, load=load_schema)`; tests inject a counting loader.
  - **Scope of "once":** one parse per schema file until the next `release_memory()`, which in
    tests means once per module per worker; in a service, once per process.
  - **Use:** `ServiceKit.__init__` (`kit.py:165`) calls `service_view(schema)` instead of
    `load_schema(schema)`, so every kit built from a file shares its view, whether built by
    `install_service` or by constructing `ServiceKit` directly. `load_schema` and
    `generation_view` are untouched. `ServiceKit.view`'s docstring says the view is shared and
    must not be modified.
  - **Threads:** the lock covers lookup and load; loads of different files are serialised by it
    (accepted: a load is rare and one per schema per process). Concurrent reads of a shared view
    race only on `SchemaView`'s own lazy cache fills, which are idempotent, as they already are
    when one kit serves several threads today.
- **PD-3 The guard on modification.** A fingerprint of the view: `view.modifications` plus a
  sha256 over `yaml_dumper.dumps(module)` of every module in `view.schema_map`, in sorted key
  order (the root and every imported module `load_schema` placed there). A test takes it, builds
  a kit from the cached view, drives it through the toy service's scene covering create, read,
  list, replace, delete, a workflow transition, archive and restore of a tenant, the events route
  (one event decoded), and the start-up migrations, then asserts the fingerprint is unchanged.
  The same test also takes, before and after, a sha256 over `yaml_dumper.dumps(slot)` of every
  `class_induced_slots(c)` result for every class, without clearing the caches in between: the
  strings are computed at each point, so an edit made to a cached induced slot object changes the
  "after" digest even though the cache returns the same objects.
- **PD-4 The recursion pin** (DEC-3). A plain context manager `default_recursion_limit_pinned()`
  and an `autouse` function-scoped fixture `default_recursion_limit` that wraps it, both in
  `tests/unit/migrations/test_migration_files_adversarial.py`; the context manager sets
  `sys.setrecursionlimit(DEFAULT_RECURSION_LIMIT)` (`1000`, CPython's default, a module constant)
  before each test of the module and restores the previous limit in `finally`. Every test of the
  module depends on the parser's depth the same way: the 120-pattern step and the deeply nested
  YAML cases (`"{" * 5000`, `"[" * 100000`, `"[" * 50000`), which under a raised limit could
  exhaust the C stack instead of raising. Nothing else in the module changes.
- **PD-5 The measurement** (DEC-4). From Langfuse, observations with
  `startTime` after #394's merge (2026-11-25 21:00 UTC), sessions whose root span's metadata
  `cwd` contains `rdf-persistence`, excluding this EPIC's own sessions. The window is the first
  epic session (one with `Subagent:` spans) during which at least two other rdf-persistence
  sessions have spans. Definitions:
  - **Gate command:** a `Tool: Bash` observation whose input `command` contains
    `make test-changed`, `make check-all`, `make test-fast` or `make check-quality`.
  - **Builder task gate:** the latency of each gate command under a `Subagent:` span whose
    command contains `make test-changed`; target: median < 3 min.
  - **`check-all` net time:** the latency of each `make check-all` command minus the `N` of its
    `test queue: waited Ns` lines in its output; target: < 15 min.
  - **Builder waiting share:** per `Subagent:` span, the sum of gate-command latencies, queue
    wait included, divided by the span's latency; target: < 10 % for every builder.

  `evidence/measure.md` holds one table: target, measured value, sessions and observation ids,
  met or missed.

## Algorithm / approach

`service_view(path)`: read the root file's bytes (raises as `load_schema` would for a missing or
unreadable file); key = (resolved, size, sha256); under the lock: entry = store.get(resolved); if
the entry's key equals, move it to the end and return its view; else view = `load_schema(path)`,
store[resolved] = (key, view), evict the oldest past `SERVICE_VIEWS`, return view. Idempotent:
the same content returns the same object; retry-safe: a failed load stores nothing.

Worked examples (each a case of task 1.2's table):
- Two `ToyService()` built in one test: `kit_a.view is kit_b.view`.
- A test writes a schema to `tmp_path / "s.yaml"` and installs it: a new path, a new entry.
- The same path rewritten with other content, at once (no sleep, same mtime step): a new view.
- The same path rewritten with the same bytes: the same view.
- Nine different schema files: the store holds eight; the first is evicted and reloaded on use.
- `release_memory()` empties the store; the next kit loads again.
- A missing file: the same exception type and message as `load_schema(path)`.
- `generation_view(TOY_SCHEMA) is not service_view(TOY_SCHEMA)`.

### Anti-patterns
| Don't | Do instead | Why |
|---|---|---|
| Cache inside `load_schema` | `service_view` for kits only | `generation_view` modifies the views it loads |
| `Annotated[…, Depends(<per-kit callable>)]` | `= Depends(…)` default | `typing` caches the subscripted type and holds the kit |
| Quarantine the parser-depth test | pin the recursion limit for the module | the behaviour is right; only the environment varied |
| Key the store on the modification time | key on size and content hash | a rewrite within one clock step keeps its mtime |
| Modify `kit.view` in a test or a consumer | copy it (`deepcopy`) or load your own | the view is shared by every kit built from the file |

## Error matrix

| Failure mode | How it is detected | Expected handling |
|---|---|---|
| Code later modifies a shared view (a new feature) | PD-3's guard test fails | the feature copies the view or stops modifying it |
| An imported schema file changes while the importing file's bytes do not (same process) | not detected: the key hashes the root file only | accepted (RISK-2): tests write new files under new paths; a long-lived dev process reloads by restart |
| Two threads build kits from one file at once | the lock | one load, both get the same view |
| A suite installs services from many temporary schemas | the store's bound | at most eight views; `release_memory()` at each module boundary empties it |
| The schema file is missing or unreadable | the read before the lookup | the same exception and message as `load_schema`; nothing stored |
| Many threads read one shared view | n/a | lazy `lru_cache` fills race idempotently, as with one kit serving many threads today |
| The OpenAPI document changes with PD-1 | `test_openapi.py`, the served golden | stop; the default form must be identical |
| The pin leaks to later tests | the fixture restores the limit in `finally` | none |
| Langfuse lacks three concurrent sessions yet | PD-5's query finds fewer | measure later; the task stays open, the fixes merge |

## Risks / Trade-offs

- **RISK-1** (outside change: linkml/linkml#4284 fixed upstream; likely medium, impact low). A
  fixed `SchemaView` makes part of the testkit's clearing unnecessary. Accept: clearing stays
  harmless; revisit when the fix ships.
- **RISK-2** (who is hurt: a developer whose long-lived process edits an imported schema;
  likely low, impact low). The cached view would be stale. Accept: production loads once at start;
  tests use new paths.
- **RISK-3** (a smaller gain than possible). The testkit plugin clears `SchemaView` caches after
  each test, so a shared view recomputes its induced slots per test; before this change every test
  built a new view whose caches were cold anyway, so it cannot get slower, only gain less than an
  uncleared cache would. Check: task 1.2's timing (command and threshold there); more than 10 %
  slower than before goes to the developer.

## Open Questions

Q1 to Q5 of `inputs/qa.md`, shaped on the recommended defaults.
