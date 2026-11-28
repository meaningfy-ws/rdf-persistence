---
kind: rule
id: P-0034
type: constraint
strength: hard
status: active
scope:
  - activity:modelling
when: modelling with an external vocabulary's terms
do: check each term and its namespace against the published specification first
because: mixed vocabulary versions go unnoticed otherwise
source: "2026-11-28 adopted from the first consumer's P-0026 (#437, aggregate-composition DEC-12): 'check each term and its namespace against the published specification first'"
added: 2026-11-28
approved: 2026-11-28
last_confirmed: 2026-11-28
private: false
---
