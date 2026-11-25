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
  (guarded by `tests/unit/api/test_openapi.py` and the served-golden test).
- **PD-2 The service view** (DEC-2). `service_view(path) -> SchemaView` in
  `rdf_persistence/schema/services/schema.py`: key `(Path(path).resolve(), stat().st_mtime_ns)`;
  a module-level `dict` guarded by a `threading.Lock`; a miss calls `load_schema(path)` and
  stores it; at most one entry per resolved path (a new modification time replaces the entry).
  `ServiceKit.__init__` (`kit.py:165`) calls `service_view(schema)` instead of `load_schema(schema)`.
  `load_schema` and `generation_view` are untouched. The cached view is shared by every kit built
  from that file in the process; nothing in the kit modifies it (guarded by PD-3's test).
- **PD-3 The guard on modification.** `SchemaView` counts its modifications (`view.modifications`,
  incremented by `set_modified()`); a test builds a kit from a cached view, drives it through a
  scene (create, read, list, delete on the toy schema), and asserts the count and the dumped schema
  (`yaml_dumper.dumps(view.schema)`) are unchanged.
- **PD-4 The recursion pin** (DEC-3). A fixture in the test module sets
  `sys.setrecursionlimit(1000)` (CPython's default) for the parser-depth test and restores the
  previous limit after it; the test uses it. Nothing else in the module changes.
- **PD-5 The measurement** (DEC-4). From Langfuse (the observations API, filtered by the
  `cwd` metadata of rdf-persistence sessions and dated after #394's merge), over the first epic
  session with at least three sessions running: the builders' `make test-changed check-quality`
  wall times (median), `make check-all` wall time minus its `test queue: waited` seconds, each
  builder's share of wall time in gate commands. Recorded in `evidence/measure.md` against the
  targets of `agent-test-control` DEC-8.

## Algorithm / approach

`service_view`: lock; key = (resolved, mtime); entry = cache.get(resolved); if entry and its
mtime equals, return its view; else view = load_schema(path), cache[resolved] = (mtime, view),
return view. Idempotent: the same key returns the same object; retry-safe (a failed load stores
nothing and raises as `load_schema` does).

Worked examples:
- Two `ToyService()` built in one test: `kit_a.view is kit_b.view`.
- A test writes a schema to `tmp_path / "s.yaml"` and installs it: a new path, a new entry.
- The same path rewritten (new mtime): a new view; the old one is dropped from the cache.
- `generation_view(TOY_SCHEMA) is not service_view(TOY_SCHEMA)`.

### Anti-patterns
| Don't | Do instead | Why |
|---|---|---|
| Cache inside `load_schema` | `service_view` for kits only | `generation_view` modifies the views it loads |
| `Annotated[…, Depends(<per-kit callable>)]` | `= Depends(…)` default | `typing` caches the subscripted type and holds the kit |
| Quarantine the parser-depth test | pin the recursion limit in the test | the behaviour is right; only the environment varied |

## Error matrix

| Failure mode | How it is detected | Expected handling |
|---|---|---|
| Code later modifies a shared view (a new feature) | PD-3's guard test fails | the feature copies the view or stops modifying it |
| An imported schema file changes while its importer's mtime does not (same process) | not detected: the key is the importer's path and mtime | accepted (RISK-2): tests write new files under new paths; a long-lived dev process reloads by restart |
| Two threads build kits from one file at once | the lock | one load, both get the same view |
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
- **RISK-3** (trade-off). With the testkit plugin clearing `SchemaView` caches after each test, a
  shared view recomputes its induced slots per test though it is parsed once. Mitigate: task 1.2
  times the adversarial API module before and after; a slowdown goes to the developer.

## Open Questions

Q1 to Q5 of `inputs/qa.md`, shaped on the recommended defaults.
