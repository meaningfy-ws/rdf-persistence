---
kind: rule
id: P-0040
type: constraint
strength: hard
status: active
scope:
  - activity:modelling
when: deciding whether a class X is a part of a class W
do: draw a composition only when X cannot exist without W and goes down with it; otherwise a pointer to W's root
because: the deletion test decides an aggregate
source: "2026-11-28 adopted from #437 B and the first consumer's S8-15 (#437, aggregate-composition DEC-12): 'draw a composition only when X cannot exist without W and goes down with it; otherwise a pointer to W's root'"
added: 2026-11-28
approved: 2026-11-28
last_confirmed: 2026-11-28
private: false
---
