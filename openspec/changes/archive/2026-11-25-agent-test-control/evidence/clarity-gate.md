# Clarity gate: agent-test-control PLAN

EPIC readiness check (lightweight), 2026-11-25: pass. Appetite, why, solution outline, DEC-1 to
DEC-8, rabbit-holes and no-gos present; golden-thread parents named; the owner's round-1 answers
recorded in `inputs/qa.md`.

Attack of the PLAN (fresh reviewer, 2026-11-25), 15 findings, all folded in:
a writing testmon run made the next select nothing (now `--testmon-nocollect`, PD-5); the seed
held the worktree lock for its whole run (now only for the swap, lock order stated, PD-6); WAL side
files at the swap (now checkpoint, DELETE journal mode, side files removed, PD-7; WAL confirmed in
testmon's `db.py:29`); pytest's exit 3 collided with the fallback code (now 75, PD-4); subprocess
generator tests invisible to testmon (generator keeps its folder rule, PD-5); `uv.lock` would
re-select everything unqueued (now a fallback; package fingerprinting confirmed in `db.py`);
`subprocess.run` left workers running after a kill (now `execvp`, PD-1); holder line truncation and
unlinking (PD-1); queue wait not measurable (now `test queue: waited Ns`); `nproc` missing on macOS
and an untestable make expression (now `workers()` in Python, `--eval` test); worked-example row 3
contradicted PD-5 (e2e helpers now testmon-visible); `PYTEST_N`'s changed meaning (PD-3); CI and
the nested `uv run` (one `uv run`, `CI` turns the queue off, PD-2); task 2.4 moved the shared tree
(now 2.5, a separate worktree); a racy queue test (task 1.1 reads the waiting line first).
Found by the planner while checking: testmon turns selection off under `-m` (`configure.py`), so
every testmon run uses `--testmon-forceselect` (PD-5, PD-7).

run 1, 2026-11-25, 8.6/10, fail (fresh reviewer; actionability 9.0, specificity 8.5, consistency
8.0, structure 9.0, disambiguation 8.0, reference clarity 8.5). Gaps, all fixed: F's argument
list and one source for the ignores (`IGNORES` pinned to `UNIT_LANE`); a changed environment
re-selecting everything unqueued (package fingerprint in `check`); `GitError`'s exit code and the
two existing tests moving to 75; target versus command in the holder line (`TEST_QUEUE_LABEL=$@`);
the Makefile test under CI (explicit child environment); `tests/fixtures/` Python files are golden
text (whole folder a fallback); the seed's exit code and a stale seed file; the doc lines that
become false (listed in 3.1 to 3.3); a hung queue holder (error-matrix row, no maximum wait);
`swap` against a shared holder (2.4's Red); 2.3's dependency on 1.2 and generator tests run twice
(T leaves `tests/generator` to F); full reason strings, the spec's missing "selects", the
shared-configuration scenario's list, `tests/library_app.py` via injected `existing`; ids plain by
convention.
run 2, 2026-11-25, 9.3/10, pass (same fresh reviewer, gaps-only re-gate; actionability 9.5,
specificity 9.5, consistency 9.0, structure 9.0, disambiguation 9.5, reference clarity 9.0).
Five slips folded in after the run: the waiting-line example's label, the seed recipe's label,
"any file under `tests/fixtures/`", `check`'s two messages, the `IGNORES` comparison and the
lock scope of `swap` in task 2.4.

Memory additions (DEC-9, PD-3 extended, PD-9, task 1.3), after the owner's round 2 and the second
measurement (inputs/memory.md):
run 3, 2026-11-25, 8.975/10, fail (same reviewer, additions only; actionability 9.5, specificity
9.0, consistency 8.5, structure 9.0, disambiguation 8.5, reference clarity 9.0). Gaps, all fixed:
the teardown hook ran before pytest's own teardown (now a hook wrapper working after `yield`, with
a module-scoped-fixture Red case); `@workers` under `TEST_QUEUE=off` (always replaced); the 600 MB
scenario had no automated check (now `@manual`, measured by the lead through the queue, a miss goes
to the developer); What Changes placed the worker cap in `tests/conftest.py`; the workers line
without `/proc` (`memory unknown`).
The gaps were each closed as the reviewer specified; accepted at that under R-0005 (the owner
asked to proceed at once), no run 4.

The owner's instruction of 2026-11-25, "finish shaping, plan and proceed with implementation
immediately", is taken as the sign-off of the spec-delta scenarios (`rp-developer-checks`).
