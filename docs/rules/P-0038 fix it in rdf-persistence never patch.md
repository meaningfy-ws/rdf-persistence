---
kind: rule
id: P-0038
type: constraint
strength: hard
status: active
scope:
  - activity:modelling
when: the converter or generator produces the wrong thing
do: fix it in rdf-persistence, never patch it in the application
because: one fix serves every consumer
source: "2026-11-28 adopted from the first consumer's developer guide (#437, aggregate-composition DEC-12): 'fix it in rdf-persistence, never patch it in the application'"
added: 2026-11-28
approved: 2026-11-28
last_confirmed: 2026-11-28
private: false
---
