# Q&A record: write-rules-followups

Secondary, preserved, never groomed. Seeds: issue #455 (`seed.md`, verbatim), the developer's
brief of 2026-11-28 (the candidate items, the process), the archived design of
`consumer-write-rules` (D-16, D-20, D-21, D-22), and the code at `origin/develop` 6bcad805.

## What the code check found (2026-11-28, the planner)

- T-F1, T-F2, R-S4, the fake's dotted keyword, the `TypeAdapter`, `reprlib`, the shared helper,
  `ban_reading` (four copies now: `test_aggregate_validators_api`, `test_rule_refusal`, the
  feature test, `test_delete_in_use`), the enum export check, the move to `technical_checks`, the
  TypeScript comment, the schema-cache comment and `hbreader` all hold.
- `Session.find` and `BadQuery` holds only in part: a value whose text does not parse is refused
  by the listing; a value whose text does parse (`5` for a string slot, `"5"` for an int slot) is
  not. Making `Session.find` strict would break `reference_collections.py:435`, which passes the
  stored rule values as text for every slot.
- `find(cls)` with no filter holds; `reader_conformance.py:119`, `:124`, `:131` call it unfiltered.
- `_item_type` does not hold as written: `list[X | None]` unwraps in two steps, and a wider union is
  a valid `TypeAdapter` input; only `Optional[list[Optional[X]]]` fails, which the generator never
  emits.
- The thread lock: generation is single-threaded; nothing needs it.

## Q: Which items are in?
- Asked because: the issue lists candidates; some no longer hold.
- Answer: all, except `_item_type` and the thread lock; `Session.find` gets its docstring corrected,
  not a strict check. Appetite SMALL, one stage.
- → DEC-1, DEC-2

## Q: An empty filter: refused or allowed?
- Asked because: a rule's `find(cls)` reads every aggregate of the class on each write.
- Answer: refused with `ValueError` in both rule readers, before any query; `Session.find` unchanged.
- → DEC-3

## Q: A status of `409.0`: accepted or refused?
- Asked because: `409.0 in {409, 422}` is true.
- Answer: refused; the status must be an `int` and not a `bool`.
- → DEC-4

## Q: The hbreader dependency and the lock?
- Asked because: the generator imports `hbreader`, which `pyproject.toml` does not declare.
- Answer: `hbreader>=0.9.1` in the `generate` extra; the lead runs `uv lock` and `uv sync`, then
  seeds again; a test fails if `Pathilizer` loses `_strifier`.
- → DEC-5

## Q: Is any item BREAKING?
- Answer: two CHANGELOG lines under BREAKING: the empty-filter refusal; the fake's `BadQuery` for a
  dotted keyword (was `NotImplementedError`).
- → DEC-6

## Q: The test scenarios?
- Answer: S1 to S7 as proposed, signed off ("accept your recommendations").
- → the spec deltas; `evidence/signoff.md`

## Q: Risks?
- Answer: "address the risks": each is mitigated, none only accepted.
- → RISK-1 to RISK-3 in `design.md`
