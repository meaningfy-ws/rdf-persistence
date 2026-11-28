---
kind: rule
id: P-0043
type: procedure
strength: default
status: active
scope:
  - activity:coding
  - activity:review
  - activity:planning
when: briefing any subagent, builder or read-only (explorer, attacker, reviewer, checker, gate)
do: "paste develop/agents.adoc#tools into the brief (Serena for Python symbols and callers, ast-grep for a code shape, Grep only for YAML, JSON, docs and the Makefile), name the checkout Serena reads (the worktree, activated as its own project, or say it is read-only orientation on another checkout), and ask the report to name the tool behind each finding"
because: rules.py --brief and the delivery brief carry no tool rules for read-only subagents, so they fell back to grep
source: "2026-11-28: 'whyis teh attacker using grep and not ast grep and serena?' and 'i am wonderign if those tool usage rules reach the subagents and when we work in a worktree insde .worktrees'"
added: 2026-11-28
approved: 2026-11-28
last_confirmed: 2026-11-28
private: false
---
