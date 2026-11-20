# Clarity gate: testkit-event-stream PLAN (design.md + tasks.md)

Full gate, 13 items, 6-criterion rubric, after the planner's own attack (step 7).

- run 1, 2026-11-20, 9.0/10, self-score (planner), pass
- run 2, 2026-11-20, 8.5/10, fresh reviewer, fail
- run 3, 2026-11-20, 9.0/10, fresh reviewer (gaps only), pass

Attack findings folded in before scoring (checked against the code at `4e8d1fe2`):

- DEC-2's frozen dataclass fails the toolkit's own model guard (`testkit` is scanned,
  `@dataclass` forbidden) and PD-24: PD-1 generates the records instead; OPEN-1.
- No signal says an app's lifespan already runs; running it twice starts a second relay: PD-3
  (flag set by the toolkit's lifespan); OPEN-2.
- A third user of `follow`/`parsed` (`test_service_kit.py` TC-36) reads a raw keep-alive the
  helper skips: rewritten to a lifetime-ended stream (design row).
- Tests that hold a stream across commits, wait for its end or prove an absence by timeout:
  task + `listening`, PD-5 (c) early end, `drained(hub)` before the next offer or clock jump,
  PD-6 sentinels.
- `Following` holds no plumbing: kept as the scenario context (PD-7); OPEN-3.
- `test-debt-paydown` edits the same file: RISK-1; OPEN-4.
- Chunk splits, split UTF-8, `\r\n`, FastAPI's `: ping`, a disconnect the app ignores, a task left
  pending by a failed scenario: error-matrix rows.

- run 1 (fresh reviewer), 2026-11-20, 8.5/10, fail. 4 gaps: tasks did not name their tier and
  failing test first; the "fails without `sse`" check was manual; "the event loop cancels" a pending
  task was unverified; `FORBIDDEN_DECORATORS` had no path. Revised: every task names its tier and
  its first failing test; the manual check dropped (2.2); PD-8 (a `streams` fixture cancels and
  gathers) and its error row; the path cited in Context. The owner's answers (inputs/qa.md) are
  folded in: SMALL, DEC-2 amended, OPEN-1 to OPEN-4 closed. Run 2 reads only these gaps.

Gaps left at the self-score, now closed by the owner: four owner decisions pending (OPEN-1 to OPEN-4), each with a default;
PD-1 departs from the letter of the frozen DEC-2 and needs the owner's logged acceptance.

**Status (2026-11-20): the owner amended DEC-2 (logged in proposal.md); the gaps-only run 3 by a
fresh reviewer scored 9.0/10, pass. Ready for an epic session.**
