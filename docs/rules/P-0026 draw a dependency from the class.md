---
kind: rule
id: P-0026
type: trigger
strength: default
status: active
scope:
  - activity:modelling
when: a class links to a controlled list in UML
do: draw a dependency from the class to the enumeration, named by the property
because: the SEMIC style guide connects classes to controlled lists this way
source: "2026-11-28 adopted from the first consumer's P-0008 (#437, aggregate-composition DEC-12): 'draw a dependency from the class to the enumeration, named by the property'"
added: 2026-11-28
approved: 2026-11-28
last_confirmed: 2026-11-28
private: false
---
