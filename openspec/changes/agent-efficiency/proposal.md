<!-- Parents: rp-developer-checks (the checks a developer and CI run);
     develop/agents.adoc (how agents deliver work here); the change test-lanes (the per-task gate).
     Seeds, the Langfuse evidence, the gate timings and the developer's answers: inputs/seed.md. -->

# EPIC: Agents stop waiting on themselves

> Shaped 2026-11-09 from the developer's request and the Langfuse traces (Q-1 to Q-4 in inputs/seed.md).

**Golden-thread parents:** `rp-developer-checks`; `develop/agents.adoc`; the change `test-lanes`,
whose per-task gate (`make test-changed`, its DEC-5) this EPIC builds on.

## Appetite

**SMALL.** One hook with its tests, and instruction changes in two places (`AGENTS.md`,
`develop/agents.adoc`). No package code, no new make target, no new dependency.

## Why

In the traced implementation sessions the shell, not the model, takes the time: 4.1 h of Bash
against 1.5 h of model calls in one session, 1.6 h against 44 min in another. About half of the
slow Bash calls are agents polling their own background runs with `sleep` loops that time out and
are issued again; the rest are gates run twice per task (builder, then lead) and full suites re-run
after each fix. Serena and ast-grep are now installed, but no instruction says when to use them, so
agents keep reading whole files and rewriting code with Python heredocs.

## Solution outline

- **No polling.** A `PreToolUse` hook in the committed `.claude/settings.json` denies a Bash command
  that loops with `sleep` (`until`/`while`/`for … do … sleep … done`), and tells the agent what to do
  instead: run the command in the foreground with a timeout of up to 10 min, or run it in the
  background and wait for the completion notice. Hooks fire for subagents too, so the rule reaches
  the builders that prose briefs do not.
- **Each gate once.** The builder runs the per-task gates and reports their times and counts; the
  lead re-runs only `make check-quality` (≈ 45 s) and reads the diff. After a red full run, only the
  failing tests are re-run until green, then the full suite once.
- **One tool per job.** `AGENTS.md` names which tool answers which question: GitNexus for blast
  radius, Serena for reading and replacing one symbol, `ast-grep` for one code shape in many places,
  Grep for text. Briefs tell builders to search with `ast-grep run` and to edit in place, never with
  Python heredoc rewrites.

Success: the hook denies every polling command in the trace corpus and allows every other command
in it; the next epic's traces show no `sleep` loops and one `check-quality` run by the lead per task.

## Key decisions

- **DEC-1**: No `make check-task`. `check-quality` is ≈ 45 s warm and `test-lanes` already sets the
  per-task test gate. Source: Q-1, the timings in inputs/seed.md. Rejected: a thin `check-task`
  skipping generated-code checks (≈ 20 s saved per task, one more target to keep).
- **DEC-2**: The hook denies sleep loops only; a single `sleep N` and `gh pr checks --watch` stay
  allowed. Source: Q-2. Rejected: also denying `--watch` (it ends on its own); warning only (agents
  ignore warnings).
- **DEC-3**: The hook fails open: if it crashes, the command runs. A broken hook must never stop
  every Bash call in every session. Rejected: fail closed.
- **DEC-4**: The deny message offers the foreground first. A subagent may have no completion notice
  to wait for, and every make target finishes within the 10 min tool timeout. Rejected: background
  only.
- **DEC-5**: No ast-grep rules in `make lint`; ast-grep is a search and rewrite tool here. Source:
  Q-3. Rejected: three guard rules (0 to 1 hits today; ruff and import-linter already hold the line).
- **DEC-6**: The builder owns the per-task gates; the lead re-runs `make check-quality` and reads
  the diff; `make check-all` before the PR is the safety net. Source: Q-4. Rejected: the lead runs
  everything again (today, ≈ 5 min per task paid twice).
- **DEC-7**: Serena is for reading and editing symbols only. Its memories and onboarding are not
  used, and `.serena/` is git-ignored: the truth stays in `openspec/specs/`.
- **DEC-8**: Giving subagents Serena, and moving DEC-6 into the method, are skillery's to decide.
  The lead files one skillery issue after the developer approves it. Rejected: editing the plugin
  cache (overwritten on update).

## Rabbit-holes

- **A shell parser.** The hook matches a loop keyword, `do`, `sleep` and `done` in one command with
  a regular expression. A loop hidden in a script file it runs is out of reach; that is accepted.
- **Measuring the gain precisely.** One look at the next epic's traces, no dashboard.
- **Tuning Serena.** Defaults, apart from not using its memories.

## No-gos

- No change to the package code, the make targets, CI, or the coverage floors.
- No ast-grep rules, no new lint gate.
- No edits to skillery or the plugin cache from this repo.
- No change to what `check-all` and `test-containers` run, or when (once per stage).
- Not touching `openspec/changes/test-lanes/` or its worktree.

---

## What Changes

- `.claude/hooks/no_polling.py`: the hook (reads the tool call on stdin, prints a JSON deny with
  the reason; never exits 2, so its own failure lets the command run).
- `.claude/settings.json`: the `PreToolUse` hook on `Bash`.
- `Makefile`: `.claude/hooks` added to `PYTHON_PATHS` (formatted and linted like the rest).
- `tests/unit/test_no_polling_hook.py`: the corpus of real commands, denied and allowed.
- `AGENTS.md`: a short "Navigating and editing code" section; the polling and gate-ownership habits.
- `docs/modules/ROOT/pages/develop/agents.adoc`: the brief line, who runs which gate, no polling;
  `questions.adoc`: the question it answers.
- `.gitignore`: `.serena/`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `rp-developer-checks`: agents' shell commands do not poll.

## Impact

- Every Claude Code session and subagent in this repository runs the hook before each Bash call
  (≈ 0.1 s each).
- Docs and agent instructions. No runtime code, no dependency, no CI change.
- Ordering: starts after `test-lanes` merges (both edit the gates table in `develop/agents.adoc`).
