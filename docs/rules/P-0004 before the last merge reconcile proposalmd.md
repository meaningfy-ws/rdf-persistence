---
kind: rule
id: P-0004
type: procedure
strength: default
status: active
scope:
  - activity:coding
when: delivering the last stage of an EPIC
do: "before the last merge, reconcile proposal.md with what was built: every row of its reconciliation table in its final state with its PR, What Changes, Capabilities and Impact as delivered, the spec deltas true of the code, and anything the shape promised but did not get, with the reason"
because: the EPIC is the shaped bet; a reader must see what was delivered and why it differs
source: "2026-11-14/15: 'reconcile the deviations of epic implementation and epic shape'; 'at the end, reconcile what the implementation and the work shape'"
added: 2026-11-15
approved: 2026-11-15
last_confirmed: 2026-11-15
private: false
---
