# Clarity gate: otel-observability (design.md + tasks.md)

No self-score by the shaper was recorded; this is the first independent run, after the attack's
fixes.

run 1, 2026-11-17, 8.9/10, pass

Full gate, 13 items; rubric: actionability 9, specificity 9, consistency 8.5, structure 9,
disambiguation 9, reference clarity 8.5. Passes under the owner's R-0005 (8.8 or more); the small
gaps below were folded in or accepted, no second run.

Gaps found by the attack and fixed before scoring:

- PD-6 pointed at a per-call table "in tasks.md" that did not exist: the 41-row table (message,
  step, slots, `exc_info`) is now PD-6, the single source; tasks cite its rows.
- The inventory missed the `problems.py` record `manual-revision-notes` PD-9 adds with a bare
  `extra={"error.type": ...}` and an unqualified class name; it would fail PD-9's guard. Added as
  PD-6's last row, TC-13c, RISK-7.
- `tenancy.py:940` (`_log_step`) logs a variable message; given a constant one.
- TC-21 was untestable as written (`NoSuchBucket` is mapped before `s3.py:57` logs); now an
  unmapped code, and `NoSuchBucket` asserts no record.
- PD-2 had no slot for the envelope's class IRI or origin (`kit.py:229,231,241`) and one slot no
  site writes (`messaging.message.id`): two added, one removed, 28 keys (TC-04).
- The relay task inherits the lifespan's context: `traced(root=True)` for `rp.relay.round`,
  RISK-8, TC-34 strengthened.
- Span placement for swallowed failures (inside the `try`) and `rp.step` on every span made
  explicit (PD-5); `log_extra` uses `by_alias=True` explicitly; `error_type` helper (TC-38);
  `spans` fixture semantics (PD-10); start depends on `manual-revision-notes` as well.

Gaps left (accepted, minor):

- The spec delta does not state that a relay round is a root span; PD-5 and TC-34 carry it.
- `messaging.system.name="redis"` is not a well-known semconv value; it is the custom lowercase
  product name the conventions allow (DEC-1's reading).
