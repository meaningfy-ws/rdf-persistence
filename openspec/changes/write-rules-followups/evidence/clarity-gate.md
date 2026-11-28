# Clarity gate: write-rules-followups PLAN

run 1, 2026-11-28, 8.1/10, fail (fresh reviewer, after an attack; actionability 8.5, specificity
8.5, consistency 7.5, structure 9, disambiguation 7.5, reference clarity 7)

- The `_strifier` test failed on day one: a fresh `Pathilizer` has no `_strifier`; only `__str__`
  reads it. Fixed: PD-10 inspects `__str__`'s source and checks `str()` and the pickle round trip.
- The readers refused in two orders (the fake's root check first). Fixed: PD-3's one order
  (helper with the empty list, value, root, unknown slot), worked example 1, a conformance case.
- The move made an import cycle (`_field_name` needs `_is_python_name`). Fixed: PD-7 moves both;
  `technical_checks` imports nothing from `pydantic_split`.
- `test_fake_reader.py`'s non-root case had an empty filter. Fixed: PD-6.
- The Lanes table said integration; it is unit only. Fixed.
- PD-1 said the log reason "stays" `!r`; it changes. `type(status) is int` refused `HTTPStatus`.
  Fixed: `isinstance(int)` and not `bool` (DEC-4 reworded), an error-matrix row.
- S6 named no enum. Fixed: `ProblemSlug` through `break_toy`.
- The builder-confirms text, the `_field_name` "if", PD-11's harnesses, the 200 vs 300 bound, line
  numbers for docs: resolved in PD-6, PD-7, PD-11, worked example 2, PD-12.

run 2, 2026-11-28, 8.8/10, accepted (fresh reviewer, the run-1 gaps only; actionability 9,
specificity 9, consistency 8.5, structure 9, disambiguation 8.5, reference clarity 8.5)

- Run-1 gaps closed. New: the order case ran on a slot `Chapter` lacks; `find(Book, nosuch=["a",
  None])` differed between readers; the `HTTPStatus` row named no test. All three folded in
  (PD-3, PD-6, error matrix); no third run, per R-0005 (`design.md` D-1).
