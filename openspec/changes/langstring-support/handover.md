# Hand-over: langstring-support, PLAN derived, scenarios signed off (2026-11-28)

**Where:** worktree `/home/lps/work/workspace-charm/rdf-persistence/.worktrees/langstring-support`,
branch `docs/plan-langstring-support` (draft PR #467), rebased on `develop`. `.venv` synced with
`uv sync --all-extras` (Python 3.13; `make install` is the target; a bare `uv sync` drops the
`generate` extra and `linkml`).

**State of the PLAN**
- EPIC (`proposal.md`) re-shaped to SMALL, two stages (DEC-6); DEC-1 to DEC-9.
- Owner's answers: `inputs/qa.md` (OPEN-1..4, Q-1..4, P-1..4). Question rounds spent (SMALL: two).
- `design.md` PD-1 to PD-20, error matrix, RISK-1 to RISK-7; `tasks.md` stage 1 (1.0 to 1.6) and
  stage 2 (2.0 to 2.12) in waves.
- Attack done (15 findings folded in; `design.md` "Attack").
- Scenarios signed off (`evidence/signoff.md`): `features/*.feature` and the spec deltas. Do not
  change them without the owner.
- **Clarity gate: run 1 was started in a fresh subagent before the compact; its result may arrive
  after it.** On arrival: fold small gaps into `design.md`/`tasks.md` (never the signed-off
  scenarios), append its line to `evidence/clarity-gate.md`, commit. R-0005: >= 8.8 is accepted; at
  most one more run, on the listed gaps only. If the result is lost, re-run the gate once with the
  brief below.

**Next: delivery, in this session, as team lead** (`epic-delivery`; `develop/agents.adoc`).
1. Stage 1 branch off `develop` (e.g. `feat/langstring-stage-1`), in a worktree of its own or this
   one after the PLAN PR merges; the PLAN files travel on #467.
2. Stage start: GitNexus impact on the existing index (the owner said no reindex unless asked);
   `make test-seed` in the background.
3. Lead task 1.0 (measures fixture), then wave A builders 1.1 ∥ 1.2 ∥ 1.3 ∥ 1.4 in parallel.
4. Then 1.5, 1.6 (`make check-generated` no diff, `make check-all`, one review pass, PR). Stage 2
   the same, from 2.0.

**Every subagent brief carries** (the owner asked twice; candidate rule pending on the card):
- the absolute worktree path, and "call `mcp__serena__activate_project` on it first";
- `develop/agents.adoc#brief` checklist pasted, and `#tools`: Serena for Python symbols and
  callers, ast-grep for shapes, Grep only for YAML/JSON/docs/Makefile, no `s.shell`/`s.mem`, no
  re-index; the report says which tool backed each finding;
- `rules.py load --activity <coding|review|planning> --brief` output;
- the AGENTS.md guards for builders, word for word.

**Pending with the owner**
- Rule-learner card: the candidate "every subagent brief, builders and read-only alike, carries
  `agents.adoc#tools` and the Serena activation on its worktree" (and an optional skillery issue:
  `rules.py --brief` and `epic-delivery`'s brief carry no tool rules for read-only subagents).
- PR #468 (rule P-0041), release 0.17.0 (changelog PR, nightly, merge #429, fast-forward `main`).

**Probes** (not committed): `temp/` (`probe_*.py`, `dec8/`, `lang/`, `attack/`).
