---
kind: rule
id: P-0009
type: constraint
strength: default
status: active
scope:
  - activity:coding
when: a value could vary per deployment (timeout, TTL, limit, URL)
do: define it in the central settings model near the package root; protocol constants such as path slugs stay next to their use
because: one place for every deployment parameter
source: 2026-11-16 'only what could be a variable must move to that __init__.py that defined variables'
added: 2026-11-17
approved: 2026-11-17
last_confirmed: 2026-11-17
private: false
---
