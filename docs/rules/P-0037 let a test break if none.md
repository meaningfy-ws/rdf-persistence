---
kind: rule
id: P-0037
type: trigger
strength: default
status: active
scope:
  - activity:modelling
when: the model changes
do: let a test break; if none does, add one
because: an untested model change goes unnoticed
source: "2026-11-28 adopted from the first consumer's developer guide (#437, aggregate-composition DEC-12): 'let a test break; if none does, add one'"
added: 2026-11-28
approved: 2026-11-28
last_confirmed: 2026-11-28
private: false
---
