<!-- PLAN (design half) for EPIC agent-efficiency (proposal.md). Decisions DEC-1..DEC-8 live in
     the proposal; this file cites them. Evidence: inputs/seed.md. Plan review: § Plan review. -->

# Design: agent-efficiency

## Context

The traces (inputs/seed.md) show the time goes to the shell: polling loops, gates run twice, full
suites re-run. The fix is one mechanical guard (the hook) and two instruction changes (who runs
which gate; which tool answers which question). The per-task test gate itself comes from
`test-lanes` (its DEC-5): `make test-changed` + `make check-quality` + `make clean-code`.

Claude Code facts this design relies on (code.claude.com/docs/en/hooks, read 2026-11-09):
hooks from settings files fire for subagents' tool calls too; a `PreToolUse` hook denies a call by
printing `hookSpecificOutput.permissionDecision: "deny"` JSON and exiting 0, or by exiting 2; any
other non-zero exit, or a timeout, lets the call run; `$CLAUDE_PROJECT_DIR` is the main checkout
the session started in, also when it works in a worktree; edits to hooks are normally picked up by
the settings file watcher.

## PD-1 The hook: what it denies

`.claude/hooks/no_polling.py`, standard library only, one public function and a `main`:

```python
def reason_to_deny(payload: dict[str, object]) -> str | None:
    """The reason to deny this tool call, or None to let it run."""
```

Algorithm:

1. If `payload["tool_name"] != "Bash"`, or `tool_input.command` is missing or not a string → `None`.
2. If the command matches `POLLING = r"\b(?:until|while|for)\b.*?\bdo\b.*?\bsleep\b.*?\bdone\b"`
   (flag `DOTALL`) → `REASON`. That is: a loop keyword, then `do`, then `sleep`, then `done`, in that
   order. (The first draft took the body up to the first `done`; it missed `done` inside the body,
   e.g. a `done.flag` marker, and nested loops. See § Plan review, C2.)
3. Otherwise → `None`.

The command is scanned as raw text, so a loop inside `bash -c '…'` is found too.

`main()` reads stdin as JSON and calls `reason_to_deny`. On a reason it prints, on stdout,
`{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
"permissionDecisionReason": REASON}}` and exits 0. Otherwise it prints nothing and exits 0. Any
exception exits 1. **The hook never exits 2.** Denying through JSON means every non-zero exit, for
any cause, lets the command run (DEC-3).

`REASON`, verbatim:

> Polling loops are blocked in this repository (AGENTS.md, Habits). Run the command in the
> foreground with a timeout of up to 600000 ms (every make target finishes within it); or run it
> with run_in_background and wait for the completion notice; or, to wait on a condition, use the
> Monitor tool. Do not sleep in a loop in Bash.

The payload is a hook protocol document, not domain data: a `dict` read once, at the edge, is the
honest type (the "models, not dicts" rule covers domain and service data).

### Examples (the test corpus, taken from the traces)

Denied:

| # | Command (shortened) |
|---|---|
| D-1 | `until grep -q "^real" temp/checkall.log; do sleep 5; done; tail -12 temp/checkall.log` |
| D-2 | `for i in $(seq 1 23); do grep -q "^real" temp/checkall.log && break; sleep 5; done; tail -1 temp/checkall.log` |
| D-3 | `cd …/tasks/; for i in $(seq 34); do kill -0 582896 2>/dev/null \|\| break; sleep 5; done` |
| D-4 | `while pgrep -f "make test" >/dev/null; do sleep 5; done; tail -30 …/buiqvrb6f.output` |
| D-5 | `timeout 178 bash -c 'until grep -q "^real" temp/dt-make-test.log; do sleep 5; done'; tail -c 200 temp/dt-make-test.log` |
| D-6 | `while ! grep -q "^real" temp/par5.log 2>/dev/null; do sleep 5; done; grep -E " passed" temp/par5.log` |
| D-7 | `until gh pr checks 154 >/dev/null 2>&1; do sleep 5; done; gh pr checks 154 --watch --interval 15` |
| D-8 | a multi-line command: `for i in $(seq 1 40); do\n  s=$(docker inspect …)\n  [ "$s" = healthy ] && break\n  sleep 6\ndone` |
| D-9 | `for i in $(seq 30); do test -f temp/done.flag && break; sleep 2; done` |
| D-10 | `while true; do grep -q done log && break; sleep 5; done` |
| D-11 | `for a in 1 2; do for b in 3; do :; done; sleep 1; done` |

Allowed:

| # | Command | Why |
|---|---|---|
| A-1 | `sleep 5; gh pr merge 41 --merge 2>&1 \| tail -1` | a single pause, no loop (DEC-2) |
| A-2 | `gh pr checks 161 --watch --interval 30 2>&1 \| tail -8` | `--watch` allowed (DEC-2) |
| A-3 | `for s in wait_until fuseki; do timeout 60 gitnexus impact $s --direction upstream; done` | loop without sleep |
| A-4 | `( time make check-all ) 2>&1 \| tail -30` | no loop |
| A-5 | `python3 - <<'E'\nwhile True:\n    time.sleep(1)\nE` | no `do … done` |
| A-6 | `git commit -m "fix: do not sleep in tests"` | no loop keyword before `do` |
| A-7 | `make test-changed` | plain |
| A-8 | `for f in *.py; do ruff format $f; done` | loop without sleep |
| A-9 | `for f in a b; do echo $f; done; sleep 3` | no `done` after the `sleep` |

Accepted false positives (denied; the agent rewrites them; RISK-1): text that only quotes a polling
loop, e.g. `grep -rn "while true; do sleep 1; done" docs/`, a commit message such as
`git commit -m "for now, do not use sleep; done"`, a heredoc writing a file that quotes D-1, or a
loop without `sleep` followed by a `sleep` and a later `done`, e.g.
`for f in *.py; do ruff format $f; done; sleep 5; make test && echo done`. The
test corpus is therefore written with the Write tool, never through a Bash heredoc.

Payloads that are not Bash calls (`{"tool_name": "Read", …}`), lack `tool_input`, or hold a
non-string command → `None`.

## PD-2 Wiring

- `.claude/settings.json` gains, next to `attribution`:
  ```json
  "hooks": {
    "PreToolUse": [
      {"matcher": "Bash",
       "hooks": [{"type": "command", "timeout": 10,
                  "command": "f=\"$CLAUDE_PROJECT_DIR/.claude/hooks/no_polling.py\"; [ -f \"$f\" ] || exit 0; python3 \"$f\" || exit 0"}]}
    ]
  }
  ```
  The wrapper lets the command run when the file is missing (the main checkout on a branch without
  it, mid-rebase, a worktree session before the merge) and when Python fails. Plain `python3`, not
  `uv run`: the hook is stdlib only, must not depend on the project's environment, and an absent
  file under `uv run` or `python3` exits 2, which would deny (§ Plan review, C1, C6). The repo rule
  "Python through uv" governs the project's tooling; this script runs outside it on purpose.
- `Makefile`: `PYTHON_PATHS` gains `$(REPO_ROOT)/.claude/hooks`, so `format-check` and `lint` cover
  the hook.
- After `test-lanes` merges: if `tests/changed.py` holds a table mapping source paths to test paths,
  add `.claude/hooks/` → `tests/unit/test_no_polling_hook.py` to it; if it holds no such table,
  change nothing (an unmapped path falls back to `make test-fast`).

## PD-3 Tests

`tests/unit/test_no_polling_hook.py`, written with the Write tool. It loads the hook with
`importlib.util.spec_from_file_location` (the `.claude` folder is not a package):

- T-1 each of D-1..D-11 → `reason_to_deny` returns `REASON`;
- T-2 each of A-1..A-9 → `None`;
- T-3 non-Bash payload, missing `tool_input`, command `None` or a list → `None`;
- T-4 end to end: `subprocess.run([sys.executable, HOOK], input=json.dumps(<D-1 payload>))` → exit
  0, stdout parses as JSON with `permissionDecision == "deny"` and a reason containing
  `run_in_background`; the same with A-1 → exit 0, empty stdout;
- T-5 end to end: stdin `not json` → non-zero exit or exit 0 with empty stdout, and never exit 2;
- T-6 the wrapper: run the `command` string from `.claude/settings.json` with `bash -c`, with
  `CLAUDE_PROJECT_DIR` set to an empty temporary folder → exit 0, empty stdout; with it set to the
  repo root and a D-1 payload on stdin → the deny JSON.

## PD-4 Instructions: `AGENTS.md`

1. Under *Working conventions*, after the "Run checks through make" bullet, a new bullet group,
   verbatim:

   > - **Navigating and editing code: one tool per question.** Blast radius before a task: GitNexus
   >   `impact` (the lead's gate). Read a symbol or a file's outline: Serena `get_symbols_overview`
   >   and `find_symbol` with its body, not `Read` on a whole file. Who calls it: Serena
   >   `find_referencing_symbols`. Replace or add a whole function: Serena `replace_symbol_body` /
   >   `insert_after_symbol`. One code shape in many files: `ast-grep run -p '<pattern>' --lang
   >   python` (look at the matches, then add `-r '<rewrite>' -U`). Text in docs, YAML, AsciiDoc or
   >   the Makefile: Grep. Subagents without Serena use `ast-grep`, Grep and Read with a line range.
   > - **Edit in place.** Use the Edit tool or Serena; never rewrite source files with Python
   >   heredocs (`s.replace(...)`) or `sed -i`.
   > - **Serena memories are not used**; the truth is `openspec/specs/` (`.serena/` is git-ignored).

2. The *Gates* bullet (AGENTS.md lines 110-114 on `develop` at shaping; re-read after `test-lanes`
   merges, RISK-3) is replaced in full by:

   > - **Gates.** Before a task is handed out, the lead runs gitnexus impact (stop and report
   >   HIGH/CRITICAL; subagents have no gitnexus tools, so briefs never ask for it). Per task the
   >   builder runs the gates listed in `develop/agents.adoc` and reports each with its time and
   >   test count; the lead re-runs `make check-quality` and reads the diff. After a red run, re-run
   >   only the failing tests until green, then the full run once. The full suite (`make check-all`,
   >   `make test-containers`) runs once, before the PR.

   Whatever per-task targets `test-lanes` wrote into the old bullet are kept in `develop/agents.adoc`
   (they are listed there), not repeated here.

3. Under *Habits*, a new first sentence:

   > **Never poll.** Run long commands in the foreground (timeout up to 10 min), with
   > `run_in_background` and its notice, or wait on a condition with the Monitor tool; a hook denies
   > `sleep` loops in Bash.

## PD-5 Instructions: `develop/agents.adoc` and `questions.adoc`

1. *Common questions*, the answer to "What does a member's report prove?" (line 25 at shaping):
   `Nothing on its own. The lead re-runs the <<gates>> and reads the diff.` becomes
   `Not enough on its own. The lead re-runs `make check-quality` and reads the diff; `make check-all`
   before the PR catches a report that was wrong. See <<gates>>.`
2. *What every brief carries here*: a third bullet, "how to work: search with `ast-grep run`, edit
   in place with the Edit tool, never with Python heredocs or `sed -i`; run commands in the
   foreground or in the background with its notice, never in a `sleep` loop (a hook denies it)".
3. *The gates*: the table gains a first column *Who* (builder or lead). The per-task test and
   quality rows say "builder"; a new row "`make check-quality` | lead | after every task, after
   reading the diff". After the table, the sentence: "The builder owns the per-task gates and
   reports them; the lead re-runs only `make check-quality`. After a red run, re-run only the failing
   tests until green, then the full run once."
4. *Habits that keep sessions consistent*: the no-polling bullet, worded as in PD-4 item 3.
5. `questions.adoc`: "Why does a Bash command fail with 'Polling loops are blocked'?" → a link to
   that habits bullet.

## PD-6 Skillery issue (DEC-8)

One issue on the skillery repository, filed by the lead only after the developer approves its text:
(a) add Serena's read and symbol-edit tools to the `implementer` and `code-reviewer` agents;
(b) in `epic-delivery`, the builder owns the per-task gates and the lead spot-checks (this repo's
DEC-6, with the trace numbers). Its URL goes into this file under *Upstream*.

## Anti-patterns

- A loop that `sleep`s waiting for a file a background run writes. Use the foreground, the notice, or
  Monitor.
- A hook whose own failure denies the call (DEC-3; why the hook never exits 2).
- Prose rules where a hook can decide (the reason this change exists).
- A second source of truth in Serena memories (DEC-7).
- Re-running the whole suite to check one fix.

## Error matrix

| Situation | Behaviour |
|---|---|
| Polling command (D-1..D-11) | Denied through JSON; `REASON` shown to the agent |
| Text that only quotes a polling loop | Denied (accepted false positive); the agent rewrites it |
| Polling inside a script file the command runs | Not seen; accepted (proposal, Rabbit-holes) |
| stdin not JSON, not a Bash call, odd types | No output, the command runs |
| The hook raises an unexpected exception | Exit 1: non-blocking, the command runs |
| The hook file is missing (`$CLAUDE_PROJECT_DIR` on another branch, mid-rebase) | The wrapper exits 0: the command runs |
| `python3` missing | The wrapper's `\|\| exit 0`: the command runs |
| The hook takes > 10 s | Claude Code times it out: the command runs |
| A subagent is denied | `REASON` offers the foreground first (DEC-4) |
| The harness itself blocks a foreground `sleep` (A-1) | Not this hook's doing; the agent follows the harness |

## Risks / Trade-offs

- **RISK-1** A false positive blocks a useful command. Likelihood low, impact low (the agent
  rewrites it). Mitigation: corpus A-1..A-9 from the traces; the quoting cases are named above; new
  cases join the corpus.
- **RISK-2** Hooks do not reach subagents. The docs say they do (Context). Likelihood low. Task 1.3
  confirms it with one subagent; if it fails, the brief line (PD-5 item 2) is the fallback and the
  finding goes into the skillery issue.
- **RISK-3** `test-lanes` changes the gates bullet, the gates table or `tests/changed.py` in a way
  PD-2, PD-4 or PD-5 did not foresee. Likelihood medium, impact low. Mitigation: start after it
  merges; tasks 1.2 and 1.4 re-read the merged files first and keep `test-lanes`' targets.
- **RISK-4** The settings watcher does not pick the hook up in a running session. Impact: task 1.3
  needs a fresh session. Mitigation: 1.3 runs in a fresh session, or `claude -p`.
- **Live check (task 1.3, 2026-11-09).** The settings watcher picked the hook up in the running
  session, so no fresh session was needed (RISK-4 did not occur). From the lead: a `for … sleep 0 …
  done` loop was denied with `REASON`; `for s in a b; do echo $s; done; sleep 1` ran. From one
  subagent: the same loop was denied with the same reason (RISK-2 did not occur). A single foreground
  `sleep 1` after a command was not blocked by the harness.
- **Trade-off**: one `python3` start per Bash call (≈ 0.03 s), accepted.

## Plan review (2026-11-09, fresh reviewer, attack + clarity gate 8/10)

Accepted and applied above:

- **C1** The hook failed closed: an absent file under `uv run` or `python3` exits 2. → JSON deny,
  never exit 2; the wrapper with `[ -f ]` and `|| exit 0`; T-6. Verified by the lead: a missing file
  exits 2 under both, the wrapper exits 0.
- **C2** The first regex missed `done` inside the body and nested loops. → the ordered regex;
  D-9..D-11. Verified by the lead: D-9..D-11 denied, A-9 still allowed.
- **C3** Quoted loops are denied. → named as accepted false positives; the corpus is written with
  the Write tool.
- **C4** The harness blocks a foreground `sleep` itself and points agents to Monitor. → `REASON`
  names Monitor; an error-matrix row.
- **C5** PD-4 and PD-5 left two contradicting lines. → the exact lines and their replacements.
- **C6** `uv run` start-up and its dependency. → plain `python3`.

Re-gate (fresh reviewer): **9/10, READY**. Its three non-blocking gaps were applied: the spec now
allows the accepted false positives and names 600000 ms and Monitor; the extra false positive joined
the list above; task 1.1's acceptance goes through make.

## Stage review (2026-11-09, one pass, L2 + L3)

No critical findings; fail-open confirmed on every path. Accepted:

- **R1** Built before `test-lanes` merged (the developer said to start now). `make test-changed`
  does not exist yet, so task 1.1's acceptance ran the hook tests directly; the gates table keeps
  the folder-level pytest row and PD-2's `tests/changed.py` mapping is left to whichever change
  merges second (RISK-3 now applies at merge time, not before the start).
- **R2** The spec's named alternatives were pinned only through the `REASON` constant. → a test that
  `REASON` names the foreground, 600000 ms, `run_in_background`, the completion notice and Monitor.
- **R3** The hook's plain `python3` reads as a breach of "Python through uv". → the *Never poll*
  habit says it runs on plain `python3` on purpose.
- **R4** The AGENTS.md brief bullet lagged behind agents.adoc. → it names "how to work".

## Upstream

- Skillery issue: filed by the developer on 2026-11-09 (URL not recorded).
