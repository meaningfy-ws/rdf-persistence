---
kind: rule
id: P-0013
type: escalation
strength: default
status: active
scope:
  - activity:delivery
when: delivering an EPIC's stage PR
do: "merge it into develop once CI is green without waiting for the developer: give CI a moment after the push, then run 'gh pr checks <n> --watch --fail-fast && gh pr merge <n> --merge --delete-branch' once in the background and wait for its notice, never reading its output file while it runs; use an admin merge where a required review would block, 'gh pr merge --auto' only once develop has required checks, and never merge on a red or missing check"
because: the developer does not want to be waited on; green CI is the merge gate
source: "2026-11-22 'the merge command is gh pr checks <n> --watch --fail-fast && gh pr merge <n> --merge --delete-branch, run once in the background, and you wait for its notice. Never read its output file while it runs. gh pr merge --auto is allowed only once the repository has required checks on develop.' (#282, accepted)"
added: 2026-11-20
approved: 2026-11-20
last_confirmed: 2026-11-20
private: false
---
