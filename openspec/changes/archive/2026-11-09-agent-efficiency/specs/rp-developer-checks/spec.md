## ADDED Requirements

### Requirement: Agents' shell commands do not poll

The repository's Claude Code settings SHALL run a `PreToolUse` hook on every Bash call that denies
a command looping with `sleep` (an `until`, `while` or `for` loop whose body runs `sleep`), with a
reason that names the alternatives: the foreground with a timeout of up to 10 minutes (600000 ms),
a background run and its completion notice, or the Monitor tool. The hook SHALL allow every other
command, except that a command which only quotes such a loop, or in which a `sleep` and a later
`done` follow a loop without `sleep`, MAY be denied. The hook SHALL let the command run when the
hook itself fails.

#### Scenario: an agent polls a background check
- **GIVEN** an agent session in this repository
- **WHEN** it runs `until grep -q real temp/checkall.log; do sleep 5; done; tail temp/checkall.log`
- **THEN** the command does not run, and the agent receives the reason naming the foreground and the
  completion notice

#### Scenario: a single pause before a command
- **GIVEN** an agent session in this repository
- **WHEN** it runs `sleep 5; gh pr merge 41 --merge`
- **THEN** the command runs

#### Scenario: a loop without sleep
- **GIVEN** an agent session in this repository
- **WHEN** it runs `for s in wait_until fuseki; do gitnexus impact $s; done`
- **THEN** the command runs

#### Scenario: the hook cannot read its input
- **GIVEN** the hook receives input that is not a Bash tool call
- **WHEN** it runs
- **THEN** it exits without denying, and the command runs
