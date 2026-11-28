---
kind: rule
id: P-0035
type: constraint
strength: hard
status: active
scope:
  - activity:modelling
when: a change to the .qea model is planned
do: start from the latest .qea on any open branch; let one branch change it at a time
because: the file is binary and cannot be merged
source: "2026-11-28 adopted from the first consumer's P-0027 (#437, aggregate-composition DEC-12): 'start from the latest .qea on any open branch; let one branch change it at a time'"
added: 2026-11-28
approved: 2026-11-28
last_confirmed: 2026-11-28
private: false
---
