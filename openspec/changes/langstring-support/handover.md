# Hand-over: langstring-support, stage 1 in PR #474, stage 2 next (2026-11-28)

**Where:** worktree `/home/lps/work/workspace-charm/rdf-persistence/.worktrees/langstring-support`,
branch `feat/langstring-stage-1` (PR #474 into `develop`; it carries the PLAN commits of draft #467).
`.venv` synced with `uv sync --all-extras` (`make install`; a bare `uv sync` drops `linkml`).

**Stage 1: done, awaiting the owner's merge.** Tasks 1.0 to 1.6. `make check-all` green after the
fix pass (unit 9295, feature 133, generator 2258; coverage 97.21 %). One review pass L2+L3: 8
findings, F-4 accepted as Critical and fixed with F-2, F-5; F-7 lead-fixed; the rest under the
floor (D-8). Delivery decisions D-1 to D-8 in `design.md`, for the owner to validate.

**Next: stage 2 (`lang_string`)**, tasks 2.0 to 2.12, from a fresh session (or this one, if the
owner says so), after #474 merges:
1. Branch `feat/langstring-stage-2` off `develop`. GitNexus impact on the existing index (no
   reindex unless the owner asks); `make test-seed` in the background only if builders share the
   worktree.
2. Lead 2.0; wave A 2.1 ∥ 2.2 ∥ 2.3 ∥ 2.4; lead 2.5 (`make generate`, `make refresh-golden`);
   wave B 2.6 ∥ 2.7 ∥ 2.8 ∥ 2.9; 2.10; lead 2.11, 2.12 (`make check-all`, `make test-containers`).
3. **D-6:** builders sharing a worktree cannot pass `make test-changed` while generator sources are
   mid-edit (the freshness plugin stops every session). Either a worktree per generator builder
   (2.2, 2.3, 2.4, 2.9), or builders run `uv run pytest -p no:rdf_persistence_generation.testkit.freshness
   -W ignore::pytest.PytestConfigWarning <files>` and the lead regenerates and runs the gates.
4. Kill no other session's queued run; stop only this worktree's stale builder runs, by pid.

**Every subagent brief carries:** the standing block used in stage 1 (the lead's scratch
`common-brief.md`, rebuilt from): the absolute worktree path and base sha; `develop/agents.adoc#brief`
checklist and `#tools`; the AGENTS.md builder guards word for word; `rules.py load --activity coding
--brief`. **Serena:** `activate_project` is not available in this CLI; Serena reads the main
checkout (`develop`), so it is read-only orientation on unchanged code; edits with Edit on absolute
worktree paths; ast-grep on the worktree.

**Pending with the owner**
- Merge #474; validate D-1 to D-8.
- Rule-learner card, row 1: every subagent brief, builders and read-only alike, carries
  `agents.adoc#tools` and the Serena activation on its worktree (optional skillery issue).
- Release follow-ups: nightly run, fast-forward `main`.

**Probes** (not committed): `temp/` (`probe_*.py`, `dec8/`, `lang/`, `attack/`, gate logs).
