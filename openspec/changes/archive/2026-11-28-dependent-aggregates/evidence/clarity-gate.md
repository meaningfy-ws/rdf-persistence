# Clarity gate: dependent-aggregates

run 1, 2026-11-28, 8.8/10, fail
accepted at 8.8 (R-0005); G-1..G-6 folded in, 2026-11-28

Below 9 on the gate's own reading, but at the 8.8 the owner accepts (R-0005): fold G-1 to G-6 into
the PLAN, no second run needed. Scored: `design.md` + `tasks.md`; read with `proposal.md`, `specs/`,
`features/`, `evidence/attack.md` and `inputs/qa.md`. The Context claims were checked against
`persistence/services/session.py` (`_claim`, `remove`, `_send_and_confirm`, `_versions_found`,
`_diagnose`, `_require_present`, `_require_match`, `READ_ROOT_VALUES`, `_DROP_DEPENDENTS`),
`collaboration/services/reference_collections.py` (`delete_cascade`, `_require_room`),
`schema/services/schema_structure.py` (`refuses_deletion`, `served_roots`), `mapper.py`
(`max_roots`, batches) and `kit.py:243`. All of them hold.

## Checklist (13 items)

| # | Item | Result |
|---|---|---|
| 1 | Actionable | partial: tasks 1.4, 1.6, 1.7, 2.2, 3.3 and 3.4 have no `Accept:` line (G-5) |
| 2 | Current | pass: OPEN-1 and OPEN-2 are closed as D-1 and D-2; RISK-6 states what `develop` holds now |
| 3 | Single source | pass |
| 4 | Decision, not wish | pass |
| 5 | Prompt-ready | pass |
| 6 | No future state | pass: PD-17's step after the archive is a decision with a task (3.1) |
| 7 | No fluff | pass |
| 8 | Type identified | pass: both files say they are the PLAN |
| 9 | Anti-patterns placed | pass: 6 rows, MEDIUM needs at least 4 |
| 10 | Test cases placed | pass: the tests are in the tasks and 12 scenarios; there are no manual checks |
| 11 | Error handling placed | partial: 20 rows, but no fallback column (G-4) |
| 12 | Deep links | partial: tasks cite `PD-n` with no `design.md#…` anchor, and some paths are partial (G-6) |
| 13 | No duplication | pass: the EPIC points to the PLAN and does not copy it |

## Rubric

| Criterion | Weight | Score |
|---|---|---|
| Actionability | 0.25 | 9.0 |
| Specificity | 0.20 | 9.0 |
| Consistency | 0.15 | 9.0 |
| Structure | 0.15 | 8.5 |
| Disambiguation | 0.15 | 8.5 |
| Reference clarity | 0.10 | 8.5 |
| **Total** | | **8.8** |

## Gaps

- **G-1** (`design.md` PD-5 step 1 and PD-6; disambiguation): a part that the transaction replaces
  (or adds), and that the cascade then reaches, meets a crash before step 2's `Conflict`.
  Example: the transaction removes A1 and replaces R1. Step 1 then calls `_remove_read(R1)`,
  which goes through `Transaction._claim` and raises `ValueError` ("already has a change in this
  transaction", `session.py:1406`). PD-5 handles only parts the caller *removes*. **Fix:** in
  step 1, a discovered part that is already collected as an add or a replace is not collected
  again, but it is still discovered from. Step 2 then raises the `Conflict`. Add a test row to
  task 2.5: "replace R1 and remove A1 in one transaction → `Conflict` naming R1 and A1, nothing
  sent".
- **G-2** (`design.md` PD-3 and Algorithm "Part write" step 2; specificity): PD-3 does not say
  *when* the early ASK and the check against the collected triples run, at `add_graph` time or
  at commit. If they run at `add_graph` time, a whole that is added *after* its part in the same
  transaction gets `NotFound`. **Fix:** say they run at commit, after PD-5's expansion, so the
  order in which the transaction collects the whole and the part does not matter. Or state that
  the whole must be collected first, and add a task 2.3 row for that order.
- **G-3** (`design.md` "Discovery query" and PD-6; consistency): PD-6 says each row gives the
  part's *type* and passes it to `_remove_read`, but the query selects only
  `?whole ?part ?version`. **Fix:** add `?type` to the `SELECT`.
- **G-4** (`design.md` Error matrix; structure): the matrix has columns for the failure, how it
  is detected and how it is handled, but no fallback column. Rows with a retry or an accepted
  risk (no-late-part, version guard, batch mode, orphans) mix the response and the fallback in
  one cell. **Fix:** split "Handling" into "Response" and "Fallback". Use "none" where there is
  no fallback, and "retry" or "RISK-n" where there is one.
- **G-5** (`tasks.md` 1.4, 1.6, 1.7, 2.2, 3.3, 3.4, and the numbering; actionability and
  structure): these tasks have no `Accept:` line. The ids also run out of order (2.5a, then 2.7
  before 2.6), so only the Roadmap gives the real order. **Fix:** give each of these tasks an
  `Accept:` line (the test named passes, or `make check-docs` passes). Renumber stage 2 in the
  Roadmap order, or add a note that the Roadmap's order wins.
- **G-6** (`tasks.md` throughout, and `design.md` Context and PD-13; reference clarity): tasks
  cite `(PD-3)` rather than `design.md#pd-3`. Some paths are partial: `router.py`,
  `uml/links.py`, `uml/classes.py`, `checks/dependence.py`, `kit.py`. **Fix:** link each PD with
  a `design.md#pd-n` anchor, and write every path from the repository root (for example
  `rdf_persistence_generation/uml/links.py`).
