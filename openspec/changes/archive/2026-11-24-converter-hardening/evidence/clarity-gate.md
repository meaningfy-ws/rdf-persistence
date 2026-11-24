# Clarity gate: converter-hardening PLAN

Planner's self-score (a fresh reviewer gates later). Full 13-item gate on design.md + tasks.md.

run 1, 2026-11-22, 8.7/10, fail
  - G-1 task 1.8 stated the meaning of `install_service`'s relative paths as fact, unverified.
    Fixed: stated as expected, the builder checks the code and writes what it does.
  - G-2 task 1.7's "one assert per Then" acceptance was a lead's grep with no target. Fixed: no
    `@then` function in `test_uml_import.py` with more than one `assert`, checked with `ast-grep`.
  - G-3 (from the attack) the encoding test could fail on a third-party import reading without an
    encoding; the staging folder could report itself as left over; an `OSError` from the stale
    globs escaped PD-3; 1.6 overlapped files with 1.2, 1.3, 1.5; `Closes #229` dropped the deferred
    items. Fixed in PD-6, PD-3, the roadmap and task 1.9.
run 2, 2026-11-22, 9.0/10, pass (only the gaps above re-read)

Weakest criterion: grounding of task 1.8 (#261): its answers are found while building, so the
PLAN fixes the questions and the proof (a named test per stated behaviour, a cold read), not the
answers. Second: PD-4 assumes `load_schema` resolves the staged root's `app_*` imports relative to
the staging folder; task 1.4's acceptance runs the feature "A drawn workflow" through it.

Scenarios: to be signed off by the owner with `inputs/qa.md` OPEN-1 to OPEN-4.
run 3, 2026-11-22, 8.6/10, fail (fresh reviewer; 5 gaps)
run 4, 2026-11-22, 8.8/10, pass (fresh reviewer, gaps-only re-gate; 1 gap)
Accepted at 8.8 under R-0005; two small gaps folded in after the run (1.4 message text, test_uml_cli.py import).
