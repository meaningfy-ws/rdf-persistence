---
kind: rule
id: P-0013
type: escalation
strength: default
status: active
scope:
  - activity:delivery
when: delivering an EPIC's stage PR
do: merge it into develop once CI is green without waiting for the developer, with an admin merge where a required review would block, never on a red or missing check
because: the developer does not want to be waited on; green CI is the merge gate
source: "2026-11-20 'dont wait on me, feel free to merge admin too'; for every EPIC: 'yes to 1'"
added: 2026-11-20
approved: 2026-11-20
last_confirmed: 2026-11-20
private: false
---
