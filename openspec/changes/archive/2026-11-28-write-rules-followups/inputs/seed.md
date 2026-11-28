Follow-ups left under the review floor by `consumer-write-rules` (#434, #447). None blocks a consumer; each is a candidate for a TINY or SMALL change (P-0020). Decisions: `openspec/changes/archive/*-consumer-write-rules/design.md` D-10, D-12, D-20, D-21.

**Rule refusal and `find`**
- [ ] `refusal_problems` given as a generator is spent by the check in `ServiceKit`, so the kit registers nothing (T-F1). Fix: `tuple()` first.
- [ ] A refusal's `status` of `409.0` passes the 409/422 check (T-F2, reachable only through `model_construct`). Fix: compare the type too.
- [ ] `service.py`'s docstring names only create and replace; any write that runs the rules answers a refusal the same way (R-S4).
- [ ] `Session.find` documents `BadQuery` for a value not of its slot's type but does not raise it; `_Reader.find` now refuses it (D-16).
- [ ] `find(cls)` with no filter pages through every aggregate of the class on each write; consider refusing an empty filter in both readers.
- [ ] `checked_find_values` builds a `TypeAdapter` per call; cache it per (class, slot).
- [ ] `_item_type` unwraps two levels only (`list[X | None]`, wider unions).
- [ ] The `BadQuery` text repeats the full value; bound it (`reprlib`).
- [ ] `_Reader.find` and `FakeAggregateReader` each split `None` and lists: one shared helper beside `checked_find_values`.
- [ ] The fake raises `NotImplementedError` for a dotted keyword where the real reader raises `BadQuery`; make them agree and pin it in `reader_conformance`.
- [ ] The feature steps' `ban_reading` repeats a test helper; move it to `tests/scene.py` on a third use.

**Generation**
- [ ] The export check of `refuse_unsupported_extensions` covers classes but not technical enums: a consumer slot ranged to an unexported technical enum fails later, at import, not with the clear error.
- [ ] `pydantic_split.py` holds the consumer-schema checks beside rendering (817 lines): move them to `extensions/technical_checks.py`.
- [ ] `ToolkitTypescriptGenerator.modules()` keeps the first module of each name: say in a comment that names are unique per closure.

**The generator's schema cache (D-15, a LinkML workaround; upstream linkml/linkml#4306)**
- [ ] It swaps a LinkML module global for a block: not safe if two threads generate at once (generation is single-threaded today). A lock and a depth counter would make it so.
- [ ] It sets `hbreader.Pathilizer._strifier`, a private attribute, and imports `hbreader`, which this project does not declare: name both in the ceiling comment, add a test that fails if the attribute goes, declare the dependency.
- [ ] The ceiling comment still says the upstream issue is "to file": it is linkml/linkml#4306.
- [ ] Remove the cache when LinkML offers a parse hook.

