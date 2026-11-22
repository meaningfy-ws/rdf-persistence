---
kind: rule
id: P-0019
type: constraint
strength: default
status: active
scope:
  - activity:coding
when: delivering a gated PLAN and it proves wrong
do: do not re-plan; stop and bring the owner one question round, each question with a recommendation
because: the PLAN is gated; changing it is the owner's decision, made fastest from concrete recommendations
source: "2026-11-21: 'The PLAN is gated; do not re-plan. If it proves wrong, stop and bring me one question round, each question with a recommendation.'"
added: 2026-11-22
approved: 2026-11-22
last_confirmed: 2026-11-22
private: false
---
