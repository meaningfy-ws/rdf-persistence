---
kind: rule
id: P-0002
type: procedure
strength: default
status: active
scope:
  - activity:coding
when: other sessions work on this repository in parallel worktrees
do: rebase the branch on develop before opening each PR
because: parallel sessions merge into develop meanwhile; a rebase surfaces conflicts before review and CI, not at merge
source: "2026-11-13: 'rebase on develop before each PR'"
added: 2026-11-13
approved: 2026-11-13
last_confirmed: 2026-11-13
private: false
---
