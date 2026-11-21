---
kind: rule
id: P-0017
type: constraint
strength: hard
status: active
scope:
  - activity:coding
when: delivering a change in worktrees while other sessions share the repository
do: never touch the main checkout; read, edit and run only in the change's worktrees under .worktrees/
because: the main checkout is shared by every session; edits there collide with other work
source: "2026-11-21: 'Never touch the main checkout.'"
added: 2026-11-22
approved: 2026-11-22
last_confirmed: 2026-11-22
private: false
---
