> Derives from: EPIC `agent-efficiency` (proposal.md), DEC-1..DEC-8. Starts after `test-lanes` merges.

## 1. Stage 1: no polling, each gate once, one tool per question

- [x] 1.1 T-1..T-5 (design PD-3, test file written with the Write tool), then
      `.claude/hooks/no_polling.py` (PD-1). Acceptance: `make test-changed` green (a direct
      `uv run pytest` on the file only for the red/green loop); `make lint` clean on the hook.
- [x] 1.2 Wire it (PD-2): `.claude/settings.json` hook with the wrapper, `PYTHON_PATHS` in the
      `Makefile`, the `tests/changed.py` mapping if `test-lanes` left a table for it; T-6.
      Acceptance: T-6 green; `make check-quality` green.
- [x] 1.3 Live check (RISK-2, RISK-4), by the lead in a fresh session: D-1 denied and A-3 allowed
      from the lead (A-1 too, noting whether the harness itself blocks it), and D-1 denied from one
      subagent. Record the result under design.md *Risks*.
- [x] 1.4 Instructions (PD-4, PD-5): `AGENTS.md`, `develop/agents.adoc`, `questions.adoc`;
      `.gitignore` gains `.serena/` (DEC-7). Acceptance: `make check-docs` and `make check-spec` green.
- [x] 1.5 Skillery issue (PD-6): draft the text, show it to the developer, file it on approval,
      record the URL in design.md *Upstream*.
- [x] 1.6 Stage gate: `make check-all`, `make test-containers`; one review pass (lenses L2 and L3,
      SMALL); accepted findings into design.md first; one PR into `develop`, merged on green CI.

## Roadmap

- [x] 1.1 · [x] 1.2 · [x] 1.3 · [x] 1.4 · [x] 1.5 · [x] 1.6

## Verification

T-1..T-5 green, the live check of 1.3 recorded, `openspec validate agent-efficiency --strict`,
the clarity gate ≥ 9/10 on design.md + tasks.md, `make check-all` green before the PR.
