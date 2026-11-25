---
kind: rule
id: P-0022
type: procedure
strength: default
status: active
scope:
  - activity:coding
when: the lead starts a stage or session in a worktree
do: run make test-seed only when builders will run make test-changed in that worktree; a session without builders (a rebase, the gates, a fix pass the lead does alone) skips it
because: the seed only feeds make test-changed, and make check-all runs every unit and feature test again before the PR
source: "2026-11-25: 'is there anythign iu caould adjust in the whoel repo instructions about this? or this inefficiency is a local fluke?' then 'go ahead' and 'yes record the rule'"
added: 2026-11-25
approved: 2026-11-25
last_confirmed: 2026-11-25
private: false
---
