---
kind: rule
id: P-0018
type: procedure
strength: default
status: active
scope:
  - activity:coding
when: briefing a builder or fixer subagent that works in a worktree
do: give it the absolute worktree path for every read and edit, Serena included
because: a relative path or a Serena project rooted elsewhere edits the main checkout or another worktree
source: "2026-11-21: 'Give builders the absolute worktree path for every edit, Serena included.'"
added: 2026-11-22
approved: 2026-11-22
last_confirmed: 2026-11-22
private: false
---
