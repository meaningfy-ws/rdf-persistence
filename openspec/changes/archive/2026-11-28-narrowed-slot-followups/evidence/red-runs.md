# Red runs (PD-2, DEC-2)

Recorded by the lead from the builder's report, 2026-11-28. Each test of working code was made to
fail by a deliberate break, run with the freshness plugin off (not of record), then the break was
undone before the green run.

| Finding | Break | Failing assertion |
|---|---|---|
| W1 | `_is_under`'s class branch forced true | row `class-not-under` fails |
| W1 | `_is_under`'s type branch forced true | row `uri-against-string` fails |
| W1 | fallback forced true | the three kind rows and both enum rows fail |
| S2 (unit) | identifier/key guard removed | both cases fail: "Child.s as key is marked" |
| W2 | override check forced false | mypy `[assignment]` at `app_narrow.py:106-107`, nothing on `main_part` |
| W2 | override check forced true | "a covariant override is marked" |
| S2 (absent keyed slot) | `None` branch removed from the template | `AttributeError: 'NoneType' object has no attribute 'code'` |
| S1 | today's template | `AttributeError: 'dict' object has no attribute 'code'` |
