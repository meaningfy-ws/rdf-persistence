# Seed: agent-efficiency (secondary; never groomed)

## The request (developer, 2026-11-09)

1. "look into the langfuse stats and tell me what takes so long and so slow any implementation
   task in this repo"
2. "where would you apply these new rules, so that agents follow them?"
3. "i just included serena mcp and ast-grep, how would you instruct the agent to use them to
   become more efficient"
4. "do you need an epic for this, or you can make changes directly? small epic better?" — the lead
   recommended a SMALL change for what touches gates and hooks; the developer: "shape that change now".

## Evidence: Langfuse, rdf-persistence sessions, 2026-10-27 to 2026-11-09

Wall time by observation kind (sum of latencies):

| Session | Bash tool | Main LLM | Subagent LLM | Turns |
|---|---|---|---|---|
| d2666b18 (iri-policy, wait-until, fix-hint) | 4.1 h (488 calls) | 58 min | 30 min | 27 |
| 5fba695a (delivery-friction) | 1.6 h (347 calls) | 17 min | 27 min | 9 |
| 3ae57a17 (guarded session) | 34 min (one call 17 min) | 16 min | 3 min | 17 |

LLM calls are fast (p50 3 to 6 s). Of the Bash calls over 30 s in d2666b18 and 5fba695a:

- About half are **polling loops** on a background run: `until grep -q real temp/checkall.log; do
  sleep 5; done`, `for i in $(seq 34); do kill -0 PID || break; sleep 5; done`,
  `while pgrep -f "make test"; do sleep 5; done`. Each ends at its ≈ 3 min timeout and is issued
  again: one `check-all` was polled 6 times in a row, one `make test` 7 times.
- **Full-suite re-runs**: `make test` (≈ 3 min) and `make check-all` (5 to 8 min) several times per
  stage (after each fix, per random seed while chasing flakes: `par1..par5.log`, `rand_*.log`).
- **Per-task gates run twice**: the builder runs them, then the lead runs them again.
- GitNexus re-index failures, 2 to 4 min each.
- Builder subagents take 20 to 40 min, much of it in the same gates.

Not usable: this session's own trace (e185d84d) holds only 197 observations.

## Measurement: `check-quality` parts, warm cache, laptop, 2026-11-09

| Target | Wall |
|---|---|
| format-check, lint, clean-code, check-architecture, check-docs | < 1 s each |
| check-spec | 2.7 s |
| typecheck-ts | 1.5 s |
| typecheck-openapi-ts | 5.1 s |
| typecheck | 10.3 s |
| typecheck-generated | 11.8 s |
| check-freshness | 10.9 s |
| **Total** | **≈ 45 s** |

The 2 to 3.5 min seen in Langfuse came from `check-quality` running beside test runs.

## Candidate ast-grep rules counted (2026-11-09), not adopted (Q-3)

`datetime.now(...)`: 1 hit (`utc_now` itself); `time.sleep` in tests: 0; `print(` in the package:
5, all in `generation/cli.py`; `-> dict[str, Any]`: 1 (`adapters/_http.py`). `sg` is deprecated in
ast-grep 0.51.1; the binary is `ast-grep`.

## Tools available (2026-11-09)

- Serena MCP (user scope, `--context claude-code --project-from-cwd`), loaded on session restart.
- ast-grep MCP (user scope) and the `ast-grep` CLI 0.51.1 on PATH.
- Subagents (skillery's `implementer`, `code-reviewer`) have fixed tool lists without MCP tools;
  they reach ast-grep only through Bash.

## Questions and answers (developer, 2026-11-09)

- **Q-1** Add a `make check-task` fast per-task gate? → **Drop it.** `check-quality` is ≈ 45 s warm;
  `test-lanes` (DEC-5) already makes `make test-changed` the per-task test gate.
- **Q-2** How strict is the polling hook? → **Deny sleep loops**; a single `sleep N` and
  `gh pr checks --watch` stay allowed.
- **Q-3** ast-grep rules in `make lint`? → **No rules, guidance only.**
- **Q-4** Who runs the per-task gates? → **The builder runs them and reports; the lead re-runs only
  `make check-quality` and reads the diff.** `check-all` before the PR catches a wrong report.

## Risks raised by the lead (accepted with the recommended handling unless the developer overrules)

- A subagent denied a loop may have no completion notice to wait for → the deny message offers the
  foreground first (timeout ≤ 10 min; every make target fits).
- The hook regex blocks a legitimate command → a corpus of real commands from the traces as tests.
- Serena's onboarding writes memories that compete with `openspec/specs/` → `.serena/` git-ignored,
  Serena memories not used.
- `test-lanes` edits the same gates table → this change starts after `test-lanes` merges.
