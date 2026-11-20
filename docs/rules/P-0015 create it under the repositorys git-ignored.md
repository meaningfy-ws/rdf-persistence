---
kind: rule
id: P-0015
type: preference
strength: default
status: active
scope:
  - activity:coding
when: creating a git worktree for a change or a builder
do: create it under the repository's git-ignored .worktrees/ folder
instead_of: a folder beside the repository
slot: worktree-location
value: .worktrees/ inside the repository
because: the session can edit it and it stays with the repository
source: 2026-11-20 'can you change the worktree into the .worktree subfolder'
added: 2026-11-20
approved: 2026-11-20
last_confirmed: 2026-11-20
private: false
---
