---
kind: rule
id: P-0036
type: constraint
strength: hard
status: active
scope:
  - activity:modelling
when: a model artefact is needed
do: generate it from the UML model; never edit a generated file
because: the model is the one source, and CI regenerates and compares
source: "2026-11-28 adopted from the first consumer's developer guide (#437, aggregate-composition DEC-12): 'generate it from the UML model; never edit a generated file'"
added: 2026-11-28
approved: 2026-11-28
last_confirmed: 2026-11-28
private: false
---
