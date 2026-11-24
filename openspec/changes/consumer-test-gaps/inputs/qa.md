# Q&A record: consumer-test-gaps (secondary, never groomed)

Shaped 2026-11-24 with the owner, two rounds (the cap for SMALL). Read before asking: the four
issues (`seed.md`); `testkit/fakes.py` (`_Instrumented.on`, `FakeStore.update`, `after_update`,
`fake_session`); `events/services/relay.py` (`Relay.paused`); `session._mark` (the relay's own
`update`); `api/entrypoints/problems.py` (`in_use_problem`, `install_problem_handlers`);
`collaboration/services/collaboration.py` (`_listed`) and `referrer_naming.py`; the `Referrer`
class in `rp_collaboration_services.yaml`; `iris/services/iris.py` (`_aggregate_re`, no reverse
IRI→id); `api/services/documents.py` (`aggregates`); `uml/slots.py` (`_bounds`, `_shape_kwargs`,
`usage_of`, `share`, `_lineage`); `uml/classes.py` (`parents`); the planning rules (R-0002 to
R-0005).

## Round 1

## Q: #319: how is a fault aimed at the request's write and not the relay's?
- Asked because: `on()` counts calls across every caller; `Relay.paused()` already exists.
- Options: document `relay.paused()` (recommended); `on(..., match=predicate)`; both.
- Answer: document `relay.paused()`.
- → DEC-1

## Q: #323: which facility holds commits for a concurrent-write test?
- Asked because: the consumer monkeypatches `store.update` and matches SPARQL text.
- Options: `FakeStore.hold(op, until=n)` with a timeout (recommended); a `before_update` hook; a
  barrier in `fake_session` (a Session seam).
- Answer: `FakeStore.hold(op, until=n)`.
- → DEC-2

## Q: #320: which of the issue's three options?
- Asked because: a client cannot form the generic GET of a referrer from the 409 body.
- Options: optional `rp_path` and id on `Referrer` (recommended); a read-by-IRI route; a class→rp_path
  map in the generated TypeScript.
- Answer: `rp_path` and id on `Referrer`.
- → DEC-3

## Q: #332: what does `usage_of` write for a differing cardinality whose own value is None?
- Asked because: `_shape_kwargs` skips None, so the parent usage's bound is inherited.
- Options: the multiplicity's own bound, plus a finding for an unbounded upper bound under a
  bounded ancestor (recommended); the same, silent; a finding on any widening (rejects the issue's
  own reproduction).
- Answer: explicit bound + finding.
- → DEC-4

## Round 2 (confirms round 1 in its option texts)

## Q: how are the stages sliced?
- Answer: three stages by concern: testkit (#319, #323), API (#320), generator (#332).
- → DEC-6

## Q: which scenarios must the change prove?
- Answer: all four offered: #319 the fault hits the request inside `paused()`; #323 one write
  wins, the other gets `Conflict`, and too few callers fail by timeout; #320 the referrer is
  followable from the 409 and the referrers listing, and both fields are absent when either cannot be
  known; #332 the reproduction, its max twin, and the finding.
- → the spec deltas and `design.md` error matrix.

## Q: risk: what outside the change could hurt a consumer, and what do we do?
- Answer: accept the regeneration diff and note it in the CHANGELOG (RISK-1); accept the
  optional fields (RISK-2); document that `hold` belongs inside `relay.paused()` (RISK-3).
  Not ticked: "the finding is a warning". So the new finding is an error, as every converter
  problem is (DEC-5, RISK-4).

## Q: which no-gos?
- Answer: all four offered: no read-by-IRI route; no `match=` on `on()`; no Session seam; no
  general UML redefinition check.
