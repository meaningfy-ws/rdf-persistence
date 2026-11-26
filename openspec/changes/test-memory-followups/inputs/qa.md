# Q&A record (secondary, never groomed)

## Round 1, 2026-11-25 — open for the developer (shaped on defaults; the developer asked for speed)

| # | Question (recommendation) | Answer | Becomes |
|---|---|---|---|
| Q1 | Where does the schema reuse live? (Recommended: a process-wide cache for the service kit only, keyed by resolved path and modification time, beside an unchanged `load_schema`; alternatives: cache inside `load_schema`, which the generator would share and modify; or `install_service` accepting a `SchemaView`) | open | DEC-2 |
| Q2 | May DEC-1 change the dependency style of `auth.py` and `sse.py` to the default-argument form `router.py` already uses? (Recommended: yes) | open | DEC-1 |
| Q3 | DEC-8's measurement waits for the paused sessions to run on the merged code: keep it in this EPIC as its last task, not blocking the PR of the fixes? (Recommended: yes) | open | DEC-4 |
| Q4 | Risks (R-0002): what outside could change (a FastAPI or linkml release, #4284 fixed upstream), who is hurt if a shared view is modified (every test sharing it), what we accept | derived from context, open for review | RISK-1 to RISK-3 |
| Q5 | Appetite SMALL | open | Appetite |

## Round 2, 2026-11-25 — answered by the developer in a `review-floors` close-out session

| # | Question (recommendation) | Answer | Becomes |
|---|---|---|---|
| Q6 | Does the spike "let the full run also refresh the seed" belong here? (Recommended: yes, as a timeboxed spike, its outcome decided by measured pass criteria) | yes: "add the spike to the parked epic change in tests followup ... it would have to be integrated there" | DEC-5, PD-6, tasks 2.1, 2.2 |
| Q7 | Record the session's lesson on test runs nobody reads? (Recommended: as a decision the lead follows in this EPIC, the docs fix already merged in #398, P-0022) | yes: "record there the wisdom on no overrunning tests if not needed" | DEC-6, PD-7 |

## Round 3, 2026-11-26 — the developer answers Q1 to Q5 at resume, and one new question

| # | Question (recommendation) | Answer | Becomes |
|---|---|---|---|
| Q1 | (as round 1) | the recommended: a cache beside `load_schema` | DEC-2 |
| Q2 | (as round 1) | yes | DEC-1 |
| Q3 | (as round 1) | yes, the last task, not blocking | DEC-4 |
| Q4, Q5 | Appetite SMALL and RISK-1 to RISK-3 as accepted; also: fold in #416's design gap (a branch that changed a shared file falls back on every task gate)? (Recommended: SMALL, #416's gap in its own change) | **fold in the #416 fallback**; the risks stand | DEC-7, PD-8, appetite MEDIUM (a logged re-shape), RISK-4 |
