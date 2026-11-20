<!-- Secondary input, never groomed: the planning round of 2026-11-20. The EPIC (../proposal.md)
     and the PLAN (../design.md, ../tasks.md) supersede it. -->

# Q&A: testkit-event-stream, planning round 1 (2026-11-20)

Asked by the planner (design.md, Open Questions), answered by the owner through the coordinator.

| Id | Question | Recommendation | Owner's answer |
|---|---|---|---|
| OPEN-1 | DEC-2's frozen dataclass fails the toolkit's model guard (`FORBIDDEN_DECORATORS` in `rdf_persistence/testkit/guards.py`, `testkit` scanned) and PD-24: generate the records? | generate `OpenedStream`, `StreamEvent` from `rp_testkit.yaml` | **Accepted.** DEC-2 replaced: generated from LinkML, per AGENTS.md principle 2 |
| OPEN-2 | The lifespan flag adds lines to `api/entrypoints/service.py`, outside What Changes | the flag `app.state.rp_lifespan_started` | **Accepted.** Added to What Changes |
| OPEN-3 | "Both private helpers are deleted": `Following` has no plumbing of its own | keep it as the scenario's state holder | **Accepted.** EPIC now says "their stream plumbing is deleted" |
| OPEN-4 | Order against `test-debt-paydown` (same test file) | this change first | **Accepted.** This change lands first |

Re-shape: the owner raised the appetite **TINY → SMALL** (2026-11-20), as the PLAN found it to be.

Gate run 1 (fresh reviewer, 8.5/10, fail) gaps, fixed in the PLAN: tasks name their tier and
failing test first; the "fails without `sse`" check dropped; pending stream tasks cancelled by an
explicit fixture; the guard's path cited.
