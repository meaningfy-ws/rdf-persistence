# Clarity gate: test-memory-followups PLAN

run 1, 2026-11-25, 8.4/10, fail (fresh reviewer; actionability 9.0, specificity 8.0, consistency
8.5, structure 9.0, disambiguation 7.5, reference clarity 8.0). Sharing one view across kits was
judged safe for the library's code as it stands (nothing reachable from the kit mutates it; the
cached `vocabulary.metamodel()` view at `kit.py:172` is a precedent). Gaps, not yet folded in:

1. PD-2: the cache is unbounded; `tmp_path` schemas (`test_service_kit.py:666`) add entries never
   evicted. Bound it (LRU, about 8) and let the testkit's `release_memory` empty it.
2. PD-2: `st_mtime_ns` can miss a rewrite within the clock's 1–10 ms step; add size and a content
   hash of the root file to the key, or the test sets the mtime with `os.utime`.
3. PD-3: the guard sees only the root module and `set_modified`; hash every module in
   `schema_map`, and drive workflows, migrations, archive/restore, `receive` and the events route;
   document `kit.view` as read-only.
4. Task 1.1: no public helper clears SchemaView and FastAPI caches without `typing`; name the calls
   or add `clear_caches(typing=False)`; reword `memory.py:_clear_typing`'s docstring.
5. Task 1.3: fixture order unstated; a named new test with
   `@pytest.mark.usefixtures("raised_limit", "default_recursion_limit")`; decide on the depth-5000
   braces test.
6. RISK-3: wrong premise (views were cold before anyway); give the timing command and a 10 %
   threshold.
7. DEC-2/spec say `install_service`, PD-2 says `ServiceKit.__init__`; a missing schema must raise as
   `load_schema` does (error row and test).
8. Thread-safety: state that concurrent reads of a shared view race only on idempotent cache fills,
   and that the global lock serialises loads of different files.
9. References: `tests/unit/api/test_openapi_served.py`, anchors for PD-n, "the paused sessions".
10. PD-5: name the Langfuse filter fields and the formulas; the three DEC-8 targets as a table.

The developer asked to fix the gaps the same day; all ten folded in (`ee023bcf`).

run 2, 2026-11-25, 8.9/10, fail (same reviewer, gaps only; actionability 9.5, specificity 8.5,
consistency 8.5, structure 9.0, disambiguation 8.5, reference clarity 9.5). All ten run-1 gaps
closed. Eight slips found and folded in after the run: the induced-slot comparison now digests
the dumped slots at each point (cached objects compared equal to themselves); a failed read
defers to `load_schema` so the error is identical; the pin is a context manager wrapped by the
autouse fixture (pytest forbids calling a fixture); the overlap on `memory.py` stated and the
roadmap corrected; "once" qualified as until the next `release_memory`; DEC-3 and What Changes
current; the `load=` seam named; the start-up migrations in the spec scenario.
Accepted at 8.9 under R-0005 (≥ 8.8: fold the small gaps in, no further run).

Side effect of run 2: the reviewer's `uv run python` installed packages into this worktree's
`.venv`; no tracked file changed. Re-seed before relying on selection data in it.

**Parked** by the developer on 2026-11-25 with the PLAN gated; Q1 to Q5 still open.

## Re-gate of the additions (DEC-5 to DEC-7, PD-6 to PD-8, sections 2 and 4, the deltas)

Resumed 2026-11-26: Q1 to Q5 answered, DEC-7 (#416) folded in, appetite MEDIUM.

run 1, 2026-11-26, 7.4/10, fail (fresh reviewer, attack and gate in one; actionability 8,
specificity 8, consistency 6, structure 8, disambiguation 7, reference clarity 8). Thirteen gaps,
six from the attack: one `seed` per lane would keep only the last lane's data; the lanes differ
from the seed (`LIBRARY_LANE`, random order); the spike's data files impossible through `seed`;
the `main` test would pass without the feature; the lock claim overstated; a reverted shared file
unnoticed; the `uv.lock` reasoning wrong; a stale commit file on a crash; the git seam unclear;
the hex check, `__all__`, the tooling case, the 2.2 Red test and the `rp-developer-checks` delta
unspecified. All folded in.

run 2, 2026-11-26, 8.5/10, fail (same reviewer, gaps only; actionability 9, specificity 9,
consistency 8, structure 9, disambiguation 8, reference clarity 9). All thirteen closed; three
new, all folded in after the run: N1, 2.2's Red test would have run a real seed through
`make -n test` (now a variable probe, `--eval='print-%: …'`, checked to work); N2, the revert
rule would fall back after every rebase (now only non-testmon-visible paths, with a worked
example); N3, the fifth recording case listed in design.md.

Two runs spent; below 9, so the developer decided: accepted at 8.5, no third run (design.md D-1).
