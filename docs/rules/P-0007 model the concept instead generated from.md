---
kind: rule
id: P-0007
type: constraint
strength: hard
status: active
scope:
  - activity:coding
when: a dict with string keys would carry a concept
do: model the concept instead (generated from LinkML where it is model data); keep dicts only at a library boundary or as an index
because: a named model is validated and keeps the concept in one place; bare string keys drift and hide typos
source: 2026-11-16 'never use bare dict key, dicts shall rarely be used, and instead prefer models, to encapsulate concepts'
added: 2026-11-17
approved: 2026-11-17
last_confirmed: 2026-11-17
private: false
---
