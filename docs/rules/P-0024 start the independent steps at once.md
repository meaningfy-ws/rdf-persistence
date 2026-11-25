---
kind: rule
id: P-0024
type: trigger
strength: default
status: active
scope:
  - activity:delivery
when: the lead waits on a long run and other steps do not depend on it
do: "start the independent steps at once: checks that take no queue slot, steps in another worktree, GitHub and spine work; hold only what writes into the files the running command reads"
because: waiting time is the session's largest cost on a shared machine
source: 2026-11-25 'can you run anythign else in parallel?' and 'carry on; and in parallel whatever can be paralllelised'
added: 2026-11-25
approved: 2026-11-25
last_confirmed: 2026-11-25
private: false
---
